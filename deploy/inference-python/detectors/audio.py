"""
音频 AIGC 检测器（骨架）
=====================

架构（对齐 ml/training/audio · 待训练启动后填充）：
    wav2vec2 / xls-r-300m → hidden (768/1024) → mean pooling
        → Dropout → Linear(hidden, 128) → ReLU → Linear(128, 2)
        → logits [B, 2] → 温度 T + Platt (a, b) 校准

预测（跟 text 一致的口径）：
    raw_logit  = logits[:, 1]
    ai_prob    = sigmoid(raw_logit)
    calibrated = sigmoid((raw_logit / T) * a + b)

segments 语义：
    - 按固定窗口切片（默认 3s 窗口 + 1s stride，overlap 66%）
    - 每片段独立打分
    - 返回 [{segment_idx, time_start, time_end, ai_prob, calibrated_prob, waveform_peak}, ...]

⚠ 现状：本模块只是加载器 + 推理管线骨架。真实权重（aigc_audio_classifier.pth）
在 legacy/ 里，格式与新架构不完全兼容；ml/ 新一代训练计划待启动。
未加载成功时 main.py 走 stub 兜底（哈希取模伪 segments）。
"""
from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class AudioSegmentPrediction:
    segment_idx: int
    time_start: float
    time_end: float
    ai_prob: float
    calibrated_prob: float
    waveform_peak: float | None = None
    source_label: str | None = None


@dataclass
class AudioPrediction:
    ai_prob: float            # 未校准（全段聚合）
    calibrated_prob: float    # 校准后
    duration_sec: float
    model_version: str
    segments: list[AudioSegmentPrediction]


class AudioAIGCDetector:
    """
    单例式：main.py startup 尝试加载；失败 fallback stub 走。
    真实加载依赖 torchaudio + transformers（Wave 5 · 训练启动时补 requirements）。
    """

    def __init__(
        self,
        base_model_path: str,
        checkpoint_path: str,
        device: str = "cpu",
        window_sec: float = 3.0,
        stride_sec: float = 1.0,
        model_version: str = "audio_v0",
    ) -> None:
        self.base_model_path = base_model_path
        self.checkpoint_path = checkpoint_path
        self.device_str = device
        self.window_sec = window_sec
        self.stride_sec = stride_sec
        self.model_version = model_version

        self.temperature: float = 1.0
        self.platt_a: float = 1.0
        self.platt_b: float = 0.0
        self.model = None
        self.processor = None

    def load(self) -> None:
        # TODO(Wave 5 · ml/training/audio 训练启动后填充)
        #   1) import torch, torchaudio, transformers
        #   2) processor = AutoFeatureExtractor.from_pretrained(base_model_path)
        #   3) model = Wav2Vec2ForSequenceClassification(...).load_state_dict(ckpt['model_state_dict'])
        #   4) 读 checkpoint 的 temperature / platt_a / platt_b / hyperparams
        raise NotImplementedError(
            "audio detector 真实加载待 Wave 5 · ml/training/audio 训练启动后实现"
        )

    def predict(self, audio_bytes: bytes, filename: str = "audio.bin") -> AudioPrediction:
        # TODO(Wave 5)
        #   1) 用 torchaudio.load 读 bytes → waveform + sample_rate
        #   2) resample 到 16kHz（wav2vec2 要求）
        #   3) 按 window/stride 切段 → segments
        #   4) 逐段 forward → logit → sigmoid + calibrate
        #   5) 全段 aiRate 用 segments 均值或长度加权
        raise NotImplementedError(
            "audio detector 真实推理待 Wave 5 实现"
        )

    def health(self) -> dict[str, Any]:
        return {
            "loaded": self.model is not None,
            "base_model_path": self.base_model_path,
            "checkpoint_path": self.checkpoint_path,
            "device": self.device_str,
            "window_sec": self.window_sec,
            "stride_sec": self.stride_sec,
            "model_version": self.model_version,
        }


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)
