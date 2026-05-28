"""
局部人类化器 — 在文本中注入人类写作特征

目标:
  - 过程性描述: 添加实验/研究过程细节
  - 轻微冗余: 人类写作的自然回指和重复
  - 非线性解释: 插入括号补充、脚注式说明
  - 经验性表达: "在实际操作中""根据经验"等
  - 不确定性表达: "可能""大致""某种程度上"

这些变换针对的是 unigram_entropy、hapax_ratio、yule_k 等词汇多样性特征
"""

import re
import random
from dataclasses import dataclass, field


@dataclass
class HumanizeResult:
    text: str
    operations: list[str] = field(default_factory=list)


# 过程性描述片段 — 可插入到方法/实验段落
_PROCESS_INSERTS = [
    "在实际操作过程中，",
    "具体实施时我们发现，",
    "经过多轮调试后，",
    "在反复验证的基础上，",
    "基于前期的预实验结果，",
    "参考已有文献的做法，",
    "为确保结果的可靠性，",
    "在样本筛选阶段，",
]

# 非线性补充 — 括号内的补充说明
_ASIDE_TEMPLATES = [
    "（这一点在后续讨论中还会涉及）",
    "（相关数据见附录）",
    "（限于篇幅不做展开）",
    "（此处仅列出主要结果）",
    "（详细推导过程参见参考文献[X]）",
    "（类似的结论在其他研究中也有报道）",
    "（该方法的局限性将在下节讨论）",
]

# 经验性表达
_EXPERIENCE_PHRASES = [
    "根据我们的经验",
    "在实践中",
    "从实际应用来看",
    "就目前的观察而言",
    "以我们团队的经验来看",
    "从多次实验的结果来看",
]

# 不确定性修饰词
_HEDGING_WORDS = {
    "表明": ["似乎表明", "初步表明", "在一定程度上表明"],
    "证明": ["暗示", "间接证明", "部分证明"],
    "导致": ["可能促使", "在某种程度上引发", "大体上导致"],
    "显著": ["较为明显", "有一定幅度的", "在统计上可观察到的"],
    "完全": ["在很大程度上", "基本", "近乎"],
    "总是": ["通常", "在多数情况下", "往往"],
    "必然": ["大概率", "倾向于", "一般会"],
}


def add_process_descriptions(text: str, max_inserts: int = 2) -> HumanizeResult:
    """在方法/实验相关段落中插入过程性描述"""
    sentences = _split_sentences(text)
    if len(sentences) < 4:
        return HumanizeResult(text=text)

    ops = []
    # 找到可能的方法/实验段落（包含关键词的句子之后）
    method_keywords = ["实验", "方法", "步骤", "流程", "测试", "分析", "数据", "样本", "模型"]
    insert_positions = []
    for i, s in enumerate(sentences):
        if any(kw in s for kw in method_keywords) and i + 1 < len(sentences):
            insert_positions.append(i + 1)

    if not insert_positions:
        return HumanizeResult(text=text)

    # 随机选最多 max_inserts 个位置插入
    random.shuffle(insert_positions)
    inserted = 0
    offset = 0
    for pos in insert_positions[:max_inserts]:
        if inserted >= max_inserts:
            break
        actual = pos + offset
        if actual < len(sentences):
            prefix = random.choice(_PROCESS_INSERTS)
            sentences[actual] = prefix + sentences[actual]
            ops.append(f"插入过程描述(句{actual})")
            inserted += 1
            offset += 1

    return PerturbationResult_with_text(sentences, ops)


def add_asides(text: str, max_asides: int = 1) -> HumanizeResult:
    """在适当位置插入括号补充说明"""
    sentences = _split_sentences(text)
    if len(sentences) < 5:
        return HumanizeResult(text=text)

    ops = []
    # 在较长的句子后插入
    long_indices = [i for i, s in enumerate(sentences) if len(s) > 30 and i < len(sentences) - 1]
    if not long_indices:
        return HumanizeResult(text=text)

    random.shuffle(long_indices)
    for idx in long_indices[:max_asides]:
        aside = random.choice(_ASIDE_TEMPLATES)
        # 在句号前插入
        s = sentences[idx]
        if s.endswith(("。", "！", "？")):
            sentences[idx] = s[:-1] + aside + s[-1]
        else:
            sentences[idx] = s + aside
        ops.append(f"插入括号补充(句{idx})")

    return PerturbationResult_with_text(sentences, ops)


def add_experience_expressions(text: str, max_inserts: int = 1) -> HumanizeResult:
    """在论述段落中加入经验性表达"""
    sentences = _split_sentences(text)
    if len(sentences) < 4:
        return HumanizeResult(text=text)

    ops = []
    # 找到论述性段落（包含"因此""所以""可以""能够"等）
    disc_keywords = ["因此", "所以", "可以", "能够", "表明", "说明", "显示", "证明"]
    candidates = [i for i, s in enumerate(sentences) if any(kw in s for kw in disc_keywords)]
    if not candidates:
        return HumanizeResult(text=text)

    random.shuffle(candidates)
    for idx in candidates[:max_inserts]:
        phrase = random.choice(_EXPERIENCE_PHRASES)
        sentences[idx] = phrase + "，" + sentences[idx]
        ops.append(f"插入经验表达(句{idx})")

    return PerturbationResult_with_text(sentences, ops)


def apply_hedging(text: str) -> HumanizeResult:
    """将绝对化表述替换为不确定性表述"""
    result = text
    ops = []
    for word, alternatives in _HEDGING_WORDS.items():
        if word in result and random.random() < 0.4:
            alt = random.choice(alternatives)
            result = result.replace(word, alt, 1)
            ops.append(f"弱化表述「{word}」→「{alt}」")

    return HumanizeResult(text=result, operations=ops)


def apply_all_humanization(text: str) -> HumanizeResult:
    """依次应用所有人类化变换"""
    all_ops = []
    current = text

    r = add_process_descriptions(current)
    current = r.text
    all_ops.extend(r.operations)

    r = add_asides(current)
    current = r.text
    all_ops.extend(r.operations)

    r = add_experience_expressions(current)
    current = r.text
    all_ops.extend(r.operations)

    r = apply_hedging(current)
    current = r.text
    all_ops.extend(r.operations)

    return HumanizeResult(text=current, operations=all_ops)


# ============================================================
# 内部辅助
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


def PerturbationResult_with_text(sentences: list[str], ops: list[str]) -> HumanizeResult:
    """从句子列表重建文本"""
    text = "".join(sentences)
    if not text.endswith(("。", "！", "？")):
        text += "。"
    return HumanizeResult(text=text, operations=ops)
