"""
结构扰动器 — 通过规则变换改变文本的统计特征

目标特征及方向:
  - sentence_length_cv (方向 -1): 低值→AI → 增大句长变异系数
  - burstiness (方向 -1): 低值→AI → 增大句子复杂度变异
  - transition_word_density (方向 +1): 高值→AI → 降低过渡词密度
  - bigram_repetition_rate (方向 +1): 高值→AI → 降低短语重复率
  - slop_word_density (方向 +1): 高值→AI → 删除 AI 标志词
"""

import re
import random
from dataclasses import dataclass, field


@dataclass
class PerturbationResult:
    text: str
    operations: list[str] = field(default_factory=list)


# 中文 AI 标志词 (与 statistical_features.py 一致)
_SLOP_WORDS = [
    "值得注意的是", "总而言之", "综上所述", "在某种程度上",
    "不可否认", "从某种意义上说", "众所周知", "显而易见",
    "毋庸置疑", "毫无疑问", "总的来说", "关键的是",
    "重要的是要认识到", "从这个角度来看", "正如前面提到的",
    "需要指出的是", "在当今时代", "值得思考的是", "从更广的视角看",
    "这是一个很好的问题", "让我来解释", "需要澄清的是",
    "归根结底", "必须承认", "不言而喻", "由此可见",
    "进一步来说", "更重要的是", "必须指出", "需要强调的是",
]

# 中文过渡词 (与 statistical_features.py 一致)
_TRANSITION_WORDS = [
    "此外", "另外", "与此同时", "另一方面", "尽管如此",
    "从而", "进而", "加之", "何况", "再者",
    "总而言之", "综上所述", "归根结底",
]

# 隐式连接替代表 — 把显式过渡词替换为更自然的隐式逻辑
_IMPLICIT_REPLACEMENTS = {
    "此外": ["", "另一个方面是", "还有"],
    "另外": ["", "再看", "还有一点"],
    "与此同时": ["同一时期", "这也伴随着", ""],
    "另一方面": ["反过来", "换个角度看", ""],
    "尽管如此": ["但即便这样", "话说回来", ""],
    "从而": ["由此", "这使得", ""],
    "进而": ["随后", "在此基础上", ""],
    "加之": ["加上", "考虑到", ""],
    "何况": ["更不用说", "更何况"],
    "再者": ["其次", "还有一点"],
    "总而言之": ["说到底", "归结起来", ""],
    "综上所述": ["从以上分析来看", "回到整体来看", ""],
    "归根结底": ["说到底", "追根溯源"],
}


def perturb_slop_words(text: str, removal_ratio: float = 1.0) -> PerturbationResult:
    """删除 AI 标志词，清理多余标点

    Args:
        removal_ratio: 0.0-1.0，控制删除比例。1.0=全部删除，0.5=随机保留一半
    """
    result = text
    removed = []
    for slop in _SLOP_WORDS:
        if slop in result:
            count = result.count(slop)
            if removal_ratio >= 1.0:
                result = result.replace(slop, "")
                removed.append(f"{slop}×{count}")
            else:
                # 部分删除: 按 ratio 随机决定每次出现是否删除
                deleted = 0
                for _ in range(count):
                    if random.random() < removal_ratio:
                        result = result.replace(slop, "", 1)
                        deleted += 1
                if deleted:
                    removed.append(f"{slop}×{deleted}/{count}")

    # 清理因删除产生的多余标点
    result = re.sub(r"[，,]{2,}", "，", result)
    result = re.sub(r"[。.]{2,}", "。", result)
    result = re.sub(r"^[，,。.\s]+", "", result)
    # 清理句首多余标点
    result = re.sub(r"([。！？])\s*[，,]", r"\1", result)

    ops = [f"删除AI标志词: {', '.join(removed)}"] if removed else []
    return PerturbationResult(text=result, operations=ops)


