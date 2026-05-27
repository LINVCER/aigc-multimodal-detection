import asyncio
import socket

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, require_quota, deduct_quota
from app.models.user import User
from app.schemas.detection import (
    TextDetectionRequest,
    DetectionTaskResponse,
    DetectionResultResponse,
    BatchDetectionRequest,
    TamperingDetectionResponse,
)
from app.services.detection_service import (
    create_task,
    get_task,
    get_detection_result,
    save_detection_result,
    update_task_status,
)
from app.workers.text_worker import detect_text_task
from app.workers.image_worker import detect_image_task
from app.workers.audio_worker import detect_audio_task

router = APIRouter(prefix="/detect", tags=["检测"])


def _redis_available() -> bool:
    try:
        from app.config import get_settings
        s = get_settings()
        sock = socket.create_connection((s.redis_host, s.redis_port), timeout=2)
        sock.close()
        return True
    except Exception:
        return False


@router.post("/text", response_model=DetectionTaskResponse)
async def detect_text(
    req: TextDetectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_quota("text")),
):
    task = await create_task(
        db=db,
        user_id=str(current_user.id),
        modality="text",
        input_content=req.content,
    )

    from app.services.text_service import detect_text as do_detect
    from app.services.detection_service import save_detection_result
    try:
        result = await asyncio.wait_for(do_detect(req.content, req.options), timeout=60)
    except asyncio.TimeoutError:
        await update_task_status(db, str(task.id), "failed")
        await db.commit()
        raise HTTPException(status_code=504, detail="检测超时，请稍后重试")
    except Exception as e:
        await update_task_status(db, str(task.id), "failed")
        await db.commit()
        raise HTTPException(status_code=500, detail=f"检测处理异常: {str(e)}")

    risk = "high" if result.confidence > 0.7 else "medium" if result.confidence > 0.25 else "low"
    await deduct_quota("text", db, current_user)
    await save_detection_result(
        db=db, task_id=str(task.id), modality="text",
        is_ai_generated=result.is_ai_generated,
        confidence=result.confidence,
        calibrated_confidence=result.calibrated_confidence,
        risk_level=risk,
        model_attribution=result.model_attribution,
    )
    await update_task_status(db, str(task.id), "completed")
    await db.commit()
    chunk_details = (result.explanation_data or {}).get("chunk_details")
    suspicious_spans = (result.explanation_data or {}).get("text_snippets", [])
    explanation_data = {
        "suspicious_spans": [
            {"start": s.get("start", 0), "end": s.get("end", 0), "reason": s.get("reason", ""), "score": s.get("score", 0)}
            for s in suspicious_spans
        ],
        "defense": (result.explanation_data or {}).get("defense"),
        "statistical_features": (result.explanation_data or {}).get("statistical_features"),
    }
    return DetectionTaskResponse(
        task_id=str(task.id), status="completed", modality="text",
        message=f"判定: {'AI生成' if result.is_ai_generated else '人类写作'}",
        is_ai_generated=result.is_ai_generated,
        confidence=result.confidence,
        calibrated_confidence=result.calibrated_confidence,
        risk_level=risk,
        chunk_details=chunk_details,
        explanation=explanation_data,
        arbitration_warning=result.metadata.get("arbitration_warning"),
    )


@router.post("/image", response_model=DetectionTaskResponse)
async def detect_image(
    file: UploadFile = File(...),
    options: str = Form(default="{}"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_quota("image")),
):
    image_data = await file.read()
    task = await create_task(
        db=db, user_id=str(current_user.id), modality="image",
    )

    from app.services.image_service import detect_image as do_detect
    from app.services.detection_service import save_detection_result
    try:
        result = await asyncio.wait_for(do_detect(image_data, {"explain": True}), timeout=60)
    except asyncio.TimeoutError:
        await update_task_status(db, str(task.id), "failed")
        await db.commit()
        raise HTTPException(status_code=504, detail="检测超时，请稍后重试")
    except Exception as e:
        await update_task_status(db, str(task.id), "failed")
        await db.commit()
        raise HTTPException(status_code=500, detail=f"检测处理异常: {str(e)}")

    from app.config import thresholds
    risk = thresholds.get_risk_level(result.confidence)
    await deduct_quota("image", db, current_user)
    await save_detection_result(
        db=db, task_id=str(task.id), modality="image",
        is_ai_generated=result.is_ai_generated,
        confidence=result.confidence, calibrated_confidence=result.calibrated_confidence,
        risk_level=risk,
    )
    await update_task_status(db, str(task.id), "completed")
    await db.commit()
    img_explanation = None
    if result.explanation_data:
        img_explanation = {
            "branches": result.explanation_data.get("branches", []),
            "frequency_analysis": result.explanation_data.get("frequency_analysis"),
            "mimo_explanation": result.explanation_data.get("mimo_explanation"),
        }
    return DetectionTaskResponse(
        task_id=str(task.id), status="completed", modality="image",
        message=f"判定: {'AI生成' if result.is_ai_generated else '真实图像'}",
        is_ai_generated=result.is_ai_generated,
        confidence=result.confidence,
        calibrated_confidence=result.calibrated_confidence,
        risk_level=risk,
        explanation=img_explanation,
    )


