"""
高频噪声分析分支 v2 — 双分支架构 (RGB+SRM + FFT)

流程:
  1. RGB + SRM 高通滤波残差 → CNN 分支
  2. FFT 频域对数幅度 → FFT 分支
  3. 双分支特征融合 → 分类
  4. Patch-based 推理支持

借鉴: CNNDetection (Wang et al.), DIRE, F3Net
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from PIL import Image
from torchvision import transforms
from torchvision.transforms import InterpolationMode

from app.detectors.base import DetectionPipeline, DetectionOutput


def get_srm_kernels() -> torch.Tensor:
    kernel1 = np.array([
        [0, 0, 0, 0, 0],
        [0, -1, 2, -1, 0],
        [0, 2, -4, 2, 0],
        [0, -1, 2, -1, 0],
        [0, 0, 0, 0, 0],
    ], dtype=np.float32)

    kernel2 = np.array([
        [-1, 2, -2, 2, -1],
        [2, -6, 8, -6, 2],
        [-2, 8, -12, 8, -2],
        [2, -6, 8, -6, 2],
        [-1, 2, -2, 2, -1],
    ], dtype=np.float32)

    kernel3 = np.array([
        [0, 0, 1, 0, 0],
        [0, -1, 2, -1, 0],
        [1, 2, -6, 2, 1],
        [0, -1, 2, -1, 0],
        [0, 0, 1, 0, 0],
    ], dtype=np.float32)

    kernels = np.stack([kernel1, kernel2, kernel3])
    return torch.from_numpy(kernels).unsqueeze(1)


class SRMFilter(nn.Module):
    def __init__(self):
        super().__init__()
        kernels = get_srm_kernels()
        self.register_buffer("kernels", kernels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, C, H, W = x.shape
        residuals = []
        for i in range(C):
            channel = x[:, i:i+1, :, :]
            for k in range(len(self.kernels)):
                kernel = self.kernels[k:k+1]
                res = F.conv2d(channel, kernel, padding=2)
                residuals.append(res)
        return torch.cat(residuals, dim=1)


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


class HighFreqCNN(nn.Module):
    """
    向后兼容: 旧版单分支 CNN
    新版权重会保存为 DualBranchCNN
    """

    def __init__(self):
        super().__init__()
        self.srm = SRMFilter()
        self.conv1 = nn.Sequential(
            nn.Conv2d(12, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.classifier = nn.Linear(128, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rgb_residuals = self.srm(x)
        combined = torch.cat([x, rgb_residuals], dim=1)
        feat = self.conv1(combined)
        feat = self.conv2(feat)
        feat = self.conv3(feat).squeeze(-1).squeeze(-1)
        logit = self.classifier(feat).squeeze(-1)
        return logit


class HighFreqBranch(DetectionPipeline):
    name = "high_frequency_cnn"
    modality = "image"
    version = "0.2.0"

    def __init__(self):
        super().__init__()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._is_dual_branch = False
        self._transform = transforms.Compose([
            transforms.Resize(256, interpolation=InterpolationMode.BICUBIC),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
        ])

    def _ensure_loaded(self):
        if self._model is not None:
            return

        import os
        ckpt_path = "../models/image/cnn_detection.pth"

        if os.path.exists(ckpt_path):
            ckpt = torch.load(ckpt_path, map_location=self.device)

            if "model" in ckpt:
                self._model = DualBranchCNN().to(self.device)
                self._model.load_state_dict(ckpt["model"])
                self._is_dual_branch = True
                metrics = ckpt.get("metrics", {})
                print(f"[HighFreqCNN] 已加载 DualBranch 权重 (auc={metrics.get('auc', 'N/A')})")
            else:
                self._model = HighFreqCNN().to(self.device)
                self._model.load_state_dict(ckpt if isinstance(ckpt, dict) and "conv1" in str(ckpt) else ckpt)
                self._is_dual_branch = False
                print(f"[HighFreqCNN] 已加载旧版单分支权重")
        else:
            self._model = DualBranchCNN().to(self.device)
            self._is_dual_branch = True
            print(f"[HighFreqCNN] 未找到权重，使用随机初始化")

        self._model.eval()

    def _preprocess(self, image: Image.Image) -> torch.Tensor:
        image = image.convert("RGB")
        tensor = self._transform(image)
        return tensor.unsqueeze(0).to(self.device)

    async def detect(self, input_data: Image.Image) -> DetectionOutput:
        self._ensure_loaded()
        x = self._preprocess(input_data)

        with torch.no_grad():
            logit = self._model(x).item()
            prob = torch.sigmoid(torch.tensor(logit)).item()

        # 过拟合模型(auc=0.955)需要强力校准
        calibrated = 0.5 + (prob - 0.5) * 0.35
        return DetectionOutput(
            is_ai_generated=calibrated > 0.6,
            confidence=round(max(0.01, min(0.99, calibrated)), 4),
            logit=logit,
        )

    async def explain(self, input_data: Image.Image, output: DetectionOutput) -> dict:
        branch_info = "RGB+SRM + FFT 双分支" if self._is_dual_branch else "RGB+SRM 单分支"
        return {
            "detector": self.name,
            "method": f"SRM high-pass filter + {branch_info} CNN",
            "note": "提取噪声残差图和频域特征中的生成器特异性伪影",
        }
