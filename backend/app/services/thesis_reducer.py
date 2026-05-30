"""
论文降 AIGC 主编排器 — 特征感知的对抗生成系统

流程:
  1. 检测原始文本 → 获取 StatisticalFeatures + AI 置信度
  2. FeatureGapAnalyzer 分析特征差距，确定优化方向
  3. StructuralPerturbator 结构扰动（句长/节奏/过渡词/重复率）
     → 每步检测 + 回滚
  4. LocalHumanizer 局部人类化（过程描述/冗余/非线性）
     → 每步检测 + 回滚
  5. AdaptiveLLMRewriter 分段改写（动态 prompt / 温度递增）
     → 每轮检测 + 回滚
  6. 生成 ReduceReport
"""

from __future__ import annotations

import asyncio
import hashlib
import time

from loguru import logger

from app.services.reducer.feature_analyzer import analyze_features, FeatureGap
from app.services.reducer.structural_perturbator import (
    perturb_slop_words,
    perturb_transitions,
    perturb_sentence_lengths,
    perturb_rhythm,
    perturb_repetitions,
)
from app.services.reducer.local_humanizer import (
    add_process_descriptions,
    add_asides,
    add_experience_expressions,
    apply_hedging,
)
from app.services.reducer.adaptive_rewriter import rewrite_with_llm
from app.services.reducer.diff_reporter import (
    ReduceReport,
    ReduceStep,
    FeatureSnapshot,
    ChangeRecord,
)


async def _detect_full(text: str) -> tuple[float, dict]:
    """全 4 路检测 — 用于初始/最终/LLM 前的关键检查点 (~2-5s)"""
    from app.services.text_service import detect_text as do_detect
    try:
        result = await asyncio.wait_for(do_detect(text, {"explain": True}), timeout=90)
    except asyncio.TimeoutError:
        logger.warning("[reducer] Full detection timed out (90s), falling back to fast")
        return await _detect_fast(text)
    features = {}
    if hasattr(result, "explanation_data") and isinstance(result.explanation_data, dict):
        features = result.explanation_data.get("statistical_features", {})
    return result.confidence, features


async def _detect_fast(text: str) -> tuple[float, dict]:
    """纯统计特征检测 — 用于中间步骤的快速回滚判断 (~5ms)"""
    from app.services.reducer.fast_detect import detect_statistical_only
    result = detect_statistical_only(text)
    return result.confidence, {}


# 结果缓存: 避免重复检测相同文本
_detection_cache: dict[str, tuple[float, dict, float]] = {}
_CACHE_TTL = 600  # 10 分钟


async def _detect_full_cached(text: str) -> tuple[float, dict]:
    """带缓存的全 4 路检测，相同时限内相同文本直接返回缓存结果"""
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    now = time.time()
    if key in _detection_cache:
        conf, feat, ts = _detection_cache[key]
        if now - ts < _CACHE_TTL:
            return conf, feat
    result = await _detect_full(text)
    _detection_cache[key] = (result[0], result[1], now)
    return result


# 默认检测函数：用 fast 做回滚判断
_detect = _detect_fast


def _make_snapshot(confidence: float, features: dict) -> FeatureSnapshot:
    return FeatureSnapshot(ai_confidence=confidence, features=features)


