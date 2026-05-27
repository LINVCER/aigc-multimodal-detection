"""文档上传 + 批量检测 API"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.api.deps import get_db, get_current_user, require_quota, deduct_quota
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/detect", tags=["文档"])


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("txt", "docx", "pdf"):
        raise HTTPException(status_code=400, detail=f"不支持 .{ext}")

    from app.utils.document_parser import parse_document
    try:
        text = parse_document(file.filename, await file.read())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {e}")

    return {"filename": file.filename, "char_count": len(text), "text": text}


# ============================================================
# 批量检测 — 企业级实现: 并行处理 + 进度追踪 + 历史管理
# ============================================================
import asyncio
import uuid as _uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field

@dataclass
class BatchState:
    batch_id: str
    user_id: str
    status: str = "pending"  # pending | processing | completed | cancelled | partial
    total: int = 0
    completed: int = 0
    results: list[dict] = field(default_factory=list)
    created_at: str = ""
    finished_at: str | None = None
    cancelled: bool = False

# 内存中的批处理状态 (生产环境可换 Redis)
_batch_store: dict[str, BatchState] = {}
MAX_CONCURRENT = 4  # 并行检测上限
MAX_FILE_SIZE = 20 * 1024 * 1024  # 单文件 20MB 上限

# 文件魔术字节校验 (防伪装文件)
MAGIC_BYTES = {
    "docx": b"PK\x03\x04",
    "pdf": b"%PDF",
    "zip": b"PK\x03\x04",
}


def validate_file_bytes(filename: str, content: bytes):
    """基础魔术字节校验 — 防止 .exe 伪装成 .txt"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in MAGIC_BYTES and not content.startswith(MAGIC_BYTES[ext]):
        raise HTTPException(status_code=400, detail=f"文件格式异常：{filename} 可能不是有效的 .{ext} 文件")


@router.post("/batch")
async def batch_detect_start(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启动批量检测任务 — 返回 batch_id，异步处理"""
    from app.utils.document_parser import parse_document

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")
    if len(files) > 100:
        raise HTTPException(status_code=400, detail="单次最多 100 个文件")

    # P0 Fix 1: 读取文件到内存，避免 UploadFile 生命周期问题
    file_payloads = []
    for f in files:
        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"{f.filename} 超过 20MB 限制")
        validate_file_bytes(f.filename, content)
        file_payloads.append({"filename": f.filename, "content": content})

    batch_id = _uuid.uuid4().hex[:12]
    state = BatchState(
        batch_id=batch_id, user_id=str(current_user.id),
        status="processing", total=len(file_payloads),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _batch_store[batch_id] = state

    # P0 Fix 2: 不传 db，后台任务内部自己创建 session
    asyncio.create_task(_process_batch(batch_id, file_payloads, str(current_user.id)))

    return {
        "batch_id": batch_id,
        "total": len(file_payloads),
        "status": "processing",
        "message": f"已提交 {len(file_payloads)} 个文件，并行处理中",
    }


@router.get("/batch/history")
async def batch_history(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的批量检测历史"""
    user_batches = [
        {
            "batch_id": s.batch_id,
            "status": s.status,
            "total": s.total,
            "completed": s.completed,
            "ai_count": sum(1 for r in s.results if r.get("is_ai_generated")),
            "created_at": s.created_at,
            "finished_at": s.finished_at,
        }
        for s in _batch_store.values()
        if s.user_id == str(current_user.id)
    ]
    user_batches.sort(key=lambda b: b["created_at"], reverse=True)
    total = len(user_batches)
    start = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "batches": user_batches[start:start + page_size],
    }


