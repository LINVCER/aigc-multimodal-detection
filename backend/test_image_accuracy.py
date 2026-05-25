"""SD1.5 验证集准确率测试"""
import asyncio, os, sys, random, time
from pathlib import Path
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.detectors.image.high_freq_branch import HighFreqBranch
from app.detectors.image.vit_branch import ViTBranch
from app.detectors.image.fusion import ImageFusion

VAL_DIR = "D:/AAA/image_data/sd_v1_5/imagenet_ai_0424_sdv5/val"
SAMPLE_SIZE = 500

async def main():
    # 随机采样
    ai_files = list(Path(f"{VAL_DIR}/ai").glob("*"))
    nature_files = list(Path(f"{VAL_DIR}/nature").glob("*"))
    random.seed(42)
    random.shuffle(ai_files)
    random.shuffle(nature_files)

    test_files = [
        (f, 1) for f in ai_files[:SAMPLE_SIZE]
    ] + [
        (f, 0) for f in nature_files[:SAMPLE_SIZE]
    ]
    random.shuffle(test_files)
    print(f"测试集: {SAMPLE_SIZE} AI + {SAMPLE_SIZE} Nature = {len(test_files)} 张")

    hf = HighFreqBranch()
    vit = ViTBranch()
    fusion = ImageFusion()

    hf_correct = vit_correct = fused_correct = 0
    total = 0
    start = time.time()

    for i, (filepath, label) in enumerate(test_files):
        try:
            img = Image.open(filepath).convert("RGB")

            hf_out = await hf.detect(img)
            vit_out = await vit.detect(img)
            fused_out = fusion.fuse(hf_out, vit_out)

            if (hf_out.confidence > 0.5) == (label == 1):
                hf_correct += 1
            if (vit_out.confidence > 0.5) == (label == 1):
                vit_correct += 1
            if (fused_out.is_ai_generated) == (label == 1):
                fused_correct += 1
            total += 1

            if (i + 1) % 100 == 0:
                elapsed = time.time() - start
                speed = (i + 1) / elapsed
                print(f"  [{i+1}/{len(test_files)}] CNN={hf_correct/total:.1%} ViT={vit_correct/total:.1%} Fused={fused_correct/total:.1%} ({speed:.1f} img/s)")

        except Exception as e:
            continue

    print(f"\n=== 准确率 (SD1.5 验证集 {total} 张) ===")
    print(f"  HighFreq CNN: {hf_correct}/{total} = {hf_correct/total:.2%}")
    print(f"  ViT Branch:   {vit_correct}/{total} = {vit_correct/total:.2%}")
    print(f"  Fused:        {fused_correct}/{total} = {fused_correct/total:.2%}")
    print(f"  耗时: {time.time()-start:.1f}s")

asyncio.run(main())
