"""
文本检测服务编排 — 并行预处理 → 三路检测 → 融合 → 解释
支持长文本: 自动分块(RoBERTa) + 全文本(统计特征) + 采样(LLM)
"""
import asyncio

from app.detectors.base import DetectionOutput
from app.detectors.text.statistical_features import (
    ChineseStatisticalExtractor,
    StatisticalFeatures,
)
from app.detectors.text.roberta_detector import ChineseRobertaDetector
from app.detectors.text.llm_logprob import LLMLogprobDetector
from app.detectors.text.ensemble import TextEnsemble
from app.detectors.text.deepseek_detector import DeepSeekDetector


# 全局单例
_stat_extractor = ChineseStatisticalExtractor()
_roberta = ChineseRobertaDetector()
_logprob = LLMLogprobDetector()
_deepseek = DeepSeekDetector()
_ensemble = TextEnsemble()

# 长文本分块参数
CHUNK_SIZE = 450     # RoBERTa 最大 token 数预留余量
CHUNK_STRIDE = 200   # 分块步长，保持重叠以捕捉上下文


async def detect_text(content: str, options: dict | None = None) -> DetectionOutput:
    """
    完整文本检测流程 (支持长文本)

    输入: 中文文本 (任意长度)
    输出: 融合后的 DetectionOutput (含置信度、溯源、解释数据)
    """
    do_explain = options.get("explain", True) if options else True

    # 防御预处理: 同形字+零宽字符标准化
    from app.detectors.defense.homoglyph_normalizer import normalize_text, has_evasion_attempts
    content, defense_warnings = normalize_text(content)
    evasion_info = has_evasion_attempts(content) if defense_warnings else {}

    text_len = len(content)
    need_chunk = text_len > 1500

    # 1. 统计特征分支 (全文本)
    stat_features = _stat_extractor.extract(content)
    stat_output = _statistical_to_output(stat_features)

    # 2. 三分支并行: RoBERTa + MiMo + DeepSeek
    sample_text = content[:2000] if text_len > 2000 else content

    async def _run_roberta():
        if need_chunk:
            return await _detect_long_text_roberta(content)
        return await _roberta.detect(content)

    async def _run_logprob():
        out = await _logprob.detect(sample_text)
        out.metadata["sampled"] = text_len > 2000
        return out

    async def _run_deepseek():
        out = await _deepseek.detect(sample_text)
        out.metadata["sampled"] = text_len > 2000
        return out

    # 三分支并行检测，部分失败时降级而非全部丢弃
    results = await asyncio.gather(
        _run_roberta(), _run_logprob(), _run_deepseek(),
        return_exceptions=True,
    )
    roberta_output = results[0] if not isinstance(results[0], Exception) else None
    logprob_output = results[1] if not isinstance(results[1], Exception) else None
    deepseek_output = results[2] if not isinstance(results[2], Exception) else None

    # 全部失败 → 纯统计分支
    if roberta_output is None and logprob_output is None and deepseek_output is None:
        return stat_output

    # 5. 按文本长度 + 成功分支动态调整融合权重
    roberta_ok = roberta_output is not None and roberta_output.metadata.get("status") != "model_load_error"
    logprob_ok = logprob_output is not None
    deepseek_ok = deepseek_output is not None

    if not roberta_ok and not logprob_ok and not deepseek_ok:
        _ensemble.set_weights(stat=1.0, roberta=0.0, logprob=0.0, deepseek=0.0)
    elif not roberta_ok:
        _ensemble.set_weights(stat=0.40, roberta=0.0, logprob=0.35 if logprob_ok else 0.0, deepseek=0.25 if deepseek_ok else 0.0)
    elif text_len < 300:
        _ensemble.set_weights(stat=0.30, roberta=0.25, logprob=0.25 if logprob_ok else 0.0, deepseek=0.20 if deepseek_ok else 0.0)
    else:
        _ensemble.set_weights(stat=0.15, roberta=0.30, logprob=0.30 if logprob_ok else 0.0, deepseek=0.25 if deepseek_ok else 0.0)

    # 构造缺失分支的占位输出
    from app.detectors.base import DetectionOutput as _DO
    _placeholder = _DO(is_ai_generated=False, confidence=0.5, logit=0.0, explanation_data={}, metadata={"status": "unavailable"})
    fused = _ensemble.fuse(
        stat_output,
        roberta_output or _placeholder,
        logprob_output or _placeholder,
        deepseek_output or _placeholder,
    )

    # 5. 校准: 训练参数不适用于融合输出，直接使用原始置信度
    fused.calibrated_confidence = fused.confidence
    fused.confidence_interval = (
        max(0.01, fused.confidence - 0.15),
        min(0.99, fused.confidence + 0.15),
    )

    # 6. 分块详情
    chunk_details = None
    if need_chunk and roberta_output is not None and "per_chunk_scores" in roberta_output.explanation_data:
        chunk_scores = roberta_output.explanation_data["per_chunk_scores"]
        chunk_size = CHUNK_SIZE
        chunk_stride = CHUNK_STRIDE
        chunk_details = []
        for i, score in enumerate(chunk_scores):
            start = i * chunk_stride
            end = min(start + chunk_size, text_len)
            chunk_text = content[start:end] if start < text_len else ""
            chunk_details.append({
                "index": i,
                "start": start,
                "end": end,
                "text_preview": chunk_text[:80] + ("..." if len(chunk_text) > 80 else ""),
                "score": round(score, 4),
                "level": "high" if score >= 0.7 else ("medium" if score >= 0.3 else "low"),
            })

    # 7. 解释
    if do_explain:
        fused.explanation_data = {
            **fused.explanation_data,
            "defense": {
                "warnings": defense_warnings,
                "evasion_attempts": evasion_info,
            },
            "statistical_features": stat_features.to_dict(),
            "roberta_explanation": {
                "chunked": need_chunk,
                "method": "chunked_average" if need_chunk else "single_pass",
            },
            "logprob_explanation": {
                "sampled": len(content) > 2000,
                "sample_length": len(sample_text),
            },
            "text_snippets": _extract_suspicious_spans(content, stat_features, (logprob_output or _placeholder).metadata),
            "text_length": len(content),
            "chunk_details": chunk_details,
        }

    return fused


