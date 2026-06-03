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

PROMPT_ROUND1 = (
    "你是一位专业的数字图像取证分析师，擅长通过视觉线索判断图片是否由人工智能生成。"
    "请你仅根据图像内容，进行一次客观、细致的分析，而不是凭感觉猜测。\n\n"
    "请按以下步骤观察并思考，用连贯的文字呈现：\n"
    "1. 细节与解剖结构：检查人物的手部、手指、脚趾、耳朵、牙齿等细节，"
    "看是否有扭曲、多余指节、错位、不对称或异常融合；留意毛发、皮肤纹理是否过于均匀光滑，"
    "是否缺乏真实的毛孔、细纹或自然凌乱感。\n"
    "2. 文字与符号：若包含文字、标志等，逐字检查是否清晰可辨，有无乱码、虚假字形。\n"
    "3. 光影与反射：确认光源方向是否一致，阴影与高光是否吻合，反射是否与环境匹配。\n"
    "4. 纹理与重复元素：观察是否有不自然的平滑区域、涂抹感、油画般笔触残留、重复纹理贴片。\n"
    "5. 透视与空间逻辑：检查物体比例、透视是否正确，是否有多个消失点矛盾。\n"
    "6. 语义合理性：判断场景中物体组合是否符合现实常识，有无AI常见的结构穿插错误。\n\n"
    "分析完成后，只返回JSON格式：\n"
    '{"confidence": 0.0到1.0, "reasoning": "20字内关键证据摘要"}'
)

PROMPT_ROUND2 = (
    "你是图像真伪鉴别专家，请重新审视这张图片，重点关注以下三个方面：\n"
    "1. 细节一致性：放大观察局部细节（毛发、皮肤纹理、布料褶皱），\n"
    "   AI图像常在细节处出现不自然的重复或模糊\n"
    "2. 边缘锐度：物体边缘是否自然，AI生成常有过度锐化或边缘模糊\n"
    "3. 全局协调性：画面整体是否协调，有无局部与整体风格不一致的区域\n\n"
    "注意：真实照片的噪点、虚化、反光、镜头畸变都是正常的，不要仅凭画面过于完美就下结论。\n"
    "只返回JSON格式：\n"
    '{"confidence": 0.0到1.0, "reasoning": "20字内关键证据摘要"}'
)


class MiMoVLBranch(DetectionPipeline):
    """AI 视觉模型检测分支"""

    name = "ai_vision_model"
    modality = "image"
    version = "0.2.0"

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
                self._call_api(input_data, PROMPT_ROUND1), timeout=15
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

    async def detect_two_rounds(self, input_data: Image.Image) -> tuple[DetectionOutput, DetectionOutput]:
        """两轮检测: 用不同prompt并发调用MiMo API，返回两个独立判定"""
        self._ensure_client()

        if not self._client:
            empty = DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "model_not_loaded"},
            )
            return empty, empty

        async def _round(prompt: str, label: str) -> DetectionOutput:
            try:
                return await asyncio.wait_for(
                    self._call_api(input_data, prompt), timeout=15
                )
            except Exception as e:
                logger.warning(f"[MiMoVL] {label} failed: {e}")
                return DetectionOutput(
                    is_ai_generated=False, confidence=0.5, logit=0.0,
                    metadata={"status": "model_not_loaded", "reason": str(e)},
                )

        r1, r2 = await asyncio.gather(
            _round(PROMPT_ROUND1, "round1"),
            _round(PROMPT_ROUND2, "round2"),
        )
        r1.metadata["round"] = 1
        r2.metadata["round"] = 2
        return r1, r2

    async def _call_api(self, image: Image.Image, prompt: str = PROMPT_ROUND1) -> DetectionOutput:
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
                        {"type": "text", "text": prompt},
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
            elif block.get("type") == "thinking":
                text += block.get("thinking", "")

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
        """从 MiMo-VL 响应中解析 confidence 和 reasoning（支持中文自然语言）"""
        import re
        # 尝试 JSON
        try:
            obj = json.loads(text.strip())
            return float(obj.get("confidence", 0.5)), obj.get("reasoning", "")
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # 尝试从文本中提取 JSON 块
        match = re.search(r'\{[^}]*"confidence"\s*:\s*([\d.]+)[^}]*\}', text)
        if match:
            return float(match.group(1)), text[:300]

        # 中文自然语言解析: 找置信度数值或关键词
        conf = 0.5
        # 匹配 "置信度: 0.85" / "confidence: 0.85" / "置信度 85%" / "85%"
        pct_match = re.search(r'置信度[：:]\s*([\d.]+)\s*%?|confidence[：:]\s*([\d.]+)', text, re.IGNORECASE)
        if pct_match:
            val = float(pct_match.group(1) or pct_match.group(2))
            conf = val / 100 if val > 1 else val
        # 关键词判断
        elif any(w in text.lower() for w in ['ai生成', 'ai 生成', '人工智能生成', 'is ai-generated', 'is ai generated']):
            conf = 0.8
        elif any(w in text.lower() for w in ['真实照片', '真实图像', '人类拍摄', '真实拍摄', 'is real', 'is authentic', 'not ai']):
            conf = 0.2
        # 找 "likely" / "probably" 类词
        elif 'probably' in text.lower() or 'likely' in text.lower() or '可能' in text:
            if 'ai' in text.lower() or '生成' in text:
                conf = 0.65
            elif 'real' in text.lower() or '真实' in text or '人类' in text:
                conf = 0.35

        return round(max(0.05, min(0.95, conf)), 4), text[:300]

    async def explain(self, input_data: Image.Image, output: DetectionOutput) -> dict:
        reasoning = output.metadata.get("mimo_reasoning", "")
        return {
            "detector": self.name,
            "method": "MiMo-VL 视觉语言模型分析 (Anthropic API)",
            "note": reasoning or "AI视觉分析",
            "model": output.metadata.get("model_used", settings.mimo_model),
        }
