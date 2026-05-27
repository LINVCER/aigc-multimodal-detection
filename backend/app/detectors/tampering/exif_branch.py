"""EXIF 元数据一致性检测分支 — 全局置信度，无空间信息"""

from __future__ import annotations

import asyncio
import logging

import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS

from app.detectors.tampering.base import SpatialEvidenceBranch
from app.detectors.tampering.output import BranchResult

logger = logging.getLogger(__name__)

# 已知编辑软件关键词
EDIT_SOFTWARE_KEYWORDS = {
    "photoshop", "gimp", "snapseed", "lightroom", "paint.net",
    "affinity", "capture one", "luminar", "darktable", "rawtherapee",
    "faceapp", "meitu", "meipai", "facetune", "picsart",
}


class EXIFBranch(SpatialEvidenceBranch):
    name = "exif_metadata"
    version = "1.0.0"

    async def detect(self, image: Image.Image) -> BranchResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_sync, image)

    def _detect_sync(self, image: Image.Image) -> BranchResult:
        h, w = image.height, image.width
        flags: list[str] = []
        score = 0.0

        try:
            exif_data = image.getexif()
            if not exif_data:
                # 无 EXIF — 可疑但不确定
                score = 0.3
                flags.append("no_exif")
            else:
                exif_dict = {TAGS.get(k, k): v for k, v in exif_data.items()}
                # 1. 检查 Software 字段
                software = str(exif_dict.get("Software", "")).lower()
                for kw in EDIT_SOFTWARE_KEYWORDS:
                    if kw in software:
                        score = max(score, 0.8)
                        flags.append(f"edit_software:{kw}")
                        break
                # 2. 检查是否有 Make/Model (相机应有)
                if "Make" not in exif_dict and "Model" not in exif_dict:
                    score = max(score, 0.2)
                    flags.append("no_camera_info")
                # 3. 检查 DateTime 异常
                dt = exif_dict.get("DateTimeOriginal") or exif_dict.get("DateTime", "")
                if not dt:
                    score = max(score, 0.15)
                    flags.append("no_datetime")
        except Exception:
            logger.debug("EXIF read error", exc_info=True)
            score = 0.1
            flags.append("exif_read_error")

        score = min(score, 1.0)
        # 全图均匀 score_map
        score_map = np.full((h, w), score, dtype=np.float32)

        return BranchResult(
            branch_name=self.name,
            score_map=score_map,
            confidence=round(score, 4),
            metadata={"flags": flags, "method": "EXIF metadata consistency"},
        )
