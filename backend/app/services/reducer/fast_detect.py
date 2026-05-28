"""
快速统计检测 — 仅用统计特征分支，无模型推理，无 API 调用

用于降 AIGC 过程中的中间步骤回滚判断 (~5ms vs 全分支 ~2-5s)。
精度低于全 4 路融合，回滚阈值需收紧以补偿。
"""

import math
from app.detectors.base import DetectionOutput
from app.detectors.text.statistical_features import ChineseStatisticalExtractor

_extractor = ChineseStatisticalExtractor()

# 与 text_service._statistical_to_output 保持一致的 sigmoid 规则
_FEATURE_RULES = [
    # (feature_attr, midpoint, steepness, weight, direction)
    ("slop_word_density", 0.4, 5.0, 0.15, +1),
    ("transition_word_density", 0.3, 6.0, 0.10, +1),
    ("idiom_density", 0.05, 50.0, 0.08, +1),
    ("bigram_repetition_rate", 0.08, 20.0, 0.10, +1),
    ("sentence_length_cv", 0.4, 8.0, 0.12, -1),
    ("burstiness", 0.3, 8.0, 0.12, -1),
    ("punctuation_entropy", 2.0, 2.0, 0.08, -1),
    ("unigram_entropy", 6.0, 1.5, 0.08, -1),
    ("zipf_deviation", 0.08, 30.0, 0.05, +1),
    ("hapax_ratio", 0.4, 4.0, 0.06, -1),
    ("yule_k", 100.0, 0.01, 0.06, +1),
]


def detect_statistical_only(text: str) -> DetectionOutput:
    """纯统计特征检测 — ~5ms，用于降 AIGC 中间步骤的快速回滚判断"""
    features = _extractor.extract(text)

    total_signal = 0.0
    total_weight = 0.0

    for attr, mid, steep, weight, direction in _FEATURE_RULES:
        value = getattr(features, attr, 0.0)
        if value == 0.0:
            continue
        z = steep * (value - mid)
        signal = 1.0 / (1.0 + math.exp(-z))
        if direction < 0:
            signal = 1.0 - signal
        total_signal += weight * signal
        total_weight += weight

    final_score = total_signal / total_weight if total_weight > 0 else 0.5
    # 与 text_service 一致的宽松决策
    final_score = 0.5 + (final_score - 0.5) * 0.6
    logit = math.log(final_score / (1 - final_score)) if 0 < final_score < 1 else 0.0

    return DetectionOutput(
        is_ai_generated=final_score > 0.5,
        confidence=round(final_score, 4),
        logit=round(logit, 6),
        explanation_data={},
        metadata={"method": "fast_statistical_only"},
    )
