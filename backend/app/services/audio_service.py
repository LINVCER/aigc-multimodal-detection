"""
音频检测服务编排 — Wav2Vec2 (主力) + MiMo API + RawNet2 → 三路融合
"""

from app.detectors.base import DetectionOutput
from app.detectors.audio.rawnet2_detector import RawNet2Detector
from app.detectors.audio.ensemble import AudioEnsemble

_local_detector = RawNet2Detector()
_ensemble = AudioEnsemble()


async def detect_audio(audio_bytes: bytes, options: dict | None = None) -> DetectionOutput:
    """
    完整音频检测流程 — 三路并行

    输入: WAV 格式音频字节
    输出: 融合后的 DetectionOutput
    """
    # RawNet2 单路检测 (4GB服务器 CPU推理限制)
    local_output = await _local_detector.detect(audio_bytes)
    fused = _ensemble.fuse(rawnet2_output=local_output)

    if options and options.get("explain", True):
        fused.explanation_data = {
            **fused.explanation_data,
            "rawnet2_confidence": local_output.confidence,
        }

    return fused
