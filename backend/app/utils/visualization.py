"""
可视化图片生成 — 用于解释报告
生成傅里叶频谱图、异常热力图、基频跳变图等
"""

import io
import numpy as np
from PIL import Image


def generate_spectrum_image(image_array: np.ndarray) -> bytes:
    """生成傅里叶频谱图 (Phase 3 完整实现)"""
    # 灰度转换
    if image_array.ndim == 3:
        gray = np.mean(image_array, axis=2)
    else:
        gray = image_array

    # FFT
    fft = np.fft.fft2(gray)
    fft_shift = np.fft.fftshift(fft)
    magnitude_spectrum = np.log(np.abs(fft_shift) + 1)

    # 归一化到 [0, 255]
    mag_norm = ((magnitude_spectrum - magnitude_spectrum.min()) /
                 (magnitude_spectrum.max() - magnitude_spectrum.min()) * 255).astype(np.uint8)

    img = Image.fromarray(mag_norm)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_heatmap(image_array: np.ndarray, anomaly_mask: np.ndarray) -> bytes:
    """生成异常区域热力图 (Phase 3 完整实现)"""
    # 将 anomaly_mask 转为红色热力叠加到原图
    img = Image.fromarray(image_array.astype(np.uint8)).convert("RGBA")
    heatmap = Image.fromarray(anomaly_mask.astype(np.uint8)).convert("L")
    # 将热力图着色为红色
    heatmap_colored = Image.new("RGBA", img.size, (0, 0, 0, 0))
    for y in range(img.height):
        for x in range(img.width):
            alpha = heatmap.getpixel((x, y))
            if alpha > 30:
                heatmap_colored.putpixel((x, y), (255, 0, 0, alpha))
    img = Image.alpha_composite(img, heatmap_colored)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
