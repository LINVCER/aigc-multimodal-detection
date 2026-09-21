"""
文本检测数据集统一 schema
=========================

所有数据源（HC3-Chinese / CSL / M4-zh / CHEAT / 自建 / 改写增强）落盘前一律转成本文件定义的
JSONL 行结构，训练、评估、推理三侧只认这一份口径。

JSONL 每行::

    {
      "text":       "……",                 # 段落文本，≥ MIN_CHARS 字
      "label":      0 | 1,                # 0 = 人类  1 = AI（含改写 / 润色后的 AI）
      "scenario":   "academic_master",    # 6 场景之一，对齐 C 端 detect_scenario_threshold
      "source":     "gpt",                # 生成器家族（溯源头类别）；人类文本固定 "human"
      "augment":    "none",               # 增强类型，见 AUGMENTS
      "origin":     "hc3",                # 原始数据集名
      "doc_id":     "hc3-open_qa-000123", # 同一原文派生的样本共享 doc_id，划分 split 时按它分组防泄漏
      "split":      "train"               # train / val / test / eval_*（由 build_evalsets 填）
    }
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Iterable, Iterator

# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------

# 对齐 backend detect_scenario_threshold.scenario 的 6 个业务场景
SCENARIOS: tuple[str, ...] = (
    "academic_bachelor",
    "academic_master",
    "academic_phd",
    "job_report",
    "self_media",
    "other",
)

# 溯源头类别；顺序即 label id，与 deploy/inference-python /api/v1/attribute 的 sources 保持一致
SOURCE_FAMILIES: tuple[str, ...] = (
    "human", "gpt", "claude", "qwen", "deepseek", "glm", "kimi", "ernie", "other",
)
SOURCE_TO_ID: dict[str, int] = {s: i for i, s in enumerate(SOURCE_FAMILIES)}

# 增强类型。paraphrase_* 三档强度对应 DATASETS.md §3.3；polished = 人写后 LLM 润色（Fraser §5.5 最难区间）
AUGMENTS: tuple[str, ...] = (
    "none",
    "paraphrase_weak",
    "paraphrase_mid",
    "paraphrase_strong",
    "polished",
    "mixcase",           # 句级人机拼接，label=1，用于 mixed evals
)

# 长度口径统一在 ml/common/constants.py（推理侧同一份）
from ml.common.constants import MAX_CHARS, MIN_CHARS  # noqa: E402,F401

# 常见生成器名 → 家族归一（M4 / MAGE / 自建数据里 source 字段五花八门）
_SOURCE_ALIASES: dict[str, str] = {
    "human": "human", "人类": "human", "real": "human",
    "chatgpt": "gpt", "gpt": "gpt", "gpt-3.5": "gpt", "gpt-3.5-turbo": "gpt", "gpt-4": "gpt",
    "gpt-4o": "gpt", "gpt4": "gpt", "davinci": "gpt", "text-davinci-003": "gpt", "openai": "gpt",
    "claude": "claude", "anthropic": "claude",
    "qwen": "qwen", "qwen2": "qwen", "qwen2.5": "qwen", "qwen3": "qwen", "tongyi": "qwen", "通义": "qwen",
    "deepseek": "deepseek", "deepseek-v3": "deepseek", "deepseek-r1": "deepseek",
    "glm": "glm", "chatglm": "glm", "glm-4": "glm", "zhipu": "glm", "智谱": "glm",
    "kimi": "kimi", "moonshot": "kimi",
    "ernie": "ernie", "wenxin": "ernie", "文心": "ernie", "baidu": "ernie",
    "bloomz": "other", "flan": "other", "flan-t5": "other", "dolly": "other", "cohere": "other",
    "llama": "other", "vicuna": "other", "baichuan": "other", "yi": "other", "gemini": "other",
}


def normalize_source(raw: str | None) -> str:
    """把任意生成器名归一到 SOURCE_FAMILIES；认不出来的一律 other。"""
    if not raw:
        return "other"
    key = str(raw).strip().lower()
    if key in _SOURCE_ALIASES:
        return _SOURCE_ALIASES[key]
    for alias, fam in _SOURCE_ALIASES.items():
        if alias in key:
            return fam
    return "other"


# ---------------------------------------------------------------------------
# 样本结构
# ---------------------------------------------------------------------------

@dataclass
class TextSample:
    text: str
    label: int
    scenario: str = "other"
    source: str = "human"
    augment: str = "none"
    origin: str = "unknown"
    doc_id: str = ""
    split: str = ""
    meta: dict = field(default_factory=dict)   # 可选：原 domain / 生成 prompt / 长度等，不进训练

    def __post_init__(self) -> None:
        if self.label not in (0, 1):
            raise ValueError(f"label 必须是 0/1，得到 {self.label!r}")
        if self.scenario not in SCENARIOS:
            raise ValueError(f"未知 scenario {self.scenario!r}，可选 {SCENARIOS}")
        if self.augment not in AUGMENTS:
            raise ValueError(f"未知 augment {self.augment!r}，可选 {AUGMENTS}")
        self.source = normalize_source(self.source)
        if self.label == 0 and self.augment in ("none",):
            # 人类原文 source 必须是 human；polished / mixcase 虽然 label=1，但 source 保留润色它的生成器
            self.source = "human"
        if not self.doc_id:
            self.doc_id = make_doc_id(self.origin, self.text)

    def to_json(self) -> str:
        d = asdict(self)
        if not d["meta"]:
            d.pop("meta")
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "TextSample":
        return cls(
            text=d["text"],
            label=int(d["label"]),
            scenario=d.get("scenario", "other"),
            source=d.get("source", "human" if int(d["label"]) == 0 else "other"),
            augment=d.get("augment", "none"),
            origin=d.get("origin", "unknown"),
            doc_id=d.get("doc_id", ""),
            split=d.get("split", ""),
            meta=d.get("meta", {}) or {},
        )


def make_doc_id(origin: str, text: str) -> str:
    """同一原文（及其改写派生）共享的稳定 id；用前 64 字的 sha1 保证改写后仍能对回原文的前提是由调用方显式传入。"""
    h = hashlib.sha1(text.strip()[:64].encode("utf-8")).hexdigest()[:12]
    return f"{origin}-{h}"


def content_hash(text: str) -> str:
    """精确去重用：去空白、全角半角统一后的 sha1。"""
    norm = "".join(text.split()).replace("，", ",").replace("。", ".").lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# JSONL IO
# ---------------------------------------------------------------------------

def iter_jsonl(path: str) -> Iterator[TextSample]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield TextSample.from_dict(json.loads(line))


def write_jsonl(path: str, samples: Iterable[TextSample]) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(s.to_json() + "\n")
            n += 1
    return n
