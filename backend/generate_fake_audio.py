"""
TTS 合成语音生成

支持多引擎:
  chattts:  本地 ChatTTS 模型, 最自然的中文合成 (默认)
  edge-tts: 微软免费 TTS, 14 种中文语音, 零模型下载

用法:
  python generate_fake_audio.py --engine chattts
  python generate_fake_audio.py --engine edge-tts
  python generate_fake_audio.py --engine all --voices 5
"""

import os, sys, json, random, argparse, asyncio, time
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


def generate_chattts(tts_list: list[dict], output_dir: str, num_voices: int = 5):
    """用本地 ChatTTS 生成合成语音 (最自然的中文 TTS)"""
    import torch
    import numpy as np
    import soundfile as sf
    from ChatTTS import Chat

    print("Loading ChatTTS...")
    c = Chat()
    c.load(source="custom", custom_path=r"D:\AAA\image_nious\models\audio\chattts_v2")
    print("  ChatTTS model loaded")

    for subset in ["train", "test"]:
        (Path(output_dir) / "fake" / subset).mkdir(parents=True, exist_ok=True)

    total = len(tts_list) * num_voices
    generated = 0

    for i, item in enumerate(tts_list):
        text = item["text"]
        if len(text) < 5:
            continue

        subset = "train" if i < len(tts_list) * 0.8 else "test"

        for v in range(num_voices):
            try:
                # Vary temperature for diverse outputs
                params = Chat.InferCodeParams(
                    temperature=0.3 + v * 0.12,
                    top_P=0.7 + v * 0.05,
                    manual_seed=42 + i * 100 + v,
                )
                wavs = c.infer([text], use_decoder=True, params_infer_code=params)

                if wavs and len(wavs) > 0:
                    audio = wavs[0]
                    if isinstance(audio, torch.Tensor):
                        audio = audio.cpu().numpy()
                    audio = np.squeeze(audio)

                    out_name = f"chattts_{item['speaker']}_{i:04d}_v{v}.wav"
                    out_path = Path(output_dir) / "fake" / subset / out_name
                    sf.write(str(out_path), audio.astype(np.float32), 24000)
                    generated += 1
                    if generated % 10 == 0:
                        print(f"  {generated}/{total} generated...")
            except Exception as e:
                print(f"  [ERR] chattts {i}/{v}: {e}")

    print(f"  ChatTTS: {generated}/{total}")


async def generate_edge_tts(tts_list: list[dict], output_dir: str, voices: list[str]):
    """用 Microsoft Edge TTS 生成合成语音"""
    import edge_tts

    # 选择多样化音色
    voices_pool = [
        "zh-CN-XiaoxiaoNeural",      # 女声 1 (标准)
        "zh-CN-XiaoyiNeural",        # 女声 2
        "zh-CN-YunxiNeural",         # 男声 1
        "zh-CN-YunjianNeural",       # 男声 2
        "zh-CN-YunyangNeural",       # 男声 3
        "zh-CN-YunxiaNeural",        # 男声 4
        "zh-CN-liaoning-XiaobeiNeural",  # 东北女声
        "zh-HK-HiuGaaiNeural",       # 粤语女声
    ]
    voices = voices_pool[:num_voices]

    fake_dir = Path(output_dir) / "fake" / "test"
    fake_dir.mkdir(parents=True, exist_ok=True)
    # 也需要 train 目录的合成语音 (用相同文本生成不同版本的)
    fake_train = Path(output_dir) / "fake" / "train"
    fake_train.mkdir(parents=True, exist_ok=True)

    total = len(tts_list) * len(voices)
    generated = 0

    for i, item in enumerate(tts_list):
        text = item["text"]
        if len(text) < 5:
            continue

        for v, voice in enumerate(voices):
            try:
                # 随机微调语速/音调避免过于统一
                rate = f"{random.randint(-10, 10):+d}%"
                pitch = f"{random.randint(-5, 5):+d}Hz"

                out_name = f"edge_{item['speaker']}_{i:04d}_{voice.split('-')[-1].replace('Neural','')}.wav"
                out_path = fake_dir / out_name

                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice,
                    rate=rate,
                    pitch=pitch,
                )
                await communicate.save(str(out_path))

                generated += 1
                if generated % 10 == 0:
                    print(f"  {generated}/{total} generated...")

                # 间隔避免限流
                await asyncio.sleep(0.2)

            except Exception as e:
                print(f"  [ERR] {i}/{voice}: {e}")
                await asyncio.sleep(1)
                continue

    print(f"  edge-tts 完成: {generated}/{total}")


def main():
    parser = argparse.ArgumentParser(description="TTS 合成语音生成")
    parser.add_argument("--engine", default="edge-tts")
    parser.add_argument("--tts_list", default="../data/audio/tts_generation_list.json")
    parser.add_argument("--output_dir", default="../data/audio")
    parser.add_argument("--voices", type=int, default=3, help="使用的音色数")
    parser.add_argument("--max_samples", type=int, default=50, help="最多生成文本数")
    args = parser.parse_args()

    with open(args.tts_list, "r", encoding="utf-8") as f:
        tts_list = json.load(f)

    if args.max_samples:
        tts_list = tts_list[:args.max_samples]

    print("=" * 60)
    print(f"TTS 合成语音生成 ({args.engine})")
    print(f"  文本数: {len(tts_list)}")
    print(f"  音色数: {args.voices}")
    print(f"  预期生成: {len(tts_list) * args.voices} 条")
    print("=" * 60)

    if args.engine in ("chattts", "all"):
        print("\n[ChatTTS]")
        generate_chattts(tts_list, args.output_dir, args.voices)

    edge_voices = ALL_VOICES[:min(args.voices, len(ALL_VOICES))]
    if args.engine in ("edge-tts", "all"):
        print("\n[edge-tts]")
        asyncio.run(generate_edge_tts(tts_list, args.output_dir, edge_voices))

    # 统计
    for subset in ["test", "train"]:
        fake_dir = Path(args.output_dir) / "fake" / subset
        if fake_dir.exists():
            count = len(list(fake_dir.glob("*.wav")))
            print(f"  fake/{subset}: {count} files")

    real_test = Path(args.output_dir) / "real" / "test"
    if real_test.exists():
        print(f"  real/test:   {len(list(real_test.glob('*.wav')))} files")

    print("\n下一步: python train_audio_detector.py")
    print("Done.")


if __name__ == "__main__":
    main()
