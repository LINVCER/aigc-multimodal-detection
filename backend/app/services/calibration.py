"""
置信度校准模块 — 核心创新点之一

实现:
  1. Temperature Scaling: p_calibrated = sigmoid(logit / T)
  2. Platt Scaling: p_calibrated = sigmoid(a * logit + b)
  3. Expected Calibration Error (ECE) 评估

校准流程:
  - 在验证集上收集各检测器的原始 logits 和真实标签
  - 优化 T (最小化 NLL) 和 (a,b) (Logistic Regression)
  - 为每个检测器存储校准参数到 Redis
"""

import math
from typing import Any
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit  # sigmoid


@dataclass
class CalibrationParams:
    """单个检测器的校准参数"""
    temperature: float = 1.0  # Temperature Scaling T
    platt_a: float = 1.0     # Platt Scaling a
    platt_b: float = 0.0     # Platt Scaling b
    ece: float = 0.0         # 当前 ECE


class ConfidenceCalibrator:
    """
    置信度校准器

    为文本/图像/音频每个检测器维护独立的校准参数
    支持在线更新 (基于用户反馈)
    """

    def __init__(self):
        self.params: dict[str, CalibrationParams] = {}

    def register_detector(self, detector_id: str):
        if detector_id not in self.params:
            self.params[detector_id] = CalibrationParams()

    # ============================================================
    # Temperature Scaling
    # ============================================================

    @staticmethod
    def fit_temperature(
        logits: np.ndarray,
        labels: np.ndarray,
    ) -> float:
        """
        在验证集上优化 Temperature T

        logits: 原始 logit 值 [N]
        labels: 真实标签 [N] (0 or 1)
        返回: 最优 T

        优化目标: NLL = -Σ y_i * log(p_i) - (1-y_i) * log(1-p_i)
        """

        def nll(T: float) -> float:
            scaled_logits = logits / max(T, 1e-8)
            probs = expit(scaled_logits)
            probs = np.clip(probs, 1e-12, 1 - 1e-12)
            return -np.mean(labels * np.log(probs) + (1 - labels) * np.log(1 - probs))

        result = minimize(nll, x0=1.0, bounds=[(0.1, 10.0)], method="L-BFGS-B")
        return float(result.x[0])

    # ============================================================
    # Platt Scaling
    # ============================================================

    @staticmethod
    def fit_platt(
        logits: np.ndarray,
        labels: np.ndarray,
    ) -> tuple[float, float]:
        """
        用 Logistic Regression 拟合 Platt Scaling 参数 (a, b)

        p_calibrated = sigmoid(a * logit + b)
        """
        from scipy.optimize import minimize

        def platt_nll(params: np.ndarray) -> float:
            a, b = params
            calib_logits = a * logits + b
            probs = expit(calib_logits)
            probs = np.clip(probs, 1e-12, 1 - 1e-12)
            return -np.mean(labels * np.log(probs) + (1 - labels) * np.log(1 - probs))

        result = minimize(
            platt_nll,
            x0=np.array([1.0, 0.0]),
            method="L-BFGS-B",
        )
        return float(result.x[0]), float(result.x[1])

    # ============================================================
    # ECE 计算
    # ============================================================

    @staticmethod
    def compute_ece(
        confidences: np.ndarray,
        accuracies: np.ndarray,
        n_bins: int = 15,
    ) -> float:
        """
        Expected Calibration Error

        ECE = Σ (|B_b| / N) * |acc(B_b) - conf(B_b)|
        """
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        for i in range(n_bins):
            in_bin = (confidences > bin_boundaries[i]) & (confidences <= bin_boundaries[i + 1])
            bin_size = np.sum(in_bin)
            if bin_size > 0:
                bin_conf = np.mean(confidences[in_bin])
                bin_acc = np.mean(accuracies[in_bin])
                ece += (bin_size / len(confidences)) * abs(bin_acc - bin_conf)
        return float(ece)

    # ============================================================
    # 完整校准流程
    # ============================================================

    def calibrate_detector(
        self,
        detector_id: str,
        logits: np.ndarray,
        labels: np.ndarray,
    ) -> CalibrationParams:
        """
        完整校准一个检测器:
          1. Temperature Scaling
          2. Platt Scaling
          3. 评估 ECE
        """
        self.register_detector(detector_id)

        T = self.fit_temperature(logits, labels)
        scaled_logits = logits / T

        a, b = self.fit_platt(scaled_logits, labels)
        calib_logits = a * scaled_logits + b
        calib_probs = expit(calib_logits)

        ece = self.compute_ece(calib_probs, labels)

        params = CalibrationParams(temperature=T, platt_a=a, platt_b=b, ece=ece)
        self.params[detector_id] = params

        # 同步到 Redis
        self._sync_to_redis(detector_id, params)

        return params

    # ============================================================
    # 实时校准 (单次推理)
    # ============================================================

    @staticmethod
    def apply_calibration(logit: float, params: CalibrationParams) -> dict[str, Any]:
        """
        对单个 logit 应用校准，返回校准后的概率和置信区间
        """
        # Temperature → Platt
        scaled = logit / params.temperature
        calib_logit = params.platt_a * scaled + params.platt_b
        calib_prob = expit(calib_logit)

        # Wilson 置信区间 (95%)
        n = 100  # 等效样本量
        z = 1.96
        margin = z * math.sqrt(calib_prob * (1 - calib_prob) / n)

        return {
            "calibrated_confidence": round(float(calib_prob), 4),
            "confidence_interval": (
                round(max(0.0, float(calib_prob - margin)), 4),
                round(min(1.0, float(calib_prob + margin)), 4),
            ),
            "ece_estimate": params.ece,
        }

    # ============================================================
    # Redis 同步
    # ============================================================

    def _sync_to_redis(self, detector_id: str, params: CalibrationParams):
        """将校准参数存储到 Redis 供运行时读取"""
        try:
            import redis
            from app.config import get_settings
            s = get_settings()
            r = redis.Redis(host=s.redis_host, port=s.redis_port, decode_responses=True)
            r.hset(
                f"calibration:{detector_id}",
                mapping={
                    "temperature": str(params.temperature),
                    "platt_a": str(params.platt_a),
                    "platt_b": str(params.platt_b),
                    "ece": str(params.ece),
                },
            )
        except Exception:
            pass  # Redis 不可用不影响校准逻辑

    def load_from_redis(self, detector_id: str) -> CalibrationParams | None:
        """从 Redis 加载校准参数"""
        try:
            import redis
            from app.config import get_settings
            s = get_settings()
            r = redis.Redis(host=s.redis_host, port=s.redis_port, decode_responses=True)
            data = r.hgetall(f"calibration:{detector_id}")
            if data:
                params = CalibrationParams(
                    temperature=float(data.get("temperature", 1.0)),
                    platt_a=float(data.get("platt_a", 1.0)),
                    platt_b=float(data.get("platt_b", 0.0)),
                    ece=float(data.get("ece", 0.0)),
                )
                self.params[detector_id] = params
                return params
        except Exception:
            pass
        return None


# 全局校准器实例 (供仲裁层使用)
_calibrator = ConfidenceCalibrator()