async def _run_step(
    step_name: str,
    transform_fn,
    current_text: str,
    original_text: str,
    max_rollback: bool = True,
    use_full: bool = False,
) -> tuple[str, ReduceStep]:
    """执行一步变换，检测效果，必要时回滚

    Args:
        use_full: True 用全 4 路检测（关键检查点），False 用快速统计检测（中间回滚）
    """
    import asyncio

    detect_fn = _detect_full if use_full else _detect
    before_conf, before_feat = await detect_fn(current_text)
    before_snap = _make_snapshot(before_conf, before_feat)

    try:
        result = transform_fn(current_text)
        if asyncio.iscoroutine(result):
            result = await result
        new_text = result.text
        changes_desc = (
            result.operations if hasattr(result, "operations")
            else [f"LLM改写({result.chunk_count}段)"] if hasattr(result, "chunk_count") else []
        )
        if hasattr(result, "error") and result.error:
            changes_desc = [f"LLM警告: {result.error}"]
    except Exception as e:
        logger.error(f"Step {step_name} failed: {e}")
        step = ReduceStep(
            step_name=step_name,
            before=before_snap,
            after=before_snap,
            error=str(e)[:100],
        )
        return current_text, step

    if not new_text or len(new_text.strip()) < 20:
        step = ReduceStep(
            step_name=step_name,
            before=before_snap,
            after=before_snap,
            error="变换结果过短，跳过",
        )
        return current_text, step

    after_conf, after_feat = await detect_fn(new_text)
    after_snap = _make_snapshot(after_conf, after_feat)

    changes = [ChangeRecord(category="transform", description=desc) for desc in changes_desc]

    # 回滚阈值: fast 检测精度较低，收紧到 +0.02 以补偿
    rollback_margin = 0.02 if not use_full else 0.01
    rolled_back = False
    if max_rollback and after_conf > before_conf + rollback_margin:
        logger.info(f"Step {step_name}: AI rate increased ({before_conf:.3f} → {after_conf:.3f}), rolling back")
        rolled_back = True
        after_snap = before_snap
        new_text = current_text

    step = ReduceStep(
        step_name=step_name,
        before=before_snap,
        after=after_snap,
        changes=changes,
        rolled_back=rolled_back,
    )
    return new_text, step


async def reduce_thesis(
    text: str,
    max_llm_iterations: int = 3,
    api_key: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
    skip_humanize: bool = False,
    skip_hedging: bool = False,
    max_slop_removal: float = 1.0,
    llm_temperature: float = 0.8,
) -> ReduceReport:
    """
    主入口: 执行完整的论文降 AIGC 流程

    Args:
        text: 原始论文文本
        max_llm_iterations: LLM 改写最大迭代次数
        api_key/api_base/model: LLM 配置 (为 None 时自动从 settings 读取)
        skip_humanize: 跳过人类化阶段 (方法论/摘要等正式章节)
        skip_hedging: 跳过弱化绝对表述 (方法论需要精确)
        max_slop_removal: slop 词删除比例 (0.0-1.0)
        llm_temperature: LLM 改写温度

    Returns:
        ReduceReport 完整报告
    """
    # 初始检测 (全 4 路 — 关键检查点)
    orig_conf, orig_feat = await _detect_full_cached(text)
    orig_snap = _make_snapshot(orig_conf, orig_feat)

    # 特征分析
    gaps = analyze_features(orig_feat)
    gaps_dict = [
        {
            "feature_name": g.feature_name,
            "current_value": g.current_value,
            "ai_contribution": g.ai_contribution,
            "weight": g.weight,
            "priority": g.priority,
            "suggestion": g.suggestion,
        }
        for g in gaps
    ]

    # 如果原始 AI 率已经很低，直接返回
    if orig_conf < 0.3:
        final_snap = _make_snapshot(orig_conf, orig_feat)
        return ReduceReport(
            original_text=text,
            optimized_text=text,
            original_snapshot=orig_snap,
            final_snapshot=final_snap,
            steps=[],
            feature_gaps=gaps_dict,
        )

    current_text = text
    steps: list[ReduceStep] = []

    # Phase 1: 结构扰动 (逐个操作，每个都检测+回滚)
    import functools
    slop_fn = functools.partial(perturb_slop_words, removal_ratio=max_slop_removal)
    structural_ops = [
        ("删除AI标志词", slop_fn),
        ("替换过渡词", perturb_transitions),
        ("句长扰动", perturb_sentence_lengths),
        ("节奏扰动", perturb_rhythm),
        ("降低重复率", perturb_repetitions),
    ]
    for op_name, op_fn in structural_ops:
        current_text, step = await _run_step(op_name, op_fn, current_text, text)
        steps.append(step)
        # 如果已经低于阈值，提前终止
        if step.after.ai_confidence < 0.3 and not step.rolled_back:
            break

    # Phase 2: 局部人类化 (按章节策略跳过)
    humanize_ops = []
    if not skip_humanize:
        humanize_ops.extend([
            ("插入过程描述", add_process_descriptions),
            ("插入括号补充", add_asides),
            ("插入经验表达", add_experience_expressions),
        ])
    if not skip_hedging:
        humanize_ops.append(("弱化绝对表述", apply_hedging))
    for op_name, op_fn in humanize_ops:
        current_text, step = await _run_step(op_name, op_fn, current_text, text)
        steps.append(step)
        if step.after.ai_confidence < 0.3 and not step.rolled_back:
            break

    # Phase 3: LLM 改写 (如果配置了 LLM)
    if api_key:
        for i in range(max_llm_iterations):
            current_conf = steps[-1].after.ai_confidence if steps else orig_conf
            if current_conf < 0.3:
                break

            # 重新分析特征差距，动态生成 prompt (全 4 路 — LLM 前关键检查)
            conf, feat = await _detect_full_cached(current_text)
            gaps = analyze_features(feat)

            async def llm_transform(t: str):
                return await rewrite_with_llm(
                    t, gaps, api_key, api_base or "", model or "",
                    temperature=llm_temperature, iteration=i,
                )

            current_text, step = await _run_step(
                f"LLM改写-轮{i+1}", llm_transform, current_text, text, use_full=True
            )
            steps.append(step)

            if step.after.ai_confidence < 0.3:
                break

    # 最终检测 (全 4 路 — 关键检查点)
    final_conf, final_feat = await _detect_full_cached(current_text)
    final_snap = _make_snapshot(final_conf, final_feat)

    return ReduceReport(
        original_text=text,
        optimized_text=current_text,
        original_snapshot=orig_snap,
        final_snapshot=final_snap,
        steps=steps,
        feature_gaps=gaps_dict,
    )


