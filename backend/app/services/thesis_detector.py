"""
论文 AIGC 检测 — 中期方案: 分块层次化 + 跨章节一致性

三层检测:
  段落级: RoBERTa 分块检测 (复用 text_service)
  章节级: 每章统计特征 + 语义特征
  文档级: 跨章节风格一致性分析 (核心创新)

核心信号:
  AI 论文 → 各章节风格高度一致 (同一模型生成)
  人类论文 → 各章节风格自然波动 (不同类型内容有不同写法)
"""

import re, math, statistics
from dataclasses import dataclass, field


# ============================================================
# 1. 章节结构解析
# ============================================================

CHAPTER_PATTERNS = {
    "abstract": [
        r'(摘\s*要|abstract|ABSTRACT)',
    ],
    "introduction": [
        r'(引\s*言|绪\s*论|前\s*言|引论|introduction|INTRODUCTION)',
        r'第[一二三四五六七八九十\d]章\s*(引言|绪论)',
    ],
    "literature_review": [
        r'(文\s*献\s*综\s*述|相\s*关\s*工\s*作|研\s*究\s*现\s*状|literature\s*review)',
        r'(国内外|已有).*(研究|综述|进展)',
    ],
    "methodology": [
        r'(研\s*究\s*方\s*法|实\s*验\s*方\s*法|方\s*法\s*论|方\s*案|method|Method)',
        r'(数\s*据|模\s*型|算\s*法).*(设计|构建|描述)',
        r'第[一二三四五六七八九十\d]章.*(方法|设计|方案|模型)',
    ],
    "experiment": [
        r'(实\s*验|结\s*果|实验设计|experiment|result|Result)',
        r'(训\s*练|测\s*试|评\s*估|验\s*证).*(过程|结果|分析)',
        r'第[一二三四五六七八九十\d]章.*(实验|结果)',
    ],
    "discussion": [
        r'(讨\s*论|分\s*析|discussion|Discussion)',
        r'(结果|实验).*(分析|讨论)',
    ],
    "conclusion": [
        r'(结\s*论|总\s*结|展\s*望|conclusion|Conclusion)',
        r'(不\s*足|局\s*限|未\s*来).*(方向|工作|研究)',
    ],
    "references": [
        r'(参\s*考\s*文\s*献|references|References|REFERENCE)',
        r'(致\s*谢|acknowledgment|Appendix|附\s*录)',
        r'^\[\d+\]',
    ],
}


@dataclass
class Chapter:
    title: str
    chapter_type: str  # abstract/introduction/methodology/...
    paragraphs: list[str] = field(default_factory=list)
    is_skip: bool = False  # 参考文献等跳过检测
    start_pos: int = 0
    end_pos: int = 0

    @property
    def full_text(self) -> str:
        return "\n".join(self.paragraphs)

    @property
    def char_count(self) -> int:
        return sum(len(p) for p in self.paragraphs)

    @property
    def paragraph_count(self) -> int:
        return len([p for p in self.paragraphs if len(p) >= 30])


def parse_chapters(text: str) -> list[Chapter]:
    """解析论文文本为章节结构"""
    lines = text.split('\n')
    chapters: list[Chapter] = []
    current = Chapter(title="正文", chapter_type="body")

    # 目录跳过
    toc_end = _find_toc_end(lines)

    for i, line in enumerate(lines):
        if i <= toc_end:
            continue
        stripped = line.strip()
        if not stripped:
            continue

        # 检查是否为章节标题
        chapter_type = _match_chapter_title(stripped)
        if chapter_type and len(stripped) < 80:
            if current.paragraphs:
                chapters.append(current)
            current = Chapter(
                title=stripped,
                chapter_type=chapter_type,
                start_pos=sum(len(c.full_text) for c in chapters),
                is_skip=(chapter_type == "references"),
            )
            continue

        # 普通段落
        if len(stripped) >= 20:
            current.paragraphs.append(stripped)

    if current.paragraphs:
        chapters.append(current)

    # 更新 end_pos
    offset = 0
    for ch in chapters:
        ch.start_pos = offset
        ch.end_pos = offset + ch.char_count
        offset = ch.end_pos

    return chapters


