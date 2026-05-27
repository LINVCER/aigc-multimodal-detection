"""
MiMo-VL 视觉语言模型分支 — 通过 Anthropic 兼容 API 调用小米 MiMo-VL 进行图像鉴伪

流程:
  1. 将图像编码为 base64 JPEG
  2. 通过 Anthropic Messages API 发送给 MiMo-VL
  3. 解析模型返回的 JSON 置信度评分
  4. 输出 DetectionOutput 供融合器使用

若 API 未配置或调用失败，自动降级为 model_not_loaded 状态
"""

import asyncio
import base64
import io
import json
import math

import httpx
from PIL import Image
from loguru import logger

from app.detectors.base import DetectionPipeline, DetectionOutput
from app.config import get_settings

settings = get_settings()

PROMPT = (
    "分析这张图片是否有AI生成的痕迹。仔细检查以下特征：\n"
    "1. 纹理伪影和不自然的平滑区域\n"
    "2. 光照和阴影的不一致\n"
    "3. 手指、牙齿、头发等细节异常\n"
    "4. 背景中的重复模式或扭曲\n"
    "5. 频域特征异常\n"
    "6. 文字/符号的不自然\n\n"
    "只返回一个JSON对象，不要有其他内容：\n"
    '{"confidence": <0.0-1.0之间的浮点数>, "reasoning": "<50字以内的简要分析>"}\n\n'
    "confidence表示该图像是AI生成的概率（0.0=确定真实，1.0=确定AI生成）"
)


class MiMoVLBranch(DetectionPipeline):
    """MiMo-VL 视觉语言模型检测分支"""

    name = "mimo_vl_vision_language"
    modality = "image"
    version = "0.1.0"

    def __init__(self):
        super().__init__()
        self._client = None  # httpx.AsyncClient

    def _ensure_client(self):
        if self._client is None and settings.mimo_api_key:
            self._client = httpx.AsyncClient(
                proxy=None,
                timeout=httpx.Timeout(20.0, connect=5.0),
            )

    async def detect(self, input_data: Image.Image) -> DetectionOutput:
        self._ensure_client()

        if not self._client:
            logger.debug("[MiMoVL] API key not configured, skipping")
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "model_not_loaded"},
            )

        try:
            result = await asyncio.wait_for(
                self._call_api(input_data), timeout=15
            )
            return result
        except asyncio.TimeoutError:
            logger.warning("[MiMoVL] API call timed out (15s)")
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "model_not_loaded", "reason": "timeout"},
            )
        except Exception as e:
            logger.warning(f"[MiMoVL] API call failed: {e}")
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "model_not_loaded", "reason": str(e)},
            )

    async def _call_api(self, image: Image.Image) -> DetectionOutput:
        # 编码图像为 base64 JPEG
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=95)
        b64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        headers = {
            "x-api-key": settings.mimo_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": settings.mimo_model,
            "max_tokens": 200,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": PROMPT},
                    ],
                }
            ],
        }

        # 尝试两种路径: /v1/messages 和 /messages
        import urllib.parse
        base = settings.mimo_api_base.rstrip("/")
        urls = [f"{base}/v1/messages", f"{base}/messages"]
        resp = None
        for url in urls:
            try:
                resp = await self._client.post(url, headers=headers, json=payload)
                if resp.status_code != 404:
                    break
            except Exception:
                continue
        if resp is None or resp.status_code >= 400:
            raise Exception(f"MiMo API failed: {resp.status_code if resp else 'no response'}")

        data = resp.json()
        # Anthropic Messages API 响应格式
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        confidence, reasoning = self._parse_response(text)

        # 钳位避免 logit 奇异值
        confidence = max(0.05, min(0.95, confidence))
        logit = math.log(confidence / (1.0 - confidence))

        return DetectionOutput(
            is_ai_generated=confidence > 0.5,
            confidence=round(confidence, 4),
            logit=round(logit, 6),
            metadata={
                "model_used": settings.mimo_model,
                "mimo_reasoning": reasoning,
            },
        )

    def _parse_response(self, text: str) -> tuple[float, str]:
        """从 MiMo-VL 响应中解析 confidence 和 reasoning"""
        # 尝试直接解析 JSON
        try:
            obj = json.loads(text.strip())
            return float(obj.get("confidence", 0.5)), obj.get("reasoning", "")
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # 尝试从文本中提取 JSON 块
        import re
        match = re.search(r'\{[^}]*"confidence"\s*:\s*([\d.]+)[^}]*\}', text)
        if match:
            confidence = float(match.group(1))
            reasoning_match = re.search(r'"reasoning"\s*:\s*"([^"]*)"', text)
            reasoning = reasoning_match.group(1) if reasoning_match else ""
            return confidence, reasoning

        logger.warning(f"[MiMoVL] Failed to parse response: {text[:200]}")
        return 0.5, "无法解析模型响应"

    async def explain(self, input_data: Image.Image, output: DetectionOutput) -> dict:
        reasoning = output.metadata.get("mimo_reasoning", "")
        return {
            "detector": self.name,
            "method": "MiMo-VL 视觉语言模型分析 (Anthropic API)",
            "note": reasoning or "AI视觉分析",
            "model": output.metadata.get("model_used", settings.mimo_model),
        }
