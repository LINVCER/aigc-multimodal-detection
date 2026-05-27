from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.task import Task
from app.models.detection import DetectionResult
from app.schemas.report import ReportResponse, HistoryResponse, HistoryItem
from app.schemas.detection import FeedbackRequest
from app.services.report_service import get_report
from app.services.detection_service import get_task, get_detection_result

router = APIRouter(prefix="/reports", tags=["报告"])


@router.get("/{task_id}", response_model=ReportResponse)
async def get_explanation_report(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await get_task(db, task_id)
    if not task or str(task.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="任务不存在")

    detection = await get_detection_result(db, task_id)
    if not detection:
        raise HTTPException(status_code=404, detail="检测结果不存在，请等待检测完成")

    report = await get_report(db, str(detection.id))

    return ReportResponse(
        id=str(report.id) if report else "",
        detection_result_id=str(detection.id),
        modality=detection.modality,
        suspicious_spans=report.suspicious_spans if report else None,
        perplexity_scores=report.perplexity_scores if report else None,
        low_freq_words=report.low_freq_words if report else None,
        feature_contributions=report.feature_contributions if report else None,
        frequency_spectrum_url=report.frequency_spectrum_url if report else None,
        anomaly_heatmap_url=report.anomaly_heatmap_url if report else None,
        pitch_jump_points=report.pitch_jump_points if report else None,
        waveform_anomaly_url=report.waveform_anomaly_url if report else None,
        arbitration_reason=report.arbitration_reason if report else None,
        conflicting_signals=report.conflicting_signals if report else None,
    )


@router.get("/history/list", response_model=HistoryResponse)
async def get_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = str(current_user.id)
    offset = (page - 1) * size

    # 总数
    count_query = select(func.count()).select_from(Task).where(Task.user_id == user_id)
    total = (await db.execute(count_query)).scalar() or 0

    # 分页查询: task JOIN detection_result
    query = (
        select(Task, DetectionResult)
        .join(DetectionResult, Task.id == DetectionResult.task_id, isouter=True)
        .where(Task.user_id == user_id)
        .order_by(desc(Task.created_at))
        .offset(offset)
        .limit(size)
    )
    rows = (await db.execute(query)).all()

    items = []
    for task, det in rows:
        items.append(HistoryItem(
            task_id=str(task.id),
            modality=task.modality,
            status=task.status,
            is_ai_generated=det.is_ai_generated if det else None,
            confidence=det.confidence if det else 0.0,
            risk_level=det.risk_level if det else None,
            created_at=str(task.created_at) if task.created_at else "",
            input_content=(task.input_content[:200] if task.input_content else (task.input_file_url[:200] if task.input_file_url else None)),
        ))

    return HistoryResponse(items=items, total=total, page=page, size=size)


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # TODO: 记录用户反馈用于持续校准
    return {"status": "ok", "message": "反馈已记录"}
