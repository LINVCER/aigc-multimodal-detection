"""
v0.1.0-baseline 音频数据加载

JSONL 每行:
    {"audio_path": ".../foo.wav", "label": 0|1, "source": "real_human|tts|cloned_voice|mixed", "duration_sec": 12.3}

- label:    0 = real_human, 1 = ai_generated
- 音频文件本身不入 git（体积），只入索引 jsonl
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class AudioSample:
    audio_path: str
    label: int
    source: str = "unknown"
    duration_sec: float = 0.0


# TODO(Wave 5)
def load_jsonl(path: str) -> list[AudioSample]:
    raise NotImplementedError("待 Wave 5 · 数据准备完成后实现")


def source_balanced_sampler(samples: Iterable[AudioSample], mix: dict[str, float]) -> list[AudioSample]:
    """按 source 等比采样，防 tts 淹没其它类型"""
    raise NotImplementedError("待 Wave 5 训练启动时实现")


def slice_windows(audio_bytes: bytes, sample_rate: int, window_sec: float, stride_sec: float) -> list[bytes]:
    """按窗口切片，训练时每片段独立打标"""
    raise NotImplementedError("待 Wave 5 训练启动时实现")
