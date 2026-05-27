"""
MiMo API 语音检测分支 — 提取声学特征发送给 AI 模型判定
"""

import io
import json
import math
import numpy as np
import soundfile as sf
from app.detectors.base import DetectionPipeline, DetectionOutput
from app.config import get_settings

settings = get_settings()


class MiMoAudioDetector(DetectionPipeline):
    name = "mimo_audio_analysis"
    modality = "audio"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self._client = None

    def _extract_features(self, audio_array: np.ndarray, sr: int) -> dict:
        """提取声学特征供 MiMo 分析"""
        duration = len(audio_array) / sr

        # 基频统计
        energy = np.sqrt(np.mean(audio_array ** 2))
        zero_crossings = np.sum(np.diff(np.signbit(audio_array))) / len(audio_array)

        # 频谱特征
        if len(audio_array) >= 512:
            fft = np.abs(np.fft.rfft(audio_array))
            freqs = np.fft.rfftfreq(len(audio_array), 1 / sr)
            spectral_centroid = np.sum(freqs * fft) / (np.sum(fft) + 1e-10)
            spectral_rolloff = np.percentile(fft, 85)
            spectral_flatness = np.exp(np.mean(np.log(fft + 1e-10))) / (np.mean(fft) + 1e-10)
        else:
            spectral_centroid = 0
            spectral_rolloff = 0
            spectral_flatness = 0

        return {
            "duration": round(duration, 2),
            "sample_rate": sr,
            "rms_energy": round(energy, 6),
            "zero_cross_rate": round(zero_crossings, 4),
            "spectral_centroid": round(spectral_centroid, 1),
            "spectral_rolloff": round(spectral_rolloff, 1),
            "spectral_flatness": round(spectral_flatness, 4),
        }

    async def detect(self, audio_bytes: bytes) -> DetectionOutput:
        if not settings.llm_api_key:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "api_unavailable", "note": "LLM API Key 未配置"},
            )

        try:
            audio_array, sr = sf.read(io.BytesIO(audio_bytes))
            if audio_array.ndim > 1:
                audio_array = audio_array.mean(axis=1)
            audio_array = audio_array.astype(np.float32)
        except Exception:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "decode_error"},
            )

        feats = self._extract_features(audio_array, sr)

        prompt = (
            "你是一个专业的AI语音检测专家。请根据以下声学特征判断这段语音是AI合成还是真人录制。\n\n"
            "声学特征：\n"
            f"- 时长: {feats['duration']}秒\n"
            f"- RMS能量: {feats['rms_energy']}\n"
            f"- 过零率: {feats['zero_cross_rate']}\n"
            f"- 频谱质心: {feats['spectral_centroid']}Hz\n"
            f"- 频谱平坦度: {feats['spectral_flatness']}\n\n"
            "AI合成语音的特点：频谱平坦度异常高或低，过零率机械规律，能量分布过于均匀\n"
            "真人录音的特点：频谱自然波动，过零率不规则，能量有自然起伏\n\n"
            "只返回JSON：{\"confidence\": 0.0-1.0, \"reasoning\": \"简短理由\"}\n"
            "confidence=0.0表示确定真人，1.0表示确定AI合成"
        )

        import httpx
        try:
            url = f"{settings.llm_api_base.rstrip('/')}/v1/messages"
            headers = {
                "x-api-key": settings.llm_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": settings.llm_model,
                "max_tokens": 150,
                "messages": [{"role": "user", "content": prompt}],
            }

            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    return DetectionOutput(
                        is_ai_generated=False, confidence=0.5, logit=0.0,
                        metadata={"status": "api_error", "code": resp.status_code},
                    )
                data = resp.json()

            # 解析响应
            content = ""
            for block in data.get("content", []):
                content = block.get("text", "") or block.get("thinking", "")
                if content:
                    break

            conf = 0.5
            try:
                obj = json.loads(content.strip())
                conf = float(obj.get("confidence", 0.5))
            except (json.JSONDecodeError, ValueError):
                # 中文关键词判断
                import re
                m = re.search(r'置信度[：:]\s*([\d.]+)', content)
                if m:
                    val = float(m.group(1))
                    conf = val / 100 if val > 1 else val
                elif 'AI合成' in content or 'ai生成' in content.lower():
                    conf = 0.75
                elif '真人' in content or '人类' in content or '真实' in content:
                    conf = 0.25

            conf = max(0.05, min(0.95, conf))
            return DetectionOutput(
                is_ai_generated=conf > 0.5,
                confidence=round(conf, 4),
                logit=math.log(conf / (1 - conf)) if 0 < conf < 1 else 0.0,
                metadata={"method": "MiMo API 声学特征分析", "features": feats, "reasoning": content[:200]},
            )

        except Exception:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "api_unavailable"},
            )

    async def explain(self, input_data: bytes, output: DetectionOutput) -> dict:
        return {
            "detector": self.name,
            "method": "MiMo 声学特征零样本判定",
            "metrics": output.metadata,
        }
