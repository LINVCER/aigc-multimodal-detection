"""
图像检测器训练脚本

用 train2017 真实图像 + 合成假图像训练双分支检测器:
  1. CLIP-ViT Nearest Neighbor 特征库 (纯真实图像，无需假样本)
  2. Linear Probing 头 (用合成假样本训练)
  3. 高频 CNN (用频域扰动生成假样本训练)

CUDA 加速训练。

用法:
  python train_image_detector.py --real_dir D:/AAA/train2017 --epochs 10
"""

import os
import sys
import argparse
import math
import random
import hashlib
from pathlib import Path
from io import BytesIO
from typing import Any
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from PIL import Image, ImageFilter, ImageOps
from tqdm import tqdm

# 项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 1. 合成假图像生成器
# ============================================================


def generate_fake_image(real_img: Image.Image, method: str | None = None) -> Image.Image:
    """
    从真实图像生成模拟的 AI 生成假图像

    策略:
      - frequency: FFT 域扰动 (模拟扩散模型频域伪影)
      - jpeg_artifacts: 重度 JPEG 压缩 (模拟 GAN 压缩伪影)
      - smooth_sharpen: 过度平滑再锐化 (模拟 AI 图像的不自然光滑度)
      - noise_pattern: 添加周期性噪声 (模拟生成器指纹)
    """
    if method is None:
        method = random.choice(["frequency", "jpeg_artifacts", "smooth_sharpen", "noise_pattern"])

    arr = np.array(real_img.convert("RGB")).astype(np.float32)

    if method == "frequency":
        # FFT 域注入伪影
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        fft = np.fft.fft2(gray)
        fft_shifted = np.fft.fftshift(fft)
        h, w = fft_shifted.shape
        # 在高频区域注入规则性噪声 (模拟扩散模型 U-Net 上采样伪影)
        mask = np.zeros((h, w), dtype=np.complex64)
        cy, cx = h // 2, w // 2
        for r in range(10, min(h, w) // 3, 30):
            y, x = np.ogrid[-cy:h-cy, -cx:w-cx]
            ring = (np.abs(np.sqrt(y**2 + x**2) - r) < 3)
            mask[ring] = 0.15 + 0.05j
        fft_shifted = fft_shifted + mask * np.max(np.abs(fft_shifted)) * 0.05
        fft_back = np.fft.ifftshift(fft_shifted)
        reconstructed = np.fft.ifft2(fft_back).real
        reconstructed = (reconstructed - reconstructed.min()) / (reconstructed.max() - reconstructed.min())
        for c in range(3):
            arr[:, :, c] = arr[:, :, c] * 0.7 + (reconstructed * 255) * 0.3

    elif method == "jpeg_artifacts":
        # 8x8 块效应 + 色度子采样 (模拟 GAN 的 JPEG 伪影)
        buf = BytesIO()
        real_img.save(buf, format="JPEG", quality=random.randint(10, 30))
        arr = np.array(Image.open(buf).convert("RGB")).astype(np.float32)

    elif method == "smooth_sharpen":
        # 过度平滑 (模拟 AI 图像不自然的平滑)
        smoothed = real_img.filter(ImageFilter.GaussianBlur(radius=random.uniform(1.5, 3.0)))
        arr = np.array(smoothed).astype(np.float32)
        # 加轻微锐化 halo
        arr = arr + (arr - np.array(real_img.filter(ImageFilter.GaussianBlur(radius=5.0))).astype(np.float32)) * 0.1

    elif method == "noise_pattern":
        # 周期性噪声图案 (模拟 GAN 生成器的棋盘格伪影)
        h, w = arr.shape[:2]
        pattern = np.zeros((h, w))
        for i in range(2, 8):
            freq = 2 ** i
            phase_x = random.random() * math.pi * 2
            phase_y = random.random() * math.pi * 2
            x = np.linspace(0, freq * math.pi, w)
            y = np.linspace(0, freq * math.pi, h)
            pattern += (np.sin(x + phase_x)[:, np.newaxis].T * np.sin(y + phase_y)[:, np.newaxis]).T * 3
        pattern = pattern / pattern.max()
        for c in range(3):
            arr[:, :, c] = np.clip(arr[:, :, c] + pattern * 8, 0, 255)

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ============================================================
# 2. 训练数据集
# ============================================================


class RealFakeDataset(Dataset):
    """真实 vs 伪造 图像对数据集"""

    def __init__(self, real_dir: str, num_samples: int = 5000, seed: int = 42):
        random.seed(seed)
        self.real_files = list(Path(real_dir).glob("*.jpg")) + list(Path(real_dir).glob("*.png"))
        random.shuffle(self.real_files)
        self.real_files = self.real_files[:num_samples]

    def __len__(self):
        return len(self.real_files) * 2  # 每个真实图像配一个假图像

    def __getitem__(self, idx: int):
        is_real = idx % 2 == 0
        real_idx = idx // 2

        real_img = Image.open(self.real_files[real_idx]).convert("RGB").resize((224, 224))

        if is_real:
            img = real_img
            label = 0  # 真实
        else:
            img = generate_fake_image(real_img)
            label = 1  # AI 生成

        tensor = torch.from_numpy(np.array(img)).float().permute(2, 0, 1) / 255.0
        return tensor, label


# ============================================================
# 3. CLIP-ViT 特征库构建 (Nearest Neighbor)
# ============================================================


def build_feature_bank(
    real_dir: str,
    device: torch.device,
    max_images: int = 5000,
    feature_dim: int = 1024,
) -> torch.Tensor:
    """用 CLIP-ViT 提取所有真实图像的特征向量"""
    from transformers import CLIPModel

    print(f"\n[FeatureBank] Loading CLIP-ViT-L/14...")
    model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14").vision_model.to(device)
    model.eval()

    files = list(Path(real_dir).glob("*.jpg")) + list(Path(real_dir).glob("*.png"))
    random.shuffle(files)
    files = files[:max_images]

    features = []
    batch_size = 32

    # CLIP 标准化参数
    mean = torch.tensor([0.48145466, 0.4578275, 0.40821073], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.26862954, 0.26130258, 0.27577711], device=device).view(1, 3, 1, 1)

    print(f"Extracting features from {len(files)} real images...")
    for i in tqdm(range(0, len(files), batch_size)):
        batch_files = files[i:i+batch_size]
        batch_tensors = []
        for f in batch_files:
            try:
                img = Image.open(f).convert("RGB").resize((224, 224))
                tensor = torch.from_numpy(np.array(img)).float().permute(2, 0, 1) / 255.0
                tensor = (tensor - mean.squeeze(0).cpu()) / std.squeeze(0).cpu()
                batch_tensors.append(tensor)
            except Exception:
                continue

        if not batch_tensors:
            continue

        batch = torch.stack(batch_tensors).to(device)
        with torch.no_grad():
            output = model(batch, output_hidden_states=True)
            feat = output.pooler_output  # [B, 1024]
            features.append(feat.cpu())

    feature_bank = torch.cat(features, dim=0)  # [N, 1024]
    # L2 归一化
    feature_bank = F.normalize(feature_bank, p=2, dim=1)

    print(f"Feature bank: {feature_bank.shape[0]} images, {feature_bank.shape[1]} dims")
    return feature_bank