# ============================================================
# 章节类型感知策略 — 不同章节有不同的优化偏好
# ============================================================

def _get_chapter_strategy(chapter_type: str) -> dict:
    """按章节类型返回差异化优化参数"""
    strategies = {
        "methodology": {
            "skip_humanize": True,      # 方法论不加"我觉得"类口语
            "skip_hedging": True,        # 方法论需要精确，不弱化
            "max_slop_removal": 0.5,     # 方法论可能有规范表述，少删
            "llm_temperature": 0.6,      # 低温度，保持专业性
        },
        "experiment": {
            "skip_humanize": False,
            "skip_hedging": False,
            "max_slop_removal": 0.8,
            "llm_temperature": 0.7,
        },
        "discussion": {
            "skip_humanize": False,
            "skip_hedging": False,
            "max_slop_removal": 1.0,     # 讨论区可以大胆删
            "llm_temperature": 0.9,
        },
        "abstract": {
            "skip_humanize": True,       # 摘要要正式
            "skip_hedging": False,
            "max_slop_removal": 1.0,
            "llm_temperature": 0.8,
        },
        "introduction": {
            "skip_humanize": False,
            "skip_hedging": False,
            "max_slop_removal": 0.9,
            "llm_temperature": 0.8,
        },
        "conclusion": {
            "skip_humanize": False,
            "skip_hedging": False,
            "max_slop_removal": 1.0,
            "llm_temperature": 0.85,
        },
        "literature_review": {
            "skip_humanize": True,       # 文献综述要客观
            "skip_hedging": True,
            "max_slop_removal": 0.7,
            "llm_temperature": 0.7,
        },
    }
    return strategies.get(chapter_type, {
        "skip_humanize": False,
        "skip_hedging": False,
        "max_slop_removal": 1.0,
        "llm_temperature": 0.8,
    })

