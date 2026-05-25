"""
文本检测三路融合层

融合策略:
  - 统计特征分支 (可解释性强, 权重 ~0.2)
  - 深度学习分支 (准确率高, 权重 ~0.5)
  - LLM logprob 分支 (溯源能力强, 权重 ~0.3)

动态权重: 若某分支不可用 (如 API 故障), 自动重新分配权重
"""

import math
from typing import Any

from app.detectors.base import DetectionOutput


class TextEnsemble:
    """
    文本检测融合器 — 将三路输出融合为统一结果

    融合方法: 加权平均 (logit 空间)
      final_logit = Σ w_i * logit_i
      final_prob = sigmoid(final_logit)
    """

    def __init__(
        self,
        stat_weight: float = 0.2,
        roberta_weight: float = 0.5,
        logprob_weight: float = 0.3,
    ):
        self.stat_weight = stat_weight
        self.roberta_weight = roberta_weight
        self.logprob_weight = logprob_weight

    def fuse(
        self,
        stat_output: DetectionOutput,
        roberta_output: DetectionOutput,
        logprob_output: DetectionOutput,
    ) -> DetectionOutput:
        """融合三路检测结果"""

        # 收集各分支的 logit 和可用性
        branches: list[tuple[float, float, str, DetectionOutput]] = []

        # 统计特征分支
        if self.stat_weight > 0:
            branches.append((self.stat_weight, stat_output.logit, "statistical", stat_output))

        # RoBERTa 分支
        if self.roberta_weight > 0 and roberta_output.metadata.get("status") != "model_not_loaded":
            branches.append((self.roberta_weight, roberta_output.logit, "roberta", roberta_output))
        elif roberta_output.metadata.get("status") == "model_not_loaded":
            pass  # 模型未加载，跳过此分支

        # LLM logprob 分支
        if self.logprob_weight > 0:
            branches.append((self.logprob_weight, logprob_output.logit, "logprob", logprob_output))

        # 动态重分配权重
        total_weight = sum(w for w, _, _, _ in branches)
        if total_weight == 0:
            return DetectionOutput(
                is_ai_generated=False,
                confidence=0.5,
                logit=0.0,
                metadata={"status": "all_branches_unavailable"},
            )

        normalized = [(w / total_weight, l, n, o) for w, l, n, o in branches]

        # 加权融合 (logit 空间)
        fused_logit = sum(w * l for w, l, _, _ in normalized)
        fused_prob = 1.0 / (1.0 + math.exp(-fused_logit))

        # 收集溯源信息
        all_attributions: list[dict[str, Any]] = []
        for _, _, name, output in normalized:
            for attr in output.model_attribution:
                all_attributions.append({**attr, "source": name})

        # 收集解释数据
        explanation_parts = {}
        for _, _, name, output in normalized:
            if output.explanation_data:
                explanation_parts[name] = output.explanation_data

        return DetectionOutput(
            is_ai_generated=fused_prob > 0.5,
            confidence=round(fused_prob, 4),
            logit=round(fused_logit, 6),
            model_attribution=all_attributions[:5],  # Top-5
            explanation_data={
                "branches": [
                    {"name": name, "weight": round(w, 3), "confidence": output.confidence}
                    for w, _, name, output in normalized
                ],
                "details": explanation_parts,
            },
            metadata={
                "fusion_method": "weighted_logit_average",
                "available_branches": len(branches),
                "branch_weights": {name: round(w, 3) for w, _, name, _ in normalized},
            },
        )

    def set_weights(self, stat: float, roberta: float, logprob: float):
        """动态调整权重 (供仲裁层调用)"""
        self.stat_weight = stat
        self.roberta_weight = roberta
        self.logprob_weight = logprob
