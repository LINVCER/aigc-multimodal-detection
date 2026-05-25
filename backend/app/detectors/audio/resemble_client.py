"""
Resemble AI Detect API 客户端 — 云端音频反欺骗检测

每月 1000 次免费检测额度，用于原型开发阶段的主检测路径
"""

import httpx
from app.detectors.base import DetectionPipeline, DetectionOutput
from app.config import get_settings

settings = get_settings()


class ResembleAIDetector(DetectionPipeline):
    name = "resemble_ai_detect"
    modality = "audio"
    version = "0.1.0"

    BASE_URL = "https://app.resemble.ai/api/v1"

    def __init__(self):
        super().__init__()
        self._api_key = settings.resemble_ai_api_key
        self._monthly_limit = settings.resemble_ai_monthly_limit
        self._call_count = 0

    async def _call_api(self, audio_bytes: bytes) -> dict | None:
        """调用 Resemble AI Detect API"""
        if not self._api_key:
            return None

        if self._call_count >= self._monthly_limit:
            print("[ResembleAI] 月度额度已用完，切换至本地 RawNet2")
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.BASE_URL}/detect",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "audio/wav",
                    },
                    content=audio_bytes,
                )
                if response.status_code == 200:
                    self._call_count += 1
                    return response.json()
                else:
                    print(f"[ResembleAI] API 错误: {response.status_code}")
                    return None
        except Exception as e:
            print(f"[ResembleAI] 请求失败: {e}")
            return None

    async def detect(self, input_data: bytes) -> DetectionOutput:
        """
        检测音频是否为 AI 生成

        input_data: WAV 格式音频字节
        """
        result = await self._call_api(input_data)

        if result is None:
            return DetectionOutput(
                is_ai_generated=False,
                confidence=0.5,
                logit=0.0,
                metadata={
                    "status": "api_unavailable",
                    "note": "Resemble AI API 不可用，请检查 API Key 或月度额度",
                    "calls_remaining": self._monthly_limit - self._call_count,
                },
            )

        # 解析 API 响应
        ai_score = result.get("ai_score", result.get("score", 0.5))
        is_ai = result.get("is_ai_generated", ai_score > 0.5)

        import math
        logit = math.log(ai_score / (1 - ai_score)) if 0 < ai_score < 1 else 0.0

        return DetectionOutput(
            is_ai_generated=is_ai,
            confidence=round(ai_score, 4),
            logit=round(logit, 6),
            metadata={
                "api_response": result,
                "calls_remaining": self._monthly_limit - self._call_count,
            },
        )

    async def explain(self, input_data: bytes, output: DetectionOutput) -> dict:
        return {
            "detector": self.name,
            "method": "Resemble AI Detect API — 云端深度学习反欺骗模型",
        }