@router.post("/audio", response_model=DetectionTaskResponse)
async def detect_audio(
    file: UploadFile = File(...),
    options: str = Form(default="{}"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_quota("audio")),
):
    task = await create_task(
        db=db, user_id=str(current_user.id),
        modality="audio", input_file_url=f"uploads/{file.filename}",
    )

    import json, asyncio
    opts = json.loads(options) if options else {}
    audio_bytes = await file.read()

    from app.services.audio_service import detect_audio as do_detect
    try:
        result = await asyncio.wait_for(do_detect(audio_bytes, opts), timeout=60)
    except asyncio.TimeoutError:
        await update_task_status(db, str(task.id), "failed")
        await db.commit()
        raise HTTPException(status_code=504, detail="检测超时")
    except Exception as e:
        await update_task_status(db, str(task.id), "failed")
        await db.commit()
        raise HTTPException(status_code=500, detail=f"检测处理异常: {str(e)}")

    risk = "high" if result.confidence > 0.7 else "medium" if result.confidence > 0.25 else "low"
    await deduct_quota("audio", db, current_user)
    await save_detection_result(
        db=db, task_id=str(task.id), modality="audio",
        is_ai_generated=result.is_ai_generated,
        confidence=result.confidence,
        risk_level=risk,
    )
    await update_task_status(db, str(task.id), "completed")
    await db.commit()

    branches = (result.explanation_data or {}).get("branches", [])
    return DetectionTaskResponse(
        task_id=str(task.id), status="completed", modality="audio",
        message=f"{'AI合成' if result.is_ai_generated else '真实语音'} (置信度 {result.confidence*100:.0f}%)",
        is_ai_generated=result.is_ai_generated,
        confidence=result.confidence,
        risk_level=risk,
        explanation={"branches": [
            {"name": b["name"], "weight": b["weight"], "confidence": b["confidence"]}
            for b in branches
        ]} if branches else None,
    )


@router.post("/tampering", response_model=TamperingDetectionResponse)
async def detect_tampering_endpoint(
    file: UploadFile = File(...),
    options: str = Form(default="{}"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_quota("tampering")),
):
    """篡改检测 — Mask R-CNN + FFT + 噪声 三路融合"""
    import json
    image_data = await file.read()
    task = await create_task(
        db=db, user_id=str(current_user.id), modality="tampering",
    )

    from app.services.tampering_service import detect_tampering as do_detect
    try:
        opts = json.loads(options) if options else {}
        result = await asyncio.wait_for(do_detect(image_data, opts), timeout=120)
    except asyncio.TimeoutError:
        await update_task_status(db, str(task.id), "failed")
        await db.commit()
        raise HTTPException(status_code=504, detail="篡改检测超时，请稍后重试")
    except Exception as e:
        await update_task_status(db, str(task.id), "failed")
        await db.commit()
        raise HTTPException(status_code=500, detail=f"检测处理异常: {str(e)}")

    from app.config import thresholds
    import json as _json
    import numpy as _np

    def _json_safe(obj):
        """递归转换 numpy 类型为原生 Python"""
        if isinstance(obj, (_np.integer,)):
            return int(obj)
        if isinstance(obj, (_np.floating,)):
            return float(obj)
        if isinstance(obj, _np.ndarray):
            return _json_safe(obj.tolist())
        if isinstance(obj, (_np.bool_,)):
            return bool(obj)
        if isinstance(obj, dict):
            return {k: _json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_json_safe(v) for v in obj]
        return obj

    risk = (
        "high" if result.tampering_score > thresholds.TAMPERING_RISK_HIGH else
        "medium" if result.tampering_score > thresholds.TAMPERING_RISK_MEDIUM else
        "low"
    )
    await deduct_quota("tampering", db, current_user)
    # 存储篡改检测完整数据到 raw_scores JSON 字段
    tampering_raw_scores = _json_safe({
        "tampering_type": result.tampering_type,
        "tampering_score": result.tampering_score,
        "is_tampered": result.is_tampered,
        "branches": [
            {"name": b.branch_name, "confidence": b.confidence,
             "is_tampered": bool(b.mask.any()) if b.mask is not None else False}
            for b in result.branch_results
        ],
        "explanation": result.explanation_data,
    })
    await save_detection_result(
        db=db, task_id=str(task.id), modality="tampering",
        is_ai_generated=result.is_tampered,
        confidence=result.tampering_score,
        risk_level=risk,
        raw_scores=tampering_raw_scores,
    )
    await update_task_status(db, str(task.id), "completed")
    await db.commit()

    return TamperingDetectionResponse(
        task_id=str(task.id),
        status="completed",
        modality="tampering",
        message=f"判定: {'检测到篡改' if result.is_tampered else '图像真实'}",
        is_tampered=result.is_tampered,
        tampering_score=result.tampering_score,
        tampering_type=result.tampering_type,
        risk_level=risk,
        mask_image=result.mask_base64,
        overlay_image=result.overlay_base64,
        branches=[
            {"name": b.branch_name, "confidence": b.confidence,
             "is_tampered": bool(b.mask.any()) if b.mask is not None else False}
            for b in result.branch_results
        ],
    )


