"""
图像检测服务编排 — 预处理 → 三分支检测 → 融合 → 解释
三分支: 高频噪声CNN + CLIP-ViT + AI视觉模型
"""

import asyncio

from PIL import Image
import io

from app.detectors.base import DetectionOutput
from app.detectors.image.high_freq_branch import HighFreqBranch
from app.detectors.image.vit_branch import ViTBranch
from app.detectors.image.mimo_branch import MiMoVLBranch
from app.detectors.image.fusion import ImageFusion

_hf_branch = HighFreqBranch()
_vit_branch = ViTBranch()
_mimo_branch = MiMoVLBranch()
_fusion = ImageFusion()


async def detect_image(image_data: bytes, options: dict | None = None) -> DetectionOutput:
    do_explain = options.get("explain", True) if options else True
    sensitivity = options.get("sensitivity", 0.6) if options else 0.6
    _fusion.set_sensitivity(sensitivity)

    try:
        image = Image.open(io.BytesIO(image_data))
    except Exception:
        return DetectionOutput(
            is_ai_generated=False, confidence=0.5, logit=0.0,
            metadata={"status": "invalid_image", "note": "无法解析图像文件"},
        )

    # 格式验证
    fmt = image.format or "UNKNOWN"
    if fmt not in ("JPEG", "PNG", "WEBP", "BMP"):
        image = image.convert("RGB")

    # 三分支并行检测 (ViT 内存不足时自动跳过)
    vit_output = DetectionOutput(is_ai_generated=False, confidence=0.5, logit=0.0,
                                 metadata={"status": "memory_error", "note": "4GB内存不足，跳过ViT"})
    try:
        hf_output, vit_output, mimo_output = await asyncio.gather(
            _hf_branch.detect(image),
            _vit_branch.detect(image),
            _mimo_branch.detect(image),
        )
    except Exception:
        hf_output, mimo_output = await asyncio.gather(
            _hf_branch.detect(image),
            _mimo_branch.detect(image),
        )

    # 融合
    fused = _fusion.fuse(hf_output, vit_output, mimo_output)

    # 校准
    fused = _hf_branch.calibrate_output(fused)

    # 计算频谱数据和解释
    if do_explain:
        import numpy as np
        try:
            gray = image.convert("L").resize((256, 256))
            gray_arr = np.array(gray, dtype=np.float32)
            fft = np.fft.fft2(gray_arr)
            fft_shifted = np.fft.fftshift(np.abs(fft))
            # 高频能量占比
            h, w = fft_shifted.shape
            center_region = fft_shifted[h//4:3*h//4, w//4:3*w//4]
            high_freq_ratio = 1.0 - center_region.sum() / fft_shifted.sum()
        except Exception:
            high_freq_ratio = None

        hf_explain = await _hf_branch.explain(image, hf_output)
        vit_explain = await _vit_branch.explain(image, vit_output)
        mimo_explain = await _mimo_branch.explain(image, mimo_output)

        branches_info = [
            {"name": "高频噪声CNN", "confidence": hf_output.confidence,
             "is_ai": hf_output.is_ai_generated},
            {"name": "CLIP-ViT语义", "confidence": vit_output.confidence,
             "is_ai": vit_output.is_ai_generated},
        ]
        # MiMo 分支只有在可用时才加入
        if mimo_output.metadata.get("status") != "model_not_loaded":
            branches_info.append(
                {"name": "AI视觉模型", "confidence": mimo_output.confidence,
                 "is_ai": mimo_output.is_ai_generated}
            )

        fused.explanation_data = {
            "image_format": fmt,
            "branches": branches_info,
            "frequency_analysis": {
                "high_freq_energy_ratio": round(high_freq_ratio, 4) if high_freq_ratio else None,
                "note": "AI生成图像常表现出异常的高频能量分布" if high_freq_ratio and high_freq_ratio > 0.65 else None,
            },
            "high_freq_explanation": hf_explain,
            "vit_explanation": vit_explain,
            "mimo_explanation": mimo_explain if mimo_output.metadata.get("status") != "model_not_loaded" else None,
        }

    return fused


async def generate_spectrum_visualization(image_data: bytes) -> bytes:
    """
    生成傅里叶频谱可视化图
    用于解释报告中的频域异常分布展示
    """
    from app.utils.visualization import generate_spectrum_image
    import numpy as np

    image = Image.open(io.BytesIO(image_data)).convert("RGB").resize((512, 512))
    img_array = np.array(image)
    return generate_spectrum_image(img_array)