def perturb_transitions(text: str) -> PerturbationResult:
    """将显式过渡词替换为隐式连接或直接删除"""
    result = text
    ops = []
    for tw in _TRANSITION_WORDS:
        if tw not in result:
            continue
        replacements = _IMPLICIT_REPLACEMENTS.get(tw, [""])
        # 逐个替换（不全部替换，保留一些自然感）
        count = result.count(tw)
        replaced = 0
        for _ in range(count):
            if tw in result and random.random() < 0.7:
                choice = random.choice(replacements)
                result = result.replace(tw, choice, 1)
                replaced += 1
        if replaced:
            ops.append(f"替换过渡词「{tw}」×{replaced}")

    # 清理多余标点
    result = re.sub(r"[，,]{2,}", "，", result)
    result = re.sub(r"^[，,。\s]+", "", result)
    return PerturbationResult(text=result, operations=ops)


def perturb_sentence_lengths(text: str) -> PerturbationResult:
    """增大句长变异系数: 合并短句、拆分长句"""
    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return PerturbationResult(text=text)

    ops = []
    # 策略1: 合并连续的很短的句子 (< 15字)
    merged = []
    i = 0
    while i < len(sentences):
        s = sentences[i]
        if len(s) < 15 and i + 1 < len(sentences) and len(sentences[i + 1]) < 30:
            # 合并两个短句
            combined = s.rstrip("，。！？,") + "，" + sentences[i + 1].lstrip()
            merged.append(combined)
            ops.append(f"合并短句({len(s)}+{len(sentences[i+1])}字)")
            i += 2
        else:
            merged.append(s)
            i += 1

    # 策略2: 拆分很长的句子 (> 60字)
    final = []
    for s in merged:
        if len(s) > 60:
            split_point = _find_split_point(s)
            if split_point > 10:
                part1 = s[:split_point].rstrip("，、；,;")
                part2 = s[split_point:].lstrip("，、；,;")
                final.extend([part1, part2])
                ops.append(f"拆分长句({len(s)}→{len(part1)}+{len(part2)}字)")
                continue
        final.append(s)

    result = "。".join(final)
    if not result.endswith(("。", "！", "？")):
        result += "。"
    return PerturbationResult(text=result, operations=ops)


def perturb_rhythm(text: str) -> PerturbationResult:
    """增大句子复杂度变异 (burstiness): 在连续中等句中插入短促句"""
    sentences = _split_sentences(text)
    if len(sentences) < 4:
        return PerturbationResult(text=text)

    ops = []
    # 计算各句长度
    lengths = [len(s) for s in sentences]
    mean_len = sum(lengths) / len(lengths)

    # 找到连续的"中等长度"句子（长度在均值±30%内），在其中插入短句
    final = []
    streak = 0
    for i, s in enumerate(sentences):
        final.append(s)
        if mean_len * 0.7 < len(s) < mean_len * 1.3:
            streak += 1
        else:
            streak = 0

        # 连续3句以上中等长度 → 插入一个短促句
        if streak >= 3 and random.random() < 0.5:
            # 从后续句子中提取一个短语作为短句
            shorty = _make_short_sentence(sentences, i)
            if shorty:
                final.append(shorty)
                ops.append(f"插入短促句({len(shorty)}字)")
                streak = 0

    result = "。".join(final)
    if not result.endswith(("。", "！", "？")):
        result += "。"
    return PerturbationResult(text=result, operations=ops)


def perturb_repetitions(text: str) -> PerturbationResult:
    """降低 bigram 重复率: 对重复出现的词组进行同义改写"""
    # 找到重复出现的中文词组 (2-4字)
    # 简化实现: 找重复的2字搭配并替换第二次及之后的出现
    bigrams = {}
    # 提取所有连续2字组合
    for i in range(len(text) - 1):
        bg = text[i:i+2]
        if '一' <= bg[0] <= '鿿' and '一' <= bg[1] <= '鿿':
            bigrams[bg] = bigrams.get(bg, 0) + 1

    # 找出出现3次以上的bigram
    frequent = {bg: cnt for bg, cnt in bigrams.items() if cnt >= 3}
    if not frequent:
        return PerturbationResult(text=text)

    ops = []
    result = text
    for bg, cnt in sorted(frequent.items(), key=lambda x: -x[1])[:5]:
        # 只替换第2次及之后的出现
        replacement = _synonym_bigram(bg)
        if replacement and replacement != bg:
            occurrences = 0
            first = result.find(bg)
            if first == -1:
                continue
            pos = first + len(bg)
            replaced = 0
            while pos < len(result):
                idx = result.find(bg, pos)
                if idx == -1:
                    break
                if random.random() < 0.5:
                    result = result[:idx] + replacement + result[idx+len(bg):]
                    replaced += 1
                    pos = idx + len(replacement)
                else:
                    pos = idx + len(bg)
            if replaced:
                ops.append(f"替换重复词组「{bg}」→「{replacement}」×{replaced}")

    return PerturbationResult(text=result, operations=ops)


