"""
论文域 AI 文本生成（L2）
========================

读种子（L0 真实论文 / CSL 的标题或首段）→ 角色化 prompt → OpenAI 兼容 LLM 生成 → 写 schema JSONL。
对齐 dataset-build-plan §3.3：每种子 2 温度 × 3 任务（续写 / 按标题写摘要 / 按要素写引言·结论），
label=1，source=模型家族，origin=custom，doc_id 继承种子（切分时同 split，杜绝泄漏）。

一模型一次跑（多家族 = 换 PARAPHRASE_MODEL/--model 多跑几次），append 断点续跑，复用 paraphrase_augment 的 env 约定::

    PARAPHRASE_BASE_URL  例 https://dashscope.aliyuncs.com/compatible-mode/v1
    PARAPHRASE_API_KEY / OPENAI_API_KEY
    PARAPHRASE_MODEL     例 qwen-plus / deepseek-chat

用法::

    python -m ml.datasets.text.generate_thesis_domain --seeds data/train.jsonl \
        --out data/gen/qwen.jsonl --engine llm --model qwen-plus --temps 0.7,1.0 --n 2000
    python -m ml.datasets.text.generate_thesis_domain --selftest     # 离线 stub，不联网
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import re
import time

from ml.common.constants import MAX_CHARS, MIN_CHARS
from ml.datasets.text.schema import SCENARIOS, TextSample, iter_jsonl, normalize_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("generate_thesis")

# 场景 → 角色措辞（prompt 用）
_SCENARIO_ROLE = {
    "academic_bachelor": "本科毕业论文作者", "academic_master": "硕士研究生", "academic_phd": "博士研究生",
    "job_report": "行业分析师", "self_media": "公众号作者", "other": "作者",
}
# 三任务 prompt：{role} {seed} 填充；禁抄原文、控长度 300~600 字
PROMPTS = {
    "continue": "你是一名{role}。请承接下面这段论文开头，续写 300~600 字正文，保持学术语体，"
                "不要照抄给定文字，只输出续写内容：\n\n{seed}",
    "abstract": "你是一名{role}。请以《{seed}》为题，写一段 300~600 字的中文论文摘要，"
                "包含研究背景、方法、结论，只输出摘要正文：",
    "intro": "你是一名{role}。研究主题：{seed}。请写一段 300~600 字的引言或结论，"
             "论证层次清晰、学术规范，只输出正文：",
}
TASKS = tuple(PROMPTS.keys())
_SENT = re.compile(r"(?<=[。！？!?])")


class GenEngine:
    """OpenAI 兼容生成客户端；env 约定与 paraphrase_augment 一致。"""

    def __init__(self, model: str | None = None, temperature: float = 0.8, max_retries: int = 4, timeout: float = 90.0):
        from openai import OpenAI   # 延迟 import，stub 不需要
        self.model = model or os.getenv("PARAPHRASE_MODEL", "qwen-plus")
        self.client = OpenAI(base_url=os.getenv("PARAPHRASE_BASE_URL"),
                             api_key=os.getenv("PARAPHRASE_API_KEY") or os.getenv("OPENAI_API_KEY"), timeout=timeout)
        self.temperature = temperature
        self.max_retries = max_retries

    @property
    def family(self) -> str:
        return normalize_source(self.model)

    def generate(self, prompt: str) -> str:
        delay = 1.5
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model, temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}])
                return (resp.choices[0].message.content or "").strip().strip("「」\"' \n")
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                log.warning("LLM 生成失败（%s），%.1fs 后重试", e, delay)
                time.sleep(delay)
                delay *= 2
        return ""


class StubEngine:
    """离线兜底：由种子模板化拼出 ≥MIN_CHARS 的伪文本，仅供 --selftest 跑通管线，不产真数据。"""

    family = "other"

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate(self, prompt: str) -> str:
        core = prompt[-80:]
        filler = "本研究在既有文献基础上进一步展开，系统梳理了相关变量并提出可检验的假设，" \
                 "通过规范的实证设计获取数据，层层递进地分析了影响机制与因果路径，结论具有一定参考价值。"
        return (core + filler) * 2


def _seed_text(s: TextSample) -> str:
    """取种子：优先 meta.title，否则正文前 60 字。"""
    title = (s.meta or {}).get("title") if isinstance(s.meta, dict) else None
    return (title or s.text[:60]).strip()


def _emit(seed: TextSample, task: str, temp: float, text: str, family: str) -> TextSample | None:
    text = (text or "").strip()
    if len(text) < MIN_CHARS:
        return None
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
    scenario = seed.scenario if seed.scenario in SCENARIOS else "other"
    return TextSample(text=text, label=1, scenario=scenario, source=family, augment="none",
                      origin="custom", doc_id=f"{seed.doc_id}-gen-{task}-{int(temp * 10)}", split=seed.split,
                      meta={"seed_doc_id": seed.doc_id, "task": task, "temp": temp})


def run(args) -> None:
    seeds = [s for s in iter_jsonl(args.seeds) if s.label == 0][: args.n]
    temps = [float(t) for t in args.temps.split(",") if t.strip()]
    done: set[str] = set()
    if args.resume and os.path.exists(args.out):
        done = {s.doc_id for s in iter_jsonl(args.out)}
        log.info("续跑：已存在 %d 条", len(done))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    n = 0
    with open(args.out, "a", encoding="utf-8") as f:
        for si, seed in enumerate(seeds):
            for temp in temps:
                eng = StubEngine() if args.engine == "stub" else GenEngine(model=args.model, temperature=temp)
                for task in TASKS:
                    doc_id = f"{seed.doc_id}-gen-{task}-{int(temp * 10)}"
                    if doc_id in done:
                        continue
                    role = _SCENARIO_ROLE.get(seed.scenario, "作者")
                    prompt = PROMPTS[task].format(role=role, seed=_seed_text(seed))
                    try:
                        out = _emit(seed, task, temp, eng.generate(prompt), eng.family)
                    except Exception as e:
                        log.warning("生成失败 doc=%s task=%s: %s", seed.doc_id, task, e)
                        continue
                    if out:
                        f.write(out.to_json() + "\n")
                        f.flush()
                        n += 1
            if (si + 1) % 50 == 0:
                log.info("进度 %d/%d 种子，已产 %d 条", si + 1, len(seeds), n)
    log.info("生成完成：%d 条 → %s", n, args.out)


def _selftest() -> None:
    import io, json, tempfile
    d = tempfile.mkdtemp()
    seeds = os.path.join(d, "seeds.jsonl")
    out = os.path.join(d, "gen.jsonl")
    with io.open(seeds, "w", encoding="utf-8") as f:
        for i in range(2):
            f.write(TextSample(text="数字媒介使用对城市青年社会资本的影响研究引言。" * 4, label=0,
                               scenario="academic_master", origin="thesis", doc_id=f"t-{i}",
                               meta={"title": f"标题{i}"}).to_json() + "\n")
    args = argparse.Namespace(seeds=seeds, out=out, engine="stub", model=None, temps="0.7,1.0", n=10, resume=False)
    run(args)
    rows = [json.loads(l) for l in io.open(out, encoding="utf-8")]
    assert rows, "应产出样本"
    assert all(r["label"] == 1 and r["origin"] == "custom" and len(r["text"]) >= MIN_CHARS for r in rows)
    assert all(r["doc_id"].startswith("t-") and "-gen-" in r["doc_id"] for r in rows)
    # 2 种子 × 2 温度 × 3 任务 = 12
    assert len(rows) == 12, f"应 12 条，实际 {len(rows)}"
    print(f"generate selftest ok：{len(rows)} 条，schema 合法")


def main() -> None:
    ap = argparse.ArgumentParser(description="论文域 AI 文本生成（L2）")
    ap.add_argument("--seeds", help="种子 JSONL（label=0 的人类样本）")
    ap.add_argument("--out", help="输出 JSONL（append 续跑）")
    ap.add_argument("--engine", choices=["llm", "stub"], default="llm")
    ap.add_argument("--model", help="覆盖 PARAPHRASE_MODEL，如 qwen-plus / deepseek-chat")
    ap.add_argument("--temps", default="0.7,1.0", help="逗号分隔温度")
    ap.add_argument("--n", type=int, default=2000, help="取前 N 个种子")
    ap.add_argument("--resume", action="store_true", help="跳过已产出的 doc_id")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    elif a.seeds and a.out:
        run(a)
    else:
        ap.error("需要 --seeds 和 --out，或 --selftest")


if __name__ == "__main__":
    main()
