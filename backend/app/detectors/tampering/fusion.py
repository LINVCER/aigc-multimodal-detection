"""核心-边缘分离融合引擎"""

from __future__ import annotations

import cv2
import numpy as np

from app.detectors.tampering.output import BranchResult, TamperingDetectionOutput


class TamperingFusion:
    """3 分支空间 mask 融合: 核心-边缘分离 + support_ratio"""

    def __init__(
        self,
        freq_threshold: float = 0.6,
        noise_threshold: float = 0.6,
        ela_threshold: float = 0.5,
        support_ratio_confirm: float = 0.35,
        support_ratio_uncertain: float = 0.15,
        shape_min_area: int = 80,
        shape_aspect_ratio_min: float = 0.1,
        shape_aspect_ratio_max: float = 8.0,
    ):
        self.freq_threshold = freq_threshold
        self.noise_threshold = noise_threshold
        self.ela_threshold = ela_threshold
        self.support_ratio_confirm = support_ratio_confirm
        self.support_ratio_uncertain = support_ratio_uncertain
        self.shape_min_area = shape_min_area
        self.shape_aspect_ratio_min = shape_aspect_ratio_min
        self.shape_aspect_ratio_max = shape_aspect_ratio_max

    def fuse(
        self,
        dl_result: BranchResult,
        freq_result: BranchResult,
        noise_result: BranchResult,
        ela_result: BranchResult,
        exif_result: BranchResult,
    ) -> tuple[np.ndarray, np.ndarray]:
        """融合 5 个分支，返回 (fused_mask, uncertain_mask)"""
        dl_mask = dl_result.mask.astype(np.uint8)
        freq_score = freq_result.score_map
        noise_score = noise_result.score_map
        ela_score = ela_result.score_map

        # 核心: 腐蚀 DL mask (高置信度内部)
        kernel_core = np.ones((3, 3), np.uint8)
        core = cv2.erode(dl_mask, kernel_core)

        # 边缘: 膨胀 DL mask - 核心
        kernel_edge = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(dl_mask, kernel_edge)
        edge = dilated - core

        # 边缘确认: freq AND noise AND ela (连续值阈值)
        edge_support = (
            (freq_score > self.freq_threshold)
            & (noise_score > self.noise_threshold)
            & (ela_score > self.ela_threshold)
        ).astype(np.uint8)

        # support_ratio 检查
        edge_pixels = int(edge.sum())
        if edge_pixels > 0:
            support_ratio = int((edge.astype(bool) & edge_support.astype(bool)).sum()) / edge_pixels
        else:
            support_ratio = 0.0

        uncertain = np.zeros_like(edge, dtype=bool)
        if support_ratio > self.support_ratio_confirm:
            confirmed_edge = edge & edge_support
        elif support_ratio > self.support_ratio_uncertain:
            # 低支持率 → 标记为不确定区域
            uncertain = (edge.astype(bool) & edge_support.astype(bool))
            confirmed_edge = np.zeros_like(edge)
        else:
            confirmed_edge = np.zeros_like(edge)

        fused = core | confirmed_edge

        # 形状过滤
        fused = self._shape_filter(fused.astype(bool))

        # 形态学闭运算
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fused = cv2.morphologyEx(fused.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool)

        return fused, uncertain

    def _shape_filter(self, mask: np.ndarray) -> np.ndarray:
        if not mask.any():
            return mask
        mask_uint8 = (mask.astype(np.uint8) * 255)
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
