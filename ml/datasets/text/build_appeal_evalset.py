"""
把运营复核过的申诉样本（后台 /admin/hard-samples/export 导出的 JSONL）转成第七套评测集 eval_appeal.jsonl。

    python -m ml.datasets.text.build_appeal_evalset \
        --in  downloads/appeal-samples-2026-10-07.jsonl \
        --out ml/datasets/text/data/evalsets/eval_appeal.jsonl

规则（docs/design/202610-assistant-growth-loop-plan.md §2.1）：
- 只收 ops_verdict ∈ {confirm_fp, confirm_tp}；unsure 丢弃
- confirm_fp → label 0（人写被判 AI，评 FPR）；confirm_tp → label 1（确实是 AI，评 TPR）
- 只进评测集，不进训练集；文件名以 eval_ 开头，ml.evaluation.text.eval --evalset-dir 会自动带上
- 文本按 MIN_CHARS 过滤：太短的段进 short 口径不进主集，和六套公开评测集一致
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from ml.datasets.text.schema import MIN_CHARS, SCENARIOS, TextSample, content_hash, write_jsonl

VERDICT_LABEL = {"confirm_fp": 0, "confirm_tp": 1}


def convert(rows: list[dict]) -> tuple[list[TextSample], Counter]:
    out: list[TextSample] = []
    stat: Counter = Counter()
    seen: set[str] = set()
    for r in rows:
        v = r.get("verdict")
        text = (r.get("text") or "").strip()
        if v not in VERDICT_LABEL:
            stat["skip_verdict"] += 1
            continue
        if not text:
            stat["skip_no_text"] += 1
            continue
        if len(text) < MIN_CHARS:
            stat["skip_short"] += 1
            continue
        h = content_hash(text)
        if h in seen:
            stat["skip_dup"] += 1
            continue
        seen.add(h)
        scenario = r.get("scenario") if r.get("scenario") in SCENARIOS else "other"
        label = VERDICT_LABEL[v]
        out.append(TextSample(
            text=text,
            label=label,
            scenario=scenario,
            source="human" if label == 0 else "other",     # 申诉里确认是 AI 的样本不知道生成器，归 other
            augment="none",
            origin="appeal",
            doc_id=f"appeal-{r.get('sample_id', h[:12])}",
            split="eval_appeal",
            meta={
                "model_prob": r.get("model_prob"),
                "model_version": r.get("model_version"),
                "task_id": r.get("task_id"),
                "paragraph_idx": r.get("paragraph_idx"),
                "verdict": v,
            },
        ))
        stat[f"label_{label}"] += 1
    return out, stat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="后台导出的 JSONL")
    ap.add_argument("--out", required=True, help="输出 eval_appeal.jsonl")
    args = ap.parse_args()

    rows = []
    with open(args.inp, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    samples, stat = convert(rows)
    n = write_jsonl(args.out, samples)
    print(f"读入 {len(rows)} 条 → 写出 {n} 条到 {args.out}")
    for k, v in sorted(stat.items()):
        print(f"  {k:<14} {v}")
    if stat.get("label_0", 0) and not stat.get("label_1", 0):
        print("注意：只有 label=0（确认误判）样本，AUROC 无定义；看报告里的 FPR 即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
