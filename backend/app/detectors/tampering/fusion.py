"""
核心-边缘分离融合 + 形状过滤 — 匹配原始项目的 ensemble_masks

核心: 腐蚀 DL mask
边缘: 膨胀 DL mask - 核心
辅助: freq_mask AND noise_mask (两者必须同时确认)
最终: core | (edge & aux)
→ 形状过滤 → 形态学闭运算
"""

import cv2
import numpy as np

from app.detectors.tampering.output import BranchResult


class TamperingFusion:

    def __init__(
        self,
        shape_min_area: int = 80,
        shape_aspect_ratio_min: float = 0.1,
        shape_aspect_ratio_max: float = 8.0,
    ):
        self.shape_min_area = shape_min_area
        self.shape_aspect_ratio_min = shape_aspect_ratio_min
        self.shape_aspect_ratio_max = shape_aspect_ratio_max

    def fuse(self, dl_mask: np.ndarray, freq_mask: np.ndarray, noise_mask: np.ndarray) -> np.ndarray:
        dl = dl_mask.astype(np.uint8)

        # 核心区域（更可靠）
        kernel_core = np.ones((3, 3), np.uint8)
        core = cv2.erode(dl, kernel_core)

        # 边缘区域（允许辅助特征补充）
        kernel_edge = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(dl, kernel_edge)
        edge = dilated - core

        # 噪声为主，频域为辅：噪声 OR (频域 AND 噪声) 确认边缘
        noise_confirm = noise_mask.astype(np.uint8)
        freq_confirm = (freq_mask & noise_mask).astype(np.uint8)

        # 核心 + 边缘内被噪声确认的区域 (噪声权重更高)
        fused = core | (edge & (noise_confirm | freq_confirm))
        fused = fused.astype(bool)

        # 形状过滤
        fused = self._shape_filter(fused)

        # 小核闭运算填补内部小孔
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fused = cv2.morphologyEx(fused.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool)

        return fused

    def _shape_filter(self, mask: np.ndarray) -> np.ndarray:
        if not mask.any():
            return mask
        mask_uint8 = mask.astype(np.uint8)
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        final = np.zeros_like(mask_uint8)
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.shape_min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            ratio = w / (h + 1e-6)
            if ratio > self.shape_aspect_ratio_max or ratio < self.shape_aspect_ratio_min:
                continue
            cv2.drawContours(final, [c], -1, 255, -1)
        return final.astype(bool)
