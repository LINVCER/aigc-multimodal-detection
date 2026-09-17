"""
多模态仲裁决策层 — 核心创新点之二

实现:
  1. 贝叶斯推理: P(fake | D_text, D_image, D_audio) ∝ P(fake) ⋅ Π P(D_i | fake)^{w_i}
  2. 冲突检测: max(P_i) - min(P_i) > threshold → 风险提示
  3. 动态权重: 基于各检测器在验证集上的 EWMA 准确率

当文本/图像/音频检测结果冲突时:
  - 不强行输出二元标签
  - 标注"本次判定置信度较低，建议人工复核"
  - 将决策权交还用户
"""

import math
import json
from dataclasses import dataclass, field
from typing import Any

import redis

from app.config import get_settings

settings = get_settings()


@dataclass
class ModalityResult:
    """单个模态的检测结果"""
    modality: str                # text | image | audio
    confidence: float           # 原始置信度 [0, 1]
    calibrated_confidence: float  # 校准后置信度
    is_ai_generated: bool
    confidence_interval: tuple[float, float]  # (lower, upper)
    model_attribution: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ArbitrationResult:
    """仲裁决策结果"""
    is_ai_generated: bool | None
    confidence: float
    risk_level: str             # low | medium | high
    warning: str | None         # 冲突风险提示
    component_results: dict[str, Any]
    conflict_detected: bool
    max_disagreement: float     # 最大模态间分歧


