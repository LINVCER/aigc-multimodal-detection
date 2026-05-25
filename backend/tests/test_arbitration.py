"""
仲裁决策层和置信度校准单元测试
"""

import pytest
import numpy as np
from app.services.arbitration import Arbitrator, ModalityResult, ArbitrationResult
from app.services.calibration import ConfidenceCalibrator


class TestConfidenceCalibrator:
    """置信度校准测试"""

    def test_fit_temperature(self):
        """Temperature Scaling 基本测试"""
        calibrator = ConfidenceCalibrator()
        logits = np.array([2.0, 1.0, 0.0, -1.0, -2.0])
        labels = np.array([1, 1, 0, 0, 0])
        T = calibrator.fit_temperature(logits, labels)
        assert 0.1 <= T <= 10.0

    def test_fit_platt(self):
        """Platt Scaling 基本测试"""
        calibrator = ConfidenceCalibrator()
        logits = np.array([2.0, 1.0, 0.0, -1.0, -2.0])
        labels = np.array([1, 1, 0, 0, 0])
        a, b = calibrator.fit_platt(logits, labels)
        assert a > 0  # 单调递增

    def test_compute_ece(self):
        """ECE 计算"""
        calibrator = ConfidenceCalibrator()
        # 完美校准: confidence = accuracy
        confidences = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        accuracies = np.array([1, 1, 1, 0, 0])
        ece = calibrator.compute_ece(confidences, accuracies, n_bins=5)
        assert ece >= 0.0

    def test_apply_calibration(self):
        """校准应用"""
        from app.services.calibration import CalibrationParams
        params = CalibrationParams(temperature=2.0, platt_a=1.5, platt_b=-0.2)
        result = ConfidenceCalibrator.apply_calibration(1.0, params)
        assert "calibrated_confidence" in result
        assert "confidence_interval" in result
        assert 0 <= result["calibrated_confidence"] <= 1


class TestArbitrator:
    """仲裁决策层测试"""

    def test_single_modality(self):
        """单模态直接返回，不需要仲裁"""
        arb = Arbitrator()
        text = ModalityResult(
            modality="text",
            confidence=0.85,
            calibrated_confidence=0.82,
            is_ai_generated=True,
            confidence_interval=(0.75, 0.89),
        )
        result = arb.arbitrate(text_result=text)
        assert result.is_ai_generated is True
        assert result.conflict_detected is False

    def test_no_disagreement(self):
        """模态一致时不应检测到冲突"""
        arb = Arbitrator()
        text = ModalityResult("text", 0.88, 0.85, True, (0.78, 0.90))
        image = ModalityResult("image", 0.82, 0.80, True, (0.72, 0.87))
        result = arb.arbitrate(text_result=text, image_result=image)
        assert result.conflict_detected is False
        assert result.warning is None

    def test_conflict_detection(self):
        """模态冲突时应触发警告"""
        arb = Arbitrator()
        text = ModalityResult("text", 0.90, 0.88, True, (0.82, 0.93))
        image = ModalityResult("image", 0.15, 0.12, False, (0.05, 0.20))
        result = arb.arbitrate(text_result=text, image_result=image)
        assert result.conflict_detected is True
        assert result.warning is not None
        assert "人工复核" in result.warning

    def test_weight_update(self):
        """动态权重更新"""
        arb = Arbitrator()
        old_weight = arb.detector_weights["text_roberta"]
        arb.update_detector_weight("text_roberta", 0.90)
        new_weight = arb.detector_weights["text_roberta"]
        # EWMA: 0.1 * 0.90 + 0.9 * old
        expected = 0.1 * 0.90 + 0.9 * old_weight
        assert abs(new_weight - expected) < 0.0001

    def test_three_modality_fusion(self):
        """三模态贝叶斯融合"""
        arb = Arbitrator()
        text = ModalityResult("text", 0.88, 0.85, True, (0.78, 0.90))
        image = ModalityResult("image", 0.75, 0.72, True, (0.65, 0.79))
        audio = ModalityResult("audio", 0.20, 0.18, False, (0.10, 0.28))
        result = arb.arbitrate(text_result=text, image_result=image, audio_result=audio)
        assert result.confidence > 0
        assert result.risk_level in ("low", "medium", "high")
        assert "text" in result.component_results
