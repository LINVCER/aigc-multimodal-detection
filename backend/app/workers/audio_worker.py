import asyncio
from datetime import datetime
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="detect_audio")
def detect_audio_task(self, task_id: str, file_path: str, options: dict | None = None):
    """异步音频检测任务 — Resemble API + RawNet2 双路融合"""
    self.update_state(state="PROCESSING", meta={"progress": 10})
    result = asyncio.run(_run_detection(task_id, file_path, options))
    self.update_state(state="COMPLETED", meta=result)
    return result


async def _run_detection(task_id: str, file_path: str, options: dict | None = None) -> dict:
    from app.services.audio_service import detect_audio
    from app.db.session import async_session_factory
    from app.services.detection_service import update_task_status, save_detection_result
    from app.services.report_service import create_report

    # 获取音频数据
    if file_path.startswith("minio://"):
        object_name = file_path.split("minio://")[1].split("/", 1)[1]
        from app.utils.file_handler import get_file_url
        import httpx
        presigned_url = await get_file_url(object_name)
        resp = httpx.get(presigned_url)
        audio_data = resp.content
    else:
        with open(file_path, "rb") as f:
            audio_data = f.read()

    detection_output = await detect_audio(audio_data, options)

    async with async_session_factory() as db:
        try:
            await update_task_status(db, task_id, "completed")
            await db.commit()

            risk = (
                "high" if detection_output.confidence > 0.8
                else "medium" if detection_output.confidence > 0.5
                else "low"
            )

            result = await save_detection_result(
                db=db, task_id=task_id, modality="audio",
                is_ai_generated=detection_output.is_ai_generated,
                confidence=detection_output.confidence,
                calibrated_confidence=detection_output.calibrated_confidence,
                confidence_interval_lower=(
                    detection_output.confidence_interval[0]
                    if detection_output.confidence_interval else None
                ),
                confidence_interval_upper=(
                    detection_output.confidence_interval[1]
                    if detection_output.confidence_interval else None
                ),
                risk_level=risk,
                raw_scores=detection_output.metadata,
            )
            await db.commit()

            await create_report(
                db=db,
                detection_result_id=str(result.id),
                modality="audio",
            )
            await db.commit()

            return {
                "task_id": task_id,
                "status": "completed",
                "is_ai_generated": detection_output.is_ai_generated,
                "confidence": detection_output.confidence,
                "risk_level": risk,
                "completed_at": str(datetime.utcnow()),
            }
        except Exception as e:
            await db.rollback()
            raise e
