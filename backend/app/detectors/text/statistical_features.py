"""
中文统计特征提取器 — 借鉴 lmscan 12 项特征设计，针对中文语境全面适配

特征列表:
  1. 字符级 n-gram 熵 (1-4 gram)
  2. 成语密度
  3. 标点间距方差
  4. 句长方差
  5. Burstiness (句子复杂度方差)
  6. Zipf 偏差
  7. 中文 Slop 词密度
  8. 标点熵
  9. 过渡词/关联词密度
  10. Bigram/Trigram 短语重复率
  11. Hapax Legomena 比率 (仅出现一次的词占比)
  12. 词汇丰富度 (Yule's K)
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# ============================================================
# 中文 Slop 词表 — AI 文本高频标志词
# ============================================================

CHINESE_SLOP_WORDS: dict[str, list[str]] = {
    "generic": [
        "值得注意的是", "总而言之", "综上所述", "在某种程度上",
        "不可否认", "从某种意义上说", "众所周知", "显而易见",
        "毋庸置疑", "毫无疑问",
    ],
    "gpt_like": [
        "值得注意的是", "总的来说", "关键的是",
        "重要的是要认识到", "从这个角度来看",
        "正如前面提到的", "需要指出的是", "在当今时代",
        "随着...的发展", "值得思考的是", "从更广的视角看",
    ],
    "claude_like": [
        "这是一个很好的问题", "让我来解释",
        "需要澄清的是",
    ],
    "wenyang_like": [
        "综上所述", "总而言之", "归根结底", "必须承认",
        "不言而喻", "众所周知", "毋庸置疑", "由此可见",
    ],
}

# 中文过渡词/关联词
CHINESE_TRANSITION_WORDS: list[str] = [
    "此外", "另外",
    "与此同时", "另一方面", "尽管如此",
    "从而", "进而", "加之", "何况", "再者",
    "总而言之", "综上所述", "归根结底",
]

# 中文标点集合
CHINESE_PUNCTUATION: set[str] = {
    "，", "。", "！", "？", "；", "：", "、",
    """, """, "（", "）", "【", "】", "《", "》",
    ",", ".", "!", "?", ";", ":", "'", '"',
}

# 常见成语结尾模式 (用于成语检测的辅助特征)
IDIOM_PATTERNS: list[str] = [
    # 四字格常见模式
    "然而", "如此", "之极", "不已", "无穷",
    "为贵", "至上", "之先",
]

# 英文 AI 标志词
ENGLISH_SLOP_WORDS: list[str] = [
    "notably", "furthermore", "moreover", "in conclusion",
    "it is worth noting", "it should be noted", "undoubtedly",
    "without a doubt", "first and foremost", "last but not least",
    "in today's world", "in recent years", "additionally",
    "consequently", "as a result", "nevertheless",
    "on the other hand", "in contrast", "similarly",
    "in other words", "to put it simply", "needless to say",
    "it goes without saying", "a crucial aspect", "a key factor",
    "plays a pivotal role", "has emerged as",
    "in the context of", "it is important to emphasize",
    "demonstrates the importance", "highlights the significance",
]

ENGLISH_TRANSITION_WORDS: list[str] = [
    "however", "therefore", "thus", "hence", "moreover",
    "furthermore", "additionally", "consequently", "accordingly",
    "nevertheless", "nonetheless", "meanwhile", "subsequently",
    "specifically", "notably", "particularly", "especially",
    "indeed", "in fact", "as a result", "in addition",
    "for instance", "for example", "in particular",
    "on the contrary", "in comparison", "alternatively",
]


@dataclass
class StatisticalFeatures:
    """12 项中文统计特征的完整输出"""

    # 1. n-gram 熵
    unigram_entropy: float = 0.0
    bigram_entropy: float = 0.0
    trigram_entropy: float = 0.0
    fourgram_entropy: float = 0.0

    # 2. 成语密度
    idiom_density: float = 0.0

    # 3. 标点间距
    punctuation_mean_spacing: float = 0.0
    punctuation_std_spacing: float = 0.0

    # 4. 句长方差
    sentence_length_mean: float = 0.0
    sentence_length_std: float = 0.0
    sentence_length_cv: float = 0.0  # 变异系数

    # 5. Burstiness
    burstiness: float = 0.0

    # 6. Zipf 偏差
    zipf_deviation: float = 0.0

    # 7. Slop 词密度
    slop_word_density: float = 0.0

    # 8. 标点熵
    punctuation_entropy: float = 0.0

    # 9. 过渡词密度
    transition_word_density: float = 0.0

    # 10. 短语重复
    bigram_repetition_rate: float = 0.0
    trigram_repetition_rate: float = 0.0

    # 11. Hapax Legomena
    hapax_ratio: float = 0.0

    # 12. 词汇丰富度
    yule_k: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "unigram_entropy": self.unigram_entropy,
            "bigram_entropy": self.bigram_entropy,
            "trigram_entropy": self.trigram_entropy,
            "fourgram_entropy": self.fourgram_entropy,
            "idiom_density": self.idiom_density,
            "punctuation_mean_spacing": self.punctuation_mean_spacing,
            "punctuation_std_spacing": self.punctuation_std_spacing,
            "sentence_length_mean": self.sentence_length_mean,
            "sentence_length_std": self.sentence_length_std,
            "sentence_length_cv": self.sentence_length_cv,
            "burstiness": self.burstiness,
            "zipf_deviation": self.zipf_deviation,
            "slop_word_density": self.slop_word_density,
            "punctuation_entropy": self.punctuation_entropy,
            "transition_word_density": self.transition_word_density,
            "bigram_repetition_rate": self.bigram_repetition_rate,
            "trigram_repetition_rate": self.trigram_repetition_rate,
            "hapax_ratio": self.hapax_ratio,
            "yule_k": self.yule_k,
        }


class ChineseStatisticalExtractor:
    """中文统计特征提取器"""

    def __init__(self):
        self._jieba_loaded = False
        self._jieba = None

    def _ensure_jieba(self):
        if not self._jieba_loaded:
            import jieba
            self._jieba = jieba
            self._jieba_loaded = True

    def extract(self, text: str) -> StatisticalFeatures:
        """提取全部 12 项特征 — 中英文自适应"""
        features = StatisticalFeatures()

        is_en = self._is_english(text)

        if is_en:
            self._extract_english(text, features)
        else:
            self._ensure_jieba()
            self._extract_chinese(text, features)

        return features

    def _extract_chinese(self, text: str, features):
        """中文特征提取"""
        sentences = self._split_sentences(text)
        words = list(self._jieba.cut(text))
        chars = list(text)

        features.unigram_entropy = self._compute_ngram_entropy(chars, 1)
        features.bigram_entropy = self._compute_ngram_entropy(chars, 2)
        features.trigram_entropy = self._compute_ngram_entropy(chars, 3)
        features.fourgram_entropy = self._compute_ngram_entropy(chars, 4)
        features.idiom_density = self._compute_idiom_density(words)

        punct_spacing = self._compute_punctuation_spacing(text)
        features.punctuation_mean_spacing = punct_spacing["mean"]
        features.punctuation_std_spacing = punct_spacing["std"]

        sent_stats = self._compute_sentence_length_stats(sentences)
        features.sentence_length_mean = sent_stats["mean"]
        features.sentence_length_std = sent_stats["std"]
        features.sentence_length_cv = sent_stats["cv"]

        features.burstiness = self._compute_burstiness(sentences)

        # 6. Zipf 偏差
        features.zipf_deviation = self._compute_zipf_deviation(words)
        # 7. Slop 词密度
        features.slop_word_density = self._compute_slop_word_density(text)
        # 8. 标点熵
        features.punctuation_entropy = self._compute_punctuation_entropy(text)
        # 9. 过渡词密度
        features.transition_word_density = self._compute_transition_word_density(text)
        # 10. 短语重复率
        features.bigram_repetition_rate = self._compute_ngram_repetition(words, 2)
        features.trigram_repetition_rate = self._compute_ngram_repetition(words, 3)
        # 11. Hapax 比率
        features.hapax_ratio = self._compute_hapax_ratio(words)
        # 12. Yule's K
        features.yule_k = self._compute_yule_k(words)

    def _extract_english(self, text: str, features):
        """英文特征提取"""
        sentences = self._split_sentences(text)
        words = text.lower().split()
        chars = list(text)

        features.unigram_entropy = self._compute_ngram_entropy(chars, 1)
        features.bigram_entropy = self._compute_ngram_entropy(chars, 2)
        features.trigram_entropy = self._compute_ngram_entropy(chars, 3)
        features.fourgram_entropy = 0.0
        features.idiom_density = 0.0

        punct_spacing = self._compute_punctuation_spacing(text)
        features.punctuation_mean_spacing = punct_spacing["mean"]
        features.punctuation_std_spacing = punct_spacing["std"]

        sent_stats = self._compute_sentence_length_stats(sentences)
        features.sentence_length_mean = sent_stats["mean"]
        features.sentence_length_std = sent_stats["std"]
        features.sentence_length_cv = sent_stats["cv"]

        features.burstiness = self._compute_burstiness_english(sentences)

        # 6. Zipf 偏差
        features.zipf_deviation = self._compute_zipf_deviation(words)

        # 7. Slop 词密度
        features.slop_word_density = self._compute_slop_word_density(text)

        # 8. 标点熵
        features.punctuation_entropy = self._compute_punctuation_entropy(text)

        # 9. 过渡词密度
        features.transition_word_density = self._compute_transition_word_density(text)

        # 10. 短语重复率
        features.bigram_repetition_rate = self._compute_ngram_repetition(words, 2)
        features.trigram_repetition_rate = self._compute_ngram_repetition(words, 3)

        # 11. Hapax 比率
        features.hapax_ratio = self._compute_hapax_ratio(words)

        # 12. Yule's K
        features.yule_k = self._compute_yule_k(words)

        return features

    # ---- 各特征计算方法 ----

    @staticmethod
    def _is_english(text: str) -> bool:
        """检测文本是否主要为英文"""
        alpha = sum(1 for c in text if c.isascii() and c.isalpha())
        cjk = sum(1 for c in text if '一' <= c <= '鿿' or '㐀' <= c <= '䶿')
        return alpha > cjk * 2 and alpha > 20

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """分句 — 中文 / 英文自适应"""
        if ChineseStatisticalExtractor._is_english(text):
            # English: split on . ! ? \n
            sentences = re.split(r"[.!?\n]+", text)
        else:
            # Chinese: split on 。！？!?\n
            sentences = re.split(r"[。！？!?\n]+", text)
        return [s.strip() for s in sentences if len(s.strip()) >= 2]

    @staticmethod
    def _compute_ngram_entropy(tokens: list[str], n: int) -> float:
        if len(tokens) < n:
            return 0.0
        grams = [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]
        counter = Counter(grams)
        total = sum(counter.values())
        entropy = 0.0
        for count in counter.values():
            p = count / total
            entropy -= p * math.log2(p)
        return round(entropy, 6)

    @staticmethod
    def _compute_idiom_density(words: list[str]) -> float:
        """
        成语密度 = 四字词数量 / 总词数
        AI 文本的成语密度往往异常高 (模型偏好使用四字格)
        """
        four_char_count = sum(1 for w in words if len(w) == 4 and all('一' <= c <= '鿿' for c in w))
        total = len(words) if words else 1
        return round(four_char_count / total, 6)

    @staticmethod
    def _compute_punctuation_spacing(text: str) -> dict[str, float]:
        positions = [i for i, ch in enumerate(text) if ch in CHINESE_PUNCTUATION]
        if len(positions) < 3:
            return {"mean": 0.0, "std": 0.0}
        spacings = [positions[i] - positions[i-1] for i in range(1, len(positions))]
        mean = sum(spacings) / len(spacings)
        variance = sum((s - mean)**2 for s in spacings) / len(spacings)
        return {"mean": round(mean, 2), "std": round(math.sqrt(variance), 2)}

    @staticmethod
    def _compute_sentence_length_stats(sentences: list[str]) -> dict[str, float]:
        if len(sentences) < 2:
            return {"mean": 0.0, "std": 0.0, "cv": 0.0}
        lengths = [len(s) for s in sentences]
        mean = sum(lengths) / len(lengths)
        variance = sum((l - mean)**2 for l in lengths) / len(lengths)
        std = math.sqrt(variance)
        cv = std / mean if mean > 0 else 0.0
        return {"mean": round(mean, 2), "std": round(std, 2), "cv": round(cv, 4)}

    def _compute_burstiness_english(self, sentences: list[str]) -> float:
        """英文 Burstiness — 基于词级复杂度"""
        if len(sentences) < 3:
            return 0.0
        complexities = []
        for s in sentences:
            words = s.strip().split()
            if len(words) < 2:
                continue
            unique = len(set(w.lower() for w in words))
            complexity = len(words) * (1 + math.log(unique + 1))
            complexities.append(complexity)
        if len(complexities) < 3:
            return 0.0
        mean_c = sum(complexities) / len(complexities)
        variance = sum((c - mean_c) ** 2 for c in complexities) / len(complexities)
        return round(math.sqrt(variance) / mean_c, 4) if mean_c > 0 else 0.0

    def _compute_burstiness(self, sentences: list[str]) -> float:
        """
        Burstiness = 句子复杂度方差
        句子复杂度 ≈ 句长 × log(独特词数 + 1)
        AI 文本的 burstiness 异常低 (句子复杂度过于均匀)
        """
        self._ensure_jieba()
        if len(sentences) < 3:
            return 0.0
        complexities = []
        for s in sentences:
            words = list(self._jieba.cut(s))
            unique = len(set(words))
            complexity = len(s) * math.log(unique + 1)
            complexities.append(complexity)
        mean = sum(complexities) / len(complexities)
        variance = sum((c - mean)**2 for c in complexities) / len(complexities)
        # 归一化: CV (变异系数)
        cv = math.sqrt(variance) / mean if mean > 0 else 0.0
        return round(cv, 6)

    @staticmethod
    def _compute_zipf_deviation(words: list[str]) -> float:
        """
        Zipf 偏差: 词频分布与理想 Zipf 分布 (rank ∝ 1/freq) 的拟合误差
        使用 KS-like 统计量: max|observed_cdf - zipf_cdf|
        """
        if len(words) < 20:
            return 0.0
        counter = Counter(words)
        freqs = sorted(counter.values(), reverse=True)
        total = sum(freqs)
        max_deviation = 0.0
        cumulative = 0.0
        for i, f in enumerate(freqs):
            cumulative += f / total
            # 理想 Zipf: 第 i 个词的累积概率
            harmonic = sum(1.0 / k for k in range(1, len(freqs) + 1))
            zipf_cumulative = sum(1.0 / (k * harmonic) for k in range(1, i + 2))
            deviation = abs(cumulative - zipf_cumulative)
            if deviation > max_deviation:
                max_deviation = deviation
        return round(max_deviation, 6)

    @staticmethod
    @staticmethod
    def _compute_slop_word_density(text: str) -> float:
        """Slop 词密度 — 中英文自适应"""
        is_en = ChineseStatisticalExtractor._is_english(text)
        if is_en:
            count = sum(text.lower().count(w) for w in ENGLISH_SLOP_WORDS)
        else:
            all_slop = set()
            for words in CHINESE_SLOP_WORDS.values():
                all_slop.update(words)
            count = 0
            for slop in all_slop:
                count += text.count(slop)
        return round(count / max(len(text), 1) * 100, 6)

    @staticmethod
    def _compute_punctuation_entropy(text: str) -> float:
        punct_counts = Counter(ch for ch in text if ch in CHINESE_PUNCTUATION)
        total = sum(punct_counts.values())
        if total == 0:
            return 0.0
        entropy = 0.0
        for count in punct_counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return round(entropy, 6)

    @staticmethod
    def _compute_transition_word_density(text: str) -> float:
        count = sum(text.count(w) for w in CHINESE_TRANSITION_WORDS)
        return round(count / max(len(text), 1) * 100, 6)

    @staticmethod
    def _compute_ngram_repetition(words: list[str], n: int) -> float:
        """n-gram 重复率"""
        if len(words) < n + 1:
            return 0.0
        grams = [tuple(words[i:i+n]) for i in range(len(words) - n + 1)]
        counter = Counter(grams)
        if len(counter) == 0:
            return 0.0
        total = sum(counter.values())
        repeated = sum(v for v in counter.values() if v > 1)
        return round(repeated / total, 4) if total > 0 else 0.0

    @staticmethod
    def _compute_hapax_ratio(words: list[str]) -> float:
        """
        Hapax Legomena 比率 = 仅出现一次的词 / 总词数
        AI 文本通常有更低的 hapax 比率 (更少创新用词)
        """
        if not words:
            return 0.0
        counter = Counter(words)
        hapax_count = sum(1 for v in counter.values() if v == 1)
        return round(hapax_count / len(counter), 6)

    @staticmethod
    def _compute_yule_k(words: list[str]) -> float:
        """
        Yule's K = 10^4 * (Σ i^2 * V_i - N) / N^2
        其中 V_i 为出现 i 次的词汇数，N 为总词数
        值越小表示词汇越丰富；AI 文本通常 Yule's K 更高 (词汇贫乏)
        """
        if not words:
            return 0.0
        N = len(words)
        counter = Counter(words)
        freq_of_freqs = Counter(counter.values())  # {出现次数: 词数}
        sum_i2_vi = sum(i * i * vi for i, vi in freq_of_freqs.items())
        yule = 10000 * (sum_i2_vi - N) / (N * N) if N > 1 else 0.0
        return round(yule, 6)