async def reduce_thesis_chapter_aware(
    text: str,
    max_llm_iterations: int = 3,
    api_key: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
) -> ReduceReport:
    """
    章节感知降 AIGC:
      1. 解析章节结构
      2. 记录优化前各章 StyleVector
      3. 对每章独立调用 reduce_thesis()
      4. 重组优化后章节
      5. 检查是否保留了自然的跨章风格差异

    若无章节结构（或仅 1 章），回退到扁平模式。
    """
    from app.services.thesis_detector import parse_chapters, extract_style_vector
    import statistics

    chapters = parse_chapters(text)
    active = [c for c in chapters if not c.is_skip and c.char_count >= 100]

    # 章节不足时回退
    if len(active) < 2:
        return await reduce_thesis(text, max_llm_iterations, api_key, api_base, model)

    # 记录优化前的跨章风格
    pre_vectors = {}
    for ch in active:
        sv = extract_style_vector(ch)
        if sv:
            pre_vectors[ch.chapter_type] = sv

    # 逐章独立优化 (应用章节类型策略)
    optimized_parts = []
    all_steps = []
    all_gaps = []
    chapter_reports = []

    for ch in chapters:
        if ch.is_skip or ch.char_count < 100:
            optimized_parts.append(ch.full_text)
            continue

        strategy = _get_chapter_strategy(ch.chapter_type)
        ch_text = ch.full_text
        ch_report = await reduce_thesis(
            ch_text, max_llm_iterations, api_key, api_base, model,
            skip_humanize=strategy["skip_humanize"],
            skip_hedging=strategy["skip_hedging"],
            max_slop_removal=strategy["max_slop_removal"],
            llm_temperature=strategy["llm_temperature"],
        )
        optimized_parts.append(ch_report.optimized_text)
        all_steps.extend(ch_report.steps)
        all_gaps.extend(ch_report.feature_gaps)
        chapter_reports.append({
            "chapter_type": ch.chapter_type,
            "title": ch.title,
            "original_confidence": ch_report.original_snapshot.ai_confidence,
            "final_confidence": ch_report.final_snapshot.ai_confidence,
            "steps_count": len(ch_report.steps),
        })

    optimized_text = "\n\n".join(optimized_parts)

    # 检查优化后是否保留了自然的跨章风格差异
    post_chapters = parse_chapters(optimized_text)
    post_active = [c for c in post_chapters if not c.is_skip and c.char_count >= 100]
    post_vectors = {}
    for ch in post_active:
        sv = extract_style_vector(ch)
        if sv:
            post_vectors[ch.chapter_type] = sv

    # 计算跨章句长 CV 变化
    style_check = _check_style_variation(pre_vectors, post_vectors)

    # 全文最终检测
    final_conf, final_feat = await _detect_full_cached(optimized_text)
    orig_conf, orig_feat = await _detect_full_cached(text)

    return ReduceReport(
        original_text=text,
        optimized_text=optimized_text,
        original_snapshot=_make_snapshot(orig_conf, orig_feat),
        final_snapshot=_make_snapshot(final_conf, final_feat),
        steps=all_steps,
        feature_gaps=all_gaps,
    )


def _check_style_variation(
    pre: dict, post: dict
) -> dict:
    """检查优化前后跨章风格变异是否保持自然"""
    import statistics

    common_types = set(pre.keys()) & set(post.keys())
    if len(common_types) < 2:
        return {"status": "insufficient_chapters"}

    pre_sent_lens = [pre[t].avg_sentence_length for t in common_types]
    post_sent_lens = [post[t].avg_sentence_length for t in common_types]

    pre_cv = statistics.stdev(pre_sent_lens) / statistics.mean(pre_sent_lens) if statistics.mean(pre_sent_lens) > 0 else 0
    post_cv = statistics.stdev(post_sent_lens) / statistics.mean(post_sent_lens) if statistics.mean(post_sent_lens) > 0 else 0

    # 如果优化后 CV 下降超过 50%，警告风格趋同
    convergence_warning = post_cv < pre_cv * 0.5 and pre_cv > 0.1

    return {
        "pre_sentence_length_cv": round(pre_cv, 4),
        "post_sentence_length_cv": round(post_cv, 4),
        "convergence_warning": convergence_warning,
        "status": "converged" if convergence_warning else "natural_variation_preserved",
    }