@router.get("/batch/{batch_id}/progress")
async def batch_progress(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    """轮询批量检测进度"""
    state = _batch_store.get(batch_id)
    if not state:
        raise HTTPException(status_code=404, detail="批次不存在或已过期")
    return {
        "batch_id": state.batch_id,
        "status": state.status,
        "total": state.total,
        "completed": state.completed,
        "progress_pct": round(state.completed / max(state.total, 1) * 100, 1),
        "results": state.results,
        "created_at": state.created_at,
        "finished_at": state.finished_at,
    }


@router.post("/batch/{batch_id}/cancel")
async def batch_cancel(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    """取消正在进行的批量检测"""
    state = _batch_store.get(batch_id)
    if not state:
        raise HTTPException(status_code=404, detail="批次不存在")
    if state.status not in ("processing", "pending"):
        raise HTTPException(status_code=400, detail="批次已结束，无法取消")
    state.cancelled = True
    state.status = "cancelled"
    state.finished_at = datetime.now(timezone.utc).isoformat()
    return {"batch_id": batch_id, "status": "cancelled", "completed": state.completed}


@router.get("/batch/{batch_id}/report")
async def batch_report(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取批次详细报告 (含汇总统计)"""
    state = _batch_store.get(batch_id)
    if not state:
        raise HTTPException(status_code=404, detail="批次不存在")

    results = state.results
    valid = [r for r in results if "confidence" in r]
    ai_items = [r for r in valid if r.get("is_ai_generated")]
    human_items = [r for r in valid if not r.get("is_ai_generated")]
    high_risk = [r for r in valid if r.get("risk_level") == "high"]
    medium_risk = [r for r in valid if r.get("risk_level") == "medium"]
    low_risk = [r for r in valid if r.get("risk_level") == "low"]
    errors = [r for r in results if "error" in r]

    confidences = [r["confidence"] for r in valid]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    max_conf = max(confidences) if confidences else 0
    min_conf = min(confidences) if confidences else 0

    return {
        "batch_id": state.batch_id,
        "status": state.status,
        "created_at": state.created_at,
        "finished_at": state.finished_at,
        "summary": {
            "total": state.total,
            "completed": state.completed,
            "ai_count": len(ai_items),
            "human_count": len(human_items),
            "ai_rate": round(len(ai_items) / max(len(valid), 1) * 100, 1),
            "high_risk": len(high_risk),
            "medium_risk": len(medium_risk),
            "low_risk": len(low_risk),
            "errors": len(errors),
        },
        "confidence_stats": {
            "avg": round(avg_conf, 4),
            "max": round(max_conf, 4),
            "min": round(min_conf, 4),
        },
        "results": results,
    }


async def _process_batch(batch_id: str, file_payloads: list[dict], user_id: str):
    """后台并行处理批量文件 — 独立创建 db session，使用预读 payload"""
    from app.utils.document_parser import parse_document
    from app.services.text_service import detect_text as do_detect
    from app.services.detection_service import create_task, update_task_status, save_detection_result
    from app.db.session import async_session_factory

    state = _batch_store.get(batch_id)
    if not state:
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    results_lock = asyncio.Lock()

    async def process_one(idx: int, payload: dict) -> dict:
        async with semaphore:
            if state.cancelled:
                return {"filename": payload["filename"], "index": idx, "error": "已取消"}

            # P0 Fix: 每个 task 独立创建 session，不共享
            async with async_session_factory() as task_db:
                try:
                    text = parse_document(payload["filename"], payload["content"])

                    task = await create_task(db=task_db, user_id=user_id,
                                             modality="text", input_content=text[:1000])
                    detection = await do_detect(text[:5000], {"explain": False})
                    risk = "high" if detection.confidence > 0.7 else "medium" if detection.confidence > 0.25 else "low"
                    await save_detection_result(
                        db=task_db, task_id=str(task.id), modality="text",
                        is_ai_generated=detection.is_ai_generated,
                        confidence=detection.confidence, risk_level=risk,
                    )
                    await update_task_status(task_db, str(task.id), "completed")

                    return {
                        "index": idx, "task_id": str(task.id),
                        "filename": payload["filename"],
                        "char_count": len(text),
                        "is_ai_generated": detection.is_ai_generated,
                        "confidence": detection.confidence,
                        "risk_level": risk,
                    }
                except Exception as e:
                    return {"filename": payload["filename"], "index": idx, "error": str(e)}

    tasks_list = [process_one(i, p) for i, p in enumerate(file_payloads)]
    for coro in asyncio.as_completed(tasks_list):
        if state.cancelled:
            break
        result = await coro
        async with results_lock:
            state.results.append(result)
            state.completed += 1

    if state.cancelled:
        state.status = "cancelled"
    elif state.completed >= state.total:
        state.status = "completed"
    else:
        state.status = "partial"
    state.finished_at = datetime.now(timezone.utc).isoformat()


@router.post("/batch-images")
async def batch_detect_images(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """批量图像检测 — 上传多张图片，逐个检测，返回汇总"""
    from app.services.image_service import detect_image as do_detect

    results = []
    for file in files:
        if not file.filename:
            continue
        try:
            img_data = await file.read()
            detection = await do_detect(img_data, {"explain": True})
            results.append({
                "filename": file.filename,
                "is_ai_generated": detection.is_ai_generated,
                "confidence": detection.confidence,
                "branches": detection.explanation_data.get("branches", []),
                "risk_level": (
                    "high" if detection.confidence > 0.8
                    else "medium" if detection.confidence > 0.5 else "low"
                ),
            })
        except Exception as e:
            results.append({"filename": file.filename, "error": str(e)})

    ai_count = sum(1 for r in results if r.get("is_ai_generated"))
    return {
        "total": len(results),
        "ai_detected": ai_count,
        "real_detected": len(results) - ai_count,
        "results": results,
    }


@router.post("/thesis")
async def detect_thesis(
    file: UploadFile = File(...),
    current_user: User = Depends(require_quota("thesis")),
    db: AsyncSession = Depends(get_db),
):
    """
    论文 AIGC 检测 — 对标知网/Turnitin 标准, 智能自适应阈值

    功能: 章节识别 → 段落分析 → 三色标注 → 疑似原因 → 判定建议
    阈值: 根据文档置信度分布自动计算 (中位数 + 标准差调整)
    """
    from app.utils.document_parser import parse_document
    from app.services.text_service import detect_text as do_detect
    from app.detectors.text.statistical_features import ChineseStatisticalExtractor
    import re
    from datetime import datetime

    stat_ext = ChineseStatisticalExtractor()

    # 解析文档 (带大小限制)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 20MB 限制")
    validate_file_bytes(file.filename, content)
    try:
        text = parse_document(file.filename, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文档解析失败: {e}")

    # ============================================================
    # Step 1: 分段 — 信任 document_parser 的 \n\n 结构, 不修改原文
    # ============================================================

    THRESHOLD = 0.25
    # P0: 学科自适应阈值
    from app.services.thesis_optimizer import detect_discipline, get_threshold
    discipline = detect_discipline(text)
    adpt_threshold = get_threshold(discipline)

    toc_re = re.compile(r'[.]{3,}|…')
    skip_re = re.compile(r'参\s*考\s*文\s*献|致\s*谢|附\s*录')
    title_re = re.compile(
        r'第[一二三四五六七八九十\d]+[章节]'
        r'|[一二三四五六七八九十\d]+[、．.]'
        r'|摘\s*要|abstract|摘要'
        r'|引\s*言|绪\s*论|前\s*言'
        r'|文\s*献\s*综\s*述|相\s*关\s*工\s*作|研\s*究\s*现\s*状'
        r'|实\s*验|方\s*法|研究方案'
        r'|结\s*[论果]|总\s*结|讨\s*论'
        r'|参\s*考\s*文\s*献|致\s*谢|附\s*录'
    )

    paragraphs: list[dict] = []
    for para in re.split(r'\n\s*\n', text):
        para = para.strip()
        if len(para) <= 20:
            continue
        first = para.split('\n')[0].strip()
        is_toc = bool(toc_re.search(first) and re.search(r'\d+$', first))
        if is_toc:
            section, is_skip = "目录", True
        elif len(first) < 60 and title_re.search(first):
            section, is_skip = first, bool(skip_re.search(first))
        else:
            section, is_skip = "正文", False
        paragraphs.append({"section": section, "text": para, "length": len(para), "skip_detection": is_skip})

    if not paragraphs:
        raise HTTPException(status_code=400, detail="文档内容过短")

    # ============================================================
    # Step 2: 强化原因分析
    # ============================================================

    def analyze_reasons(feats, conf: float) -> list[str]:
        r = []
        if feats.slop_word_density > 0.8:
            r.append(f"AI标志词高频(d={feats.slop_word_density:.2f})")
        elif feats.slop_word_density > 0.5:
            r.append(f"含AI标志性短语(d={feats.slop_word_density:.2f})")

        if feats.transition_word_density > 0.5:
            r.append(f"过渡词过多(d={feats.transition_word_density:.2f})")
        elif feats.transition_word_density > 0.3:
            r.append(f"过渡词密度偏高(d={feats.transition_word_density:.2f})")

        if feats.sentence_length_cv < 0.2:
            r.append(f"句式高度均匀(CV={feats.sentence_length_cv:.2f})")
        elif feats.sentence_length_cv < 0.35:
            r.append(f"句式较为均匀(CV={feats.sentence_length_cv:.2f})")

        if feats.burstiness < 0.15:
            r.append(f"段落节奏异常一致(B={feats.burstiness:.3f})")
        elif feats.burstiness < 0.25:
            r.append(f"段落节奏偏均匀(B={feats.burstiness:.3f})")

        if feats.bigram_entropy < 3.0:
            r.append(f"词语搭配单一(2-gram熵={feats.bigram_entropy:.2f})")
        if feats.trigram_entropy < 2.5:
            r.append(f"三词组合重复(3-gram熵={feats.trigram_entropy:.2f})")

        if feats.zipf_deviation > 0.3:
            r.append(f"词频偏离自然语言(Zipf偏差={feats.zipf_deviation:.3f})")
        if feats.hapax_ratio < 0.3:
            r.append(f"一次性词汇偏少(Hapax={feats.hapax_ratio:.2f})")

        if conf > 0.6 and not r:
            r.append("深度语义模型综合判定为疑似AI生成")
        elif not r:
            r.append("语言特征自然，未发现明显AI生成痕迹") if conf <= 0.35 else r.append("部分语言模式接近AI风格")
        return r

    # ============================================================
    # Step 3: 逐段检测 (并行, 最多 5 段同时检测)
    # ============================================================

    _semaphore = asyncio.Semaphore(5)

    async def _detect_para(i: int, p: dict) -> dict:
        para_text = p["text"]

        if p.get("skip_detection"):
            return {
                "index": i, "text": para_text, "length": p["length"],
                "section": p["section"],
                "confidence": 0.0, "is_ai_generated": False,
                "suspicion": 0.0, "level": "low",
                "reasons": [f"{p['section']} — 固判人类写作"],
                "excluded": False,
                "is_reference": True,
            }

        if len(para_text) < 30:
            return {
                "index": i, "text": para_text, "length": p["length"],
                "section": p["section"],
                "confidence": 0.0, "is_ai_generated": False,
                "suspicion": 0.0, "level": "low",
                "reasons": ["段落过短，不纳入统计"],
                "excluded": True,
            }

        async with _semaphore:
            result = await do_detect(para_text[:1500], {"explain": False})
        conf = result.confidence
        feats = stat_ext.extract(para_text)
        return i, para_text, p, conf, feats

    # 并行执行所有段落检测
    raw_results = await asyncio.gather(*[
        _detect_para(i, p) for i, p in enumerate(paragraphs)
    ])

    # 组装结果 (保持原始顺序)
    para_results = []
    for item in raw_results:
        if isinstance(item, dict):
            # skip_detection 或 short paragraph — 直接是最终结果
            para_results.append(item)
            continue

        i, para_text, p, conf, feats = item

        para_results.append({
            "index": i, "text": para_text, "length": p["length"],
            "section": p["section"],
            "confidence": round(conf, 4),
            "is_ai_generated": False,
            "suspicion": round(conf * 100, 1),
            "level": "low",
            "reasons": analyze_reasons(feats, conf),
            "stat_features": {
                "slop": round(feats.slop_word_density, 3),
                "trans": round(feats.transition_word_density, 3),
                "cv": round(feats.sentence_length_cv, 3),
                "burst": round(feats.burstiness, 3),
                "bigram_e": round(feats.bigram_entropy, 2),
                "hapax": round(feats.hapax_ratio, 3),
            },
        })

    # ============================================================
    # Step 4: 固定阈值 + 统计
    # ============================================================

    for p in para_results:
        if p.get("excluded"):
            continue
        c = p["confidence"]
        p["is_ai_generated"] = c > THRESHOLD
        p["level"] = "high" if c >= 0.7 else ("medium" if c >= THRESHOLD else "low")

    chapter_stats: dict[str, dict] = {}
    for p in para_results:
        if p.get("excluded"):
            continue
        sec = p.get("section", "正文")
        if sec not in chapter_stats:
            chapter_stats[sec] = {"paragraphs": 0, "ai_paragraphs": 0}
        chapter_stats[sec]["paragraphs"] += 1
        if p.get("is_ai_generated"):
            chapter_stats[sec]["ai_paragraphs"] += 1
    for st in chapter_stats.values():
        st["ai_rate"] = round(st["ai_paragraphs"] / st["paragraphs"] * 100, 1) if st["paragraphs"] > 0 else 0

    valid_paras = [p for p in para_results if not p.get("excluded")]
    total_paras = len(valid_paras)
    ai_paras = sum(1 for p in valid_paras if p.get("is_ai_generated"))
    total_weight = sum(p["length"] for p in valid_paras)
    weighted_rate = sum(p["suspicion"] * p["length"] for p in valid_paras) / total_weight if total_weight > 0 else 0
    overall_ai_rate = round(weighted_rate, 1)

    if overall_ai_rate <= 15:
        recommendation, rec_detail = "建议通过", "整体AI疑似度在安全范围内，可直接提交"
    elif overall_ai_rate <= 30:
        recommendation, rec_detail = "需修改后重检", "部分段落疑似AI生成，建议针对性修改后重新检测"
    else:
        recommendation, rec_detail = "不建议通过", "大量段落高度疑似AI生成，需大幅人工改写后重新检测"

    # 跨章节一致性分析 (中期方案核心)
    from app.services.thesis_detector import parse_chapters, analyze_cross_chapter_consistency
    chapters = parse_chapters(text)
    consistency = analyze_cross_chapter_consistency(chapters)
    consistency_data = None
    if consistency:
        consistency_data = {
            "overall_score": consistency.overall_score,
            "style_variance": consistency.style_variance,
            "slop_pattern": consistency.slop_pattern,
            "transition_pattern": consistency.transition_pattern,
            "sentence_length_pattern": consistency.sentence_length_pattern,
            "chapter_count": consistency.chapter_count,
            "analyzed_count": consistency.analyzed_count,
            "details": consistency.details,
        }
        # 一致性调整整体评分
        if consistency.overall_score > 0.6 and overall_ai_rate > 20:
            overall_ai_rate = min(100, overall_ai_rate + 10)
            rec_detail += "；跨章节风格高度一致，AI典型特征"
        elif consistency.overall_score > 0.6 and overall_ai_rate <= 20:
            rec_detail += "；注意：跨章节风格一致但AI率低，可能是格式规范的人类论文"

    # 取证分析: 引用验证 + 数据具体性
    from app.services.thesis_forensics import analyze_thesis_forensics
    forensics = analyze_thesis_forensics(text)
    forensics_data = {
        "overall_risk": forensics.overall_risk,
        "risk_factors": forensics.risk_factors,
        "human_indicators": forensics.human_indicators,
    }
    if forensics.citation:
        forensics_data["citation"] = {
            "total": forensics.citation.total_citations,
            "unique": forensics.citation.unique_citations,
            "density": forensics.citation.density,
            "generic_ratio": forensics.citation.generic_ratio,
            "pattern": forensics.citation.consecutive_pattern,
            "suspicion": forensics.citation.suspicion_score,
        }
    forensics_data["specificity"] = {
        "score": forensics.specificity.specificity_score,
        "specific_count": forensics.specificity.specific_numbers,
        "vague_count": forensics.specificity.vague_phrases,
        "ratio": forensics.specificity.ratio,
        "diagnosis": forensics.specificity.diagnosis,
    }

    # 全局优化分析
    from app.services.thesis_optimizer import (
        detect_discipline, get_threshold, generate_thesis_report
    )
    discipline = detect_discipline(text)
    adpt_threshold = get_threshold(discipline)
    chapter_dicts = [
        {"text": ch.full_text, "type": ch.chapter_type} for ch in chapters if not ch.is_skip
    ] if consistency else None
    thesis_report = generate_thesis_report(
        text, para_results,
        chapters=chapter_dicts,
        sentences_list=[ch.paragraphs for ch in chapters if not ch.is_skip and ch.paragraphs] if consistency else None,
    )
    optimization_data = {
        "discipline": discipline,
        "adaptive_threshold": round(adpt_threshold, 3),
        "ai_participation": {
            "score": thesis_report.ai_participation.overall_score,
            "ai_ratio": thesis_report.ai_participation.ai_ratio,
            "classification": thesis_report.ai_participation.classification,
            "confidence": thesis_report.ai_participation.confidence,
            "ai_count": thesis_report.ai_participation.ai_sentence_count,
            "human_count": thesis_report.ai_participation.human_sentence_count,
            "mixed_count": thesis_report.ai_participation.mixed_sentence_count,
        },
        "english_analysis": thesis_report.english_support,
    }
    if thesis_report.style_consistency:
        optimization_data["style_consistency"] = {
            "variance": thesis_report.style_consistency.style_variance,
            "diagnosis": thesis_report.style_consistency.variance_diagnosis,
            "score": thesis_report.style_consistency.consistency_score,
        }
    optimization_data["risk_factors"] = thesis_report.risk_factors
    optimization_data["human_indicators"] = thesis_report.human_indicators

    await deduct_quota("thesis", db, current_user)

    return {
        "report_meta": {
            "filename": file.filename,
            "detection_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "algorithm_version": "AIGC--多模态检测 v4.0 — 学科自适应 + 全局优化",
            "adaptive_threshold": adpt_threshold,
            "threshold_method": f"学科自适应 ({discipline})",
        },
        "consistency": consistency_data,
        "forensics": forensics_data,
        "optimization": optimization_data,
        "overall_score": {
            "ai_rate": overall_ai_rate,
            "is_ai_generated": overall_ai_rate > adpt_threshold,
            "confidence": round(sum(p["confidence"] for p in valid_paras) / len(valid_paras), 4) if valid_paras else 0.0,
            "total_chars": len(text),
            "total_paragraphs": len(para_results),
        },
        "recommendation": {
            "verdict": recommendation, "detail": rec_detail,
            "risk_level": "high" if overall_ai_rate > 30 else ("medium" if overall_ai_rate > 15 else "low"),
        },
        "chapters": chapter_stats,
        "paragraphs": para_results,
        "summary": {
            "total_paragraphs": len(para_results),
            "valid_paragraphs": total_paras,
            "ai_paragraph_count": ai_paras,
            "human_paragraph_count": total_paras - ai_paras,
            "excluded_count": len(para_results) - total_paras,
            "high_risk_count": sum(1 for p in valid_paras if p["level"] == "high"),
            "medium_risk_count": sum(1 for p in valid_paras if p["level"] == "medium"),
            "low_risk_count": sum(1 for p in valid_paras if p["level"] == "low"),
            "weighted_ai_rate": overall_ai_rate,
        },
    }
