"""
AI 改写/翻译回译检测器

检测以下改写模式:
  1. 翻译回译痕迹: 中→英→中 产生的语法僵硬
  2. 同义词过度替换: 词汇多样性异常高 + 句式一致性高
  3. 人机混合: 部分段落 AI 风格 + 部分人类风格 (突发性异常高)
  4. Prompt 改写: Slop 词消失但其他统计特征仍指向 AI
"""

from app.detectors.text.statistical_features import ChineseStatisticalExtractor


def detect_paraphrasing(text: str) -> dict:
    """
    检测文本是否经过改写处理以逃避 AI 检测

    返回:
      {
        "is_paraphrased": bool,
        "confidence": float,
        "methods": [str],    # 检测到的改写方法
        "evidence": [str],   # 证据描述
        "suggestions": [str], # 建议
      }
    """
    extractor = ChineseStatisticalExtractor()
    feats = extractor.extract(text)

    methods = []
    evidence = []
    score = 0.0

    # 1. 翻译回译检测: 低 Burstiness + 低 Slop 词 + 高 ngram 熵
    if feats.burstiness < 0.2 and feats.slop_word_density < 0.3 and feats.unigram_entropy > 7.0:
        score += 0.35
        methods.append("翻译回译")
        evidence.append(
            f"句子复杂度异常均匀 (burstiness={feats.burstiness:.3f})，"
            f"无 AI 标志性短语 (slop={feats.slop_word_density:.3f})，"
            f"但词汇熵偏高 (unigram_entropy={feats.unigram_entropy:.1f})——"
            f"符合中→英→中翻译特征"
        )

    # 2. 同义词替换: 高词汇多样性 + 低重复率 + 正常 Slop 词低
    if feats.hapax_ratio > 0.85 and feats.bigram_repetition_rate < 0.03:
        score += 0.25
        methods.append("同义词替换")
        evidence.append(
            f"词汇多样性异常高 (hapax={feats.hapax_ratio:.3f})，"
            f"但短语重复率极低 ({feats.bigram_repetition_rate:.4f})——"
            f"疑似大量同义词替换操作"
        )

    # 3. 人机混合: 高 Burstiness + 中等 Slop 词
    if feats.burstiness > 0.6 and 0.2 < feats.slop_word_density < 1.0:
        score += 0.20
        methods.append("人机混合")
        evidence.append(
            f"句子复杂度波动异常大 (burstiness={feats.burstiness:.3f})，"
            f"部分段落使用 AI 标志短语 (slop={feats.slop_word_density:.3f})——"
            f"疑似 AI 生成后人工修改或混合创作"
        )

    # 4. Prompt 改写: 过渡词偏高但 Slop 词偏低
    if feats.transition_word_density > 0.4 and feats.slop_word_density < 0.3:
        score += 0.15
        methods.append("Prompt引导改写")
        evidence.append(
            f"过渡词密度偏高 ({feats.transition_word_density:.3f})"
            f"但不含典型 AI 标志短语——疑似用 Prompt 要求 AI 模仿人类风格"
        )

    # 5. 句式重构: 句长CV正常但标点熵高
    if 0.3 < feats.sentence_length_cv < 0.6 and feats.punctuation_entropy > 2.5:
        score += 0.10
        methods.append("句式重构")
        evidence.append("标点使用模式异常丰富，疑似人工干预改写")

    confidence = min(score, 0.95)
    is_paraphrased = score >= 0.30

    suggestions = []
    if is_paraphrased:
        if "翻译回译" in methods:
            suggestions.append("建议检查翻译工具使用记录")
        if "同义词替换" in methods:
            suggestions.append("建议人工核查关键术语的准确性")
        if "人机混合" in methods:
            suggestions.append("建议要求学生提供写作过程材料")
        if not suggestions:
            suggestions.append("建议人工审核，结合其他检测手段综合判断")

    return {
        "is_paraphrased": is_paraphrased,
        "confidence": round(confidence, 4),
        "methods": methods,
        "evidence": evidence,
        "suggestions": suggestions,
    }
