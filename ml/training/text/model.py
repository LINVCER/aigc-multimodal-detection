"""
v0.1.0-baseline 文本 AIGC 检测模型
"""
from __future__ import annotations

import torch
import torch.nn as nn
from transformers import AutoModel


class TextAIGCModel(nn.Module):
    """
    结构：RoBERTa/DeBERTa → [CLS] embedding → Dropout → Linear(hidden, 256) → ReLU
          → Dropout → Linear(256, num_classes)

    对比 legacy/algorithms/train_text_detector.py 的差异：
    - 去掉 GRL 领域对抗（首个 baseline 不做多任务）
    - 去掉 contrastive head（v0.1.0 先跑通再加复杂度）
    - 校准头（temperature + Platt）拆到 calibration.py 独立处理
    """

    def __init__(self, backbone: str, num_classes: int = 2,
                 classifier_hidden: int = 256, dropout: float = 0.1):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(backbone, trust_remote_code=True)
        hidden = self.backbone.config.hidden_size
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(hidden, classifier_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(classifier_hidden, num_classes),
        )

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        outputs = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        cls_emb = outputs.last_hidden_state[:, 0, :]
        return self.classifier(cls_emb)


# TODO(v0.1.0)：解冻策略工具（只解冻 backbone 最后 N 层）
def freeze_backbone_except_last(model: TextAIGCModel, unfreeze_layers: int) -> None:
    raise NotImplementedError("待 v0.1.0 训练启动时实现")
