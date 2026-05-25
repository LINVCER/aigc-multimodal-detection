import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.task import Task
from app.models.detection import DetectionResult


async def create_task(
    db: AsyncSession,
    user_id: str,
    modality: str,
    task_type: str = "single",
    input_content: str | None = None,
    input_file_url: str | None = None,
    batch_id: str | None = None,
) -> Task:
    task = Task(
        id=uuid.uuid4(),
        user_id=user_id,
        modality=modality,
        task_type=task_type,
        status="pending",
        input_content=input_content,
        input_file_url=input_file_url,
        batch_id=batch_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


async def get_task(db: AsyncSession, task_id: str) -> Task | None:
    result = await db.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def update_task_status(db: AsyncSession, task_id: str, status: str, error_message: str | None = None):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task:
        task.status = status
        if error_message:
            task.error_message = error_message
        await db.flush()
    return task


async def save_detection_result(
    db: AsyncSession,
    task_id: str,
    modality: str,
    is_ai_generated: bool | None,
    confidence: float,
    calibrated_confidence: float | None = None,
    confidence_interval_lower: float | None = None,
    confidence_interval_upper: float | None = None,
    risk_level: str | None = None,
    raw_scores: dict | None = None,
    model_attribution: dict | None = None,
    arbitration_warning: str | None = None,
) -> DetectionResult:
    result = DetectionResult(
        id=uuid.uuid4(),
        task_id=task_id,
        modality=modality,
        is_ai_generated=is_ai_generated,
        confidence=confidence,
        calibrated_confidence=calibrated_confidence,
        confidence_interval_lower=confidence_interval_lower,
        confidence_interval_upper=confidence_interval_upper,
        risk_level=risk_level,
        raw_scores=raw_scores,
        model_attribution=model_attribution,
        arbitration_warning=arbitration_warning,
    )
    db.add(result)
    await db.flush()
    await db.refresh(result)
    return result


async def get_detection_result(db: AsyncSession, task_id: str) -> DetectionResult | None:
    result = await db.execute(
        select(DetectionResult).where(DetectionResult.task_id == task_id)
    )
    return result.scalar_one_or_none()
