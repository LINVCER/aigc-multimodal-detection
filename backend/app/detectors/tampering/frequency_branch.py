"""FFT 频域异常检测分支 — 输出连续 score_map"""

from __future__ import annotations

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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_sync, image)

    def _detect_sync(self, image: Image.Image) -> BranchResult:
        img_np = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY).astype(np.float32)
        
        h, w = gray.shape
        
        # 1. 计算相位谱（对篡改边界更敏感）
        f = np.fft.fft2(gray)
        phase = np.angle(f)
        phase_shift = np.fft.fftshift(phase)
        
        # 2. 计算幅度谱的高频衰减异常
        magnitude = np.abs(f)
        magnitude_shift = np.fft.fftshift(magnitude)
        
        # 3. 创建频率环形掩码，检测不同频率区间的能量分布
        cy, cx = h // 2, w // 2
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        max_dist = min(cx, cy)
        
        # 低频、中频、高频区域
        low_mask = dist < max_dist * 0.1
        mid_mask = (dist >= max_dist * 0.1) & (dist < max_dist * 0.5)
        high_mask = dist >= max_dist * 0.5
        
        # 计算各频段能量比
        total_energy = np.sum(magnitude_shift ** 2) + 1e-10
        low_energy = np.sum((magnitude_shift * low_mask) ** 2) / total_energy
        mid_energy = np.sum((magnitude_shift * mid_mask) ** 2) / total_energy
        high_energy = np.sum((magnitude_shift * high_mask) ** 2) / total_energy
        
        # 4. 检测8x8块边界频率特征（JPEG压缩痕迹）
        # 对每个8x8块进行FFT，检测块边界的频率突变
        block_size = 8
        score_map = np.zeros((h, w), dtype=np.float32)
        
        # 使用滑动窗口检测局部频率异常
        step = block_size
        for y in range(0, h - block_size, step):
            for x in range(0, w - block_size, step):
                block = gray[y:y+block_size, x:x+block_size]
                block_fft = np.fft.fft2(block)
                block_mag = np.abs(block_fft)
                
                # 检测块内高频分量异常
                high_freq_ratio = np.sum(block_mag[4:, 4:]) / (np.sum(block_mag) + 1e-10)
                score_map[y:y+block_size, x:x+block_size] = high_freq_ratio
        
        # 5. 相位一致性异常检测
        # 篡改区域的相位通常不一致
        # 计算局部相位标准差（使用滑动窗口）
        phase_abs = np.abs(phase_shift)
        phase_blur = cv2.GaussianBlur(phase_abs, (5, 5), 0)
        phase_diff = np.abs(phase_abs - phase_blur)
        phase_score = cv2.normalize(phase_diff, None, 0.0, 1.0, cv2.NORM_MINMAX)
        
        # 6. 综合评分
        # 能量分布异常 + 块边界异常 + 相位不一致
        energy_anomaly = np.full((h, w), 1.0 - low_energy, dtype=np.float32)
        block_anomaly = cv2.normalize(score_map, None, 0.0, 1.0, cv2.NORM_MINMAX)
        
        # 加权融合
        final_score_map = (
            0.4 * block_anomaly + 
            0.3 * phase_score + 
            0.3 * energy_anomaly
        )
        
        # 归一化到 [0,1]
        score_map = cv2.normalize(final_score_map, None, 0.0, 1.0, cv2.NORM_MINMAX).astype(np.float32)
        
        # 计算整体置信度（使用高百分位）
        confidence = float(np.percentile(score_map, 95))
        
        return BranchResult(
            branch_name=self.name,
            score_map=score_map,
            confidence=round(confidence, 4),
            metadata={
                "method": "FFT phase + 8x8 block + energy distribution",
                "energy_distribution": {
                    "low": round(low_energy, 4),
                    "mid": round(mid_energy, 4),
                    "high": round(high_energy, 4),
                },
            },
        )
