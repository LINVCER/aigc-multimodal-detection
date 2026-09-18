"""
v0.1.0-baseline 音频 AIGC 检测模型

结构（wav2vec2 微调 + 分类头）：
    Wav2Vec2 backbone → hidden [B, T, H]
        → mean pooling over T → [B, H]
        → Dropout → Linear(H, 128) → ReLU → Dropout → Linear(128, num_classes)
"""
from __future__ import annotations

import torch
import torch.nn as nn


class AudioAIGCModel(nn.Module):
    def __init__(self, backbone: str, num_classes: int = 2,
                 classifier_hidden: int = 128, dropout: float = 0.1,
                 pooling: str = "mean"):
        super().__init__()
        # TODO(Wave 5)：
        #   from transformers import Wav2Vec2Model
        #   self.backbone = Wav2Vec2Model.from_pretrained(backbone)
        #   hidden = self.backbone.config.hidden_size
        raise NotImplementedError("待 Wave 5 · ml/training/audio 训练启动时实现")

    def forward(self, input_values: torch.Tensor, attention_mask: torch.Tensor | None = None) -> torch.Tensor:
        raise NotImplementedError
