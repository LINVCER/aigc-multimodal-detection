"""
AI Image Detector Training Script v2

Improvements:
  1. Data sampling: shuffle before truncation
  2. Resize: BICUBIC + RandomResizedCrop
  3. torchvision transforms: full augmentation pipeline
  4. Metrics: AUC / EER / TPR@FPR=1% / ECE
  5. Train/val leak guard: filename hash dedup
  6. BCE logits shape: squeeze(-1)
  7. JPEG/compression augmentation
  8. FFT dual-branch CNN
  9. ViT partial finetune: unfreeze last N layers
 10. CLS token instead of pooler_output
 11. AMP mixed precision
 12. Frozen feature pre-extraction cache
 13. Multi-generator data support
 14. Shortcut defense: EXIF strip / re-encode / random resize
 15. Patch-based inference
 16. DataLoader optimization
 17. Deterministic seed
 18. Early stopping
 19. Full checkpoint save
 20. Experiment config logging
"""

import os
import sys
import argparse
import random
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.amp import autocast, GradScaler
from torchvision import transforms
from torchvision.transforms import InterpolationMode
from PIL import Image
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# Deterministic seed
# ============================================================

def set_deterministic(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.deterministic = False


# ============================================================
# JPEG / Compression Augmentation
# ============================================================

class RandomJPEGCompression:
    def __init__(self, quality_range=(70, 100)):
        self.quality_range = quality_range

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() < 0.5:
            return img
        import io
        quality = random.randint(*self.quality_range)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        return Image.open(buf).convert("RGB")


class RandomResize:
    def __init__(self, scale_range=(0.8, 1.2)):
        self.scale_range = scale_range

    def __call__(self, img: Image.Image) -> Image.Image:
        scale = random.uniform(*self.scale_range)
        w, h = img.size
        new_w, new_h = int(w * scale), int(h * scale)
        return img.resize((new_w, new_h), Image.BICUBIC)


class EXIFStrip:
    def __call__(self, img: Image.Image) -> Image.Image:
        img = img.convert("RGB")
        data = img.getdata()
        new_img = Image.new("RGB", img.size)
        new_img.putdata(data)
        return new_img


# ============================================================
# Transform Pipelines
# ============================================================

def build_train_transform():
    return transforms.Compose([
        EXIFStrip(),
        RandomResize((0.8, 1.2)),
        RandomJPEGCompression((70, 100)),
        transforms.RandomResizedCrop(224, interpolation=InterpolationMode.BICUBIC),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(0.1, 0.1, 0.1, 0.05),
        transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.5)),
        transforms.ToTensor(),
    ])


def build_val_transform():
    return transforms.Compose([
        EXIFStrip(),
        transforms.Resize(256, interpolation=InterpolationMode.BICUBIC),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
    ])


# ============================================================
# Dataset
# ============================================================

class GenImageDataset(Dataset):
    def __init__(
        self,
        ai_dirs: list,
        nature_dirs: list,
        max_samples: int = 10000,
        transform=None,
        split: str = "train",
        leak_guard: bool = True,
    ):
        self.samples = []
        self.transform = transform or build_train_transform()

        all_ai = []
        all_nature = []
        for d in ai_dirs:
            all_ai.extend(Path(d).glob("*"))
        for d in nature_dirs:
            all_nature.extend(Path(d).glob("*"))

        random.Random(42).shuffle(all_ai)
        random.Random(42).shuffle(all_nature)

        all_ai = all_ai[:max_samples]
        all_nature = all_nature[:max_samples]

        if leak_guard and split == "val":
            train_hashes = self._load_train_hashes(ai_dirs, nature_dirs)
            all_ai = [f for f in all_ai if self._file_hash(f) not in train_hashes]
            all_nature = [f for f in all_nature if self._file_hash(f) not in train_hashes]

        for f in all_ai:
            self.samples.append((str(f), 1))
        for f in all_nature:
            self.samples.append((str(f), 0))

        random.Random(42).shuffle(self.samples)

    @staticmethod
    def _file_hash(filepath: Path) -> str:
        name = filepath.stem
        return hashlib.md5(name.encode()).hexdigest()[:8]

    @staticmethod
    def _load_train_hashes(ai_dirs, nature_dirs) -> set:
        hashes = set()
        for d in ai_dirs:
            parent = Path(d).parent
            train_dir = parent / "train" / "ai"
            if train_dir.exists():
                for f in train_dir.glob("*"):
                    hashes.add(GenImageDataset._file_hash(f))
        for d in nature_dirs:
            parent = Path(d).parent
            train_dir = parent / "train" / "nature"
            if train_dir.exists():
                for f in train_dir.glob("*"):
                    hashes.add(GenImageDataset._file_hash(f))
        return hashes

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        filepath, label = self.samples[idx]
        try:
            img = Image.open(filepath).convert("RGB")
        except Exception:
            img = Image.new("RGB", (256, 256))
        tensor = self.transform(img)
        return tensor, label


