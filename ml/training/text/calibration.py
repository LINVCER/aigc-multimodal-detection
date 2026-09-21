"""
校准与阈值
==========

推理公式（与 deploy/inference-python/detectors/text.py 完全一致）::

    calibrated_prob = sigmoid( (raw_logit / T) * a + b )

除温度 + Platt 外，本模块还负责 Fraser 2025 §6 的「低假阳阈值」：论文场景误伤真论文代价高，
在 human 验证集上搜索使 FPR ≤ 1% / 5% 的判定阈值随 checkpoint 一起落盘，
运行时按场景选用（默认 fpr_5pct，博士论文等高风险场景可切 fpr_1pct）。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit


@dataclass
class CalibrationParams:
    temperature: float = 1.0
    platt_a: float = 1.0
    platt_b: float = 0.0
    ece_before: float = 0.0
    ece_after: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _nll(probs: np.ndarray, labels: np.ndarray) -> float:
    p = np.clip(probs, 1e-7, 1 - 1e-7)
    return float(-np.mean(labels * np.log(p) + (1 - labels) * np.log(1 - p)))


def fit_temperature(logits: np.ndarray, labels: np.ndarray, max_iter: int = 200) -> float:
    """温度缩放（Guo 2017）：一维 L-BFGS 最小化 NLL，T 限制在 [0.05, 20]。"""
    logits = np.asarray(logits, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)

    def obj(t: np.ndarray) -> float:
        return _nll(expit(logits / max(float(t[0]), 1e-6)), labels)

    best = minimize(obj, x0=np.array([1.0]), bounds=[(0.05, 20.0)], method="L-BFGS-B", options={"maxiter": max_iter})
    return float(best.x[0])


def fit_platt(scaled_logits: np.ndarray, labels: np.ndarray, c: float = 1.0) -> tuple[float, float]:
    """Platt sigmoid：对已温度缩放的 logit 再拟合 a, b（带 L2 = 1/c 防过拟合小验证集）。"""
    x = np.asarray(scaled_logits, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    reg = 0.0 if c <= 0 else 1.0 / c

    def obj(p: np.ndarray) -> float:
        a, b = p
        return _nll(expit(a * x + b), y) + reg * 1e-3 * (a - 1.0) ** 2

    best = minimize(obj, x0=np.array([1.0, 0.0]), method="L-BFGS-B", bounds=[(0.05, 20.0), (-10.0, 10.0)])
    return float(best.x[0]), float(best.x[1])


def apply_calibration(logits: np.ndarray, params: CalibrationParams) -> np.ndarray:
    return expit((np.asarray(logits, dtype=np.float64) / max(params.temperature, 1e-6)) * params.platt_a + params.platt_b)


# ---------------------------------------------------------------------------
# 指标
# ---------------------------------------------------------------------------

def ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 15) -> float:
    """Expected Calibration Error（二分类，按预测 AI 概率分箱）。"""
    probs = np.asarray(probs, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(probs)
    if total == 0:
        return 0.0
    out = 0.0
    for i in range(n_bins):
        m = (probs > edges[i]) & (probs <= edges[i + 1])
        if m.any():
            out += m.sum() / total * abs(labels[m].mean() - probs[m].mean())
    return float(out)


def brier(probs: np.ndarray, labels: np.ndarray) -> float:
    return float(np.mean((np.asarray(probs, dtype=np.float64) - np.asarray(labels, dtype=np.float64)) ** 2))


def roc_curve(scores: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (fpr, tpr, thresholds)，阈值降序。不依赖 sklearn，评测镜像可瘦身。"""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(bool)
    order = np.argsort(-scores, kind="mergesort")
    s, y = scores[order], labels[order]
    n_pos = max(int(y.sum()), 1)
    n_neg = max(int((~y).sum()), 1)
    tps = np.cumsum(y)
    fps = np.cumsum(~y)
    # 相同分数合并
    distinct = np.r_[np.where(np.diff(s))[0], len(s) - 1]
    tpr = np.r_[0.0, tps[distinct] / n_pos]
    fpr = np.r_[0.0, fps[distinct] / n_neg]
    thr = np.r_[np.inf, s[distinct]]
    return fpr, tpr, thr


def auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    labels = np.asarray(labels)
    if labels.min() == labels.max():
        return float("nan")
    fpr, tpr, _ = roc_curve(scores, labels)
    return float(np.trapz(tpr, fpr))


def tpr_at_fpr(scores: np.ndarray, labels: np.ndarray, target_fpr: float = 0.01) -> tuple[float, float]:
    """返回 (TPR, 阈值)：在 FPR ≤ target 的最宽松阈值处的召回。"""
    fpr, tpr, thr = roc_curve(scores, labels)
    ok = np.where(fpr <= target_fpr)[0]
    if len(ok) == 0:
        return 0.0, float("inf")
    i = ok[-1]
    return float(tpr[i]), float(thr[i])


def find_thresholds(probs: np.ndarray, labels: np.ndarray, target_fprs=(0.01, 0.05)) -> dict[str, float]:
    """
    以校准概率为分数，产出多套判定阈值写入 checkpoint：
      - fpr_1pct / fpr_5pct：human 集假阳 ≤ 1% / 5%
      - youden：TPR - FPR 最大点
      - default_0_5：固定 0.5 参考
    """
    out: dict[str, float] = {"default_0_5": 0.5}
    fpr, tpr, thr = roc_curve(probs, labels)
    for t in target_fprs:
        _, th = tpr_at_fpr(probs, labels, t)
        key = f"fpr_{int(round(t * 100))}pct"
        out[key] = float(min(max(th, 0.0), 1.0)) if np.isfinite(th) else 1.0
    j = np.argmax(tpr - fpr)
    out["youden"] = float(min(max(thr[j], 0.0), 1.0)) if np.isfinite(thr[j]) else 0.5
    return out


def binary_metrics(probs: np.ndarray, labels: np.ndarray, threshold: float = 0.5) -> dict[str, float]:
    probs = np.asarray(probs, dtype=np.float64)
    labels = np.asarray(labels).astype(int)
    pred = (probs >= threshold).astype(int)
    tp = int(((pred == 1) & (labels == 1)).sum())
    fp = int(((pred == 1) & (labels == 0)).sum())
    fn = int(((pred == 0) & (labels == 1)).sum())
    tn = int(((pred == 0) & (labels == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": (tp + tn) / max(len(labels), 1),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


# ---------------------------------------------------------------------------
# 一站式
# ---------------------------------------------------------------------------

def calibrate(logits: np.ndarray, labels: np.ndarray, temperature_max_iter: int = 200,
              platt_c: float = 1.0) -> tuple[CalibrationParams, np.ndarray]:
    """在验证集 logits 上拟合 T → Platt，返回参数与校准后概率。"""
    logits = np.asarray(logits, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    ece_before = ece(expit(logits), labels)
    t = fit_temperature(logits, labels, max_iter=temperature_max_iter)
    a, b = fit_platt(logits / t, labels, c=platt_c)
    params = CalibrationParams(temperature=t, platt_a=a, platt_b=b, ece_before=ece_before)
    probs = apply_calibration(logits, params)
    params.ece_after = ece(probs, labels)
    return params, probs