# ============================================================
# 4. 训练 Linear Probing 头
# ============================================================


def train_linear_probe(
    real_dir: str,
    device: torch.device,
    epochs: int = 10,
    batch_size: int = 64,
    lr: float = 1e-3,
    save_path: str = "../models/image/ufd_linear_head.pth",
):
    """用真实+合成假图像训练 Linear Probing 头"""
    from transformers import CLIPModel

    print(f"\n[LinearProbe] Loading CLIP-ViT-L/14 backbone...")
    vit = CLIPModel.from_pretrained("openai/clip-vit-large-patch14").vision_model.to(device)
    for param in vit.parameters():
        param.requires_grad = False
    vit.eval()

    hidden_dim = vit.config.hidden_size
    linear_head = nn.Linear(hidden_dim, 1).to(device)

    # CLIP 标准化
    mean = torch.tensor([0.48145466, 0.4578275, 0.40821073], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.26862954, 0.26130258, 0.27577711], device=device).view(1, 3, 1, 1)

    dataset = RealFakeDataset(real_dir, num_samples=5000)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)

    optimizer = torch.optim.AdamW(linear_head.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.BCEWithLogitsLoss()

    best_val_acc = 0.0

    print(f"\nTraining: {len(train_ds)} train, {len(val_ds)} val, {epochs} epochs, batch={batch_size}")
    for epoch in range(epochs):
        # Train
        linear_head.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}"):
            images = images.to(device)
            labels = labels.float().to(device)

            # CLIP 标准化
            images = (images - mean) / std

            with torch.no_grad():
                output = vit(images, output_hidden_states=True)
                features = output.pooler_output  # [B, 1024]

            logits = linear_head(features).squeeze(-1)
            loss = criterion(logits, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            preds = (torch.sigmoid(logits) > 0.5).float()
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)

        train_acc = train_correct / train_total

        # Val
        linear_head.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        all_logits = []
        all_labels = []

        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = labels.float().to(device)
                images = (images - mean) / std
                features = vit(images, output_hidden_states=True).pooler_output
                logits = linear_head(features).squeeze(-1)
                loss = criterion(logits, labels)

                val_loss += loss.item()
                preds = (torch.sigmoid(logits) > 0.5).float()
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)
                all_logits.extend(logits.cpu().numpy().tolist())
                all_labels.extend(labels.cpu().numpy().tolist())

        val_acc = val_correct / val_total

        # 计算校准参数 (Temperature)
        from app.services.calibration import ConfidenceCalibrator
        calibrator = ConfidenceCalibrator()
        logits_np = np.array(all_logits)
        labels_np = np.array(all_labels)
        T = calibrator.fit_temperature(logits_np, labels_np)
        a, b = calibrator.fit_platt(logits_np / T, labels_np)

        print(f"  Train Loss={train_loss/len(train_loader):.4f} Acc={train_acc:.4f}")
        print(f"  Val   Loss={val_loss/len(val_loader):.4f} Acc={val_acc:.4f} T={T:.3f} Platt=({a:.3f},{b:.3f})")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            torch.save(
                {
                    "linear_head": linear_head.state_dict(),
                    "temperature": T,
                    "platt_a": a,
                    "platt_b": b,
                    "val_acc": val_acc,
                },
                save_path,
            )
            print(f"  -> Saved best model (acc={val_acc:.4f}) to {save_path}")

        scheduler.step()

    print(f"\nBest val acc: {best_val_acc:.4f}")
    return best_val_acc


