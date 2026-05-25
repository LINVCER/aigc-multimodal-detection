"""
Wav2Vec2 音频 AIGC 检测训练脚本

训练策略:
  1. 冻结 Wav2Vec2 XLS-R 编码器 (315M, 不训练)
  2. 训练轻量分类头 (~1M 参数)
  3. 支持小样本训练 (200-5000 条)

数据目录结构:
  data/audio/
    real/        — 真实人类语音 (.wav)
    fake/        — AI 合成语音 (.wav)
    test_real/   — 测试集真实语音 (可选)
    test_fake/   — 测试集合成语音 (可选)

用法:
  python train_audio_detector.py                                    # 默认训练
  python train_audio_detector.py --real_dir ../data/audio/real --fake_dir ../data/audio/fake
  python train_audio_detector.py --epochs 20 --batch_size 16        # 自定义参数
"""

import os, sys, json, random, argparse
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn as nn
import numpy as np
from tqdm import tqdm

random.seed(42)
torch.manual_seed(42)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SAMPLE_RATE = 16000


# ============================================================
# 数据加载
# ============================================================

class AudioDataset(torch.utils.data.Dataset):
    """音频检测数据集"""

    def __init__(self, real_dir: str, fake_dir: str, feature_extractor,
                 max_samples: int = 0):
        self.samples: list[tuple[np.ndarray, int]] = []
        self.feature_extractor = feature_extractor

        for label, d in [(0, real_dir), (1, fake_dir)]:
            if not os.path.isdir(d):
                print(f"  [WARN] 目录不存在: {d}")
                continue
            files = [f for f in os.listdir(d) if f.lower().endswith(('.wav', '.mp3', '.flac', '.m4a'))]
            if max_samples > 0:
                files = files[:max_samples // 2]
            for fname in files:
                self.samples.append((os.path.join(d, fname), label))

        label_counts = defaultdict(int)
        for _, lb in self.samples:
            label_counts[lb] += 1
        print(f"  数据集: {len(self.samples)} ({label_counts[0]} real + {label_counts[1]} fake)")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        try:
            audio, sr = self._load_audio(path)
            # 随机裁剪 3-5 秒
            target_len = random.randint(3, 5) * SAMPLE_RATE
            if len(audio) > target_len:
                start = random.randint(0, len(audio) - target_len)
                audio = audio[start:start + target_len]
            elif len(audio) < SAMPLE_RATE:  # 太短: 填充
                audio = np.pad(audio, (0, SAMPLE_RATE - len(audio)))

            # 随机数据增强
            if random.random() < 0.3:
                audio = self._augment(audio)

            # Wav2Vec2 特征提取
            inputs = self.feature_extractor(
                audio, sampling_rate=SAMPLE_RATE,
                return_tensors="pt", padding=True,
            )
            return inputs.input_values.squeeze(0), torch.tensor(label, dtype=torch.long)
        except Exception as e:
            # 失败返回静音
            return torch.zeros(SAMPLE_RATE * 3), torch.tensor(label, dtype=torch.long)

    def _load_audio(self, path: str) -> tuple[np.ndarray, int]:
        """加载音频文件, 统一转 16kHz mono"""
        try:
            import librosa
            audio, sr = librosa.load(path, sr=SAMPLE_RATE, mono=True)
            return audio.astype(np.float32), sr
        except Exception:
            # ffmpeg 降级
            import subprocess, tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
            subprocess.run([
                'ffmpeg', '-i', path, '-ar', str(SAMPLE_RATE), '-ac', '1',
                '-f', 'wav', tmp_path, '-y', '-loglevel', 'quiet',
            ], check=True)
            import soundfile as sf
            audio, sr = sf.read(tmp_path)
            os.unlink(tmp_path)
            return audio.astype(np.float32), sr

    def _augment(self, audio: np.ndarray) -> np.ndarray:
        """随机数据增强"""
        aug_type = random.randint(0, 3)
        if aug_type == 0:
            # 加噪
            noise = np.random.randn(len(audio)) * 0.005
            return audio + noise.astype(np.float32)
        elif aug_type == 1:
            # 音量缩放
            return audio * random.uniform(0.7, 1.3)
        elif aug_type == 2:
            # 小幅度变速 (重采样模拟)
            rate = random.uniform(0.95, 1.05)
            indices = np.arange(0, len(audio), rate)[:len(audio)].astype(int)
            return audio[indices]
        else:
            return audio


# ============================================================
# 分类头模型 (匹配 detector 结构)
# ============================================================

class AudioClassifier(nn.Module):
    """轻量分类头"""
    def __init__(self, hidden_size: int = 1024):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
        )

    def forward(self, x):
        return self.net(x)