def _find_toc_end(lines: list[str]) -> int:
    """找目录结束位置"""
    toc_pattern = re.compile(r'[.]{3,}|…|[·•]{3,}')
    toc_indices = [i for i, l in enumerate(lines) if toc_pattern.search(l)]
    if toc_indices:
        return max(toc_indices) + 2
    return 0


def _match_chapter_title(line: str) -> str | None:
    """匹配章节标题 -> 返回章节类型"""
    for ctype, patterns in CHAPTER_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, line):
                return ctype
    # 通用章节匹配 (第X章)
    if re.match(r'^第[一二三四五六七八九十\d]+章', line):
        return "body"
    return None


# ============================================================
# 2. 风格特征提取 (跨章节一致性分析)
# ============================================================

@dataclass
class StyleVector:
    """单章风格特征向量"""
    chapter_type: str
    avg_sentence_length: float
    sentence_length_cv: float     # 句长变异系数
    slop_word_density: float       # slop 词密度
    transition_density: float      # 过渡词密度
    punctuation_entropy: float     # 标点熵
    idiom_density: float           # 四字词密度
    avg_word_length: float         # 平均词长
    paragraph_count: int
    char_count: int


SLOP_WORDS = {
    "值得注意的是", "进一步来说", "总而言之", "从某种意义上讲",
    "不可否认", "需要强调的是", "研究表明", "数据显示",
    "在一定程度上", "具有重要的", "为...提供了",
    "首先", "其次", "最后", "不仅", "而且",
    "众所周知", "毋庸置疑", "毫无疑问",
}

TRANSITION_WORDS = {
    "因此", "所以", "然而", "但是", "此外", "另外",
    "与此同时", "另一方面", "相比之下", "换言之",
    "具体而言", "总的来说", "综上所述",
}


