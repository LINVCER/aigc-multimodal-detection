"""
用人类正文语料拟合 30 维表层特征的 mean/std，产出外置基线 JSON。

用途：当前部署的 cls_only checkpoint 没有表层支路（surface_scaler 为空），助手解释「为什么像 AI」时
拿不到 z-score。把本脚本产出的文件通过 TEXT_SURFACE_BASELINE_PATH 挂给推理服务，
cls_only 模型也能给出「相对通用论文基线」的方向性证据；fusion 模型训出来后以 checkpoint 自带 scaler 为准。

输入：ml/datasets/text/schema.py 口径的 jsonl（text / label / scenario），默认只取 label=0 的人类正文。
用法：
    python -m ml.datasets.text.build_surface_baseline \
        --input ml/datasets/text/data/train.jsonl \
        --output deploy/inference-python/assets/surface_baseline_zh_thesis.json \
        --scenarios academic_bachelor academic_master academic_phd
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

from ml.common.surface_features import SurfaceScaler, extract_surface_features_batch


def _iter_texts(path: Path, human_only: bool, scenarios: set[str] | None, min_chars: int):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if human_only and int(d.get("label", 1)) != 0:
                continue
            if scenarios and d.get("scenario") not in scenarios:
                continue
            text = (d.get("text") or "").strip()
            if len(text) >= min_chars:
                yield text


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, nargs="+", help="jsonl 文件，可多个")
    ap.add_argument("--output", required=True)
    ap.add_argument("--scenarios", nargs="*", default=None, help="只取这些场景；缺省取全部")
    ap.add_argument("--include-ai", action="store_true", help="同时纳入 label=1 的样本（默认只用人类正文）")
    ap.add_argument("--min-chars", type=int, default=120)
    ap.add_argument("--max-samples", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    scenarios = set(args.scenarios) if args.scenarios else None
    texts: list[str] = []
    for p in args.input:
        texts.extend(_iter_texts(Path(p), not args.include_ai, scenarios, args.min_chars))
    if len(texts) < 50:
        raise SystemExit(f"样本太少（{len(texts)} 条），基线不可信；至少 50 条")
    if len(texts) > args.max_samples:
        texts = random.Random(args.seed).sample(texts, args.max_samples)

    scaler = SurfaceScaler().fit(extract_surface_features_batch(texts))
    payload = scaler.to_dict()
    payload.update({
        "n": len(texts),
        "human_only": not args.include_ai,
        "scenarios": sorted(scenarios) if scenarios else "all",
        "inputs": [str(p) for p in args.input],
    })
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    std = np.asarray(payload["std"])
    print(f"基线已写入 {out}：{len(texts)} 段，{len(payload['names'])} 维，常数列 {int((std == 1.0).sum())} 个")


if __name__ == "__main__":
    main()