# ============================================================
# 训练循环
# ============================================================

def train_audio_detector(
    real_dir: str = "../data/audio/real",
    fake_dir: str = "../data/audio/fake",
    test_real_dir: str = "../data/audio/test_real",
    test_fake_dir: str = "../data/audio/test_fake",
    model_dir: str = "../models/audio/wav2vec2-xls-r-300m",
    save_path: str = "../models/audio/aigc_audio_classifier.pth",
    epochs: int = 15,
    batch_size: int = 8,
    lr: float = 1e-3,
    max_samples: int = 0,
    val_split: float = 0.2,
):
    print("=" * 60)
    print("Wav2Vec2 音频 AIGC 检测训练")
    print("=" * 60)

    # 加载特征提取器
    print(f"\n[1/4] 加载 Wav2Vec2 编码器: {model_dir}")
    from transformers import AutoModel, AutoFeatureExtractor
    feature_extractor = AutoFeatureExtractor.from_pretrained(model_dir)
    encoder = AutoModel.from_pretrained(model_dir, local_files_only=True).to(DEVICE)
    encoder.eval()
    for p in encoder.parameters():
        p.requires_grad = False
    hidden_size = encoder.config.hidden_size
    print(f"  编码器冻结: {sum(p.numel() for p in encoder.parameters())/1e6:.0f}M params")
    print(f"  特征维度: {hidden_size}")

    # 加载数据
    print(f"\n[2/4] 加载数据...")
    dataset = AudioDataset(real_dir, fake_dir, feature_extractor, max_samples)
    if len(dataset) < 10:
        print("  数据不足 (<10), 仅保存随机权重")
        classifier = AudioClassifier(hidden_size)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        torch.save(classifier.state_dict(), save_path)
        print(f"  已保存: {save_path}")
        return

    n_val = max(1, int(len(dataset) * val_split))
    n_train = len(dataset) - n_val
    train_ds, val_ds = torch.utils.data.random_split(dataset, [n_train, n_val])
    def collate_pad(batch):
        tensors, labels = zip(*batch)
        max_len = max(t.size(0) for t in tensors)
        padded = torch.zeros(len(tensors), max_len)
        for i, t in enumerate(tensors):
            padded[i, :t.size(0)] = t
        return padded, torch.tensor(labels)

    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0, collate_fn=collate_pad)
    val_loader = torch.utils.data.DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0, collate_fn=collate_pad)
    print(f"  Train: {n_train} | Val: {n_val}")

    # 分类头
    print(f"\n[3/4] 训练分类头...")
    classifier = AudioClassifier(hidden_size).to(DEVICE)
    print(f"  可训练参数: {sum(p.numel() for p in classifier.parameters())/1e3:.0f}K")

    optimizer = torch.optim.AdamW(classifier.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.BCEWithLogitsLoss()

    best_val_acc = 0.0

    for epoch in range(epochs):
        # Train
        classifier.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}")
        for audio_tensors, labels in pbar:
            audio_tensors = audio_tensors.to(DEVICE)
            labels = labels.to(DEVICE).float()

            # 通过冻结编码器提取特征
            with torch.no_grad():
                # 处理变长输入
                if audio_tensors.dim() == 2:
                    outputs = encoder(audio_tensors)
                else:
                    # padding
                    attention_mask = (audio_tensors.abs().sum(dim=-1) > 0).float()
                    outputs = encoder(audio_tensors, attention_mask=attention_mask)
                features = outputs.last_hidden_state.mean(dim=1)  # [B, 1024]

            logits = classifier(features).squeeze(-1)
            loss = criterion(logits, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            preds = (torch.sigmoid(logits) > 0.5).float()
            train_loss += loss.item()
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)

            pbar.set_postfix({
                "loss": f"{loss.item():.4f}",
                "acc": f"{train_correct / max(train_total, 1):.3f}",
            })

        scheduler.step()

        # Val
        classifier.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for audio_tensors, labels in val_loader:
                audio_tensors = audio_tensors.to(DEVICE)
                labels = labels.to(DEVICE).float()
                outputs = encoder(audio_tensors)
                features = outputs.last_hidden_state.mean(dim=1)
                logits = classifier(features).squeeze(-1)
                preds = (torch.sigmoid(logits) > 0.5).float()
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)

        val_acc = val_correct / max(val_total, 1)
        print(f"  Train: loss={train_loss/len(train_loader):.4f} acc={train_correct/max(train_total,1):.4f}")
        print(f"  Val:   acc={val_acc:.4f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            torch.save(classifier.state_dict(), save_path)
            print(f"  -> Best model saved ({save_path})")

    # 测试集评估
    print(f"\n[4/4] 测试集评估...")
    test_acc = _evaluate(encoder, classifier, test_real_dir, test_fake_dir, feature_extractor)
    print(f"  Test Acc: {test_acc:.4f}" if test_acc is not None else "  (无独立测试集)")

    print(f"\nBest val_acc: {best_val_acc:.4f}")
    print(f"Model saved: {save_path}")
    print("Done.")


def _evaluate(encoder, classifier, real_dir: str, fake_dir: str, feature_extractor):
    """独立测试集评估"""
    if not os.path.isdir(real_dir) or not os.path.isdir(fake_dir):
        return None

    correct = 0
    total = 0
    classifier.eval()

    for label, d in [(0, real_dir), (1, fake_dir)]:
        files = [f for f in os.listdir(d) if f.lower().endswith(('.wav', '.mp3', '.flac'))]
        for fname in files[:200]:  # 最多 200 条
            try:
                import librosa
                audio, sr = librosa.load(os.path.join(d, fname), sr=SAMPLE_RATE, mono=True)
                audio = audio.astype(np.float32)
                # 取中间 5 秒
                if len(audio) > 5 * SAMPLE_RATE:
                    start = (len(audio) - 5 * SAMPLE_RATE) // 2
                    audio = audio[start:start + 5 * SAMPLE_RATE]

                inputs = feature_extractor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True)
                with torch.no_grad():
                    outputs = encoder(inputs.input_values.to(DEVICE))
                    features = outputs.last_hidden_state.mean(dim=1)
                    logit = classifier(features).squeeze(-1)
                    pred = (torch.sigmoid(logit) > 0.5).float().item()
                correct += (pred == label)
                total += 1
            except Exception:
                continue

    return correct / max(total, 1) if total > 0 else None


