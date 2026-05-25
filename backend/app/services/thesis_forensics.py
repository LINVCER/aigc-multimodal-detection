"""
论文取证分析 — 引用验证 + 数据具体性

不需要训练的纯统计特征，直接用于论文检测增强。

1. 引用验证: AI 编造引用模式 vs 真实引用
2. 数据具体性: 具体数字 vs 模糊描述的比值
3. 逻辑链完整性: 章节间逻辑衔接质量
"""

import re, math
from dataclasses import dataclass, field
from collections import Counter


# ============================================================
# 1. 引用验证
# ============================================================

@dataclass
class CitationReport:
    """引用分析报告"""
    total_citations: int
    unique_citations: int
    density: float              # 每千字引用数
    pattern_entropy: float      # 引用模式熵 (低=AI, 高=人类)
    generic_ratio: float        # 泛化引用比例 "[1]" vs 具体 "[3,5-7]"
    consecutive_pattern: str    # 连续引用模式诊断
    suspicion_score: float      # 0-1, 越高越可疑


CITATION_RE = re.compile(r'\[(\d+(?:[,，\s]*\d+)*|\d+[-–—]\d+)\]')


def analyze_citations(text: str) -> CitationReport | None:
    """分析论文引用模式"""
    citations = CITATION_RE.findall(text)
    if not citations:
        return None

    total = len(citations)
    # 提取所有引用编号
    all_refs = []
    for c in citations:
        parts = re.split(r'[,，\s]+', c)
        for p in parts:
            p = p.strip()
            if '-' in p or '–' in p or '—' in p:
                try:
                    rng = re.split(r'[-–—]', p)
                    start, end = int(rng[0]), int(rng[1])
                    all_refs.extend(range(start, end + 1))
                except ValueError:
                    continue
            else:
                try:
                    all_refs.append(int(p))
                except ValueError:
                    continue

    unique = len(set(all_refs))

    # 密度: 每千字引用数
    density = total / max(len(text) / 1000, 1)

    # 引用模式熵 (衡量引用分布的多样性)
    if all_refs:
        ref_counter = Counter(all_refs)
        total_refs = len(all_refs)
        entropy = -sum(
            (c / total_refs) * math.log2(c / total_refs)
            for c in ref_counter.values()
        )
    else:
        entropy = 0

    # 泛化引用比例: 单引用 "[1]" vs 范围引用 "[3-7]"
    single_count = sum(1 for c in citations if re.match(r'^\d+$', c.strip()))
    generic_ratio = single_count / max(total, 1)

    # AI 特征: 高泛化比例 + 低熵 = 编造引用
    if density > 5 and generic_ratio > 0.6 and entropy < 3:
        consecutive_pattern = "引用密度高但模式单一 — AI 编造引用典型特征"
        suspicion = 0.8
    elif generic_ratio > 0.5 and entropy < 4:
        consecutive_pattern = "引用多为单一编号,缺少范围引用 — 可疑"
        suspicion = 0.6
    elif density < 1:
        consecutive_pattern = "引用密度极低"
        suspicion = 0.1
    else:
        consecutive_pattern = "引用模式自然,范围引用和单引用混合"
        suspicion = 0.2

    return CitationReport(
        total_citations=total,
        unique_citations=unique,
        density=round(density, 2),
        pattern_entropy=round(entropy, 2),
        generic_ratio=round(generic_ratio, 2),
        consecutive_pattern=consecutive_pattern,
        suspicion_score=round(suspicion, 2),
    )


# ============================================================
# 2. 数据具体性
# ============================================================

@dataclass
class SpecificityReport:
    """数据具体性报告"""
    specificity_score: float     # 0-1, 越低越像 AI
    specific_numbers: int        # 具体数字出现次数 (12.3%, p<0.01)
    vague_phrases: int           # 模糊描述次数 (显著提升)
    ratio: float                 # 具体/模糊比值
    detail_level: str            # 详细度等级
    diagnosis: str


