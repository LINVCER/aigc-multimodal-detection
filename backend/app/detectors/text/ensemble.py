"""
文本检测四路融合层

融合策略:
  - 统计特征分支 (可解释性强)
  - 深度学习分支 (RoBERTa v3)
  - MiMo 视觉语言模型 (Anthropic API)
  - DeepSeek 语言模型 (OpenAI API, logprobs)

置信度加权: 每路分支根据自身输出的确定性计算 reliability，
融合权重 = base_weight × reliability，避免低确定性分支稀释强信号。
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

    @staticmethod
    def _compute_branch_reliability(name: str, output: DetectionOutput) -> float:
        """计算单分支的自可靠性，clamp 到 [0.3, 1.0]"""
        if name == "statistical":
            # 距离 0.5 越远越确定
            r = 1.0 - 2.0 * abs(output.confidence - 0.5)
        elif name == "roberta":
            # logit 绝对值越大越确定; logit=3 ≈ 95%
            r = min(abs(output.logit) / 3.0, 1.0)
            # 分块方差惩罚: 高方差表示各块不一致，降低可靠性
            variance = output.metadata.get("score_variance")
            if variance is not None:
                r *= max(0.3, 1.0 - variance * 2.0)
        elif name in ("mimo_vl", "deepseek"):
            # 用 yes/no logprob 的边际衡量确定性
            margin = output.metadata.get("margin")
            if margin is not None:
                r = min(margin / 5.0, 1.0)
            else:
                # Anthropic 路径无原始 logprob，用 confidence 距离 0.5 衡量
                r = 1.0 - 2.0 * abs(output.confidence - 0.5)
        else:
            r = 0.5
        return max(0.3, min(1.0, r))

    def fuse(
        self,
        stat_output: DetectionOutput,
        roberta_output: DetectionOutput,
        logprob_output: DetectionOutput,
        deepseek_output: DetectionOutput | None = None,
    ) -> DetectionOutput:
        """融合四路检测结果（置信度加权）"""

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

        # 置信度加权: base_weight × reliability
        adjusted = []
        for w, l, name, output in branches:
            reliability = self._compute_branch_reliability(name, output)
            adjusted.append((w * reliability, l, name, output, reliability))
        total_adjusted = sum(aw for aw, _, _, _, _ in adjusted)
        normalized = [(aw / total_adjusted, l, n, o, r) for aw, l, n, o, r in adjusted]

        fused_logit = sum(w * l for w, l, _, _, _ in normalized)
        fused_prob = 1.0 / (1.0 + math.exp(-fused_logit))

        # 分支分歧检测: 各分支概率 std > 0.25 时标记
        branch_probs = []
        for _, l, _, _, _ in normalized:
            bp = 1.0 / (1.0 + math.exp(-l))
            branch_probs.append(bp)
        prob_std = (sum((p - fused_prob) ** 2 for p in branch_probs) / len(branch_probs)) ** 0.5
        high_disagreement = prob_std > 0.25

        all_attributions: list[dict[str, Any]] = []
        explanation_parts = {}
        for _, _, name, output, _ in normalized:
            for attr in output.model_attribution:
                all_attributions.append({**attr, "source": name})
            if output.explanation_data:
                explanation_parts[name] = output.explanation_data

        meta = {
            "fusion_method": "confidence_weighted_logit_average",
            "available_branches": len(branches),
            "branch_weights": {name: round(w, 3) for w, _, name, _, _ in normalized},
            "branch_reliability": {name: round(r, 3) for _, _, name, _, r in normalized},
        }
        if high_disagreement:
            meta["high_disagreement"] = True
            meta["branch_probability_std"] = round(prob_std, 4)

        # 分歧时加宽置信区间
        ci_half = 0.25 if high_disagreement else 0.15
        ci = (max(0.01, fused_prob - ci_half), min(0.99, fused_prob + ci_half))

        return DetectionOutput(
            is_ai_generated=fused_prob > 0.5,
            confidence=round(fused_prob, 4),
            logit=round(fused_logit, 6),
            confidence_interval=ci,
            model_attribution=all_attributions[:5],
            explanation_data={
                "branches": [
                    {
                        "name": name,
                        "weight": round(w, 3),
                        "reliability": round(r, 3),
                        "confidence": output.confidence,
                    }
                    for w, _, name, output, r in normalized
                ],
                "details": explanation_parts,
            },
            metadata=meta,
        )

    def set_weights(self, stat: float, roberta: float, logprob: float, deepseek: float = 0.0):
        self.stat_weight = stat
        self.roberta_weight = roberta
        self.logprob_weight = logprob
        self.deepseek_weight = deepseek