async def _detect_long_text_roberta(text: str) -> DetectionOutput:
    """
    长文本 RoBERTa 分块检测

    策略:
    1. 按字符分块 (CHUNK_SIZE 字符 ≈ 450 字符)
    2. 步长 CHUNK_STRIDE (200 字符重叠)
    3. 每块独立检测
    4. 聚合: 置信度均值 + 方差惩罚
       - 方差低 (各块一致) → 偏向判定方
       - 方差高 (各块不一致) → 拉向 0.5 (不确定)，典型人类写作特征
    """
    import math

    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start:start + CHUNK_SIZE]
        if len(chunk) >= 50:  # 跳过过短尾块
            chunks.append((start, chunk))
        start += CHUNK_STRIDE

    if not chunks:
        return await _roberta.detect(text)

    # 逐块检测
    scores = []
    logits = []
    for _, chunk in chunks:
        output = await _roberta.detect(chunk)
        scores.append(output.confidence)
        logits.append(output.logit)

    # 聚合统计
    mean_score = sum(scores) / len(scores)
    mean_logit = sum(logits) / len(logits)

    # 方差惩罚: 高方差 → 拉向 0.5 (uncertain)
    variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
    std = math.sqrt(variance)

    # 用方差调整置信度: conf = mean_score - penalty * std
    # penalty 系数让高方差文本 (人类写作特征) 拉回中性点
    penalty = 0.5
    adjusted_score = mean_score - penalty * std * (2 * mean_score - 1)

    # 重新计算 logit
    adjusted_score = max(0.01, min(0.99, adjusted_score))
    adjusted_logit = math.log(adjusted_score / (1 - adjusted_score))

    return DetectionOutput(
        is_ai_generated=adjusted_score > 0.5,
        confidence=round(adjusted_score, 4),
        logit=round(adjusted_logit, 6),
        explanation_data={
            "num_chunks": len(chunks),
            "mean_confidence": round(mean_score, 4),
            "variance": round(variance, 6),
            "per_chunk_scores": [round(s, 3) for s in scores],
        },
        metadata={
            "method": "chunked_roberta",
            "num_chunks": len(chunks),
            "score_variance": round(variance, 4),
        },
    )


