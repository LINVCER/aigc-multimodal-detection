"""
文本检测四路融合层

融合策略:
  - 统计特征分支 (可解释性强)
  - 深度学习分支 (RoBERTa v3)
  - MiMo 视觉语言模型 (Anthropic API)
  - DeepSeek 语言模型 (OpenAI API, logprobs)

动态权重: 若某分支不可用, 自动重新分配权重
"""

import math
from typing import Any

from app.detectors.base import DetectionOutput


class TextEnsemble:

    def __init__(
        self,
        stat_weight: float = 0.15,
        roberta_weight: float = 0.40,
        logprob_weight: float = 0.30,
        deepseek_weight: float = 0.15,
    ):
        self.stat_weight = stat_weight
        self.roberta_weight = roberta_weight
        self.logprob_weight = logprob_weight
        self.deepseek_weight = deepseek_weight

    def fuse(
        self,
        stat_output: DetectionOutput,
        roberta_output: DetectionOutput,
        logprob_output: DetectionOutput,
        deepseek_output: DetectionOutput | None = None,
    ) -> DetectionOutput:
        """融合四路检测结果"""

        branches: list[tuple[float, float, str, DetectionOutput]] = []

        if self.stat_weight > 0:
            branches.append((self.stat_weight, stat_output.logit, "statistical", stat_output))

        if self.roberta_weight > 0 and roberta_output.metadata.get("status") != "model_not_loaded":
            branches.append((self.roberta_weight, roberta_output.logit, "roberta", roberta_output))

        if self.logprob_weight > 0:
            branches.append((self.logprob_weight, logprob_output.logit, "mimo_vl", logprob_output))

        if self.deepseek_weight > 0 and deepseek_output is not None:
            ds_ok = deepseek_output.metadata.get("status") != "api_unavailable"
            if ds_ok:
                branches.append((self.deepseek_weight, deepseek_output.logit, "deepseek", deepseek_output))

        total_weight = sum(w for w, _, _, _ in branches)
        if total_weight == 0:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "all_branches_unavailable"},
            )

        normalized = [(w / total_weight, l, n, o) for w, l, n, o in branches]

        fused_logit = sum(w * l for w, l, _, _ in normalized)
        fused_prob = 1.0 / (1.0 + math.exp(-fused_logit))

        all_attributions: list[dict[str, Any]] = []
        explanation_parts = {}
        for _, _, name, output in normalized:
            for attr in output.model_attribution:
                all_attributions.append({**attr, "source": name})
            if output.explanation_data:
                explanation_parts[name] = output.explanation_data

        return DetectionOutput(
            is_ai_generated=fused_prob > 0.5,
            confidence=round(fused_prob, 4),
            logit=round(fused_logit, 6),
            model_attribution=all_attributions[:5],
            explanation_data={
                "branches": [
                    {"name": name, "weight": round(w, 3), "confidence": output.confidence}
                    for w, _, name, output in normalized
                ],
                "details": explanation_parts,
            },
            metadata={
                "fusion_method": "weighted_logit_average_4branch",
                "available_branches": len(branches),
                "branch_weights": {name: round(w, 3) for w, _, name, _ in normalized},
            },
        )

    def set_weights(self, stat: float, roberta: float, logprob: float, deepseek: float = 0.0):
        self.stat_weight = stat
        self.roberta_weight = roberta
        self.logprob_weight = logprob
        self.deepseek_weight = deepseek
