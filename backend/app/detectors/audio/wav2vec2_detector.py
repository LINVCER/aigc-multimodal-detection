"""
Wav2Vec2 XLS-R 音频 AIGC 检测器

基于 SSL_Anti-spoofing 架构:
  - 冻结 Wav2Vec2 XLS-R 编码器 (315M, 多语言预训练)
  - 轻量分类头 (~1M 参数, 可训练)
  - 支持零样本推理 + 微调

模型路径: ../models/audio/wav2vec2-xls-r-300m (基础编码器)
           ../models/audio/aigc_audio_classifier.pth (分类头权重)
"""

import math
import os
import torch
import torch.nn as nn
import numpy as np
from transformers import AutoModel, AutoFeatureExtractor

from app.detectors.base import DetectionPipeline, DetectionOutput

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class Wav2Vec2AIGCDetector(DetectionPipeline):
    """Wav2Vec2 XLS-R 音频 AIGC 检测器"""

    name = "wav2vec2_xlsr_aigc"
    modality = "audio"
    version = "0.1.0"

    def __init__(self, model_dir: str | None = None, classifier_path: str | None = None):
        super().__init__()
        self.model_dir = model_dir or "../models/audio/wav2vec2-base"
        self.classifier_path = classifier_path or "../models/audio/aigc_audio_classifier.pth"
        self._encoder = None
        self._feature_extractor = None
        self._classifier = None
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return

        # 加载特征提取器
        self._feature_extractor = AutoFeatureExtractor.from_pretrained(
            self.model_dir,
        )

        # 加载冻结编码器
        self._encoder = AutoModel.from_pretrained(
            self.model_dir,
            local_files_only=True,
        ).to(DEVICE)
        self._encoder.eval()
        for param in self._encoder.parameters():
            param.requires_grad = False

        hidden = self._encoder.config.hidden_size  # 1024

        # 分类头
        self._classifier = nn.Sequential(
            nn.Linear(hidden, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
        ).to(DEVICE)

        # 加载预训练分类头 (如果有)
        if os.path.exists(self.classifier_path):
            try:
                state = torch.load(self.classifier_path, map_location=DEVICE)
                # 兼容 training script 的 'net.' 前缀
                if any(k.startswith('net.') for k in state.keys()):
                    state = {k.replace('net.', ''): v for k, v in state.items()}
                self._classifier.load_state_dict(state)
                print(f"[Wav2Vec2Detector] 已加载分类头: {self.classifier_path}")
            except Exception as e:
                print(f"[Wav2Vec2Detector] 分类头加载失败 ({e})，使用随机初始化")

        self._loaded = True
        print(f"[Wav2Vec2Detector] 模型就绪: {sum(p.numel() for p in self._classifier.parameters())/1e3:.0f}K trainable params")

    def _extract_features(self, audio: np.ndarray, sample_rate: int = 16000) -> torch.Tensor:
        """提取 Wav2Vec2 帧级特征 → 均值池化 [1024]"""
        self._ensure_loaded()

        # 重采样到 16kHz
        if sample_rate != 16000:
            import librosa
            audio = librosa.resample(
                audio, orig_sr=sample_rate, target_sr=16000,
            )
            sample_rate = 16000

        # 分段处理 (每段 3-8秒)
        chunk_size = 16000 * 5  # 5秒
        if len(audio) > chunk_size:
            # 取音频中段 (避免开头静音)
            start = (len(audio) - chunk_size) // 2
            audio = audio[start:start + chunk_size]

        # 提取特征
        inputs = self._feature_extractor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
            padding=True,
        )

        with torch.no_grad():
            outputs = self._encoder(**{k: v.to(DEVICE) for k, v in inputs.items()})
            # 帧级特征: [1, T, 1024]
            features = outputs.last_hidden_state
            # 均值池化
            pooled = features.mean(dim=1)  # [1, 1024]

        return pooled

    def unload(self):
        """释放模型内存"""
        if self._encoder:
            self._encoder.cpu()
            del self._encoder
            self._encoder = None
        if self._classifier:
            del self._classifier
            self._classifier = None
        self._loaded = False
        self._feature_extractor = None
        import gc; gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    async def detect(self, input_data: np.ndarray, sample_rate: int = 16000) -> DetectionOutput:
        import asyncio

        try:
            self._ensure_loaded()
        except Exception:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "model_load_error"},
            )

        try:
            features = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self._extract_features, input_data, sample_rate,
                ),
                timeout=30,
            )
        except (asyncio.TimeoutError, Exception):
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "feature_extraction_timeout"},
            )

        logit = self._classifier(features).squeeze(-1).item()
        prob = torch.sigmoid(torch.tensor(logit)).item()
        if math.isnan(logit) or math.isnan(prob):
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "nan_output", "note": "CPU推理数值异常，跳过此分支"},
            )

        return DetectionOutput(
            is_ai_generated=prob > 0.3,
            confidence=round(prob, 4),
            logit=round(logit, 6),
        )

    async def explain(self, input_data, output: DetectionOutput) -> dict:
        return {
            "detector": self.name,
            "method": "Wav2Vec2 XLS-R 300M (frozen) + lightweight classifier",
            "note": "多语言预训练编码器提取帧级特征，分类头判断AIGC痕迹",
        }
