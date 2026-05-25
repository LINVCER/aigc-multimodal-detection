"""
音频训练数据全套生成 (edge-tts + 增强)

策略:
  1. 14 种 edge-tts 中文音色全覆盖
  2. 音频增强: 加噪/MP3压缩/变速/混响
  3. 模拟真实场景多样化合成语音

用法:
  python generate_full_audio_data.py --num_texts 50 --augment
"""

import os, sys, json, random, asyncio, argparse
from pathlib import Path

random.seed(42)

ALL_VOICES = [
    "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural",
    "zh-CN-YunjianNeural", "zh-CN-YunxiNeural",
    "zh-CN-YunxiaNeural", "zh-CN-YunyangNeural",
    "zh-CN-liaoning-XiaobeiNeural",
    "zh-CN-shaanxi-XiaoniNeural",
    "zh-HK-HiuGaaiNeural", "zh-HK-HiuMaanNeural",
    "zh-HK-WanLungNeural",
    "zh-TW-HsiaoChenNeural", "zh-TW-HsiaoYuNeural",
    "zh-TW-YunJheNeural",
]


async def generate_edge_tts(tts_list: list[dict], output_dir: str, voices: list[str]):
    import edge_tts

    for subset in ["train", "test"]:
        (Path(output_dir) / "fake" / subset).mkdir(parents=True, exist_ok=True)

    total = len(tts_list) * len(voices)
    generated = 0

    for i, item in enumerate(tts_list):
        text = item["text"]
        if len(text) < 5:
            continue

        # 前半文本 → train, 后半 → test
        subset = "train" if i < len(tts_list) * 0.8 else "test"

        for v, voice in enumerate(voices):
            try:
                out_name = f"edge_{item['speaker']}_{i:04d}_{voice.split('-')[-1].replace('Neural','')}.wav"
                out_path = Path(output_dir) / "fake" / subset / out_name

                communicate = edge_tts.Communicate(
                    text=text, voice=voice,
                    rate=f"{random.randint(-15, 15):+d}%",
                    pitch=f"{random.randint(-8, 8):+d}Hz",
                )
                await communicate.save(str(out_path))
                generated += 1
                if generated % 20 == 0:
                    print(f"  {generated}/{total} generated...")
                await asyncio.sleep(0.15)
            except Exception as e:
                print(f"  [ERR] {i}/{voice}: {e}")
                await asyncio.sleep(1)

    print(f"  Generated: {generated}/{total}")


def augment_audio(input_dir: str, output_dir: str, num_augmented: int = 3):
    """
    音频增强: 对每条合成语音生成多个增强版本
    - 加噪
    - 低码率 MP3 压缩模拟
    - 音量随机化
    """
    try:
        import librosa
        import soundfile as sf
        import numpy as np
    except ImportError:
        print("  [SKIP] librosa/soundfile not available")
        return

    wavs = list(Path(input_dir).glob("*.wav"))
    if not wavs:
        return

    augmented_dir = Path(output_dir)
    augmented_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for wav_path in wavs[:200]:  # 最多增强 200 条
        audio, sr = librosa.load(str(wav_path), sr=24000, mono=True)

        for aug_idx in range(num_augmented):
            aug = audio.copy()
            aug_type = aug_idx % 3

            if aug_type == 0:
                # 加高斯噪声 (SNR 10-20dB)
                signal_power = np.mean(aug ** 2)
                snr = random.uniform(10, 20)
                noise_power = signal_power / (10 ** (snr / 10))
                noise = np.random.randn(len(aug)) * np.sqrt(noise_power)
                aug = aug + noise.astype(np.float32)
            elif aug_type == 1:
                # 低通滤波模拟电话音质
                from scipy.signal import butter, lfilter
                b, a = butter(4, 0.5, btype='low')
                aug = lfilter(b, a, aug).astype(np.float32)
            elif aug_type == 2:
                # 音量变化 ±6dB
                aug = aug * random.uniform(0.5, 1.5)

            aug = np.clip(aug, -1.0, 1.0)
            out_name = f"{wav_path.stem}_aug{aug_idx}.wav"
            sf.write(str(augmented_dir / out_name), aug, sr)
            count += 1

    print(f"  Augmented: {count} variants")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tts_list", default="../data/audio/tts_generation_list.json")
    parser.add_argument("--output_dir", default="../data/audio")
    parser.add_argument("--num_texts", type=int, default=50)
    parser.add_argument("--voices", type=int, default=14, help="使用的音色数")
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--augment_count", type=int, default=2)
    args = parser.parse_args()

    with open(args.tts_list, "r", encoding="utf-8") as f:
        tts_list = json.load(f)[:args.num_texts]

    voices = ALL_VOICES[:args.voices]
    print("=" * 60)
    print(f"音频数据全套生成")
    print(f"  文本数: {len(tts_list)}")
    print(f"  音色数: {len(voices)}")
    print(f"  预期生成: {len(tts_list) * len(voices)} 条")
    print(f"  增强: {'yes' if args.augment else 'no'}")
    print("=" * 60)

    asyncio.run(generate_edge_tts(tts_list, args.output_dir, voices))

    if args.augment:
        print("\n[增强] fake/train...")
        augment_audio(
            os.path.join(args.output_dir, "fake", "train"),
            os.path.join(args.output_dir, "fake_aug", "train"),
            args.augment_count,
        )

    # 统计
    for sub in ["train", "test"]:
        d = Path(args.output_dir) / "fake" / sub
        cnt = len(list(d.glob("*.wav"))) if d.exists() else 0
        print(f"  fake/{sub}: {cnt} files")

    print("Done.")


if __name__ == "__main__":
    main()
