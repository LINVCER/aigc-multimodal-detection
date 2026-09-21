"""
文本 AIGC 检测模型（训练侧入口）

真正的定义在 ml/common/fusion_model.py，训练与推理共用；这里只做 re-export，
保持 `from ml.training.text.model import ...` 的历史 import 路径可用。
"""
from __future__ import annotations

from ml.common.fusion_model import (  # noqa: F401
    ARCH_CLS_ONLY,
    ARCH_FUSION,
    ARCHS,
    FusionAIGCDetector,
    MultiScaleTextCNN,
    freeze_backbone_except_last,
)

# 历史别名
TextAIGCModel = FusionAIGCDetector

__all__ = [
    "ARCH_CLS_ONLY", "ARCH_FUSION", "ARCHS",
    "FusionAIGCDetector", "MultiScaleTextCNN", "TextAIGCModel",
    "freeze_backbone_except_last",
]