# ============================================================
# Metrics
# ============================================================

def compute_metrics(logits: np.ndarray, labels: np.ndarray) -> dict:
    from scipy.special import expit

    probs = expit(logits.astype(np.float64))
    preds = (probs > 0.5).astype(int)
    acc = np.mean(preds == labels)

    try:
        from sklearn.metrics import roc_auc_score
        auc = roc_auc_score(labels, probs)
    except Exception:
        auc = 0.5

    sorted_indices = np.argsort(-probs)
    sorted_labels = labels[sorted_indices]
    sorted_probs = probs[sorted_indices]

    eer = compute_eer(sorted_labels, sorted_probs)
    tpr_at_fpr1 = compute_tpr_at_fpr(sorted_labels, sorted_probs, fpr_target=0.01)

    n_bins = 15
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        in_bin = (probs > bin_boundaries[i]) & (probs <= bin_boundaries[i + 1])
        bin_size = np.sum(in_bin)
        if bin_size > 0:
            bin_conf = np.mean(probs[in_bin])
            bin_acc = np.mean(labels[in_bin])
            ece += (bin_size / len(probs)) * abs(bin_acc - bin_conf)

    return {
        "acc": round(float(acc), 4),
        "auc": round(float(auc), 4),
        "eer": round(float(eer), 4),
        "tpr_at_fpr1": round(float(tpr_at_fpr1), 4),
        "ece": round(float(ece), 4),
    }


def compute_eer(labels: np.ndarray, probs: np.ndarray) -> float:
    genuine = probs[labels == 1]
    impostor = probs[labels == 0]
    if len(genuine) == 0 or len(impostor) == 0:
        return 0.5

    thresholds = np.sort(np.unique(probs))[::-1]
    fpr_list, tpr_list = [], []

    for t in thresholds:
        fpr_list.append(np.mean(impostor >= t))
        tpr_list.append(np.mean(genuine >= t))

    fpr_arr = np.array([1.0] + fpr_list + [0.0])
    tpr_arr = np.array([1.0] + tpr_list + [0.0])

    try:
        fnr_arr = 1.0 - tpr_arr
        eer_idx = np.argmin(np.abs(fpr_arr - fnr_arr))
        eer = (fpr_arr[eer_idx] + fnr_arr[eer_idx]) / 2.0
    except Exception:
        eer = 0.5

    return float(eer)


def compute_tpr_at_fpr(labels: np.ndarray, probs: np.ndarray, fpr_target: float = 0.01) -> float:
    genuine = probs[labels == 1]
    impostor = probs[labels == 0]
    if len(genuine) == 0 or len(impostor) == 0:
        return 0.0

    thresholds = np.sort(np.unique(probs))[::-1]
    for t in thresholds:
        fpr = np.mean(impostor >= t)
        if fpr <= fpr_target:
            tpr = np.mean(genuine >= t)
            return float(tpr)
    return 0.0


# ============================================================
# Early Stopping
# ============================================================

class EarlyStopping:
    def __init__(self, patience: int = 3, min_delta: float = 1e-4, mode: str = "max"):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score = None
        self.should_stop = False

    def step(self, score: float) -> bool:
        if self.best_score is None:
            self.best_score = score
            return False

        improved = (score - self.best_score > self.min_delta) if self.mode == "max" else (self.best_score - score > self.min_delta)

        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True

        return self.should_stop


# ============================================================
# Checkpoint
# ============================================================

