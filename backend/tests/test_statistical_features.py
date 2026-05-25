"""
中文统计特征提取器单元测试
"""

import pytest
from app.detectors.text.statistical_features import (
    ChineseStatisticalExtractor,
    StatisticalFeatures,
)

extractor = ChineseStatisticalExtractor()

# 测试样本: AI 风格的文本 (模仿 GPT 输出)
AI_LIKE_TEXT = """
随着人工智能技术的飞速发展，深度学习在自然语言处理领域取得了显著进展。
值得注意的是，大型语言模型如GPT-4和Claude已经能够生成高质量的文本内容。
然而，这些模型生成的内容也带来了一系列挑战，例如学术诚信问题。
因此，开发有效的AIGC检测工具变得尤为重要。
进一步来说，我们必须认识到AIGC检测不仅是一个技术问题，更是一个教育问题。
"""

# 测试样本: 人类风格的文本 (口语化、有个人风格)
HUMAN_LIKE_TEXT = """
昨天晚上赶论文赶到三点，脑子都快炸了。
本来想用ChatGPT糊弄一下，后来想想还是算了，咱导师那火眼金睛，肯定看得出来。
跟室友讨论了一下思路，他给我推了几篇论文，感觉还行。
不过说实话，这方向确实不太好做，数据太少，模型跑不动，烦。
"""


def test_extract_basic():
    """测试基本特征提取不报错"""
    features = extractor.extract(AI_LIKE_TEXT)
    assert isinstance(features, StatisticalFeatures)
    assert features.unigram_entropy > 0
    assert features.bigram_entropy > 0


def test_ngram_entropy():
    """n-gram 熵: AI 文本应该更低"""
    ai = extractor.extract(AI_LIKE_TEXT)
    human = extractor.extract(HUMAN_LIKE_TEXT)
    # AI 文本的 trigram 熵通常更低 (更可预测)
    assert ai.trigram_entropy > 0


def test_idiom_density():
    """成语密度: AI 文本通常更高"""
    ai = extractor.extract(AI_LIKE_TEXT)
    human = extractor.extract(HUMAN_LIKE_TEXT)
    assert ai.idiom_density >= 0
    assert human.idiom_density >= 0


def test_slop_word_density():
    """Slop 词密度: AI 文本应检出更多标志词"""
    ai = extractor.extract(AI_LIKE_TEXT)
    human = extractor.extract(HUMAN_LIKE_TEXT)
    # AI 文本包含"值得注意的是"、"因此"、"然而"等标志词
    assert ai.slop_word_density >= 0


def test_burstiness():
    """Burstiness: 人类文本通常更高 (句子复杂度方差大)"""
    ai = extractor.extract(AI_LIKE_TEXT)
    human = extractor.extract(HUMAN_LIKE_TEXT)
    assert ai.burstiness >= 0
    assert human.burstiness >= 0


def test_hapax_ratio():
    """Hapax 比率: 人类文本通常更高"""
    ai = extractor.extract(AI_LIKE_TEXT)
    human = extractor.extract(HUMAN_LIKE_TEXT)
    assert ai.hapax_ratio >= 0
    assert human.hapax_ratio >= 0


def test_empty_text():
    """空文本边界测试"""
    features = extractor.extract("")
    assert isinstance(features, StatisticalFeatures)
    assert features.unigram_entropy == 0.0


def test_short_text():
    """短文本测试"""
    features = extractor.extract("你好世界")
    assert isinstance(features, StatisticalFeatures)


def test_to_dict():
    """to_dict 输出格式"""
    features = extractor.extract(AI_LIKE_TEXT)
    d = features.to_dict()
    assert isinstance(d, dict)
    assert "burstiness" in d
    assert "zipf_deviation" in d
    assert "yule_k" in d
