"""
v0.1.0-baseline 训练入口
========================

用法（v0.1.0 数据准备完成后）：
    python -m ml.training.text.train --config ml/configs/text/v0.1.0-baseline.yaml

产出：
    ml/checkpoints/text/v0.1.0-baseline/
    ├── best.pth             （含 model_state_dict + temperature + platt_a + platt_b + hyperparams）
    ├── metrics.json         （val/test 指标）
    └── config.snapshot.yaml （config 快照，可复现）

checkpoint schema 严格对齐 deploy/inference-python/detectors/text.py 的 load()
以便训完直接被推理服务加载。
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="ml/configs/text/*.yaml")
    args = parser.parse_args()

    # TODO(v0.1.0)：
    #  1) 读 yaml
    #  2) load_jsonl → scenario_balanced_sampler
    #  3) TextAIGCModel + freeze_backbone_except_last
    #  4) train loop（AdamW + warmup + grad_clip + early_stop）
    #  5) 验证集拿 logits → fit_temperature → fit_platt
    #  6) torch.save({model_state_dict, temperature, platt_a, platt_b, hyperparams, metrics})
    raise NotImplementedError(f"训练计划待启动；config={args.config}")


if __name__ == "__main__":
    main()
