import asyncio
from datetime import datetime
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="detect_image")
def detect_image_task(self, task_id: str, file_path: str, options: dict | None = None):
    """
    异步图像检测任务 — 双分支融合管线
    执行: 高频噪声 CNN → ViT 语义 → 融合 → 校准 → 频谱可视化
    """
    self.update_state(state="PROCESSING", meta={"progress": 10})
    result = asyncio.run(_run_detection(task_id, file_path, options))
    self.update_state(state="COMPLETED", meta=result)
    return result


async def _run_detection(task_id: str, file_path: str, options: dict | None = None) -> dict:
    from app.services.image_service import detect_image, generate_spectrum_visualization
    from app.db.session import async_session_factory
    from app.services.detection_service import update_task_status, save_detection_result
    from app.services.report_service import create_report
    from app.utils.file_handler import get_file_url

    # 从 MinIO 下载图像数据
    # file_path 格式: minio://bucket/object_name
    if file_path.startswith("minio://"):
        object_name = file_path.split("minio://")[1].split("/", 1)[1]
        import httpx
        presigned_url = await get_file_url(object_name)
        resp = httpx.get(presigned_url)
        image_data = resp.content
    else:
        # 本地测试路径
        with open(file_path, "rb") as f:
            image_data = f.read()

    detection_output = await detect_image(image_data, options)

    # 生成频谱图
    spectrum_bytes = await generate_spectrum_visualization(image_data)

    # 持久化
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
                modality="image",
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

            # 保存频谱图到 MinIO (简化: 直接存到报告字段中)
            spectrum_url = f"minio://reports/{task_id}_spectrum.png"
            # TODO: 上传 spectrum_bytes 到 MinIO

            await create_report(
                db=db,
                detection_result_id=str(result.id),
                modality="image",
                frequency_spectrum_url=spectrum_url,
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
