"""
六套评测集切分（MODEL_UPGRADE_PLAN §2.4 · 固定不动，任何模型改动必须全量跑）
========================================================================

    eval_in_domain.jsonl        test.jsonl 里 augment=none 的样本
    eval_cross_generator.jsonl  held_out.jsonl（build_dataset --held-out-sources 产出的未见生成器 AI 样本）+ 等量 human
    eval_adversarial.jsonl      test 里 paraphrase_mid / paraphrase_strong + 等量 human（改写鲁棒）
    eval_polished.jsonl         test 里 polished + 等量 human（Fraser「差于随机」区间，单独盯）
    eval_mixed.jsonl            test 里 mixcase + polished + 等量 human（人机混写）
    eval_short_text.jsonl       short.jsonl（50-119 字）

用法::

    python -m ml.datasets.text.build_evalsets --data ml/datasets/text/data
    # 附加外部基准（C-ReD / MAGA-Bench 等已转 schema 的 jsonl）：
    python -m ml.datasets.text.build_evalsets --data ... --extra cred=path/to/cred.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random

from ml.datasets.text.schema import TextSample, iter_jsonl, write_jsonl

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
log = logging.getLogger("evalsets")


def _load(path: str) -> list[TextSample]:
    return list(iter_jsonl(path)) if os.path.exists(path) else []


def _with_human(ai: list[TextSample], human_pool: list[TextSample], rng: random.Random,
                ratio: float = 1.0) -> list[TextSample]:
    n = min(len(human_pool), int(len(ai) * ratio))
    out = ai + rng.sample(human_pool, n)
    rng.shuffle(out)
    return out


def build(data_dir: str, extra: dict[str, str], seed: int, min_size: int) -> None:
    rng = random.Random(seed)
    out_dir = os.path.join(data_dir, "evalsets")
    os.makedirs(out_dir, exist_ok=True)
    test = _load(os.path.join(data_dir, "test.jsonl"))
    human = [s for s in test if s.label == 0 and s.augment == "none"]
    sets: dict[str, list[TextSample]] = {}

    sets["in_domain"] = [s for s in test if s.augment == "none"]

    held = _load(os.path.join(data_dir, "held_out.jsonl"))
    if held:
        sets["cross_generator"] = _with_human([s for s in held if s.label == 1], human, rng)

    adv = [s for s in test if s.augment in ("paraphrase_mid", "paraphrase_strong")]
    if adv:
        sets["adversarial"] = _with_human(adv, human, rng)

    pol = [s for s in test if s.augment == "polished"]
    if pol:
        sets["polished"] = _with_human(pol, human, rng)

    mixed = [s for s in test if s.augment in ("mixcase", "polished")]
    if mixed:
        sets["mixed"] = _with_human(mixed, human, rng)

    short = _load(os.path.join(data_dir, "short.jsonl"))
    if short:
        sets["short_text"] = short

    for name, path in extra.items():
        rows = _load(path)
        if rows:
            sets[name] = rows

    summary = {}
    for name, rows in sets.items():
        for s in rows:
            s.split = f"eval_{name}"
        n_ai = sum(s.label for s in rows)
        if len(rows) < min_size:
            log.warning("eval_%s 只有 %d 条（< %d），统计意义不足；先产出但请补数据", name, len(rows), min_size)
        write_jsonl(os.path.join(out_dir, f"eval_{name}.jsonl"), rows)
        summary[name] = {"n": len(rows), "ai": n_ai, "human": len(rows) - n_ai}
        log.info("eval_%-16s n=%-6d ai=%-6d human=%d", name, len(rows), n_ai, len(rows) - n_ai)
    missing = [k for k in ("cross_generator", "adversarial", "polished", "mixed", "short_text") if k not in sets]
    if missing:
        log.warning("缺少评测集 %s：分别需要 --held-out-sources / paraphrase_augment 三种模式 / short.jsonl", missing)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="ml/datasets/text/data")
    p.add_argument("--extra", action="append", default=[], help="name=path，外部基准 jsonl（已转 schema）")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-size", type=int, default=300)
    args = p.parse_args()
    extra = dict(x.split("=", 1) for x in args.extra)
    build(args.data, extra, args.seed, args.min_size)


if __name__ == "__main__":
    main()
