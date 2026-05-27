"""篡改检测输出数据类型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class BranchResult:
    """单分支检测结果"""
    branch_name: str
    score_map: np.ndarray          # (H,W) float32 [0,1] — 连续置信度图
    confidence: float              # 全局置信度 [0,1]
    mask: np.ndarray | None = None # (H,W) bool — 仅 DL 分支有像素级 mask
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TamperingDetectionOutput:
    """篡改检测统一输出"""
    is_tampered: bool
    tampering_score: float             # [0,1] 加权置信度
    tampering_type: str                # splicing / copy_move / inpainting / retouching / unknown
    mask: np.ndarray                   # (H,W) bool 最终融合 mask
    uncertain_mask: np.ndarray         # (H,W) bool 低置信度区域
    mask_base64: str                   # PNG base64
    overlay_base64: str                # PNG base64 (红=篡改 黄=不确定)
    branch_results: list[BranchResult]
    explanation_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