@router.get("/status/{task_id}")
async def get_detection_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await get_task(db, task_id)
    if not task or str(task.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": str(task.id),
        "status": task.status,
        "modality": task.modality,
        "created_at": str(task.created_at),
    }


@router.post("/multimodal", response_model=DetectionTaskResponse)
async def detect_multimodal(
    text_content: str | None = Form(None),
    image_file: UploadFile | None = File(None),
    audio_file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    多模态联合检测 — 调用仲裁决策层

    至少需要提供一个模态的输入。系统将分别执行各模态检测，
    然后通过贝叶斯冲突消解输出统一判定。
    """
    if not text_content and not image_file and not audio_file:
        raise HTTPException(status_code=400, detail="至少提供一种模态的输入")

    task = await create_task(
        db=db, user_id=str(current_user.id), modality="multimodal",
    )
    await update_task_status(db, str(task.id), "processing")

    # 提交各模态检测任务
    if text_content:
        detect_text_task.delay(str(task.id), text_content, {"explain": True, "attribution": True})
    if image_file:
        file_url = f"minio://uploads/{image_file.filename}"
        detect_image_task.delay(str(task.id), file_url, {"explain": True})
    if audio_file:
        file_url = f"minio://uploads/{audio_file.filename}"
        detect_audio_task.delay(str(task.id), file_url, {"explain": True})

    return DetectionTaskResponse(
        task_id=str(task.id),
        status="processing",
        modality="multimodal",
        message=f"多模态检测已提交 (文本={'是' if text_content else '否'}, 图像={'是' if image_file else '否'}, 音频={'是' if audio_file else '否'})",
    )


@router.get("/result/{task_id}", response_model=DetectionResultResponse)
async def get_detection_result_api(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await get_task(db, task_id)
    if not task or str(task.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    detection = await get_detection_result(db, task_id)
    if not detection:
        raise HTTPException(status_code=404, detail="检测结果不存在")

    # 论文检测: 从 raw_scores 直接返回完整结果
    if detection.modality == "thesis":
        raw = detection.raw_scores or {}
        raw["task_id"] = str(task.id)
        raw["status"] = task.status
        return raw

    # 篡改检测: 从 raw_scores 提取 tampering 数据返回
    if detection.modality == "tampering":
        raw = detection.raw_scores or {}
        return TamperingDetectionResponse(
            task_id=str(task.id),
            status=task.status,
            modality="tampering",
            message=f"判定: {'检测到篡改' if raw.get('is_tampered') else '图像真实'}",
            is_tampered=raw.get("is_tampered", detection.is_ai_generated),
            tampering_score=raw.get("tampering_score", detection.confidence),
            tampering_type=raw.get("tampering_type", "unknown"),
            risk_level=detection.risk_level,
            branches=raw.get("branches"),
        )

    return DetectionResultResponse(
        task_id=str(task.id),
        status=task.status,
        modality=detection.modality,
        is_ai_generated=detection.is_ai_generated,
        confidence=detection.confidence,
        calibrated_confidence=detection.calibrated_confidence,
        confidence_interval=(
            (detection.confidence_interval_lower, detection.confidence_interval_upper)
            if detection.confidence_interval_lower is not None
            else None
        ),
        risk_level=detection.risk_level,
        model_attribution=detection.model_attribution or [],
        arbitration_warning=detection.arbitration_warning,
    )


# ============================================================

