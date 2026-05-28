"""
自适应 LLM 改写器 — 根据特征差距动态生成 prompt 进行分段改写

核心思想:
  不使用通用 prompt，而是根据 FeatureGapAnalyzer 的结果，
  针对贡献度最高的特征生成具体改写指令。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.reducer.feature_analyzer import FeatureGap


@dataclass
class RewriteResult:
    text: str
    prompt_used: str
    chunk_count: int
    error: str | None = None


# 特征名 → 中文改写指令
_FEATURE_INSTRUCTIONS = {
    "slop_word_density": (
        "删除所有AI标志词（值得注意的是、综上所述、毫无疑问、显而易见、"
        "众所周知、毋庸置疑等），用更自然的表述替代"
    ),
    "transition_word_density": (
        "大幅减少显式过渡词（此外、另外、与此同时、从而、进而等），"
        "改用隐式逻辑连接或直接陈述"
    ),
    "idiom_density": (
        "减少四字成语和固定搭配的密集使用，"
        "用更口语化、更具体的表述替代程式化的四字词组"
    ),
    "bigram_repetition_rate": (
        "避免重复使用相同的词组搭配，"
        "对同一个概念使用不同的表述方式"
    ),
    "sentence_length_cv": (
        "大幅增加句式变化：混合使用短句（5-15字）和长句（40字以上），"
        "让句子长度差异明显，避免每句话都差不多长"
    ),
    "burstiness": (
        "增加句子复杂度的变化：交替使用简单短句和复杂长句，"
        "在几句话的平铺直叙后插入一个短促有力的断言，"
        "然后跟一个展开论述的长句"
    ),
    "punctuation_entropy": (
        "丰富标点符号的使用：不要只用逗号和句号，"
        "适当使用分号、冒号、破折号、括号、省略号等"
    ),
    "unigram_entropy": (
        "增加用词多样性：避免反复使用相同的词汇，"
        "用同义词、近义词、具体名词替换高频重复词"
    ),
    "zipf_deviation": (
        "让词频分布更自然：减少高频词的过度使用，"
        "增加低频但准确的专业词汇"
    ),
    "hapax_ratio": (
        "增加只出现一次的词汇比例：引入更多独特、"
        "具体的词汇表达，减少通用词的反复出现"
    ),
    "yule_k": (
        "降低词汇集中度：使用更多样化的词汇，"
        "避免少数词汇反复出现"
    ),
}

# 通用学术改写系统 prompt
_SYSTEM_PROMPT = (
    "你是学术论文写作优化助手。你的任务是将AI生成的学术文本改写为更自然的人类写作风格。\n"
    "核心要求:\n"
    "1. 保持学术严谨性和专业术语的准确性\n"
    "2. 保持原文的核心论点和逻辑结构不变\n"
    "3. 按照下方的具体指令针对性改写\n"
    "4. 直接输出改写后的文本，不加任何说明、注释或前缀\n"
    "5. 改写后的文本字数应与原文大致相当"
)


def build_rewrite_prompt(gaps: list[FeatureGap], max_instructions: int = 4) -> str:
    """根据特征差距生成针对性改写指令"""
    # 取优先级最高的几个特征
    top_gaps = [g for g in gaps if g.ai_contribution > 0.3][:max_instructions]

    if not top_gaps:
        return "请将以下文本改写为更自然的人类写作风格，保持原意不变。"

    instructions = []
    for gap in top_gaps:
        feat_instr = _FEATURE_INSTRUCTIONS.get(gap.feature_name, "")
        if feat_instr:
            instructions.append(
                f"- {feat_instr}（当前该特征AI贡献度: {gap.ai_contribution:.0%}）"
            )

    if not instructions:
        return "请将以下文本改写为更自然的人类写作风格，保持原意不变。"

    return "请重点从以下方面改写文本:\n" + "\n".join(instructions)


def split_into_chunks(text: str, max_chunk: int = 2500) -> list[str]:
    """按段落边界分段，每段不超过 max_chunk 字符"""
    paragraphs = text.split("\n")
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 1 > max_chunk and current:
            chunks.append(current.strip())
            current = p
        else:
            current = current + "\n" + p if current else p
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


async def rewrite_with_llm(
    text: str,
    gaps: list[FeatureGap],
    api_key: str,
    api_base: str,
    model: str,
    temperature: float = 0.8,
    iteration: int = 0,
) -> RewriteResult:
    """使用 LLM 进行特征感知的文本改写"""
    try:
        import httpx
        from openai import OpenAI
    except ImportError:
        return RewriteResult(text=text, prompt_used="", chunk_count=0, error="openai 库未安装")

    # 清除代理环境变量
    import os
    for key in list(os.environ.keys()):
        if key.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            os.environ.pop(key, None)

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_base,
            http_client=httpx.Client(proxy=None, timeout=60.0),
        )
    except Exception as e:
        return RewriteResult(text=text, prompt_used="", chunk_count=0, error=f"LLM客户端初始化失败: {e}")

    user_instruction = build_rewrite_prompt(gaps)
    temp = min(temperature + iteration * 0.08, 1.3)
    chunks = split_into_chunks(text)
    rewritten_chunks = []
    prompt_preview = user_instruction[:200]

    for chunk in chunks:
        if len(chunk.strip()) < 20:
            rewritten_chunks.append(chunk)
            continue
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"{user_instruction}\n\n原文：{chunk}"},
                ],
                max_tokens=2500,
                temperature=temp,
                timeout=45,
            )
            result = r.choices[0].message.content.strip()
            if len(result) < 10:
                rewritten_chunks.append(chunk)  # 改写失败，保留原文
            else:
                rewritten_chunks.append(result)
        except Exception:
            rewritten_chunks.append(chunk)  # API 失败，保留原文

    final_text = "\n".join(rewritten_chunks)
    return RewriteResult(
        text=final_text,
        prompt_used=prompt_preview,
        chunk_count=len(chunks),
    )
