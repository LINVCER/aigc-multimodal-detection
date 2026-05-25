import asyncio
from datetime import datetime
from app.workers.celery_app import celery_app
from app.config import get_settings

settings = get_settings()


@celery_app.task(bind=True, name="detect_text")
def detect_text_task(self, task_id: str, content: str, options: dict | None = None):
    """
    异步文本检测任务 — 三路融合管线
    执行: 统计特征 → RoBERTa → LLM logprob → 融合 → 校准 → 解释
    """
    self.update_state(state="PROCESSING", meta={"progress": 10})

    # 在 Celery worker 中运行异步检测
    result = asyncio.run(_run_detection(task_id, content, options))

    self.update_state(state="COMPLETED", meta=result)
    return result


async def _run_detection(task_id: str, content: str, options: dict | None = None) -> dict:
    from app.services.text_service import detect_text
    from app.db.session import async_session_factory
    from app.services.detection_service import (
        update_task_status,
        save_detection_result,
    )
    from app.services.report_service import create_report

    detection_output = await detect_text(content, options)

    # 持久化结果到数据库
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
                db=db,
                task_id=task_id,
                modality="text",
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
                model_attribution=detection_output.model_attribution,
            )
            await db.commit()

            # 生成解释报告
            expl_data = detection_output.explanation_data
            await create_report(
                db=db,
                detection_result_id=str(result.id),
                modality="text",
                suspicious_spans=expl_data.get("text_snippets"),
                feature_contributions=expl_data.get("statistical_features"),
                perplexity_scores=(
                    [{"perplexity": detection_output.metadata.get("perplexity")}]
                    if detection_output.metadata.get("perplexity") else None
                ),
            )
            await db.commit()

            return {
                "task_id": task_id,
                "status": "completed",
                "is_ai_generated": detection_output.is_ai_generated,
                "confidence": detection_output.confidence,
                "calibrated_confidence": detection_output.calibrated_confidence,
                "risk_level": risk,
                "model_attribution": detection_output.model_attribution,
                "completed_at": str(datetime.utcnow()),
            }
        except Exception as e:
            await db.rollback()
            raise e
