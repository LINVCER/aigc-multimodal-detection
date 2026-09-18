"""
v0.1.0-baseline 音频训练入口（Wave 5）

用法（数据 & 依赖就绪后）：
    python -m ml.training.audio.train --config ml/configs/audio/v0.1.0-baseline.yaml

产出（对齐 deploy/inference-python/detectors/audio.py 的 load 期望字段）：
    ml/checkpoints/audio/v0.1.0-baseline/
    ├── best.pth   { model_state_dict, temperature, platt_a, platt_b, hyperparams, metrics }
    ├── metrics.json
    └── config.snapshot.yaml
"""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="ml/configs/audio/*.yaml")
    args = parser.parse_args()

    # TODO(Wave 5)：
    #   1) 读 yaml
    #   2) load_jsonl → source_balanced_sampler
    #   3) AudioAIGCModel + freeze_feature_encoder
    #   4) train loop（AdamW + warmup + grad_clip + early_stop）
    #   5) 验证集拿 logits → fit_temperature → fit_platt
    #   6) torch.save 对齐推理侧 load() 期望的 schema
    raise NotImplementedError(f"训练计划待启动；config={args.config}")


if __name__ == "__main__":
    main()
