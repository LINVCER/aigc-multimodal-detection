"""
v0.1.0 离线评估
==============

用法：
    python -m ml.evaluation.text.eval \
        --checkpoint ml/checkpoints/text/v0.1.0-baseline/best.pth \
        --test-jsonl ml/datasets/text/test.jsonl

产出：
    ml/checkpoints/text/{version}/eval-report.json
    - 总体：Accuracy / F1 / AUROC / ECE / Brier
    - 按场景细分：6 场景各自的 F1（防偏科）
    - 按 source 细分：human / gpt / claude / qwen / ... 各自 recall
    - 混淆矩阵
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--test-jsonl", required=True)
    args = parser.parse_args()

    # TODO(v0.1.0)：
    #  1) 加载 checkpoint 走 deploy 侧同款 pipeline
    #  2) 遍历 test set → 逐条 predict
    #  3) 计算 Accuracy / F1 / AUROC / ECE / Brier
    #  4) 按 scenario / source 分组细分
    #  5) dump eval-report.json + 打印摘要
    raise NotImplementedError(f"评估计划待启动；checkpoint={args.checkpoint}")


if __name__ == "__main__":
    main()
