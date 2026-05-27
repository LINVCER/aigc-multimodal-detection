"""
噪声不一致检测 — 匹配原始项目的 noise_inconsistency

简单高效: gray → GaussianBlur(5,5) → absdiff → normalize → threshold 25
"""

import asyncio

import cv2
import numpy as np
from PIL import Image

from app.detectors.tampering.base import SpatialEvidenceBranch
from app.detectors.tampering.output import BranchResult


class NoiseBranch(SpatialEvidenceBranch):
    name = "noise_inconsistency"
    version = "1.0.0"

    async def detect(self, image: Image.Image) -> BranchResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._detect_sync, image)

    def _detect_sync(self, image: Image.Image) -> BranchResult:
        img_np = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        noise = cv2.absdiff(gray, blur)
        noise = cv2.normalize(noise, None, 0, 255, cv2.NORM_MINMAX)
        _, binary = cv2.threshold(noise, 25, 255, cv2.THRESH_BINARY)
        mask = binary.astype(bool)

        # 置信度: 使用归一化噪声强度的95分位数表示噪声异常程度
        noise_intensity = np.percentile(noise / 255.0, 95)
        normalized_confidence = min(float(noise_intensity), 1.0)

        return BranchResult(
            branch_name=self.name,
            score_map=mask.astype(np.float32),
            confidence=round(normalized_confidence, 4),
            mask=mask,
            metadata={"method": "GaussianBlur absdiff threshold 25"},
        )