def apply_all_perturbations(text: str) -> PerturbationResult:
    """依次应用所有结构扰动"""
    all_ops = []
    current = text

    # 1. 删除 AI 标志词
    r = perturb_slop_words(current)
    current = r.text
    all_ops.extend(r.operations)

    # 2. 替换过渡词
    r = perturb_transitions(current)
    current = r.text
    all_ops.extend(r.operations)

    # 3. 句长扰动
    r = perturb_sentence_lengths(current)
    current = r.text
    all_ops.extend(r.operations)

    # 4. 节奏扰动
    r = perturb_rhythm(current)
    current = r.text
    all_ops.extend(r.operations)

    # 5. 重复率降低
    r = perturb_repetitions(current)
    current = r.text
    all_ops.extend(r.operations)

    return PerturbationResult(text=current, operations=all_ops)


# ============================================================
# 内部辅助函数
# ============================================================

def _split_sentences(text: str) -> list[str]:
    """按中文句号/感叹号/问号分句"""
    parts = re.split(r"([。！？])", text)
    sentences = []
    i = 0
    while i < len(parts):
        s = parts[i].strip()
        if i + 1 < len(parts) and parts[i + 1] in ("。", "！", "？"):
            s += parts[i + 1]
            i += 2
        else:
            i += 1
        if len(s) >= 2:
            sentences.append(s)
    return sentences


def _find_split_point(sentence: str) -> int:
    """在长句中找到合适的拆分点（逗号、顿号等）"""
    # 优先在句中逗号处拆分
    mid = len(sentence) // 2
    # 在中间区域找最近的逗号
    best = -1
    for offset in range(0, mid // 2 + 1):
        for pos in [mid + offset, mid - offset]:
            if 0 < pos < len(sentence) and sentence[pos] in "，、；,":
                return pos + 1
    return -1


def _make_short_sentence(sentences: list[str], current_idx: int) -> str | None:
    """从上下文中构造一个短促有力的句子"""
    # 短句模板
    templates = [
        "事实并非如此", "这引出了一个关键问题", "数据说明一切",
        "但现实更加复杂", "值得注意的一个细节", "这恰恰是问题所在",
        "回到核心议题", "具体来看", "换个角度思考",
        "这一点常被忽略", "问题的关键在于", "这背后的逻辑很简单",
    ]
    if random.random() < 0.4:
        return random.choice(templates)
    return None


def _synonym_bigram(bigram: str) -> str | None:
    """为常见2字组合提供同义替换"""
    synonyms = {
        "研究": "探究", "分析": "剖析", "方法": "手段", "结果": "结论",
        "发展": "演变", "影响": "波及", "提高": "增强", "降低": "削减",
        "重要": "核心", "问题": "议题", "技术": "工艺", "系统": "体系",
        "效果": "成效", "数据": "数值", "过程": "流程", "目标": "方向",
        "关系": "关联", "变化": "变动", "水平": "程度", "情况": "状况",
        "方面": "维度", "进行": "展开", "实现": "达成", "利用": "借助",
        "通过": "经由", "基于": "立足于", "采用": "选用", "表明": "显示",
        "认为": "看来", "指出": "提到", "发现": "观察到", "提出": "给出",
    }
    return synonyms.get(bigram)