# 模糊 AI 套话
VAGUE_PATTERNS = [
    "显著提升", "大幅提高", "明显改善", "取得了较好的效果",
    "具有重要的理论意义", "具有广泛的应用前景",
    "有效的", "更好的", "较好的", "较强的",
    "一定程度的", "较为明显的", "比较显著的",
]

# 具体数据模式
SPECIFIC_PATTERNS = [
    r'\d+\.?\d*%',                          # 12.3%
    r'p\s*[<≤]\s*0\.\d+',                   # p < 0.01
    r'F1\s*[=＝]\s*0?\.?\d+',               # F1=0.93
    r'\d+\.?\d*\s*(ms|s|min|h)',            # 单位
    r'n\s*[=＝]\s*\d+',                      # n=100
    r'\d+\.?\d*\s*[倍个百分点]',              # 3倍, 5个百分点
    r'[=＝]\s*\d+\.\d+',                    # = 0.95
]


def analyze_specificity(text: str) -> SpecificityReport:
    """分析文本数据具体性"""
    specific_count = 0
    for pat in SPECIFIC_PATTERNS:
        specific_count += len(re.findall(pat, text, re.IGNORECASE))

    vague_count = 0
    for pat in VAGUE_PATTERNS:
        vague_count += text.count(pat)

    total = specific_count + vague_count
    ratio = specific_count / max(vague_count, 1)

    if ratio > 2.0:
        detail_level = "high"
        diagnosis = "数据具体明确,包含精确数值和统计指标 — 人类学术写作特征"
    elif ratio > 1.0:
        detail_level = "medium"
        diagnosis = "有具体数据但也有模糊表述"
    elif ratio > 0.3:
        detail_level = "low"
        diagnosis = "大量使用模糊表述,缺乏精确数据 — AI 论文常见特征"
    else:
        detail_level = "very_low"
        diagnosis = "几乎只有定性描述,严重缺乏数据支撑 — 高度可疑"

    return SpecificityReport(
        specificity_score=round(min(ratio / 3, 1), 2),
        specific_numbers=specific_count,
        vague_phrases=vague_count,
        ratio=round(ratio, 2),
        detail_level=detail_level,
        diagnosis=diagnosis,
    )


# ============================================================
# 3. 综合取证报告
# ============================================================

@dataclass
class ForensicReport:
    """论文取证综合报告"""
    citation: CitationReport | None
    specificity: SpecificityReport
    overall_risk: float          # 0-1
    risk_factors: list[str] = field(default_factory=list)
    human_indicators: list[str] = field(default_factory=list)


def analyze_thesis_forensics(text: str) -> ForensicReport:
    """论文取证综合分析"""
    citation = analyze_citations(text)
    specificity = analyze_specificity(text)

    risk_factors = []
    human_indicators = []
    risk = 0.0
    weight_sum = 0.0

    # 引用分析贡献
    if citation:
        w = 0.3
        weight_sum += w
        risk += citation.suspicion_score * w
        if citation.suspicion_score > 0.5:
            risk_factors.append(f"引用异常: {citation.consecutive_pattern}")
        else:
            human_indicators.append(f"引用正常: {citation.consecutive_pattern}")

    # 数据具体性贡献
    w = 0.5
    weight_sum += w
    risk += (1 - specificity.specificity_score) * w
    if specificity.detail_level in ("low", "very_low"):
        risk_factors.append(f"数据模糊: {specificity.diagnosis}")
    else:
        human_indicators.append(f"数据具体: {specificity.diagnosis}")

    # 归一化
    overall_risk = risk / max(weight_sum, 0.01)
    overall_risk = round(max(0.0, min(1.0, overall_risk)), 2)

    return ForensicReport(
        citation=citation,
        specificity=specificity,
        overall_risk=overall_risk,
        risk_factors=risk_factors,
        human_indicators=human_indicators,
    )