def extract_style_vector(chapter: Chapter) -> StyleVector | None:
    """提取章节的风格特征向量"""
    text = chapter.full_text
    if len(text) < 100:
        return None

    # 分句
    sentences = re.split(r'[。！？；\n]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 10]
    if len(sentences) < 3:
        return None

    sent_lengths = [len(s) for s in sentences]
    avg_len = statistics.mean(sent_lengths)
    std_len = statistics.stdev(sent_lengths) if len(sent_lengths) > 1 else 0
    cv = std_len / avg_len if avg_len > 0 else 0

    # Slop 词密度
    slop_count = sum(text.count(w) for w in SLOP_WORDS)
    slop_density = slop_count / max(len(text) / 100, 1)

    # 过渡词密度
    trans_count = sum(text.count(w) for w in TRANSITION_WORDS)
    trans_density = trans_count / max(len(text) / 100, 1)

    # 标点熵
    puncts = re.findall(r'[，。！？；：、""''（）《》【】]', text)
    punct_freq = {}
    for p in puncts:
        punct_freq[p] = punct_freq.get(p, 0) + 1
    total = len(puncts) or 1
    punct_entropy = -sum((c/total) * math.log2(c/total) for c in punct_freq.values())

    # 四字词密度
    words = re.findall(r'[一-鿿]{4}', text)
    idiom_density = len(words) / max(len(text) / 100, 1)

    # 平均词长
    all_words = re.findall(r'[一-鿿]+', text)
    avg_word_len = statistics.mean(len(w) for w in all_words) if all_words else 0

    return StyleVector(
        chapter_type=chapter.chapter_type,
        avg_sentence_length=avg_len,
        sentence_length_cv=cv,
        slop_word_density=slop_density,
        transition_density=trans_density,
        punctuation_entropy=punct_entropy,
        idiom_density=idiom_density,
        avg_word_length=avg_word_len,
        paragraph_count=chapter.paragraph_count,
        char_count=chapter.char_count,
    )


# ============================================================
# 3. 跨章节一致性评分 (核心创新)
# ============================================================

@dataclass
class ConsistencyReport:
    """跨章节一致性分析报告"""
    overall_score: float           # 0-1, 越高越像 AI (太一致)
    style_variance: float          # 风格方差 (低=AI)
    slop_pattern: str              # slop 词分布模式
    transition_pattern: str        # 过渡词分布模式
    sentence_length_pattern: str   # 句长分布模式
    chapter_count: int
    analyzed_count: int
    details: list[dict] = field(default_factory=list)


def analyze_cross_chapter_consistency(chapters: list[Chapter]) -> ConsistencyReport | None:
    """分析跨章节风格一致性 — AI 论文核心判别信号"""
    active_chapters = [c for c in chapters if not c.is_skip and c.char_count >= 100]
    if len(active_chapters) < 2:
        return None

    vectors = []
    for ch in active_chapters:
        sv = extract_style_vector(ch)
        if sv:
            vectors.append(sv)

    if len(vectors) < 2:
        return None

    # 计算各维度的跨章节变异系数 (CV = std/mean)
    features = {
        "slop_density": [v.slop_word_density for v in vectors],
        "transition_density": [v.transition_density for v in vectors],
        "sentence_cv": [v.sentence_length_cv for v in vectors],
        "sent_len": [v.avg_sentence_length for v in vectors],
        "punct_entropy": [v.punctuation_entropy for v in vectors],
        "idiom_density": [v.idiom_density for v in vectors],
    }

    cross_cvs = {}
    for name, vals in features.items():
        mean_val = statistics.mean(vals)
        std_val = statistics.stdev(vals) if len(vals) > 1 else 0.0
        cross_cvs[name] = std_val / mean_val if mean_val > 0 else 0.0

    # 综合风格方差: 各维度 CV 的加权平均
    # 低方差 → 各章风格太一致 → AI 特征
    weights = {
        "slop_density": 0.25,
        "transition_density": 0.20,
        "sentence_cv": 0.20,
        "sent_len": 0.15,
        "punct_entropy": 0.10,
        "idiom_density": 0.10,
    }
    weighted_cv = sum(cross_cvs[n] * weights[n] for n in weights)

    # 映射到 0-1: CV 越低 → AI 分数越高
    # 人类论文 CV 通常在 0.3-0.6
    # AI 论文 CV 通常在 0.05-0.2
    if weighted_cv < 0.1:
        consistency_score = 0.9   # 极其一致 → 很可能 AI
    elif weighted_cv < 0.2:
        consistency_score = 0.7
    elif weighted_cv < 0.3:
        consistency_score = 0.5
    elif weighted_cv < 0.4:
        consistency_score = 0.3
    else:
        consistency_score = 0.1   # 风格多变 → 像人类

    # 诊断信息
    slop_cv = cross_cvs["slop_density"]
    trans_cv = cross_cvs["transition_density"]
    sent_cv = cross_cvs["sentence_cv"]

    if slop_cv < 0.15:
        slop_pattern = f"Slop词分布高度一致 (CV={slop_cv:.2f}) — 各章节slop词密度几乎相同，AI典型特征"
    elif slop_cv < 0.3:
        slop_pattern = f"Slop词分布较一致 (CV={slop_cv:.2f})"
    else:
        slop_pattern = f"Slop词分布有自然波动 (CV={slop_cv:.2f}) — 人类写作特征"

    if trans_cv < 0.15:
        transition_pattern = f"过渡词使用高度一致 (CV={trans_cv:.2f}) — AI典型特征"
    elif trans_cv < 0.3:
        transition_pattern = f"过渡词使用较一致 (CV={trans_cv:.2f})"
    else:
        transition_pattern = f"过渡词使用有自然变化 (CV={trans_cv:.2f}) — 人类写作特征"

    if sent_cv < 0.15:
        sentence_length_pattern = f"句长分布高度一致 (CV={sent_cv:.2f}) — AI章节间句式过于均匀"
    elif sent_cv < 0.3:
        sentence_length_pattern = f"句长分布较一致 (CV={sent_cv:.2f})"
    else:
        sentence_length_pattern = f"句长分布有自然变化 (CV={sent_cv:.2f}) — 人类写作特征"

    details = []
    for v in vectors:
        details.append({
            "chapter": v.chapter_type,
            "sent_len_avg": round(v.avg_sentence_length, 1),
            "sent_len_cv": round(v.sentence_length_cv, 3),
            "slop_density": round(v.slop_word_density, 3),
            "transition_density": round(v.transition_density, 3),
            "char_count": v.char_count,
        })

    return ConsistencyReport(
        overall_score=round(consistency_score, 3),
        style_variance=round(weighted_cv, 3),
        slop_pattern=slop_pattern,
        transition_pattern=transition_pattern,
        sentence_length_pattern=sentence_length_pattern,
        chapter_count=len(active_chapters),
        analyzed_count=len(vectors),
        details=details,
    )


# ============================================================
# 4. 综合检测报告
# ============================================================

@dataclass
class ThesisDetectionReport:
    """三层检测综合报告"""
    # 文档级
    overall_ai_score: float
    overall_verdict: str
    risk_level: str

    # 章节级
    chapter_scores: list[dict]

    # 一致性
    consistency: ConsistencyReport | None

    # 段落级
    paragraph_count: int
    ai_paragraph_count: int
    suspicious_spans: list[dict]

    # 元数据
    total_chars: int
    chapter_count: int
    detection_method: str


async def detect_thesis(text: str) -> ThesisDetectionReport:
    """论文综合检测 — 三层分析"""
    from app.services.text_service import detect_text as detect_segment

    # 1. 章节解析
    chapters = parse_chapters(text)
    if not chapters:
        # 退化为整段检测
        result = await detect_segment(text[:5000], {"explain": False})
        return ThesisDetectionReport(
            overall_ai_score=result.confidence,
            overall_verdict="AI生成" if result.is_ai_generated else "人类写作",
            risk_level="high" if result.confidence > 0.7 else "medium" if result.confidence > 0.3 else "low",
            chapter_scores=[],
            consistency=None,
            paragraph_count=1,
            ai_paragraph_count=1 if result.is_ai_generated else 0,
            suspicious_spans=[],
            total_chars=len(text),
            chapter_count=0,
            detection_method="fallback_single_pass",
        )

    # 2. 逐章节检测
    chapter_scores = []
    all_paragraph_scores = []
    total_ai_paras = 0
    total_paras = 0

    for ch in chapters:
        if ch.is_skip:
            chapter_scores.append({
                "chapter_type": ch.chapter_type,
                "title": ch.title,
                "score": 0.0,
                "is_skipped": True,
                "char_count": ch.char_count,
            })
            continue

        # 对长度足够的章节逐段检测
        para_scores = []
        for para in ch.paragraphs:
            if len(para) < 30:
                continue
            result = await detect_segment(para[:1500], {"explain": False})
            para_scores.append(result.confidence)
            total_paras += 1
            if result.is_ai_generated:
                total_ai_paras += 1

        # 章节得分 = 段落平均
        ch_score = statistics.mean(para_scores) if para_scores else 0.5
        chapter_scores.append({
            "chapter_type": ch.chapter_type,
            "title": ch.title,
            "score": round(ch_score, 4),
            "paragraph_count": len(para_scores),
            "ai_paragraph_count": sum(1 for s in para_scores if s > 0.3),
            "char_count": ch.char_count,
            "paragraph_scores": [round(s, 3) for s in para_scores],
        })
        all_paragraph_scores.extend(para_scores)

    # 3. 跨章节一致性
    consistency = analyze_cross_chapter_consistency(chapters)

    # 4. 综合评分
    if all_paragraph_scores:
        avg_content_score = statistics.mean(all_paragraph_scores)
        # 一致性调整
        consistency_penalty = 0
        if consistency:
            # 高一致性 + 中等内容分数 → 更可能是 AI
            # 高一致性 + 低内容分数 → 可能是格式规范的人类论文
            if consistency.overall_score > 0.6 and avg_content_score > 0.4:
                consistency_penalty = 0.15  # 加分：太一致了
            elif consistency.overall_score > 0.6 and avg_content_score <= 0.4:
                consistency_penalty = -0.05  # 减分：人类规范性写作

        overall = avg_content_score + consistency_penalty
        overall = max(0.0, min(1.0, overall))
    else:
        overall = 0.5

    # 判定
    if overall > 0.6:
        verdict = "高度疑似 AI 生成"
    elif overall > 0.3:
        verdict = "部分段落疑似 AI 生成，建议人工复核"
    else:
        verdict = "以人类写作为主"

    risk = "high" if overall > 0.6 else "medium" if overall > 0.3 else "low"

    return ThesisDetectionReport(
        overall_ai_score=round(overall, 4),
        overall_verdict=verdict,
        risk_level=risk,
        chapter_scores=chapter_scores,
        consistency=consistency,
        paragraph_count=total_paras,
        ai_paragraph_count=total_ai_paras,
        suspicious_spans=[],
        total_chars=len(text),
        chapter_count=len(chapters),
        detection_method="hierarchical_3tier_chapter_aware",
    )
