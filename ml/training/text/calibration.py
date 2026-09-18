"""
校准：温度缩放（Guo 2017）+ Platt sigmoid

推理时公式（跟 deploy/inference-python/detectors/text.py 完全一致）：
    calibrated_prob = sigmoid((raw_logit / T) * a + b)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class CalibrationParams:
    temperature: float
    platt_a: float
    platt_b: float


# TODO(v0.1.0)：温度缩放，L-BFGS on NLL
def fit_temperature(logits: np.ndarray, labels: np.ndarray, max_iter: int = 200) -> float:
    raise NotImplementedError("待 v0.1.0 训练启动时实现")


# TODO(v0.1.0)：Platt sigmoid（LR on scaled logits）
def fit_platt(scaled_logits: np.ndarray, labels: np.ndarray, c: float = 1.0) -> tuple[float, float]:
    raise NotImplementedError("待 v0.1.0 训练启动时实现")


def ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 15) -> float:
    """Expected Calibration Error（越低越准）"""
    raise NotImplementedError("待 v0.1.0 训练启动时实现")
