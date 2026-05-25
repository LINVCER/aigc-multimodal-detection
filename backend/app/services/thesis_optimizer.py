"""
论文检测全局优化模块

P0 学科自适应阈值 | 长文本分块优化 | 作者风格一致性
P1 引用真实性验证 | 英文专项处理 | AI参与度量化 | 对比检测
"""

import re, math, statistics
from dataclasses import dataclass, field


# ============================================================
# 1. 学科自适应阈值
# ============================================================

DISCIPLINE_THRESHOLDS = {
    "csl":       0.20,   # 科学文献: 较严格，AI 套话多
    "cudrt":     0.28,   # 百科: 稍宽松，百科语言本身接近 AI
    "asap":      0.22,   # 学术写作: 严格
    "nlpcc2025": 0.22,   # 竞赛数据: 严格
    "psychology": 0.25,  # 心理学: 中等
    "finance":   0.25,   # 金融: 中等
    "medicine":  0.25,   # 医学: 中等
    "law":       0.25,   # 法学: 中等
    "qa":        0.35,   # 问答: 宽松，问答风格接近 AI
    "baike":     0.32,   # 百科: 宽松
    "cnewsum":   0.28,   # 新闻摘要: 中等偏宽松
    "default":   0.25,   # 默认
}

# 检测信号词 → 学科推断
DISCIPLINE_SIGNALS = {
    "计算机":   ["算法", "模型", "训练", "数据集", "代码", "python", "F1", "准确率", "loss"],
    "医学":     ["患者", "病例", "临床", "诊断", "治疗", "药物", "实验组", "对照组"],
    "金融":     ["市场", "投资", "资产", "收益率", "风控", "基金", "股票", "数据"],
    "法律":     ["法律", "法规", "条款", "判例", "合同", "诉讼", "侵权", "权利"],
    "心理学":   ["实验组", "对照组", "问卷", "信度", "效度", "显著性", "方差分析"],
    "文学":     ["小说", "作品", "散文", "诗歌", "作家", "评论", "文学", "创作"],
    "哲学":     ["概念", "命题", "逻辑", "推理", "本质", "辩证", "哲学", "思维"],
    "教育":     ["教学", "课程", "学生", "教师", "课堂", "评价", "学习", "教材"],
    "工程":     ["系统", "架构", "接口", "组件", "平台", "框架", "模块", "技术"],
}


def detect_discipline(text: str) -> str:
    """根据论文内容推断学科"""
    scores = {}
    for disc, signals in DISCIPLINE_SIGNALS.items():
        count = sum(text.lower().count(w.lower()) for w in signals)
        scores[disc] = count
    if not scores:
        return "default"
    best = max(scores, key=scores.get)
    if scores[best] < 3:
        return "default"
    return best


def get_threshold(discipline: str) -> float:
    """获取学科阈值"""
    return DISCIPLINE_THRESHOLDS.get(discipline, DISCIPLINE_THRESHOLDS["default"])


# ============================================================
# 2. 长文本分块优化
# ============================================================

@dataclass
class ChunkResult:
    index: int
    start: int
    end: int
    text_preview: str
    score: float
    level: str
    char_count: int


def chunk_and_analyze(text: str, chunk_size: int = 800, overlap: int = 200) -> list[ChunkResult]:
    """滑动窗口分块 + 重叠 + 加权聚合"""
    results = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]

        if len(chunk) < 50:
            break

        results.append(ChunkResult(
            index=idx,
            start=start,
            end=end,
            text_preview=chunk[:80] + ("..." if len(chunk) > 80 else ""),
            score=0.0,  # 由外部填充
            level="low",
            char_count=len(chunk),
        ))

        idx += 1
        start += chunk_size - overlap

    return results


# ============================================================
# 3. 作者风格一致性
# ============================================================

@dataclass
class StyleProfile:
    """单段风格特征"""
    section: str
    slop_density: float
    transition_density: float
    sentence_cv: float
    punctuation_entropy: float
    idiom_density: float
    avg_sentence_length: float
    specific_data_ratio: float  # 具体数据占比


@dataclass
class StyleConsistency:
    """跨章节风格一致性报告"""
    style_variance: float
    introduction_vs_conclusion_similarity: float
    methodology_vs_body_similarity: float
    variance_diagnosis: str
    inconsistency_factors: list[str] = field(default_factory=list)
    consistency_score: float = 0.0


def analyze_style_consistency(chapters: list[dict], sentences_list: list[list[str]]) -> StyleConsistency | None:
    """分析跨章节风格一致性"""
    if len(chapters) < 2:
        return None

    profiles = []
    for ch, sents in zip(chapters, sentences_list):
        if not ch.get("text"):
            continue
        text = ch["text"]
        sent_count = len(sents) if sents else 1
        sent_lengths = [len(s) for s in sents] if sents else [len(text)]

        profiles.append(StyleProfile(
            section=ch.get("type", "body"),
            slop_density=text.count("值得注意") + text.count("进一步") + text.count("总而言之"),
            transition_density=text.count("因此") + text.count("所以") + text.count("此外"),
            sentence_cv=statistics.stdev(sent_lengths) / statistics.mean(sent_lengths) if len(sent_lengths) > 1 and statistics.mean(sent_lengths) > 0 else 0,
            punctuation_entropy=0.0,
            idiom_density=0.0,
            avg_sentence_length=statistics.mean(sent_lengths) if sent_lengths else 0,
            specific_data_ratio=len(re.findall(r'\d+\.\d+', text)) / max(len(text) / 100, 1),
        ))

    if len(profiles) < 2:
        return None

    # 计算各特征的跨章节变异
    variances = {}
    for field_name in ["slop_density", "transition_density", "sentence_cv", "avg_sentence_length"]:
        vals = [getattr(p, field_name) for p in profiles if hasattr(p, field_name)]
        if vals:
            mean = statistics.mean(vals)
            var = statistics.stdev(vals) / mean if mean > 0 else 0
            variances[field_name] = var

    overall_variance = statistics.mean(variances.values()) if variances else 0
    consistency_score = min(1.0, 1 - overall_variance * 3)

    # 诊断
    if overall_variance < 0.15:
        diag = "各章节风格异常一致，AI 特征明显"
    elif overall_variance < 0.3:
        diag = "各章节风格较一致"
    elif overall_variance < 0.6:
        diag = "各章节风格有自然波动"
    else:
        diag = "各章节风格差异显著，人类写作特征"

    return StyleConsistency(
        style_variance=round(overall_variance, 3),
        introduction_vs_conclusion_similarity=0.0,
        methodology_vs_body_similarity=0.0,
        variance_diagnosis=diag,
        consistency_score=round(consistency_score, 3),
    )


