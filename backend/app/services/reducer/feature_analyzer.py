"""特征差距分析器 — 识别哪些统计特征贡献了最高的 AI 分"""

import math
from dataclasses import dataclass


@dataclass
class FeatureGap:
    feature_name: str
    current_value: float
    midpoint: float
    weight: float
    direction: int  # +1=高值→AI, -1=低值→AI
    ai_contribution: float  # 0.0=人类, 1.0=AI
    priority: float  # ai_contribution * weight
    suggestion: str


# 与 text_service._statistical_to_output 完全一致的特征规则
FEATURE_RULES = {
    "slop_word_density":      {"midpoint": 0.4,  "steepness": 5.0,  "weight": 0.15, "direction": +1},
    "transition_word_density": {"midpoint": 0.3,  "steepness": 6.0,  "weight": 0.10, "direction": +1},
    "idiom_density":          {"midpoint": 0.05, "steepness": 50.0, "weight": 0.08, "direction": +1},
    "bigram_repetition_rate": {"midpoint": 0.08, "steepness": 20.0, "weight": 0.10, "direction": +1},
    "sentence_length_cv":     {"midpoint": 0.4,  "steepness": 8.0,  "weight": 0.12, "direction": -1},
    "burstiness":             {"midpoint": 0.3,  "steepness": 8.0,  "weight": 0.12, "direction": -1},
    "punctuation_entropy":    {"midpoint": 2.0,  "steepness": 2.0,  "weight": 0.08, "direction": -1},
    "unigram_entropy":        {"midpoint": 6.0,  "steepness": 1.5,  "weight": 0.08, "direction": -1},
    "zipf_deviation":         {"midpoint": 0.08, "steepness": 30.0, "weight": 0.05, "direction": +1},
    "hapax_ratio":            {"midpoint": 0.4,  "steepness": 4.0,  "weight": 0.06, "direction": -1},
    "yule_k":                 {"midpoint": 100.0,"steepness": 0.01, "weight": 0.06, "direction": +1},
}

SUGGESTIONS = {
    "slop_word_density": "删除AI标志词（值得注意的是、综上所述、毫无疑问等）",
    "transition_word_density": "减少过渡词（此外、因此、然而），改用隐式逻辑连接",
    "idiom_density": "减少四字成语的密集使用，用更口语化的表达",
    "bigram_repetition_rate": "避免重复使用相同的词组搭配",
    "sentence_length_cv": "增加句长变化，混合短句和长句",
    "burstiness": "增加句子复杂度变化，插入短促有力的句子",
    "punctuation_entropy": "丰富标点使用，不要只用逗号和句号",
    "unigram_entropy": "增加用字多样性，避免重复用词",
    "zipf_deviation": "让词频分布更接近自然语言的 Zipf 分布",
    "hapax_ratio": "增加只出现一次的词汇比例",
    "yule_k": "降低词汇集中度，使用更多样化的词汇",
}


def compute_ai_contribution(value: float, midpoint: float, steepness: float, direction: int) -> float:
    """计算单个特征的 AI 贡献度（与 _statistical_to_output 相同的 sigmoid 映射）"""
    z = steepness * (value - midpoint)
    signal = 1.0 / (1.0 + math.exp(-z))
    if direction < 0:
        signal = 1.0 - signal
    return signal


def analyze_features(features_dict: dict) -> list[FeatureGap]:
    """分析特征差距，返回按优先级排序的 FeatureGap 列表"""
    gaps = []

    for name, rule in FEATURE_RULES.items():
        value = features_dict.get(name, 0.0)
        if value == 0.0 and name not in ("slop_word_density", "transition_word_density"):
            continue

        ai_contrib = compute_ai_contribution(
            value, rule["midpoint"], rule["steepness"], rule["direction"]
        )
        priority = ai_contrib * rule["weight"]

        gaps.append(FeatureGap(
            feature_name=name,
            current_value=value,
            midpoint=rule["midpoint"],
            weight=rule["weight"],
            direction=rule["direction"],
            ai_contribution=round(ai_contrib, 4),
            priority=round(priority, 4),
            suggestion=SUGGESTIONS.get(name, ""),
        ))

    gaps.sort(key=lambda g: g.priority, reverse=True)
    return gaps
