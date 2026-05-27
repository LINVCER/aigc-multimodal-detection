"""
Image Fusion v2 — Sensitivity-Aware Weighted Fusion

Improvements over v1:
  - Configurable sensitivity parameter (0.0 ~ 1.0)
  - Adaptive threshold: lower = more aggressive AI detection
  - Logit bias: push fused output toward AI when sensitivity > 0
  - Confidence sharpening: amplify separation between AI/human
  - Branch disagreement handling: if branches disagree strongly, trust the stronger one

Sensitivity levels:
  0.0 = Conservative (threshold=0.5, no bias) — minimize false positives
  0.3 = Balanced      (threshold=0.44, mild bias)
  0.5 = Sensitive    (threshold=0.40, moderate bias) — recommended
  0.7 = Aggressive   (threshold=0.36, strong bias)
  1.0 = Maximum      (threshold=0.30, maximum bias) — catch everything
"""

import math
from app.detectors.base import DetectionOutput


class ImageFusion:
    """Image detection fusion with adjustable sensitivity"""

    def __init__(
        self,
        high_freq_weight: float = 0.30,
        vit_weight: float = 0.35,
        mimo_weight: float = 0.35,
        sensitivity: float = 0.25,
    ):
        self.high_freq_weight = high_freq_weight
        self.vit_weight = vit_weight
        self.mimo_weight = mimo_weight
        self.sensitivity = max(0.0, min(1.0, sensitivity))

    @property
    def decision_threshold(self) -> float:
        return 0.50 - self.sensitivity * 0.20

    @property
    def logit_bias(self) -> float:
        return self.sensitivity * 0.40

    def fuse(
        self,
        high_freq_output: DetectionOutput,
        vit_output: DetectionOutput,
        mimo_output: DetectionOutput | None = None,
    ) -> DetectionOutput:
        branches = []
        hf_available = high_freq_output.metadata.get("status") != "model_not_loaded"
        vit_available = vit_output.metadata.get("status") != "model_not_loaded"
        mimo_available = (
            mimo_output is not None
            and mimo_output.metadata.get("status") != "model_not_loaded"
        )

        if hf_available:
            branches.append((self.high_freq_weight, high_freq_output.logit, "high_freq", high_freq_output))
        if vit_available:
            branches.append((self.vit_weight, vit_output.logit, "vit", vit_output))
        if mimo_available:
            branches.append((self.mimo_weight, mimo_output.logit, "mimo_vl", mimo_output))

        if not branches:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "all_branches_unavailable"},
            )

        total_weight = sum(w for w, _, _, _ in branches)
        normalized = [(w / total_weight, l, n, o) for w, l, n, o in branches]

        confidences = [o.confidence for _, _, _, o in normalized]
        max_conf = max(confidences)
        min_conf = min(confidences)
        conf_spread = max_conf - min_conf

        if len(branches) >= 2 and conf_spread > 0.5:
            adaptive_weights = []
            for w, l, name, o in normalized:
                if o.confidence > 0.7 or o.confidence < 0.3:
                    adaptive_weights.append((w * 1.3, l, name, o))
                else:
                    adaptive_weights.append((w * 0.8, l, name, o))
            total_aw = sum(aw for aw, _, _, _ in adaptive_weights)
            normalized = [(aw / total_aw, l, n, o) for aw, l, n, o in adaptive_weights]

        fused_logit = sum(w * l for w, l, _, _ in normalized)
        fused_logit += self.logit_bias
        fused_prob = 1.0 / (1.0 + math.exp(-fused_logit))

        if self.sensitivity > 0.5:
            sharpen_factor = 1.0 + (self.sensitivity - 0.5) * 0.8
            fused_prob = pow(fused_prob, 1.0 / sharpen_factor)

        is_ai = fused_prob > self.decision_threshold

        return DetectionOutput(
            is_ai_generated=is_ai,
            confidence=round(fused_prob, 4),
            logit=round(fused_logit, 6),
            explanation_data={
                "branches": [
                    {"name": name, "weight": round(w, 3), "confidence": round(o.confidence, 4)}
                    for w, _, name, o in normalized
                ],
                "sensitivity": round(self.sensitivity, 2),
                "threshold_used": round(self.decision_threshold, 3),
                "logit_bias_applied": round(self.logit_bias, 3),
            },
            metadata={
                "fusion_method": "sensitive_weighted_fusion",
                "branch_weights": {name: round(w, 3) for w, _, name, _ in normalized},
                "max_branch_confidence": round(max_conf, 4),
                "min_branch_confidence": round(min_conf, 4),
                "confidence_spread": round(conf_spread, 4),
            },
        )

    def set_sensitivity(self, value: float):
        self.sensitivity = max(0.0, min(1.0, value))

    def set_weights(self, high_freq: float, vit: float, mimo: float = 0.25):
        self.high_freq_weight = high_freq
        self.vit_weight = vit
        self.mimo_weight = mimo
