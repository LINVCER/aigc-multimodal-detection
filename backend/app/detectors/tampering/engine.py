"""
篡改检测总调度 — 匹配原始项目的 industrial_detect

流程: DL多尺度推理 → 置信度过滤 → FFT + 噪声辅助 → 核心边缘融合 → 形状过滤 → 形态学闭运算
"""

import asyncio
import logging
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

from app.detectors.tampering.maskrcnn_branch import MaskRCNNBranch
from app.detectors.tampering.frequency_branch import FrequencyBranch
from app.detectors.tampering.noise_branch import NoiseBranch
from app.detectors.tampering.fusion import TamperingFusion
from app.detectors.tampering.output import TamperingDetectionOutput

logger = logging.getLogger(__name__)


class TamperingEngine:

    def __init__(self):
        self._maskrcnn = MaskRCNNBranch()
        self._freq = FrequencyBranch()
        self._noise = NoiseBranch()
        self._fusion = TamperingFusion()

    async def run(self, image_data: bytes) -> TamperingDetectionOutput:
        try:
            image = Image.open(BytesIO(image_data)).convert("RGB")
        except Exception as e:
            raise ValueError(f"无法解码图像: {e}")

        w, h = image.size
        img_np = np.array(image)

        # 1. 深度学习多尺度检测 + 置信度映射
        dl_result = self._maskrcnn._detect_sync(image)
        dl_mask = dl_result.mask
        score_map = dl_result.score_map

        # 2. 辅助特征
        freq_result = self._freq._detect_sync(image)
        noise_result = self._noise._detect_sync(image)
        freq_mask = freq_result.mask
        noise_mask = noise_result.mask

        # 3. 核心-边缘分离融合
        fused_mask = self._fusion.fuse(dl_mask, freq_mask, noise_mask)

        # 4. 生成可视化
        overlay_base64 = self._make_overlay(image, fused_mask)
        mask_base64 = self._make_mask_image(fused_mask)

        # 5. 获取全局最高置信度
        prob = float(score_map.max()) if score_map.any() else 0.0

        # 6. 判定
        is_forged = bool(np.any(fused_mask))

        # 风险等级
        risk_level = "high" if prob > 0.7 else "medium" if prob > 0.3 else "low"

        # 篡改类型
        tampering_type = "unknown"
        if is_forged:
            area_ratio = fused_mask.sum() / fused_mask.size
            if area_ratio > 0.3:
                tampering_type = "retouching"
            elif area_ratio < 0.01:
                tampering_type = "copy_move"
            else:
                tampering_type = "splicing"

        return TamperingDetectionOutput(
            is_tampered=is_forged,
            tampering_score=round(prob, 4),
            tampering_type=tampering_type,
            mask=fused_mask,
            uncertain_mask=np.zeros((h, w), dtype=bool),
            mask_base64=mask_base64,
            overlay_base64=overlay_base64,
            branch_results=[dl_result, freq_result, noise_result],
            explanation_data={
                "branches": [
                    {"name": "maskrcnn_resnet50_fpn", "confidence": dl_result.confidence,
                     "is_tampered": dl_result.confidence > 0.65 and bool(dl_mask.any())},
                    {"name": "fft_frequency_anomaly", "confidence": freq_result.confidence,
                     "is_tampered": freq_result.confidence > 0.65},
                    {"name": "noise_inconsistency", "confidence": noise_result.confidence,
                     "is_tampered": noise_result.confidence > 0.65},
                ],
                "fusion_method": "核心-边缘分离集成",
                "risk_level": risk_level,
                "tampered_pixels": int(fused_mask.sum()),
                "total_pixels": int(fused_mask.size),
            },
            metadata={"original_size": (w, h)},
        )

    def _make_overlay(self, image: Image.Image, mask: np.ndarray) -> str:
        import base64
        overlay = np.array(image).copy()
        if mask.any():
            overlay[mask] = (overlay[mask] * 0.6 + np.array([255, 0, 0]) * 0.4).astype(np.uint8)
        # 缩小到最大 1024px
        h, w = overlay.shape[:2]
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            overlay = cv2.resize(overlay, (int(w * scale), int(h * scale)))
        img = Image.fromarray(overlay)
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"

    def _make_mask_image(self, mask: np.ndarray) -> str:
        import base64
        mask_vis = (mask.astype(np.uint8) * 255)
        h, w = mask_vis.shape[:2]
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            mask_vis = cv2.resize(mask_vis, (int(w * scale), int(h * scale)))
        img = Image.fromarray(mask_vis, mode="L").convert("RGB")
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
