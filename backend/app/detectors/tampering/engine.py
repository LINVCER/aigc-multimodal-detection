"""篡改检测总调度引擎"""

from __future__ import annotations

import asyncio
import logging

import cv2
import numpy as np
from PIL import Image

from app.detectors.tampering.maskrcnn_branch import MaskRCNNBranch
from app.detectors.tampering.frequency_branch import FrequencyBranch
from app.detectors.tampering.noise_branch import NoiseBranch
from app.detectors.tampering.ela_branch import ELABranch
from app.detectors.tampering.exif_branch import EXIFBranch
from app.detectors.tampering.fusion import TamperingFusion
from app.detectors.tampering.calibrator import TamperingCalibrator
from app.detectors.tampering.visualizer import TamperingVisualizer
from app.detectors.tampering.output import BranchResult, TamperingDetectionOutput

logger = logging.getLogger(__name__)

MAX_LONG_EDGE = 1536


def _resize_for_inference(image: Image.Image) -> tuple[Image.Image, tuple[int, int]]:
    """长边缩放到 MAX_LONG_EDGE，返回 (缩放后图像, 原始尺寸)"""
    w, h = image.size
    if max(w, h) <= MAX_LONG_EDGE:
        return image, (w, h)
    scale = MAX_LONG_EDGE / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    return image.resize((new_w, new_h), Image.BICUBIC), (w, h)


def _resize_mask_to_original(mask: np.ndarray, orig_size: tuple[int, int]) -> np.ndarray:
    """将 mask 缩放回原始尺寸 (INTER_NEAREST 避免灰色过渡带)"""
    orig_w, orig_h = orig_size
    h, w = mask.shape[:2]
    if (w, h) == (orig_w, orig_h):
        return mask
    if mask.dtype == bool:
        uint8_mask = (mask.astype(np.uint8) * 255)
        resized = cv2.resize(uint8_mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
        return resized > 127
    return cv2.resize(mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)


class TamperingEngine:
    """篡改检测总调度"""

    def __init__(self):
        self._maskrcnn = MaskRCNNBranch()
        self._freq = FrequencyBranch()
        self._noise = NoiseBranch()
        self._ela = ELABranch()
        self._exif = EXIFBranch()
        self._fusion = TamperingFusion()
        self._calibrator = TamperingCalibrator()
        self._visualizer = TamperingVisualizer()

    async def run(self, image_data: bytes) -> TamperingDetectionOutput:
        """完整篡改检测流程"""
        try:
            image = Image.open(__import__("io").BytesIO(image_data)).convert("RGB")
        except Exception as e:
            raise ValueError(f"无法解码图像: {e}")

        # 输入标准化: 长边缩放
        infer_image, orig_size = _resize_for_inference(image)

        # 并行执行 5 个分支 (FFT/Noise/ELA/EXIF 用线程池卸载 CPU 密集操作)
        dl_result, freq_result, noise_result, ela_result, exif_result = await asyncio.gather(
            self._maskrcnn.detect(infer_image),
            self._freq.detect(infer_image),
            self._noise.detect(infer_image),
            self._ela.detect(infer_image),
            self._exif.detect(infer_image),
        )

        # 融合
        fused_mask, uncertain_mask = self._fusion.fuse(
            dl_result, freq_result, noise_result, ela_result, exif_result,
        )

        # 缩放回原图尺寸
        fused_mask = _resize_mask_to_original(fused_mask, orig_size)
        uncertain_mask = _resize_mask_to_original(uncertain_mask, orig_size)

        # 置信度校准
        tampering_score, tampering_type = self._calibrator.compute(
            fused_mask, dl_result,
            [dl_result, freq_result, noise_result, ela_result, exif_result],
        )

        # 可视化 (在原图上标注)
        overlay_base64 = self._visualizer.generate_overlay(image, fused_mask, uncertain_mask)
        mask_base64 = self._visualizer.generate_mask_image(fused_mask)

        risk_level = (
            "high" if tampering_score > 0.7 else
            "medium" if tampering_score > 0.3 else
            "low"
        )

        # 计算篡改区域面积比例
        total_pixels = fused_mask.size
        tampered_pixels = np.sum(fused_mask)
        tampering_ratio = tampered_pixels / total_pixels if total_pixels > 0 else 0

        # 更合理的is_tampered判定：
        # 1. 篡改区域面积比例超过阈值（避免小噪声区域导致假阳性）
        # 2. 或者篡改置信度超过阈值
        min_area_ratio = 0.001  # 最小面积比例阈值（0.1%）
        min_confidence = 0.3    # 最小置信度阈值
        
        is_tampered = (
            (tampering_ratio > min_area_ratio and tampering_score > min_confidence) or
            (tampering_score > 0.5)  # 高置信度时忽略面积限制
        )

        return TamperingDetectionOutput(
            is_tampered=bool(is_tampered),
            tampering_score=tampering_score,
            tampering_type=tampering_type,
            mask=fused_mask,
            uncertain_mask=uncertain_mask,
            mask_base64=mask_base64,
            overlay_base64=overlay_base64,
            branch_results=[dl_result, freq_result, noise_result, ela_result, exif_result],
            explanation_data={
                "branches": [
                    {"name": b.branch_name, "confidence": b.confidence,
                     "is_tampered": bool(b.mask.any()) if b.mask is not None else False}
                    for b in [dl_result, freq_result, noise_result, ela_result, exif_result]
                ],
                "fusion_method": "核心-边缘分离集成 + support_ratio",
                "risk_level": risk_level,
                "tampering_ratio": round(tampering_ratio, 6),
                "tampered_pixels": int(tampered_pixels),
                "total_pixels": total_pixels,
            },
            metadata={"original_size": orig_size, "inference_size": infer_image.size},
        )
