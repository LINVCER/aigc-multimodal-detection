"""完整图像检测管线测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from PIL import Image
import numpy as np


async def main():
    print("=" * 60)
    print("AIGC--多模态检测 Image Detection Pipeline Test")
    print("=" * 60)

    # 生成测试图像 (真实照片模拟 vs 纯色/AI风格模拟)
    real_img = Image.fromarray(
        np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    )
    # 模拟扩散模型生成: 加入一些规律性噪声
    ai_img_array = np.random.normal(128, 30, (256, 256, 3)).astype(np.uint8)
    # 加入一些结构化伪影 (模拟SD/Flux的特征)
    for i in range(0, 256, 16):
        ai_img_array[i:i+2, :, :] = ai_img_array[i:i+2, :, :] * 0.8 + 40
    ai_img = Image.fromarray(np.clip(ai_img_array, 0, 255).astype(np.uint8))

    # --- High Frequency Branch ---
    print("\n[1] High-Frequency CNN Branch...")
    from app.detectors.image.high_freq_branch import HighFreqBranch
    hf = HighFreqBranch()
    hf._ensure_loaded()
    hf_output = await hf.detect(real_img)
    print(f"  Real image: confidence={hf_output.confidence:.4f}, logit={hf_output.logit:.4f}")

    # --- ViT Branch ---
    print("\n[2] CLIP-ViT-L/14 Branch (UniversalFakeDetect)...")
    from app.detectors.image.vit_branch import ViTBranch
    vit = ViTBranch()
    vit._ensure_loaded()
    vit_output = await vit.detect(real_img)
    print(f"  Loaded: {vit._loaded}")
    print(f"  Real image: confidence={vit_output.confidence:.4f}, logit={vit_output.logit:.4f}")

    if vit._loaded:
        vit_ai = await vit.detect(ai_img)
        print(f"  AI-like image: confidence={vit_ai.confidence:.4f}")

    # --- Fusion ---
    print("\n[3] Dual-Branch Fusion...")
    from app.detectors.image.fusion import ImageFusion
    fusion = ImageFusion()
    fused = fusion.fuse(hf_output, vit_output)
    print(f"  Fused: is_ai={fused.is_ai_generated}, conf={fused.confidence:.4f}")
    print(f"  Branches: {fused.explanation_data.get('branches', [])}")

    # --- Calibration ---
    fused_cal = hf.calibrate_output(fused)
    print(f"\n[4] Calibrated: conf={fused_cal.calibrated_confidence:.4f}, CI={fused_cal.confidence_interval}")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
