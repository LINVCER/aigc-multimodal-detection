"""
FFT 频域异常检测 — 匹配原始项目的 frequency_anomaly

简单高效: fft2d → log magnitude → normalize 0-255 → threshold
"""

import asyncio

import cv2
import numpy as np
from PIL import Image

from app.detectors.tampering.base import SpatialEvidenceBranch
from app.detectors.tampering.output import BranchResult


class FrequencyBranch(SpatialEvidenceBranch):
    name = "fft_frequency_anomaly"
    version = "1.0.0"

    async def detect(self, image: Image.Image) -> BranchResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._detect_sync, image)

    def _detect_sync(self, image: Image.Image) -> BranchResult:
        img_np = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude = np.log(np.abs(fshift) + 1)
        norm = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, binary = cv2.threshold(norm, 180, 255, cv2.THRESH_BINARY)
        mask = binary.astype(bool)

        # 置信度: 使用归一化幅度的95分位数表示频率异常程度
        magnitude_score = np.percentile(magnitude / (np.max(magnitude) + 1e-10), 95)
        normalized_confidence = min(float(magnitude_score), 1.0)

        return BranchResult(
            branch_name=self.name,
            score_map=mask.astype(np.float32),
            confidence=round(normalized_confidence, 4),
            mask=mask,
            metadata={"method": "FFT log-magnitude threshold 180"},
        )
