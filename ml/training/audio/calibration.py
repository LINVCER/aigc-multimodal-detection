"""
音频校准（跟 ml/training/text/calibration.py 完全一致的公式）
    calibrated_prob = sigmoid((raw_logit / T) * a + b)

同 checkpoint 里存 { temperature, platt_a, platt_b }。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class CalibrationParams:
    temperature: float
    platt_a: float
    platt_b: float


# TODO(Wave 5)
def fit_temperature(logits: np.ndarray, labels: np.ndarray, max_iter: int = 200) -> float:
    raise NotImplementedError


def fit_platt(scaled_logits: np.ndarray, labels: np.ndarray, c: float = 1.0) -> tuple[float, float]:
    raise NotImplementedError


def ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 15) -> float:
    raise NotImplementedError
