"""噪声不一致检测分支 — 输出连续 score_map"""

from __future__ import annotations

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
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_sync, image)

    def _detect_sync(self, image: Image.Image) -> BranchResult:
        img_np = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY).astype(np.float32)
        
        h, w = gray.shape
        
        # 1. 提取噪声层（去除信号后的残差）
        # 使用中值滤波去除细节，保留噪声
        denoised = cv2.medianBlur(np.uint8(gray), 5).astype(np.float32)
        noise = gray - denoised
        
        # 2. 计算局部噪声统计量
        # 使用滑动窗口计算局部噪声的标准差
        block_size = 32
        noise_std_map = np.zeros((h, w), dtype=np.float32)
        noise_mean_map = np.zeros((h, w), dtype=np.float32)
        
        # 使用积分图加速计算
        noise_sq = noise ** 2
        
        # 计算局部均值和标准差
        kernel = np.ones((block_size, block_size), dtype=np.float32) / (block_size * block_size)
        local_mean = cv2.filter2D(noise, -1, kernel)
        local_sq_mean = cv2.filter2D(noise_sq, -1, kernel)
        local_var = local_sq_mean - local_mean ** 2
        local_std = np.sqrt(np.maximum(local_var, 0))
        
        # 3. 检测噪声模式不一致性
        # 将图像分成网格，比较每个区域的噪声特性
        grid_size = 4
        grid_h, grid_w = h // grid_size, w // grid_size
        
        grid_stds = []
        for i in range(grid_size):
            for j in range(grid_size):
                y1, y2 = i * grid_h, (i + 1) * grid_h
                x1, x2 = j * grid_w, (j + 1) * grid_w
                block_noise = noise[y1:y2, x1:x2]
                grid_stds.append(np.std(block_noise))
        
        # 计算噪声标准差的变异系数（CV）
        grid_stds = np.array(grid_stds)
        mean_std = np.mean(grid_stds)
        cv_noise = np.std(grid_stds) / (mean_std + 1e-10)
        
        # 4. 生成score_map
        # 基于局部噪声标准差与全局噪声模式的偏差
        global_noise_std = np.std(noise)
        
        # 计算每个像素的噪声异常分数
        # 基于局部标准差与全局标准差的偏差
        deviation = np.abs(local_std - global_noise_std) / (global_noise_std + 1e-10)
        
        # 归一化到 [0,1]
        score_map = cv2.normalize(deviation, None, 0.0, 1.0, cv2.NORM_MINMAX).astype(np.float32)
        
        # 5. 添加噪声模式空间一致性检测
        # 使用LBP（局部二值模式）检测噪声纹理的突变
        # 简化版：计算噪声的梯度
        noise_grad_x = cv2.Sobel(noise, cv2.CV_32F, 1, 0, ksize=3)
        noise_grad_y = cv2.Sobel(noise, cv2.CV_32F, 0, 1, ksize=3)
        noise_grad = np.sqrt(noise_grad_x ** 2 + noise_grad_y ** 2)
        noise_grad_norm = cv2.normalize(noise_grad, None, 0.0, 1.0, cv2.NORM_MINMAX)
        
        # 综合评分：局部噪声偏差 + 噪声梯度异常
        final_score = 0.7 * score_map + 0.3 * noise_grad_norm
        score_map = cv2.normalize(final_score, None, 0.0, 1.0, cv2.NORM_MINMAX).astype(np.float32)
        
        # 计算整体置信度
        confidence = float(np.percentile(score_map, 95))
        
        return BranchResult(
            branch_name=self.name,
            score_map=score_map,
            confidence=round(confidence, 4),
            metadata={
                "method": "Noise pattern inconsistency (local std deviation + gradient)",
                "cv_noise": round(cv_noise, 4),
                "global_noise_std": round(global_noise_std, 4),
            },
        )