def _statistical_to_output(features: StatisticalFeatures) -> DetectionOutput:
    """
    将 12 项统计特征转换为 AI 检测信号
    重点依赖 slop 词密度和过渡词密度（不受文本长度影响）
    n-gram 熵等在短文本上不可靠，降低权重
    """
    import math

    feature_rules = [
        # (value, midpoint, steepness, weight, direction) -1=低值→AI, +1=高值→AI
        # 降低slop词和过渡词权重，减少正常写作误判
        (features.slop_word_density, 0.4, 5.0, 0.15, +1),
        (features.transition_word_density, 0.3, 6.0, 0.10, +1),
        (features.idiom_density, 0.05, 50.0, 0.08, +1),
        (features.bigram_repetition_rate, 0.08, 20.0, 0.10, +1),
        (features.sentence_length_cv, 0.4, 8.0, 0.12, -1),
        (features.burstiness, 0.3, 8.0, 0.12, -1),
        (features.punctuation_entropy, 2.0, 2.0, 0.08, -1),
        (features.unigram_entropy, 6.0, 1.5, 0.08, -1),
        (features.zipf_deviation, 0.08, 30.0, 0.05, +1),
        (features.hapax_ratio, 0.4, 4.0, 0.06, -1),
        (features.yule_k, 100.0, 0.01, 0.06, +1),
    ]

    total_signal = 0.0
    total_weight = 0.0

    for value, mid, steep, weight, direction in feature_rules:
        if value == 0.0:
            continue
        z = steep * (value - mid)
        signal = 1.0 / (1.0 + math.exp(-z))
        if direction < 0:
            signal = 1.0 - signal
        total_signal += weight * signal
        total_weight += weight

    final_score = total_signal / total_weight if total_weight > 0 else 0.5
    # 宽松决策：偏向 0.5，让 RoBERTa 和 logprob 分支主导
    final_score = 0.5 + (final_score - 0.5) * 0.6
    logit = math.log(final_score / (1 - final_score)) if 0 < final_score < 1 else 0.0

    return DetectionOutput(
        is_ai_generated=final_score > 0.5,
        confidence=round(final_score, 4),
        logit=round(logit, 6),
        explanation_data={},
        metadata={"method": "statistical_features_weighted"},
    )


def _extract_suspicious_spans(
    text: str,
    features: StatisticalFeatures,
    logprob_meta: dict,
) -> list[dict]:
    """
    提取可疑文本片段 — 用于解释报告中的高亮标注
    """
    spans = []

    # 从 Slop 词定位可疑短语
    all_slop = set()
    for words in [
        ["值得注意的是", "总而言之", "综上所述", "在某种程度上", "不可否认",
         "从某种意义上说", "众所周知", "显而易见", "毋庸置疑", "毫无疑问",
         "进一步来说", "更重要的是", "必须指出", "需要强调的是", "总体而言"],
    ]:
        all_slop.update(words)

    for slop_word in all_slop:
        pos = text.find(slop_word)
        if pos >= 0:
            spans.append({
                "start": pos,
                "end": pos + len(slop_word),
                "reason": "slop_word",
                "score": 0.75,
                "detail": f"AI 标志短语: {slop_word}",
            })

    # 标记高频四字词
    import jieba
    words = list(jieba.cut(text))
    word_freq = {}
    for w in words:
        if len(w) == 4 and all('一' <= c <= '鿿' for c in w):
            word_freq[w] = word_freq.get(w, 0) + 1

    for w, count in word_freq.items():
        if count >= 3:
            pos = text.find(w)
            while pos >= 0:
                spans.append({
                    "start": pos,
                    "end": pos + len(w),
                    "reason": "repeated_idiom",
                    "score": min(0.6 + count * 0.05, 0.9),
                    "detail": f"高频四字词: {w} (出现 {count} 次)",
                })
                pos = text.find(w, pos + 1)

    # 按位置排序
    spans.sort(key=lambda s: s["start"])
    return spans
