"""
中文字符级 n-gram 提取工具
借鉴 lmscan 的统计特征设计，针对中文无空格特性适配
"""

from collections import Counter
from typing import Any


def extract_char_ngrams(
    text: str, n_range: tuple[int, int] = (1, 4)
) -> dict[int, list[tuple[str, int]]]:
    """
    提取字符级 n-gram 频率分布
    中文以字符为单位，不做分词即可提取 n-gram
    返回 {n: [(gram, count), ...]}
    """
    result: dict[int, Counter] = {}
    for n in range(n_range[0], n_range[1] + 1):
        grams = [text[i : i + n] for i in range(len(text) - n + 1)]
        result[n] = Counter(grams)
    return {
        n: counter.most_common(50) for n, counter in result.items()
    }


def compute_ngram_entropy(text: str, n: int = 3) -> float:
    """计算 n-gram 的香农熵 — AI 文本通常熵值更低"""
    import math

    if len(text) < n:
        return 0.0

    grams = [text[i : i + n] for i in range(len(text) - n + 1)]
    counter = Counter(grams)
    total = sum(counter.values())
    entropy = 0.0
    for count in counter.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def compute_punctuation_spacing(text: str) -> dict[str, Any]:
    """
    标点间距统计 — 中文特有特征
    AI 文本在标点使用上往往更有规律，间距方差较小
    """
    import re

    punctuation_positions = [i for i, ch in enumerate(text) if ch in "，。！？；：、"",.?!;:""''"]
    if len(punctuation_positions) < 3:
        return {"mean_spacing": 0, "std_spacing": 0, "count": len(punctuation_positions)}

    spacings = [
        punctuation_positions[i] - punctuation_positions[i - 1]
        for i in range(1, len(punctuation_positions))
    ]
    mean_s = sum(spacings) / len(spacings)
    variance = sum((s - mean_s) ** 2 for s in spacings) / len(spacings)
    return {
        "mean_spacing": round(mean_s, 2),
        "std_spacing": round(variance**0.5, 2),
        "count": len(punctuation_positions),
    }
