"""
改写 / 润色 / 混写增强（Fraser §5.5 + Chen §5.3 落地）
=====================================================

为什么必须做：Fraser 2025 实证「训练中未见 mixcase / polished 样本 → 所有检测器在该区间差于随机；
见过后 RADAR ≈ 88%」。论文场景的典型用法恰恰是 AI 生成后人改、人写后 AI 润色、人机混写。

三种模式（--mode）::

    paraphrase  抽 label=1 的 AI 原文 → LLM 三档改写（weak/mid/strong）→ label 仍为 1
    polish      抽 label=0 的人写原文 → LLM「保持内容只提升清晰度」润色 → label=1，augment=polished
    mixcase     抽 label=0 的人写原文 → 随机 30-60% 句子换成 LLM 改写句 → label=1，augment=mixcase

派生样本继承原文 doc_id，因此 build_dataset 的 split 规则保证它们与原文同 split（不泄漏）。

引擎（--engine）::

    llm   OpenAI-compatible 接口（Qwen / DeepSeek / GLM / GPT 皆可），环境变量：
              PARAPHRASE_BASE_URL   例 https://dashscope.aliyuncs.com/compatible-mode/v1
              PARAPHRASE_API_KEY
              PARAPHRASE_MODEL      例 qwen-plus / deepseek-chat / glm-4
    rule  离线规则弱改写（同义替换 + 句序），只产 paraphrase_weak，用于无 API 时跑通流程

用法::

    python -m ml.datasets.text.paraphrase_augment --mode paraphrase --in ml/datasets/text/data/train.jsonl \
        --out ml/datasets/text/data/augment/paraphrase.jsonl --n 6000 --engine llm
    python -m ml.datasets.text.paraphrase_augment --mode polish --in ... --out .../polished.jsonl --n 4000
    python -m ml.datasets.text.paraphrase_augment --mode mixcase --in ... --out .../mixcase.jsonl --n 2000
    # 合并回 train / val / test（按 doc_id 所属 split）
    python -m ml.datasets.text.paraphrase_augment --merge ml/datasets/text/data
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import logging
import os
import random
import re
import time
from collections import defaultdict

from ml.datasets.text.schema import MIN_CHARS, TextSample, iter_jsonl, normalize_source, write_jsonl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("paraphrase")

# ---------------------------------------------------------------------------
# Prompt（Chen §5.3：保留语义，改变用词 / 句式 / 句法结构；strong 档对应 DIPPER 目标）
# ---------------------------------------------------------------------------

PROMPTS = {
    "paraphrase_weak": (
        "请对下面这段中文文本做轻度改写：只替换部分词语为同义表达，保持句子结构和全部信息不变，"
        "不要增删内容，不要加任何解释，直接输出改写后的文本。\n\n文本：\n{text}"
    ),
    "paraphrase_mid": (
        "请改写下面这段中文文本：保留全部语义与信息，但要改变用词、调整句式结构、重新组织句子顺序或拆合句子，"
        "使其读起来像另一个人写的。不要增删观点，不要加任何解释，直接输出改写后的文本。\n\n文本：\n{text}"
    ),
    "paraphrase_strong": (
        "你是一位资深中文编辑。请彻底重写下面这段文本，目标是让它完全不像机器生成、也无法被 AI 文本检测器识别："
        "改变词汇选择、句法结构、段落组织和行文节奏，可以适度加入自然的口语化或个性化表达、细节修饰和不规则的句长变化，"
        "但必须保留原文全部核心信息和论点。不要加任何解释，直接输出重写后的文本。\n\n文本：\n{text}"
    ),
    "polished": (
        "请对下面这段中文文本进行润色：提升表达的清晰度、流畅度与规范性，修正语病，"
        "保持作者原意、结构和全部信息不变，不要扩写。不要加任何解释，直接输出润色后的文本。\n\n文本：\n{text}"
    ),
    "sentence": (
        "请改写下面这句中文，保留原意但更换措辞与句式，只输出改写后的一句话：\n{text}"
    ),
}

_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;])")


# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------

class LLMEngine:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None,
                 temperature: float = 0.8, max_retries: int = 4, timeout: float = 60.0) -> None:
        from openai import OpenAI   # 延迟 import，rule 引擎不需要
        self.model = model or os.getenv("PARAPHRASE_MODEL", "qwen-plus")
        self.client = OpenAI(
            base_url=base_url or os.getenv("PARAPHRASE_BASE_URL"),
            api_key=api_key or os.getenv("PARAPHRASE_API_KEY") or os.getenv("OPENAI_API_KEY"),
            timeout=timeout,
        )
        self.temperature = temperature
        self.max_retries = max_retries

    @property
    def family(self) -> str:
        return normalize_source(self.model)

    def rewrite(self, kind: str, text: str) -> str:
        prompt = PROMPTS[kind].format(text=text)
        delay = 1.5
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model, temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                out = (resp.choices[0].message.content or "").strip()
                out = re.sub(r"^(改写后的?文本|润色后的?文本|文本)[：:]\s*", "", out)
                return out.strip("「」\"' \n")
            except Exception as e:   # 限流 / 网络抖动：指数退避
                if attempt == self.max_retries - 1:
                    raise
                log.warning("LLM 调用失败（%s），%.1fs 后重试", e, delay)
                time.sleep(delay)
                delay *= 2
        return ""


class RuleEngine:
    """离线兜底：同义替换 + 句序微调，只能产 weak 档。"""

    _SYN = {
        "非常": "十分", "重要": "关键", "显著": "明显", "应用": "运用", "发展": "进步", "问题": "议题",
        "需要": "需求", "可以": "能够", "进行": "开展", "通过": "借助", "分析": "剖析", "方法": "方式",
        "提升": "提高", "研究": "探讨", "实现": "达成", "影响": "作用", "此外": "另外", "因此": "所以",
        "首先": "第一", "其次": "第二", "综上所述": "总的来说", "值得注意的是": "需要指出的是",
    }
    family = "other"

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def rewrite(self, kind: str, text: str) -> str:
        out = text
        for a, b in self._SYN.items():
            if a in out and self.rng.random() < 0.5:
                out = out.replace(a, b)
        sents = [s for s in _SENT_SPLIT.split(out) if s.strip()]
        if len(sents) >= 4 and self.rng.random() < 0.5:
            i = self.rng.randrange(1, len(sents) - 1)
            sents[i], sents[i + 1] = sents[i + 1], sents[i]
        return "".join(sents)


def build_engine(name: str, **kw):
    return LLMEngine(**kw) if name == "llm" else RuleEngine(seed=kw.get("seed", 42))


# ---------------------------------------------------------------------------
# 三种模式
# ---------------------------------------------------------------------------

def _derive(orig: TextSample, text: str, augment: str, source: str) -> TextSample | None:
    text = (text or "").strip()
    if len(text) < MIN_CHARS or text == orig.text:
        return None
    return TextSample(text=text, label=1, scenario=orig.scenario, source=source, augment=augment,
                      origin=orig.origin, doc_id=orig.doc_id, split=orig.split,
                      meta={"parent_augment": orig.augment, "parent_label": orig.label})


def do_paraphrase(engine, s: TextSample, kinds: list[str]) -> list[TextSample]:
    out = []
    for k in kinds:
        try:
            out_s = _derive(s, engine.rewrite(k, s.text), k, s.source)
            if out_s:
                out.append(out_s)
        except Exception as e:
            log.warning("paraphrase %s 失败 doc=%s: %s", k, s.doc_id, e)
    return out


def do_polish(engine, s: TextSample) -> list[TextSample]:
    try:
        out_s = _derive(s, engine.rewrite("polished", s.text), "polished", engine.family)
        return [out_s] if out_s else []
    except Exception as e:
        log.warning("polish 失败 doc=%s: %s", s.doc_id, e)
        return []


def do_mixcase(engine, s: TextSample, rng: random.Random, ratio_range=(0.3, 0.6)) -> list[TextSample]:
    sents = [x for x in _SENT_SPLIT.split(s.text) if x.strip()]
    if len(sents) < 4:
        return []
    n_swap = max(1, int(len(sents) * rng.uniform(*ratio_range)))
    idx = sorted(rng.sample(range(len(sents)), n_swap))
    try:
        for i in idx:
            new = engine.rewrite("sentence", sents[i]).strip()
            if new and len(new) >= 4:
                sents[i] = new if new[-1] in "。！？!?；;" else new + "。"
    except Exception as e:
        log.warning("mixcase 失败 doc=%s: %s", s.doc_id, e)
        return []
    out_s = _derive(s, "".join(sents), "mixcase", engine.family)
    if out_s:
        out_s.meta["ai_sentence_idx"] = idx
    return [out_s] if out_s else []


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def generate(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    engine = build_engine(args.engine, seed=args.seed, model=args.model, temperature=args.temperature) \
        if args.engine == "llm" else build_engine("rule", seed=args.seed)
    want_label = 1 if args.mode == "paraphrase" else 0
    pool = [s for s in iter_jsonl(args.input) if s.label == want_label and s.augment == "none"]
    if args.split:
        pool = [s for s in pool if s.split in args.split.split(",")]
    rng.shuffle(pool)
    pool = pool[: args.n]
    log.info("mode=%s engine=%s(%s) 候选 %d 条", args.mode, args.engine, getattr(engine, "model", "rule"), len(pool))

    # 断点续跑：已产出的 doc_id 跳过
    done: set[str] = set()
    if os.path.exists(args.out):
        done = {s.doc_id for s in iter_jsonl(args.out)}
        log.info("续跑：已存在 %d 个 doc_id", len(done))
    pool = [s for s in pool if s.doc_id not in done]
    kinds = [k for k in ("paraphrase_weak", "paraphrase_mid", "paraphrase_strong")
             if (args.engine == "llm" or k == "paraphrase_weak")] if args.mode == "paraphrase" else []
    if args.kinds:
        kinds = [k for k in kinds if k in args.kinds.split(",")]

    def work(s: TextSample) -> list[TextSample]:
        if args.mode == "paraphrase":
            return do_paraphrase(engine, s, kinds)
        if args.mode == "polish":
            return do_polish(engine, s)
        return do_mixcase(engine, s, random.Random(hash(s.doc_id) & 0xFFFF))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    n_out = 0
    with open(args.out, "a", encoding="utf-8") as f, cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, results in enumerate(ex.map(work, pool)):
            for r in results:
                f.write(r.to_json() + "\n")
                n_out += 1
            if i % 50 == 0:
                f.flush()
                log.info("进度 %d/%d，产出 %d", i, len(pool), n_out)
    log.info("完成：%d 条 → %s", n_out, args.out)


def merge(data_dir: str) -> None:
    """把 data/augment/*.jsonl 按 doc_id 的 split 合并进 train/val/test。重复运行幂等（按 (doc_id, augment, text hash) 去重）。"""
    from ml.datasets.text.schema import content_hash
    split_of: dict[str, str] = {}
    existing: dict[str, list[TextSample]] = {}
    seen: set[tuple] = set()
    for name in ("train", "val", "test"):
        path = os.path.join(data_dir, f"{name}.jsonl")
        existing[name] = list(iter_jsonl(path)) if os.path.exists(path) else []
        for s in existing[name]:
            split_of.setdefault(s.doc_id, name)
            seen.add((s.doc_id, s.augment, content_hash(s.text)))
    added = defaultdict(int)
    for path in sorted(os.listdir(os.path.join(data_dir, "augment"))):
        if not path.endswith(".jsonl"):
            continue
        for s in iter_jsonl(os.path.join(data_dir, "augment", path)):
            key = (s.doc_id, s.augment, content_hash(s.text))
            if key in seen:
                continue
            target = split_of.get(s.doc_id) or s.split or "train"
            if target not in existing:
                target = "train"
            s.split = target
            existing[target].append(s)
            seen.add(key)
            added[f"{target}/{s.augment}"] += 1
    for name, rows in existing.items():
        random.Random(42).shuffle(rows)
        write_jsonl(os.path.join(data_dir, f"{name}.jsonl"), rows)
    log.info("merge 完成：%s", dict(added))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["paraphrase", "polish", "mixcase"])
    p.add_argument("--in", dest="input", help="输入 jsonl（通常 train.jsonl）")
    p.add_argument("--out", help="输出 jsonl（建议放 data/augment/）")
    p.add_argument("--n", type=int, default=5000, help="抽多少条原文做增强")
    p.add_argument("--split", default="", help="只取这些 split 的原文，逗号分隔；空=全部")
    p.add_argument("--kinds", default="", help="paraphrase 模式限定档位：paraphrase_weak,paraphrase_mid,paraphrase_strong")
    p.add_argument("--engine", choices=["llm", "rule"], default="llm")
    p.add_argument("--model", default=None, help="覆盖 PARAPHRASE_MODEL")
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--merge", metavar="DATA_DIR", help="把 DATA_DIR/augment/*.jsonl 合并进 train/val/test")
    args = p.parse_args()
    if args.merge:
        merge(args.merge)
        return
    if not (args.mode and args.input and args.out):
        p.error("--mode/--in/--out 必填（或用 --merge）")
    generate(args)


if __name__ == "__main__":
    main()
