"""
音频检测服务编排 — Wav2Vec2 (主力) + MiMo API + RawNet2 → 三路融合
"""

from app.detectors.base import DetectionOutput
from app.detectors.audio.wav2vec2_detector import Wav2Vec2AIGCDetector
from app.detectors.audio.rawnet2_detector import RawNet2Detector
from app.detectors.audio.ensemble import AudioEnsemble

_wav2vec2 = Wav2Vec2AIGCDetector()
_local_detector = RawNet2Detector()
_ensemble = AudioEnsemble()


async def detect_audio(audio_bytes: bytes, options: dict | None = None) -> DetectionOutput:
    """
    音频检测 — Wav2Vec2-base (380MB) + RawNet2 双路

    输入: WAV 格式音频字节
    输出: 融合后的 DetectionOutput
    """
    import numpy as np
    import io
    import soundfile as sf
    audio_array, sample_rate = sf.read(io.BytesIO(audio_bytes))
    if audio_array.ndim > 1:
        audio_array = audio_array.mean(axis=1)
    audio_array = audio_array.astype(np.float32)

    w2v_output = await _wav2vec2.detect(audio_array, sample_rate)
    local_output = await _local_detector.detect(audio_bytes)
    fused = _ensemble.fuse(wav2vec2_output=w2v_output, rawnet2_output=local_output)

    if options and options.get("explain", True):
        fused.explanation_data = {
            **fused.explanation_data,
            "wav2vec2_confidence": w2v_output.confidence,
            "rawnet2_confidence": local_output.confidence,
        }

    return fused
