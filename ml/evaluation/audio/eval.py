"""
v0.1.0 音频离线评估

用法：
    python -m ml.evaluation.audio.eval \
        --checkpoint ml/checkpoints/audio/v0.1.0-baseline/best.pth \
        --test-jsonl ml/datasets/audio/test.jsonl

产出 ml/checkpoints/audio/{version}/eval-report.json：
    - 总体：Accuracy / F1 / AUROC / ECE / Brier
    - 按 source 细分：real_human / tts / cloned_voice / mixed 各自 recall
    - 按时长桶细分：0-5s / 5-15s / 15-60s / 60s+ 各自 F1
    - 混淆矩阵
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--test-jsonl", required=True)
    args = parser.parse_args()

    # TODO(Wave 5)
    raise NotImplementedError(f"评估计划待启动；checkpoint={args.checkpoint}")


if __name__ == "__main__":
    main()