def save_checkpoint(state: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(state, path)


def save_config(config: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ============================================================
# FFT Dual-Branch CNN
# ============================================================

class FFTBranch(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x).squeeze(-1).squeeze(-1)


class DualBranchCNN(nn.Module):
    def __init__(self):
        super().__init__()
        from app.detectors.image.high_freq_branch import SRMFilter
        self.srm = SRMFilter()

        self.rgb_branch = nn.Sequential(
            nn.Conv2d(12, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )

        self.fft_branch = FFTBranch()

        self.classifier = nn.Sequential(
            nn.Linear(128 + 64, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 1),
        )

    @staticmethod
    def compute_fft_features(x: torch.Tensor) -> torch.Tensor:
        gray = 0.2989 * x[:, 0] + 0.5870 * x[:, 1] + 0.1140 * x[:, 2]
        fft = torch.fft.fft2(gray)
        magnitude = torch.log(torch.abs(fft) + 1e-8)
        return magnitude.unsqueeze(1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rgb_residuals = self.srm(x)
        combined = torch.cat([x, rgb_residuals], dim=1)
        rgb_feat = self.rgb_branch(combined).squeeze(-1).squeeze(-1)

        fft_input = self.compute_fft_features(x)
        fft_feat = self.fft_branch(fft_input)

        fused = torch.cat([rgb_feat, fft_feat], dim=1)
        logit = self.classifier(fused).squeeze(-1)
        return logit


# ============================================================
# Patch-based Inference
# ============================================================

def patch_inference(model: nn.Module, image: Image.Image, device: torch.device, n_patches: int = 4, patch_size: int = 128) -> dict:
    model.eval()
    w, h = image.size
    transform = build_val_transform()

    patches = []
    step_w = max((w - patch_size) // (n_patches // 2), 1)
    step_h = max((h - patch_size) // (n_patches // 2), 1)

    for i in range(n_patches // 2):
        for j in range(n_patches // 2):
            left = min(i * step_w, w - patch_size)
            top = min(j * step_h, h - patch_size)
            patch = image.crop((left, top, left + patch_size, top + patch_size))
            patches.append(transform(patch))

    if not patches:
        patches.append(transform(image))

    batch = torch.stack(patches).to(device)

    with torch.no_grad():
        logits = model(batch)
        probs = torch.sigmoid(logits)

    prob_list = probs.cpu().tolist()
    mean_prob = float(probs.mean())
    vote_ai = sum(1 for p in prob_list if p > 0.5) / len(prob_list)

    return {
        "mean_prob": round(mean_prob, 4),
        "vote_ratio": round(vote_ai, 4),
        "patch_probs": [round(p, 4) for p in prob_list],
        "is_ai": mean_prob > 0.5,
    }


# ============================================================
# CNN Training
# ============================================================

def train_cnn(
    ai_dirs, nature_dirs,
    val_ai_dirs, val_nature_dirs,
    device, epochs=8, batch_size=64,
    lr=1e-3, max_samples=10000,
    save_path="../models/image/cnn_detection.pth",
    patience=3,
):
    print(f"\n[CNN] Loading data...")
    train_ds = GenImageDataset(ai_dirs, nature_dirs, max_samples, build_train_transform(), "train")
    val_ds = GenImageDataset(val_ai_dirs, val_nature_dirs, max_samples // 4, build_val_transform(), "val")
    print(f"  Train: {len(train_ds)}  Val: {len(val_ds)}")

    num_workers = max(os.cpu_count() // 2, 2)
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True,
        persistent_workers=True, prefetch_factor=4,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True,
        persistent_workers=True, prefetch_factor=4,
    )

    model = DualBranchCNN().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.BCEWithLogitsLoss()
    scaler = GradScaler("cuda")
    early_stop = EarlyStopping(patience=patience, mode="max")

    best_metrics = None
    print(f"  Start training ({epochs} epochs, AMP=True)")

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}"):
            images, labels = images.to(device), labels.float().to(device)

            with autocast("cuda"):
                logits = model(images)
                loss = criterion(logits, labels)

            optimizer.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            train_loss += loss.item()
            preds = (torch.sigmoid(logits) > 0.5).float()
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)

        train_acc = train_correct / train_total

        model.eval()
        all_logits = []
        all_labels = []
        val_loss = 0.0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.float().to(device)
                with autocast("cuda"):
                    logits = model(images)
                    loss = criterion(logits, labels)
                val_loss += loss.item()
                all_logits.extend(logits.cpu().tolist())
                all_labels.extend(labels.cpu().tolist())

        metrics = compute_metrics(np.array(all_logits), np.array(all_labels))
        print(f"  Train: loss={train_loss/len(train_loader):.4f} acc={train_acc:.4f}")
        print(f"  Val:   loss={val_loss/len(val_loader):.4f} | acc={metrics['acc']:.4f} auc={metrics['auc']:.4f} eer={metrics['eer']:.4f} tpr@1%={metrics['tpr_at_fpr1']:.4f} ece={metrics['ece']:.4f}")

        if best_metrics is None or metrics["auc"] > best_metrics["auc"]:
            best_metrics = metrics
            save_checkpoint({
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "epoch": epoch,
                "metrics": metrics,
            }, save_path)
            print(f"  -> Saved best (auc={metrics['auc']:.4f})")

        scheduler.step()

        if early_stop.step(metrics["auc"]):
            print(f"  Early stopping at epoch {epoch+1}")
            break

    print(f"\nCNN Best: {best_metrics}")
    return best_metrics


# ============================================================
# ViT Training (Partial Finetune + CLS Token + AMP + Cache)
# ============================================================

def train_vit(
    ai_dirs, nature_dirs,
    val_ai_dirs, val_nature_dirs,
    device, epochs=5, batch_size=64,
    lr=1e-3, max_samples=10000,
    save_path="../models/image/ufd_linear_head.pth",
    patience=3,
    unfreeze_layers=2,
    use_cache=True,
):
    from transformers import CLIPModel

    print(f"\n[ViT] Loading CLIP backbone...")
    clip = CLIPModel.from_pretrained("openai/clip-vit-large-patch14", local_files_only=True)
    vit = clip.vision_model.to(device)
    hidden_dim = vit.config.hidden_size

    for p in vit.parameters():
        p.requires_grad = False

    if unfreeze_layers > 0:
        total_layers = len(vit.encoder.layers)
        for i in range(total_layers - unfreeze_layers, total_layers):
            for p in vit.encoder.layers[i].parameters():
                p.requires_grad = True
        print(f"  Unfreeze last {unfreeze_layers} layers")

    vit.eval()
    trainable_params = [p for p in vit.parameters() if p.requires_grad]
    has_trainable_vit = len(trainable_params) > 0

    linear_head = nn.Linear(hidden_dim, 1).to(device)

    mean = torch.tensor([0.48145466, 0.4578275, 0.40821073], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.26862954, 0.26130258, 0.27577711], device=device).view(1, 3, 1, 1)

    print(f"  Loading data...")
    train_ds = GenImageDataset(ai_dirs, nature_dirs, max_samples, build_train_transform(), "train")
    val_ds = GenImageDataset(val_ai_dirs, val_nature_dirs, max_samples // 4, build_val_transform(), "val")
    print(f"  Train: {len(train_ds)}  Val: {len(val_ds)}")

    num_workers = max(os.cpu_count() // 2, 2)
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True,
        persistent_workers=True, prefetch_factor=4,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True,
        persistent_workers=True, prefetch_factor=4,
    )

    param_groups = [{"params": linear_head.parameters(), "lr": lr}]
    if has_trainable_vit:
        param_groups.append({"params": trainable_params, "lr": lr * 0.1})

    optimizer = torch.optim.AdamW(param_groups, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.BCEWithLogitsLoss()
    scaler = GradScaler("cuda")
    early_stop = EarlyStopping(patience=patience, mode="max")

    cache_dir = Path(save_path).parent / "feature_cache"
    if use_cache and not has_trainable_vit:
        train_features_path = cache_dir / "train_features.pt"
        train_labels_path = cache_dir / "train_labels.pt"
        val_features_path = cache_dir / "val_features.pt"
        val_labels_path = cache_dir / "val_labels.pt"

        if train_features_path.exists() and val_features_path.exists():
            print(f"  Loading cached features...")
            train_features = torch.load(train_features_path, map_location=device)
            train_labels_cache = torch.load(train_labels_path, map_location=device)
            val_features = torch.load(val_features_path, map_location=device)
            val_labels_cache = torch.load(val_labels_path, map_location=device)
            print(f"  Train: {train_features.shape[0]}  Val: {val_features.shape[0]}")
        else:
            print(f"  Pre-extracting features...")
            cache_dir.mkdir(parents=True, exist_ok=True)
            train_features, train_labels_cache = _extract_features(vit, train_loader, mean, std, device)
            val_features, val_labels_cache = _extract_features(vit, val_loader, mean, std, device)
            torch.save(train_features, train_features_path)
            torch.save(train_labels_cache, train_labels_path)
            torch.save(val_features, val_features_path)
            torch.save(val_labels_cache, val_labels_path)
            print(f"  Features cached to {cache_dir}")

        print(f"  Start training Linear Head ({epochs} epochs, cached features)")
        best_metrics = None
        dataset_train = torch.utils.data.TensorDataset(train_features, train_labels_cache)
        loader_train = DataLoader(dataset_train, batch_size=batch_size, shuffle=True)

        for epoch in range(epochs):
            linear_head.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0

            for features, labels in tqdm(loader_train, desc=f"Epoch {epoch+1}/{epochs}"):
                features, labels = features.to(device), labels.float().to(device)
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

            linear_head.eval()
            with torch.no_grad():
                logits = linear_head(val_features).squeeze(-1)
                val_labels_np = val_labels_cache.cpu().numpy()
                logits_np = logits.cpu().numpy()

            metrics = compute_metrics(logits_np, val_labels_np)
            print(f"  Train: loss={train_loss/len(loader_train):.4f} acc={train_acc:.4f}")
            print(f"  Val:   acc={metrics['acc']:.4f} auc={metrics['auc']:.4f} eer={metrics['eer']:.4f} tpr@1%={metrics['tpr_at_fpr1']:.4f}")

            if best_metrics is None or metrics["auc"] > best_metrics["auc"]:
                best_metrics = metrics
                _save_vit_checkpoint(linear_head, vit, logits_np, val_labels_np, metrics, epoch, save_path)
                print(f"  -> Saved best (auc={metrics['auc']:.4f})")

            scheduler.step()
            if early_stop.step(metrics["auc"]):
                print(f"  Early stopping at epoch {epoch+1}")
                break

        print(f"\nViT Best: {best_metrics}")
        return best_metrics

    # ---- Non-cache path (partial finetune) ----
    best_metrics = None
    print(f"  Start training ({epochs} epochs, partial finetune, AMP=True)")

    for epoch in range(epochs):
        linear_head.train()
        if has_trainable_vit:
            vit.train()
            for m in vit.modules():
                if isinstance(m, nn.LayerNorm):
                    m.eval()

        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}"):
            images = images.to(device)
            labels = labels.float().to(device)
            images_norm = (images - mean) / std

            with autocast("cuda"):
                vision_out = vit(images_norm, output_hidden_states=True)
                cls_token = vision_out.last_hidden_state[:, 0]
                logits = linear_head(cls_token).squeeze(-1)
                loss = criterion(logits, labels)

            optimizer.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            train_loss += loss.item()
            preds = (torch.sigmoid(logits) > 0.5).float()
            train_correct += (preds == labels).sum().item()
            train_total += labels.size(0)

        train_acc = train_correct / train_total

        linear_head.eval()
        vit.eval()
        all_logits = []
        all_labels_list = []
        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels_f = labels.float().to(device)
                images_norm = (images - mean) / std
                with autocast("cuda"):
                    vision_out = vit(images_norm, output_hidden_states=True)
                    cls_token = vision_out.last_hidden_state[:, 0]
                    logits = linear_head(cls_token).squeeze(-1)
                all_logits.extend(logits.cpu().tolist())
                all_labels_list.extend(labels_f.cpu().tolist())

        metrics = compute_metrics(np.array(all_logits), np.array(all_labels_list))
        print(f"  Train: loss={train_loss/len(train_loader):.4f} acc={train_acc:.4f}")
        print(f"  Val:   acc={metrics['acc']:.4f} auc={metrics['auc']:.4f} eer={metrics['eer']:.4f} tpr@1%={metrics['tpr_at_fpr1']:.4f}")

        if best_metrics is None or metrics["auc"] > best_metrics["auc"]:
            best_metrics = metrics
            _save_vit_checkpoint(linear_head, vit, np.array(all_logits), np.array(all_labels_list), metrics, epoch, save_path)
            print(f"  -> Saved best (auc={metrics['auc']:.4f})")

        scheduler.step()
        if early_stop.step(metrics["auc"]):
            print(f"  Early stopping at epoch {epoch+1}")
            break

    print(f"\nViT Best: {best_metrics}")
    return best_metrics


def _extract_features(vit, loader, mean, std, device):
    vit.eval()
    all_features = []
    all_labels = []
    with torch.no_grad():
        for images, labels in tqdm(loader, desc="Extracting features"):
            images = images.to(device)
            images_norm = (images - mean) / std
            vision_out = vit(images_norm, output_hidden_states=True)
            cls_token = vision_out.last_hidden_state[:, 0]
            all_features.append(cls_token.cpu())
            all_labels.append(labels)
    return torch.cat(all_features, dim=0), torch.cat(all_labels, dim=0).float()


def _save_vit_checkpoint(linear_head, vit, logits_np, labels_np, metrics, epoch, save_path):
    from app.services.calibration import ConfidenceCalibrator
    cal = ConfidenceCalibrator()
    T = cal.fit_temperature(logits_np, labels_np)
    a, b = cal.fit_platt(logits_np / T, labels_np)

    state = {
        "linear_head": linear_head.state_dict(),
        "temperature": T,
        "platt_a": a,
        "platt_b": b,
        "val_metrics": metrics,
        "epoch": epoch,
    }
    trainable_params = [p for p in vit.parameters() if p.requires_grad]
    if len(trainable_params) > 0:
        state["vit_partial"] = {k: v.cpu() for k, v in vit.state_dict().items() if any(v is p for p in trainable_params)}

    save_checkpoint(state, save_path)


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="AI Image Detector Training v2")
    parser.add_argument("--ai_dir", default="D:/AAA/image_data/sd_v1_5/imagenet_ai_0424_sdv5/train/ai")
    parser.add_argument("--nature_dir", default="D:/AAA/image_data/sd_v1_5/imagenet_ai_0424_sdv5/train/nature")
    parser.add_argument("--val_ai", default="D:/AAA/image_data/sd_v1_5/imagenet_ai_0424_sdv5/val/ai")
    parser.add_argument("--val_nature", default="D:/AAA/image_data/sd_v1_5/imagenet_ai_0424_sdv5/val/nature")
    parser.add_argument("--extra_ai_dirs", nargs="*", default=[])
    parser.add_argument("--extra_nature_dirs", nargs="*", default=[])
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--max_samples", type=int, default=10000)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--unfreeze_layers", type=int, default=2)
    parser.add_argument("--no_cache", action="store_true")
    parser.add_argument("--skip_cnn", action="store_true")
    parser.add_argument("--skip_vit", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_deterministic(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    ai_dirs = [args.ai_dir] + args.extra_ai_dirs
    nature_dirs = [args.nature_dir] + args.extra_nature_dirs
    val_ai_dirs = [args.val_ai]
    val_nature_dirs = [args.val_nature]

    config = {
        "timestamp": datetime.now().isoformat(),
        "seed": args.seed,
        "device": str(device),
        "ai_dirs": ai_dirs,
        "nature_dirs": nature_dirs,
        "max_samples": args.max_samples,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "patience": args.patience,
        "unfreeze_layers": args.unfreeze_layers,
        "use_cache": not args.no_cache,
    }

    config_path = "../models/image/train_config.json"
    save_config(config, config_path)
    print(f"Config saved: {config_path}")

    t0 = time.time()

    if not args.skip_cnn:
        train_cnn(
            ai_dirs, nature_dirs, val_ai_dirs, val_nature_dirs,
            device, args.epochs, args.batch_size, lr=args.lr,
            max_samples=args.max_samples, patience=args.patience,
        )

    if not args.skip_vit:
        train_vit(
            ai_dirs, nature_dirs, val_ai_dirs, val_nature_dirs,
            device, args.epochs, args.batch_size, lr=args.lr,
            max_samples=args.max_samples, patience=args.patience,
            unfreeze_layers=args.unfreeze_layers,
            use_cache=not args.no_cache,
        )

    print(f"\nDone! Total: {(time.time()-t0)/60:.0f} min")


if __name__ == "__main__":
    main()