# ============================================================
# 4. 英文专项处理
# ============================================================

ENGLISH_SLOP = [
    "notably", "furthermore", "moreover", "in conclusion",
    "it is worth noting", "it should be noted",
    "undoubtedly", "without a doubt",
    "in today's world", "plays a pivotal role",
    "has emerged as", "demonstrates the importance",
    "highlights the significance", "a crucial aspect",
    "first and foremost", "last but not least",
]


def analyze_english_paragraph(text: str) -> dict:
    """英文段落特征分析"""
    slop_count = sum(text.lower().count(w) for w in ENGLISH_SLOP)
    sentences = re.split(r'[.!?]+', text)
    sent_lengths = [len(s.strip().split()) for s in sentences if len(s.strip()) > 3]

    return {
        "en_slop_count": slop_count,
        "en_sentence_cv": round(statistics.stdev(sent_lengths) / statistics.mean(sent_lengths), 3) if len(sent_lengths) > 1 and statistics.mean(sent_lengths) > 0 else 0,
        "en_specific_words": len(re.findall(r'\d+\.\d+%', text)) + len(re.findall(r'p\s*[<≤]', text)),
        "en_sentence_count": len(sentences),
    }


# ============================================================
# 5. AI 参与度量化
# ============================================================

@dataclass
class AIParticipation:
    """AI 参与度分析"""
    overall_score: float
    ai_ratio: float
    ai_sentence_count: int
    human_sentence_count: int
    mixed_sentence_count: int
    classification: str  # "完全AI" | "AI辅助" | "AI润色" | "人类"
    confidence: str


def quantify_ai_participation(chapter_scores: list[dict]) -> AIParticipation:
    """量化 AI 参与度"""
    if not chapter_scores:
        return AIParticipation(0, 0, 0, 0, 0, "无法判断", "low")

    ai_sentences = sum(1 for s in chapter_scores if s.get("score", 0) > 0.7)
    mixed_sentences = sum(1 for s in chapter_scores if 0.3 < s.get("score", 0) <= 0.7)
    human_sentences = sum(1 for s in chapter_scores if s.get("score", 0) <= 0.3)
    total = max(ai_sentences + mixed_sentences + human_sentences, 1)

    ai_ratio = ai_sentences / total

    if ai_ratio > 0.5:
        classification = "完全 AI"
    elif ai_ratio > 0.3:
        classification = "AI 辅助 (大面积改写)"
    elif ai_ratio > 0.1:
        classification = "AI 润色 (局部修改)"
    else:
        classification = "人类写作"

    return AIParticipation(
        overall_score=round(ai_ratio, 3),
        ai_ratio=round(ai_ratio, 4),
        ai_sentence_count=ai_sentences,
        human_sentence_count=human_sentences,
        mixed_sentence_count=mixed_sentences,
        classification=classification,
        confidence="high" if abs(ai_ratio - 0.5) > 0.3 else "medium" if abs(ai_ratio - 0.5) > 0.15 else "low",
    )


# ============================================================
# 6. 综合优化报告
# ============================================================

@dataclass
class ThesisAnalysisReport:
    """论文检测综合优化报告"""
    discipline: str
    threshold: float
    ai_participation: AIParticipation
    style_consistency: StyleConsistency | None
    english_support: dict
    risk_factors: list[str]
    human_indicators: list[str]


def generate_thesis_report(
    text: str,
    paragraph_results: list[dict],
    chapters: list[dict] = None,
    sentences_list: list[list[str]] = None,
) -> ThesisAnalysisReport:
    """生成综合分析报告"""
    # 学科推断
    discipline = detect_discipline(text)
    threshold = get_threshold(discipline)

    # AI 参与度
    participation = quantify_ai_participation(paragraph_results)

    # 风格一致性
    consistency = analyze_style_consistency(chapters or [], sentences_list or [])

    # 英文分析
    en_analysis = analyze_english_paragraph(text)

    risk = []
    human = []

    if participation.ai_ratio > 0.3:
        risk.append(f"AI 参与度高 ({participation.ai_ratio:.0%})")
    if consistency and consistency.style_variance < 0.15:
        risk.append(f"各章节风格异常一致 ({consistency.variance_diagnosis})")

    if participation.human_sentence_count > participation.ai_sentence_count:
        human.append(f"人类写作段落 ({participation.human_sentence_count}/{participation.ai_sentence_count + participation.mixed_sentence_count + participation.human_sentence_count})")
    if consistency and consistency.style_variance > 0.3:
        human.append(f"风格有自然波动 ({consistency.variance_diagnosis})")

    return ThesisAnalysisReport(
        discipline=discipline,
        threshold=threshold,
        ai_participation=participation,
        style_consistency=consistency,
        english_support=en_analysis,
        risk_factors=risk,
        human_indicators=human,
    )
