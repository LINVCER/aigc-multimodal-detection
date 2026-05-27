"""JPEG ELA (Error Level Analysis) 分支 — 压缩一致性检测"""

from __future__ import annotations

import asyncio
import io

import cv2
import numpy as np
from PIL import Image

from app.detectors.tampering.base import SpatialEvidenceBranch
from app.detectors.tampering.output import BranchResult


class ELABranch(SpatialEvidenceBranch):
    name = "jpeg_ela"
    version = "1.0.0"

    def __init__(self, quality: int = 95):
        self.quality = quality

    async def detect(self, image: Image.Image) -> BranchResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_sync, image)

    def _detect_sync(self, image: Image.Image) -> BranchResult:
        # 以指定 quality 重新保存为 JPEG
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=self.quality)
        buf.seek(0)
        recompressed = Image.open(buf).convert("RGB")

        orig = np.array(image, dtype=np.float32)
        recomp = np.array(recompressed, dtype=np.float32)
        # 逐通道差值取最大值
        diff = np.abs(orig - recomp)
        ela_gray = np.max(diff, axis=2)
        # 归一化到 [0,1]
        max_val = ela_gray.max()
        if max_val > 0:
            score_map = (ela_gray / max_val).astype(np.float32)
        else:
            score_map = np.zeros_like(ela_gray, dtype=np.float32)

        confidence = float(np.percentile(score_map, 95))
        return BranchResult(
            branch_name=self.name,
            score_map=score_map,
            confidence=round(confidence, 4),
            metadata={"method": f"JPEG ELA quality={self.quality}"},
        )
