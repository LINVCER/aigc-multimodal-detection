"""篡改检测可视化引擎 — overlay/mask/uncertain base64 生成"""

from __future__ import annotations

import base64
import io

import cv2
import numpy as np
from PIL import Image

MAX_DISPLAY_SIZE = 1024


def _resize_to_display(image_np: np.ndarray) -> np.ndarray:
    """缩放到最大 MAX_DISPLAY_SIZE px"""
    h, w = image_np.shape[:2]
    if max(h, w) <= MAX_DISPLAY_SIZE:
        return image_np
    scale = MAX_DISPLAY_SIZE / max(h, w)
    return cv2.resize(image_np, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def _to_base64_png(arr: np.ndarray) -> str:
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


class TamperingVisualizer:
    """生成可视化 base64 图像"""

    def generate_overlay(
        self,
        image: Image.Image,
        mask: np.ndarray,
        uncertain_mask: np.ndarray,
    ) -> str:
        """
        红色 = 确认篡改区域 (40% 透明度)
        黄色 = 不确定区域 (30% 透明度)
        其他 = 原图
        """
        overlay = np.array(image).copy()
        # 红色标注确认篡改
        if mask.any():
            overlay[mask] = (overlay[mask] * 0.6 + np.array([255, 0, 0]) * 0.4).astype(np.uint8)
        # 黄色标注不确定 (排除已确认区域)
        uncertain_only = uncertain_mask & ~mask
        if uncertain_only.any():
            overlay[uncertain_only] = (
                overlay[uncertain_only] * 0.7 + np.array([255, 255, 0]) * 0.3
            ).astype(np.uint8)
        overlay = _resize_to_display(overlay)
        return _to_base64_png(overlay)

    def generate_mask_image(self, mask: np.ndarray) -> str:
        """白=篡改, 黑=真实"""
        mask_vis = (mask.astype(np.uint8) * 255)
        mask_vis = _resize_to_display(mask_vis)
        # 确保 3 通道
        if mask_vis.ndim == 2:
            mask_vis = cv2.cvtColor(mask_vis, cv2.COLOR_GRAY2RGB)
        return _to_base64_png(mask_vis)