# ============================================================
# 构建中文测试集 (自建)
# ============================================================

def build_chinese_testset(
    real_source: str = "../data/audio/aishell3",
    output_dir: str = "../data/audio",
    num_samples: int = 200,
):
    """
    从 AISHELL-3 构建中文测试集

    AISHELL-3 结构: aishell3/
      train/wav/SSB0005/SSB00050001.wav
      ...
    需要先下载: https://www.aishelltech.com/aishell_3
    """
    print("=" * 60)
    print("构建中文音频测试集")
    print("=" * 60)

    real_output = os.path.join(output_dir, "test_real")
    os.makedirs(real_output, exist_ok=True)

    count = 0
    if os.path.isdir(real_source):
        all_wavs = []
        for root, _, files in os.walk(real_source):
            for f in files:
                if f.endswith('.wav'):
                    all_wavs.append(os.path.join(root, f))

        selected = random.sample(all_wavs, min(num_samples, len(all_wavs)))
        for src in selected:
            import shutil
            fname = os.path.basename(src)
            dst = os.path.join(real_output, fname)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
            count += 1

    print(f"  真实语音测试集: {count} 条 -> {real_output}")
    print(f"  合成语音测试集: 需要手动用 TTS 生成 (ChatTTS/CosyVoice) -> {output_dir}/test_fake/")
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wav2Vec2 音频 AIGC 检测训练")
    parser.add_argument("--real_dir", default="../data/audio/real")
    parser.add_argument("--fake_dir", default="../data/audio/fake")
    parser.add_argument("--test_real_dir", default="../data/audio/test_real")
    parser.add_argument("--test_fake_dir", default="../data/audio/test_fake")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--max_samples", type=int, default=0)
    parser.add_argument("--save_path", default="../models/audio/aigc_audio_classifier.pth")
    parser.add_argument("--build_testset", action="store_true", help="构建中文测试集")
    parser.add_argument("--real_source", default="../data/audio/aishell3")
    args = parser.parse_args()

    if args.build_testset:
        build_chinese_testset(args.real_source, "../data/audio")
    else:
        train_audio_detector(
            real_dir=args.real_dir,
            fake_dir=args.fake_dir,
            test_real_dir=args.test_real_dir,
            test_fake_dir=args.test_fake_dir,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            max_samples=args.max_samples,
            save_path=args.save_path,
        )
