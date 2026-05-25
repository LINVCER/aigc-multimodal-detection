"""
AISHELL-3 音频数据准备

1. 解析 content.txt 提取中文文本
2. 采样说话人 (训练200人/测试18人，不重叠)
3. 复制 wav 到 data/audio/real/
4. 生成 TTS 合成文本列表

用法:
  python prepare_audio_data.py --aishell_dir D:/AAA/AISHELL-3 --output_dir ../data/audio
"""

import os, sys, json, random, shutil, re, argparse
from pathlib import Path
from collections import defaultdict

random.seed(42)


def parse_content(content_path: str) -> list[dict]:
    """解析 content.txt → [{speaker, filename, text_pinyin, text_clean}]"""
    samples = []
    with open(content_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            fname = parts[0].strip()
            text_pinyin = parts[1].strip()
            # 提取纯中文文本 (去除拼音)
            clean = re.sub(r'\s+[a-z]+\d', '', text_pinyin)
            clean = re.sub(r'[a-zA-Z0-9\s]', '', clean)
            clean = clean.strip()
            if len(clean) < 5:
                continue
            # 解析 speaker ID (e.g., SSB0005)
            speaker = fname[:7] if len(fname) >= 7 else "unknown"
            samples.append({
                "filename": fname,
                "speaker": speaker,
                "text_pinyin": text_pinyin,
                "text_clean": clean,
                "text_len": len(clean),
            })
    return samples


def build_audio_dataset(
    aishell_dir: str = "D:/AAA/AISHELL-3",
    output_dir: str = "../data/audio",
    train_speakers: int = 200,
    test_speakers: int = 18,
    samples_per_speaker: int = 3,
):
    print("=" * 60)
    print("AISHELL-3 音频数据准备")
    print("=" * 60)

    aishell = Path(aishell_dir)
    if not aishell.exists():
        print(f"错误: {aishell_dir} 不存在")
        return

    # Step 1: 解析数据 (train目录=训练说话人, test目录=测试说话人)
    print("\n[1/4] 解析数据...")
    train_content = aishell / "train" / "content.txt"
    test_content = aishell / "test" / "content.txt"

    all_train = parse_content(str(train_content))
    all_test = parse_content(str(test_content)) if test_content.exists() else []
    print(f"  Train: {len(all_train)} 条 | Test: {len(all_test)} 条")

    # 按说话人分组
    train_speaker_groups = defaultdict(list)
    for s in all_train:
        train_speaker_groups[s["speaker"]].append(s)

    test_speaker_groups = defaultdict(list)
    for s in all_test:
        test_speaker_groups[s["speaker"]].append(s)

    print(f"  Train 说话人: {len(train_speaker_groups)}")
    print(f"  Test 说话人:  {len(test_speaker_groups)} (不重叠)")

    # Step 2: 采样说话人 + 音频
    print(f"\n[2/4] 采样...")
    train_spks = random.sample(list(train_speaker_groups.keys()),
                               min(train_speakers, len(train_speaker_groups)))
    test_spks = random.sample(list(test_speaker_groups.keys()),
                              min(test_speakers, len(test_speaker_groups)))

    # 每个说话人选 samples_per_speaker 条 (选中等长度文本)
    def select_samples(speaker_list, n_per_spk, groups):
        selected = []
        for spk in speaker_list:
            samples = groups[spk]
            # 按文本长度排序，选中等长度 (避免太短或太长)
            samples.sort(key=lambda x: x["text_len"])
            mid = len(samples) // 2
            # 从中段均匀采样
            start = max(0, mid - 2 * n_per_spk)
            pool = samples[start:start + 5 * n_per_spk]
            selected.extend(random.sample(pool, min(n_per_spk, len(pool))))
        return selected

    train_selected = select_samples(train_spks, samples_per_speaker, train_speaker_groups)
    test_selected = select_samples(test_spks, samples_per_speaker, test_speaker_groups)

    print(f"  Train: {len(train_selected)} 条 ({len(train_spks)} speakers)")
    print(f"  Test:  {len(test_selected)} 条 ({len(test_spks)} speakers)")

    # Step 3: 复制音频文件
    print(f"\n[3/4] 复制音频文件...")
    out = Path(output_dir)

    for subset, samples, source_dir in [
        ("train", train_selected, "train"),
        ("test", test_selected, "test"),
    ]:
        real_dir = out / "real" / subset
        real_dir.mkdir(parents=True, exist_ok=True)

        for s in samples:
            src = aishell / source_dir / "wav" / s["speaker"] / s["filename"]
            if src.exists():
                dst = real_dir / s["filename"]
                if not dst.exists():
                    shutil.copy2(str(src), str(dst))

        count = len(list(real_dir.glob("*.wav")))
        print(f"  real/{subset}: {count} wav files")

    # 创建 fake 目录 (待 TTS 生成)
    for subset in ["train", "test"]:
        (out / "fake" / subset).mkdir(parents=True, exist_ok=True)

    # Step 4: 保存文本列表 (供 TTS 合成)
    print(f"\n[4/4] 生成 TTS 文本列表...")

    # 为每个 test 样本生成合成文本
    tts_list = []
    for s in test_selected:
        tts_list.append({
            "ref_audio": f"real/test/{s['filename']}",
            "text": s["text_clean"],
            "speaker": s["speaker"],
            "text_len": s["text_len"],
        })

    # 保存 JSON
    tts_file = out / "tts_generation_list.json"
    with open(tts_file, "w", encoding="utf-8") as f:
        json.dump(tts_list, f, ensure_ascii=False, indent=2)
    print(f"  TTS 列表: {tts_file} ({len(tts_list)} 条)")

    # 保存纯文本 (一行一句)
    txt_file = out / "tts_texts.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        for s in tts_list:
            f.write(s["text"] + "\n")
    print(f"  纯文本: {txt_file}")

    # 保存元数据
    meta = {
        "source": "AISHELL-3",
        "train_speakers": len(train_spks),
        "test_speakers": len(test_spks),
        "train_samples": len(train_selected),
        "test_samples": len(test_selected),
        "tts_targets": len(tts_list),
        "train_speaker_ids": train_spks,
        "test_speaker_ids": test_spks,
    }
    meta_file = out / "dataset_meta.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n完成!")
    print(f"  真实语音: {out}/real/")
    print(f"  待合成:   {out}/fake/ (需运行 TTS 生成)")
    print(f"  下一步: 用 {tts_file} 中的文本 + ChatTTS/CosyVoice 生成合成语音")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AISHELL-3 音频数据准备")
    parser.add_argument("--aishell_dir", default="D:/AAA/AISHELL-3")
    parser.add_argument("--output_dir", default="../data/audio")
    parser.add_argument("--samples_per_speaker", type=int, default=3)
    args = parser.parse_args()

    build_audio_dataset(
        aishell_dir=args.aishell_dir,
        output_dir=args.output_dir,
        samples_per_speaker=args.samples_per_speaker,
    )
