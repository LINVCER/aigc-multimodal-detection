"""篡改检测服务层 — 薄层: 调 engine + 存 DB"""

from __future__ import annotations

import logging

from app.detectors.tampering.engine import TamperingEngine
from app.detectors.tampering.output import TamperingDetectionOutput

logger = logging.getLogger(__name__)

# 模块级单例 (懒加载)
_engine: TamperingEngine | None = None


def _get_engine() -> TamperingEngine:
    global _engine
    if _engine is None:
        _engine = TamperingEngine()
    return _engine


async def detect_tampering(
    image_data: bytes,
    options: dict | None = None,
) -> TamperingDetectionOutput:
    """执行篡改检测"""
    engine = _get_engine()
    return await engine.run(image_data)
