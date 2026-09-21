"""
表层 / 文体特征提取（Chen 2026 特征融合支路中的 f 向量）
=======================================================

设计依据：docs/research/AIGC文本论文检测-文献精读笔记.md §五
    h = [h_cls ; h_cnn ; f]
其中 f 是「在文本变换下相对稳定的表层规律」：结构、词汇、语言多样性、以及近似停顿 / 节奏的
"发音相关代理特征"。这些特征对 paraphrase / 润色的敏感度远低于深层语义表示，是改写鲁棒性的来源。

约束：
- 训练侧（ml/training/text）与推理侧（deploy/inference-python）**必须 import 同一份实现**，
  否则 z-score 统计量对不上，融合支路会输出垃圾。
- 纯 Python + numpy，jieba 可选（缺失时退化为字级统计，特征维度不变）。
- 输出固定 SURFACE_DIM 维 float32，顺序以 SURFACE_FEATURE_NAMES 为准；新增特征只能追加在末尾，
  并同步 bump SURFACE_FEATURE_VERSION，训练时把 version 写进 checkpoint，推理时校验。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

import numpy as np

try:  # jieba 为可选依赖：训练镜像必装；推理镜像缺失时走字级退化
    import jieba  # type: ignore

    jieba.setLogLevel(60)
    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    jieba = None  # type: ignore
    _HAS_JIEBA = False


SURFACE_FEATURE_VERSION = "sf-v1"

# 特征名即字段顺序；共 30 维
SURFACE_FEATURE_NAMES: tuple[str, ...] = (
    # --- 结构 (8)
    "punct_density", "comma_ratio", "period_ratio", "question_excl_ratio",
    "pronoun_ratio", "discourse_marker_rate", "stopword_ratio", "special_symbol_ratio",
    # --- 词汇 (8)
    "avg_sent_len", "sent_len_std", "sent_len_cv", "n_sentences_log",
    "ttr", "unique_char_ratio", "avg_word_len", "long_word_ratio",
    # --- 多样性 / 可读性 (8)
    "char_entropy", "word_entropy", "yule_k", "repeat_bigram_rate",
    "repeat_trigram_rate", "hapax_ratio", "digit_ratio", "latin_ratio",
    # --- 节奏代理 (6)
    "punct_gap_mean", "punct_gap_std", "punct_gap_cv",
    "clause_len_mean", "clause_len_std", "repeat_token_rate",
)
SURFACE_DIM = len(SURFACE_FEATURE_NAMES)

# ---------------------------------------------------------------------------
# 词表
# ---------------------------------------------------------------------------

_SENT_END = "。！？!?；;"
_COMMA = "，,、"
_ALL_PUNCT = set("。！？!?；;，,、：:“”\"‘’'（）()《》〈〉【】[]—…－-·/％%")
_SPECIAL = set("“”\"‘’'（）()《》〈〉【】[]—…－-·/％%：:")

_PRONOUNS = ("我们", "你们", "他们", "她们", "它们", "我", "你", "他", "她", "它", "咱", "您")

# AI 中文常见话语标记 / 翻译腔连接词（MODEL_RESEARCH_TEXT §1.1 指出的可利用偏差）
_DISCOURSE_MARKERS = (
    "首先", "其次", "再次", "最后", "此外", "另外", "然而", "但是", "因此", "所以", "总之",
    "综上所述", "值得注意的是", "总体而言", "总的来说", "一方面", "另一方面", "与此同时",
    "换句话说", "也就是说", "不可否认", "毫无疑问", "众所周知", "需要指出的是", "具体而言",
    "简而言之", "由此可见", "进一步", "更重要的是", "从……角度",
)

_STOPCHARS = set("的了是在和与或及等着过也都就而但把被让给对于为以及并且")

_LATIN_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"[0-9０-９]")
_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    if _HAS_JIEBA:
        toks = [t for t in jieba.lcut(text) if t.strip() and t not in _ALL_PUNCT]
        if toks:
            return toks
    return [ch for ch in text if not ch.isspace() and ch not in _ALL_PUNCT]


def _split_sentences(text: str) -> list[str]:
    out, buf = [], []
    for ch in text:
        buf.append(ch)
        if ch in _SENT_END:
            s = "".join(buf).strip()
            if s:
                out.append(s)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log(c / total + 1e-12) for c in counter.values())


def _safe_std(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    return float(np.std(np.asarray(xs, dtype=np.float64)))


def _ngram_repeat_rate(tokens: list[str], n: int) -> float:
    if len(tokens) < n + 1:
        return 0.0
    grams = Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))
    total = sum(grams.values())
    repeated = sum(c for c in grams.values() if c > 1)
    return repeated / total if total else 0.0


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def extract_surface_features(text: str) -> np.ndarray:
    """
    对单段文本提取 SURFACE_DIM 维表层特征（未标准化）。

    空文本 / 极短文本返回全零向量，由训练侧的 z-score 决定其位置；推理侧对 <MIN 字样本本就不该单独判定。
    """
    text = _WS_RE.sub(" ", (text or "")).strip()
    feats = np.zeros(SURFACE_DIM, dtype=np.float32)
    if len(text) < 2:
        return feats

    n_chars = len(text)
    chars_no_ws = [c for c in text if not c.isspace()]
    n_cnw = max(len(chars_no_ws), 1)

    # ---- 标点统计
    puncts = [c for c in text if c in _ALL_PUNCT]
    n_punct = len(puncts)
    n_comma = sum(1 for c in puncts if c in _COMMA)
    n_period = sum(1 for c in puncts if c in "。.")
    n_qe = sum(1 for c in puncts if c in "！？!?")
    n_special = sum(1 for c in puncts if c in _SPECIAL)

    # ---- 句 / 子句
    sents = _split_sentences(text)
    sent_lens = [len(s) for s in sents] or [n_chars]
    clauses = [c for c in re.split(r"[，,、；;。！？!?]", text) if c.strip()]
    clause_lens = [len(c) for c in clauses] or [n_chars]

    # ---- 分词
    tokens = _tokenize(text)
    n_tok = max(len(tokens), 1)
    tok_counter = Counter(tokens)
    char_counter = Counter(chars_no_ws)

    # ---- 标点间隔（节奏代理）
    gaps, last = [], -1
    for i, c in enumerate(text):
        if c in _ALL_PUNCT:
            if last >= 0:
                gaps.append(i - last)
            last = i
    if not gaps:
        gaps = [n_chars]

    # ---- 话语标记
    n_markers = sum(text.count(m) for m in _DISCOURSE_MARKERS)
    n_pronoun_chars = sum(len(p) * text.count(p) for p in _PRONOUNS)

    # ---- Yule's K：词频分布集中度，AI 文本词汇多样性低 → K 偏高
    m1 = n_tok
    m2 = sum(c * c for c in tok_counter.values())
    yule_k = 1e4 * (m2 - m1) / (m1 * m1) if m1 > 0 else 0.0

    # ---- 相邻重复 token
    rep_tok = sum(1 for i in range(1, len(tokens)) if tokens[i] == tokens[i - 1])

    vals = {
        # 结构
        "punct_density": n_punct / n_cnw,
        "comma_ratio": n_comma / n_punct if n_punct else 0.0,
        "period_ratio": n_period / n_punct if n_punct else 0.0,
        "question_excl_ratio": n_qe / n_punct if n_punct else 0.0,
        "pronoun_ratio": min(n_pronoun_chars / n_cnw, 1.0),
        "discourse_marker_rate": n_markers / max(len(sents), 1),
        "stopword_ratio": sum(1 for c in chars_no_ws if c in _STOPCHARS) / n_cnw,
        "special_symbol_ratio": n_special / n_cnw,
        # 词汇
        "avg_sent_len": float(np.mean(sent_lens)),
        "sent_len_std": _safe_std(sent_lens),
        "sent_len_cv": _safe_std(sent_lens) / (float(np.mean(sent_lens)) + 1e-6),
        "n_sentences_log": math.log1p(len(sents)),
        "ttr": len(tok_counter) / n_tok,
        "unique_char_ratio": len(char_counter) / n_cnw,
        "avg_word_len": float(np.mean([len(t) for t in tokens])) if tokens else 1.0,
        "long_word_ratio": sum(1 for t in tokens if len(t) >= 4) / n_tok,
        # 多样性 / 可读性
        "char_entropy": _entropy(char_counter),
        "word_entropy": _entropy(tok_counter),
        "yule_k": yule_k,
        "repeat_bigram_rate": _ngram_repeat_rate(tokens, 2),
        "repeat_trigram_rate": _ngram_repeat_rate(tokens, 3),
        "hapax_ratio": sum(1 for c in tok_counter.values() if c == 1) / max(len(tok_counter), 1),
        "digit_ratio": len(_DIGIT_RE.findall(text)) / n_cnw,
        "latin_ratio": len(_LATIN_RE.findall(text)) / n_cnw,
        # 节奏代理
        "punct_gap_mean": float(np.mean(gaps)),
        "punct_gap_std": _safe_std(gaps),
        "punct_gap_cv": _safe_std(gaps) / (float(np.mean(gaps)) + 1e-6),
        "clause_len_mean": float(np.mean(clause_lens)),
        "clause_len_std": _safe_std(clause_lens),
        "repeat_token_rate": rep_tok / n_tok,
    }
    for i, name in enumerate(SURFACE_FEATURE_NAMES):
        v = vals[name]
        feats[i] = 0.0 if (v is None or math.isnan(v) or math.isinf(v)) else float(v)
    return feats


def extract_surface_features_batch(texts: Sequence[str]) -> np.ndarray:
    return np.stack([extract_surface_features(t) for t in texts], axis=0) if texts else np.zeros((0, SURFACE_DIM), np.float32)


# ---------------------------------------------------------------------------
# 标准化（训练集拟合 → 写入 checkpoint → 推理复用）
# ---------------------------------------------------------------------------

class SurfaceScaler:
    """z-score；mean/std 在训练集上拟合，随 checkpoint 一起持久化。"""

    def __init__(self, mean: np.ndarray | None = None, std: np.ndarray | None = None) -> None:
        self.mean = None if mean is None else np.asarray(mean, dtype=np.float32)
        self.std = None if std is None else np.asarray(std, dtype=np.float32)

    def fit(self, feats: np.ndarray) -> "SurfaceScaler":
        self.mean = feats.mean(axis=0).astype(np.float32)
        std = feats.std(axis=0).astype(np.float32)
        std[std < 1e-6] = 1.0   # 常数列不缩放，避免除零放大噪声
        self.std = std
        return self

    def transform(self, feats: np.ndarray) -> np.ndarray:
        if self.mean is None or self.std is None:
            return feats.astype(np.float32)
        z = (feats - self.mean) / self.std
        return np.clip(z, -6.0, 6.0).astype(np.float32)   # 截断极端值，防单条离群样本主导融合层

    def to_dict(self) -> dict:
        return {
            "version": SURFACE_FEATURE_VERSION,
            "names": list(SURFACE_FEATURE_NAMES),
            "mean": None if self.mean is None else self.mean.tolist(),
            "std": None if self.std is None else self.std.tolist(),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "SurfaceScaler":
        if not d or d.get("mean") is None:
            return cls()
        if d.get("version") != SURFACE_FEATURE_VERSION:
            raise ValueError(
                f"surface feature 版本不匹配：checkpoint={d.get('version')} 代码={SURFACE_FEATURE_VERSION}，"
                "请用同版本代码推理或重训"
            )
        return cls(np.asarray(d["mean"]), np.asarray(d["std"]))