# ============================================================
# 5. 训练高频 CNN
# ============================================================


def train_high_freq_cnn(
    real_dir: str,
    device: torch.device,
    epochs: int = 15,
    batch_size: int = 64,
    lr: float = 1e-3,
    save_path: str = "../models/image/cnn_detection.pth",
):
    """用真实+合成假图像训练高频噪声 CNN"""
    from app.detectors.image.high_freq_branch import HighFreqCNN

    print(f"\n[HighFreqCNN] Initializing model...")
    model = HighFreqCNN().to(device)

    dataset = RealFakeDataset(real_dir, num_samples=5000)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.BCEWithLogitsLoss()

    best_val_acc = 0.0

    print(f"\nTraining: {len(train_ds)} train, {len(val_ds)} val, {epochs} epochs")
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}"):
            images = images.to(device)
            labels = labels.float().to(device)

            logits = model(images)
            loss = criterion(logits, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            preds = (torch.sigmoid(logits) > 0.5).float()
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)

        train_acc = train_correct / train_total

        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = labels.float().to(device)
                logits = model(images)
                loss = criterion(logits, labels)

                val_loss += loss.item()
                preds = (torch.sigmoid(logits) > 0.5).float()
                val_correct += (preds == labels).sum().item()
                val_total += labels.size(0)

        val_acc = val_correct / val_total
        print(f"  Train Loss={train_loss/len(train_loader):.4f} Acc={train_acc:.4f}")
        print(f"  Val   Loss={val_loss/len(val_loader):.4f} Acc={val_acc:.4f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            torch.save(model.state_dict(), save_path)
            print(f"  -> Saved best model (acc={val_acc:.4f}) to {save_path}")

        scheduler.step()

    print(f"\nBest val acc: {best_val_acc:.4f}")
    return best_val_acc


# ============================================================
# Main
# ============================================================


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real_dir", type=str, default="D:/AAA/train2017")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--max_images", type=int, default=5000)
    parser.add_argument("--skip_feature_bank", action="store_true")
    parser.add_argument("--skip_linear_probe", action="store_true")
    parser.add_argument("--skip_high_freq", action="store_true")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    model_dir = "../models/image"
    os.makedirs(model_dir, exist_ok=True)

    # Step 1: 构建特征库 (Nearest Neighbor)
    if not args.skip_feature_bank:
        feature_bank = build_feature_bank(
            args.real_dir, device, max_images=args.max_images
        )
        torch.save(feature_bank, os.path.join(model_dir, "real_feature_bank.pt"))
        print(f"Feature bank saved to {model_dir}/real_feature_bank.pt")

    # Step 2: 训练 Linear Probing
    if not args.skip_linear_probe:
        train_linear_probe(
            args.real_dir, device,
            epochs=args.epochs,
            batch_size=args.batch_size,
            save_path=os.path.join(model_dir, "ufd_linear_head.pth"),
        )

    # Step 3: 训练高频 CNN
    if not args.skip_high_freq:
        train_high_freq_cnn(
            args.real_dir, device,
            epochs=args.epochs,
            batch_size=args.batch_size,
            save_path=os.path.join(model_dir, "cnn_detection.pth"),
        )

    print("\nDone! All models trained and saved.")


if __name__ == "__main__":
    main()
