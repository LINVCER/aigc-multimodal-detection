from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.api.v1 import router as v1_router
from app.models.db_imports import *  # noqa: 确保所有模型注册到 SQLAlchemy

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name}...")
    from app.db.session import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 为 users 表添加签到字段（兼容已有数据库）
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE users ADD COLUMN last_checkin_date DATE"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN checkin_streak INTEGER DEFAULT 0"))
        except Exception:
            pass  # 字段已存在则忽略
    logger.info("Database tables verified/created")
    yield
    logger.info(f"Shutting down {settings.app_name}...")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api.v1.auth import router as auth_router
from app.api.v1.detection import router as detection_router
from app.api.v1.report import router as report_router
from app.api.v1.admin import router as admin_router
from app.api.v1.upload import router as upload_router
from app.api.v1.identifier import router as identifier_router
from app.api.v1.robustness import router as robustness_router
from app.api.v1.assistant import router as assistant_router

v1_router.include_router(auth_router)
v1_router.include_router(detection_router)
v1_router.include_router(report_router)
v1_router.include_router(admin_router)
v1_router.include_router(upload_router)
v1_router.include_router(identifier_router)
v1_router.include_router(robustness_router)
v1_router.include_router(assistant_router)
app.include_router(v1_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name, "version": "0.1.0"}


@app.get("/api/v1/system/model-info")
async def model_info():
    """返回当前文本检测模型信息"""
    import os
    checkpoint = os.path.join(settings.model_dir, settings.text_detector_checkpoint)
    info = {
        "modality": "text",
        "base_model": settings.text_model_path,
        "checkpoint": settings.text_detector_checkpoint,
        "checkpoint_exists": os.path.exists(checkpoint),
        "threshold": getattr(settings, "text_detection_threshold", 0.3),
        "llm_api": {
            "enabled": bool(settings.llm_api_key),
            "provider": "deepseek-chat" if "deepseek" in settings.llm_api_base else settings.llm_model,
            "base_url": settings.llm_api_base,
        },
        "pipeline": {
            "branches": [
                {"name": "统计特征", "status": "active"},
                {"name": "RoBERTa 深度语义", "status": "active"},
                {"name": "LLM logprob", "status": "active" if settings.llm_api_key else "inactive"},
            ],
        },
    }
    if info["checkpoint_exists"]:
        try:
            import torch
            ckpt = torch.load(checkpoint, map_location="cpu")
            info["val_acc"] = ckpt.get("val_acc", "N/A")
            info["val_f1"] = ckpt.get("val_f1", "N/A")
            info["ece"] = ckpt.get("ece", "N/A")
            info["temperature"] = ckpt.get("temperature", 1.0)
            info["platt_a"] = ckpt.get("platt_a", 1.0)
            info["platt_b"] = ckpt.get("platt_b", 0.0)
            info["calibration"] = "disabled" if (info["temperature"] == 1.0 and info["platt_a"] == 1.0 and info["platt_b"] == 0.0) else "enabled"
        except Exception:
            pass
    return info