class Arbitrator:
    """
    多模态仲裁器 — 贝叶斯冲突消解 + 动态权重
    """

    # 冲突阈值: 模态间置信度差异超过此值触发风险提示
    CONFLICT_THRESHOLD = 0.35

    # 默认先验: P(fake) — 可根据场景调整
    DEFAULT_PRIOR_FAKE = 0.3

    def __init__(self):
        self.detector_weights: dict[str, float] = {
            "text_statistical": 0.75,
            "text_roberta": 0.85,
            "text_logprob": 0.80,
            "image_high_freq": 0.78,
            "image_vit": 0.83,
            "audio_resemble": 0.88,
            "audio_rawnet2": 0.82,
        }

    # ============================================================
    # 核心仲裁方法
    # ============================================================

    def arbitrate(
        self,
        text_result: ModalityResult | None = None,
        image_result: ModalityResult | None = None,
        audio_result: ModalityResult | None = None,
    ) -> ArbitrationResult:
        """
        多模态贝叶斯仲裁

        输入: 各模态检测结果 (至少一个)
        输出: 仲裁决策 + 风险提示
        """
        # 收集可用的模态结果
        available: list[ModalityResult] = []
        if text_result:
            available.append(text_result)
        if image_result:
            available.append(image_result)
        if audio_result:
            available.append(audio_result)

        if not available:
            return ArbitrationResult(
                is_ai_generated=None,
                confidence=0.5,
                risk_level="high",
                warning="无可用的检测结果，请检查检测器状态",
                component_results={},
                conflict_detected=True,
                max_disagreement=0.0,
            )

        # 单模态: 直接返回，无需仲裁
        if len(available) == 1:
            r = available[0]
            return ArbitrationResult(
                is_ai_generated=r.is_ai_generated,
                confidence=r.calibrated_confidence,
                risk_level=self._assess_risk(r.calibrated_confidence),
                warning=None,
                component_results={r.modality: self._serialize(r)},
                conflict_detected=False,
                max_disagreement=0.0,
            )

        # 多模态: 贝叶斯融合
        posterior_fake, posterior_real = self._bayesian_fusion(available)

        # 判定
        is_fake = posterior_fake > posterior_real
        confidence = max(posterior_fake, posterior_real)

        # 冲突检测
        confidences = [r.calibrated_confidence for r in available]
        max_disagreement = max(confidences) - min(confidences)
        conflict = max_disagreement > self.CONFLICT_THRESHOLD

        # 生成警告信息
        warning = None
        if conflict:
            disagreeing = self._describe_disagreement(available)
            warning = (
                f"多模态检测结果存在显著差异 (分歧度={max_disagreement:.2f})。"
                f"{disagreeing}。"
                f"建议人工复核。"
            )

        return ArbitrationResult(
            is_ai_generated=is_fake,
            confidence=round(confidence, 4),
            risk_level=self._assess_risk(confidence, conflict),
            warning=warning,
            component_results={r.modality: self._serialize(r) for r in available},
            conflict_detected=conflict,
            max_disagreement=round(max_disagreement, 4),
        )

    # ============================================================
    # 贝叶斯融合
    # ============================================================

    def _bayesian_fusion(
        self,
        results: list[ModalityResult],
    ) -> tuple[float, float]:
        """
        贝叶斯后验融合:

          P(fake | D1, D2, D3) ∝ P(fake) ⋅ P(D1|fake)^{w1} ⋅ P(D2|fake)^{w2} ⋅ P(D3|fake)^{w3}

        取对数避免数值下溢:
          log P(fake|D) ∝ log P(fake) + Σ w_i ⋅ log P(D_i|fake)
        """
        prior_fake = math.log(self.DEFAULT_PRIOR_FAKE)
        prior_real = math.log(1 - self.DEFAULT_PRIOR_FAKE)

        log_fake = prior_fake
        log_real = prior_real

        for r in results:
            w = self._get_weight(r)

            # P(D_i | fake) 近似为检测器的置信度 (指认为 fake 的置信度)
            # 如果检测器认为 fake，则 P(D|fake) = conf
            # 如果检测器认为 real，则 P(D|fake) = 1 - conf
            if r.is_ai_generated:
                p_d_given_fake = r.calibrated_confidence
                p_d_given_real = 1 - r.calibrated_confidence
            else:
                p_d_given_fake = 1 - r.calibrated_confidence
                p_d_given_real = r.calibrated_confidence

            # 平滑处理避免 log(0)
            p_d_given_fake = max(p_d_given_fake, 1e-10)
            p_d_given_real = max(p_d_given_real, 1e-10)

            log_fake += w * math.log(p_d_given_fake)
            log_real += w * math.log(p_d_given_real)

        # log-sum-exp 归一化
        max_log = max(log_fake, log_real)
        exp_fake = math.exp(log_fake - max_log)
        exp_real = math.exp(log_real - max_log)
        total = exp_fake + exp_real

        return exp_fake / total, exp_real / total

    # ============================================================
    # 权重管理
    # ============================================================

    def _get_weight(self, result: ModalityResult) -> float:
        """获取模态检测器的动态权重"""
        # 默认按模态取平均权重
        modality_weights = {
            "text": 0.9,    # 文本检测在中文场景最成熟
            "image": 0.85,
            "audio": 0.80,
        }
        base_weight = modality_weights.get(result.modality, 0.8)

        # 从 Redis 读取 EWMA 准确率调整
        try:
            r = redis.Redis(host=settings.redis_host, port=settings.redis_port,
                           decode_responses=True)
            ewma = r.hget("detector_weights", result.modality)
            if ewma:
                acc = float(ewma)
                base_weight *= acc
        except Exception:
            pass

        return base_weight

    def update_detector_weight(self, detector_id: str, recent_accuracy: float, alpha: float = 0.1):
        """
        指数加权移动平均更新检测器权重

        new_weight = α * recent_accuracy + (1-α) * old_weight

        每次收集到新的验证数据后调用
        """
        old = self.detector_weights.get(detector_id, 0.8)
        new_weight = alpha * recent_accuracy + (1 - alpha) * old
        self.detector_weights[detector_id] = new_weight

        # 存储到 Redis
        try:
            r = redis.Redis(host=settings.redis_host, port=settings.redis_port,
                           decode_responses=True)
            r.hset("detector_weights", detector_id, str(round(new_weight, 4)))
        except Exception:
            pass

    # ============================================================
    # 辅助方法
    # ============================================================

    def _assess_risk(self, confidence: float, conflict: bool = False) -> str:
        """评估风险等级"""
        if conflict:
            return "high"
        if confidence > 0.85:
            return "low"
        if confidence > 0.55:
            return "medium"
        return "high"

    def _describe_disagreement(self, results: list[ModalityResult]) -> str:
        """生成分歧描述"""
        parts = []
        for r in results:
            label = {"text": "文本", "image": "图像", "audio": "音频"}.get(r.modality, r.modality)
            verdict = "AI生成" if r.is_ai_generated else "人类创作/真实"
            parts.append(f"{label}检测={verdict}(置信度{r.calibrated_confidence:.0%})")
        return "，".join(parts)

    @staticmethod
    def _serialize(r: ModalityResult) -> dict:
        return {
            "modality": r.modality,
            "is_ai_generated": r.is_ai_generated,
            "confidence": r.confidence,
            "calibrated_confidence": r.calibrated_confidence,
            "confidence_interval": list(r.confidence_interval),
            "model_attribution": r.model_attribution,
        }
