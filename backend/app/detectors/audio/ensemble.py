"""
音频检测三路融合

Wav2Vec2 XLS-R (主力本地) + MiMo AI模型 (在线) + RawNet2 (本地兜底)

策略:
  API 可用: Wav2Vec2 0.50 | MiMo 0.35 | RawNet2 0.15
  API 不可用: Wav2Vec2 0.75 | RawNet2 0.25
"""

import math
from app.detectors.base import DetectionOutput


class AudioEnsemble:
    """音频检测融合器 — 三路加权"""

    def __init__(self):
        pass

    def fuse(
        self,
        wav2vec2_output: DetectionOutput | None = None,
        resemble_output: DetectionOutput | None = None,
        rawnet2_output: DetectionOutput | None = None,
    ) -> DetectionOutput:
        branches = []

        # Wav2Vec2 (CPU不可靠，跳过)
        w2v_alive = False

        # MiMo API (声学特征不够可靠，仅辅助)
        api_available = (
            resemble_output
            and resemble_output.metadata.get("status") != "api_unavailable"
        )
        if api_available and w2v_alive:
            branches.append((0.25, resemble_output.logit, "mimo_audio_analysis", resemble_output))

        # RawNet2 (主力，Wav2Vec2死后独占)
        rn2_ok = rawnet2_output and rawnet2_output.metadata.get("status") != "preprocessing_error"
        if rn2_ok and w2v_alive:
            branches.append((0.25, rawnet2_output.logit, "rawnet2", rawnet2_output))
        elif rn2_ok:
            branches.append((1.0, rawnet2_output.logit, "rawnet2", rawnet2_output))

        if not branches:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "all_branches_unavailable"},
            )

        # 动态重分配权重
        total_weight = sum(w for w, _, _, _ in branches)
        normalized = [(w / total_weight, l, n, o) for w, l, n, o in branches]

        fused_logit = sum(w * l for w, l, _, _ in normalized)
        fused_prob = 1.0 / (1.0 + math.exp(-fused_logit))
        is_ai = fused_prob > 0.55

        return DetectionOutput(
            is_ai_generated=is_ai,
            confidence=round(fused_prob, 4),
            logit=round(fused_logit, 6),
            explanation_data={
                "branches": [
                    {"name": name, "weight": round(w, 3), "confidence": output.confidence}
                    for w, _, name, output in normalized
                ],
                "fusion_method": "weighted_logit_average",
            },
            metadata={
                "api_available": api_available,
                "num_branches": len(branches),
                "verdict": "AI合成" if is_ai else "真实语音",
            },
        )
