"""
大模型 AI 文本检测 — 支持 Anthropic API (MiMo) / OpenAI API (DeepSeek)

通过 LLM 零样本判断文本是否为 AI 生成，输出置信度。
"""

import math
import json
from dataclasses import dataclass

from app.detectors.base import DetectionPipeline, DetectionOutput
from app.config import get_settings

settings = get_settings()


def _is_anthropic_api() -> bool:
    """检测是否使用 Anthropic 兼容 API (MiMo)"""
    return "anthropic" in settings.llm_api_base.lower() or "mimo" in settings.llm_model.lower()


class LLMLogprobDetector(DetectionPipeline):
    """基于大模型的文本检测器 — 自动适配 Anthropic / OpenAI API"""

    name = "llm_logprob_analysis"
    modality = "text"
    version = "0.2.0"

    def __init__(self):
        super().__init__()
        self._client_type: str | None = None  # "anthropic" | "openai"

    async def _call_anthropic(self, text: str) -> float | None:
        """通过 Anthropic Messages API 检测"""
        try:
            import httpx

            sample = text[:1200]
            prompt = (
                "你是一个专业的AI文本检测器。请仔细分析以下文本，判断它是AI生成还是人类写作。\n\n"
                "分析要点：\n"
                "1. 词汇多样性：AI倾向使用重复的高频词\n"
                "2. 句式结构：AI倾向过于规整的句式\n"
                "3. 逻辑连贯性：AI有时会出现逻辑跳跃\n"
                "4. 个性化表达：人类写作通常有更自然的语气变化\n\n"
                f"待检测文本：\n{sample}\n\n"
                "请用JSON格式回答，只返回：\n"
                '{"result": "AI"|"HUMAN", "confidence": 0.0-1.0, "reason": "简短理由"}'
            )

            url = f"{settings.llm_api_base}/v1/messages"
            headers = {
                "x-api-key": settings.llm_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": settings.llm_model,
                "max_tokens": 200,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": prompt}],
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    return None
                data = resp.json()

            # 处理 Anthropic/MiMo 响应，支持 text 和 thinking 两种 content 类型
            raw_content = data.get("content", [{}])
            content_text = ""
            for block in raw_content:
                if block.get("type") == "text":
                    content_text = block.get("text", "")
                    break
                elif block.get("type") == "thinking":
                    content_text = block.get("thinking", "")
                    break
            content = content_text
            # Parse JSON from response
            content = content.strip()
            # Handle markdown code block
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.split("```")[0]
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Try to find JSON in text
                import re
                m = re.search(r'\{[^}]+\}', content)
                if m:
                    try:
                        result = json.loads(m.group())
                    except json.JSONDecodeError:
                        return None
                else:
                    return None

            is_ai = result.get("result", "").upper() == "AI"
            confidence = float(result.get("confidence", 0.5))
            if is_ai:
                return 0.5 + confidence * 0.5
            else:
                return 0.5 - confidence * 0.5

        except Exception:
            return None

    async def _call_openai(self, text: str) -> float | None:
        """通过 OpenAI API (DeepSeek) 的 logprobs 检测"""
        import httpx
        from openai import OpenAI

        try:
            http_client = httpx.Client(proxy=None, timeout=30.0)
            client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base,
                http_client=http_client,
            )
            sample = text[:800]
            prompt = (
                "请判断以下文本是否为 AI 生成。只回答 YES 或 NO。\n\n"
                f"文本: {sample}\n\n回答:"
            )
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1,
                temperature=0.0,
                logprobs=True,
                top_logprobs=20,
                timeout=30,
            )
            lp_content = response.choices[0].logprobs
            if not lp_content or not lp_content.content:
                return None

            top_tokens = lp_content.content[0].top_logprobs
            if not top_tokens:
                return None

            yes_logprob = None
            no_logprob = None
            for t in top_tokens:
                token_str = t.token.strip().upper()
                if token_str in ("YES", " YES"):
                    if yes_logprob is None or t.logprob > yes_logprob:
                        yes_logprob = t.logprob
                elif token_str in ("NO", " NO"):
                    if no_logprob is None or t.logprob > no_logprob:
                        no_logprob = t.logprob

            if yes_logprob is None and no_logprob is None:
                return None
            if yes_logprob is None:
                yes_logprob = -10.0
            if no_logprob is None:
                no_logprob = -10.0

            return math.exp(yes_logprob) / (math.exp(yes_logprob) + math.exp(no_logprob))
        except Exception:
            return None

    async def detect(self, input_data: str) -> DetectionOutput:
        import asyncio

        if not settings.llm_api_key:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "api_unavailable", "note": "LLM API Key 未配置"},
            )

        try:
            if _is_anthropic_api():
                ai_score = await asyncio.wait_for(self._call_anthropic(input_data), timeout=30)
            else:
                ai_score = await asyncio.wait_for(self._call_openai(input_data), timeout=15)
        except (asyncio.TimeoutError, Exception):
            ai_score = None

        if ai_score is None:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "api_unavailable", "note": "LLM API 调用失败"},
            )

        ai_score = max(0.05, min(0.95, ai_score))
        logit = math.log(ai_score / (1 - ai_score)) if 0 < ai_score < 1 else 0.0

        return DetectionOutput(
            is_ai_generated=ai_score > 0.3,
            confidence=round(ai_score, 4),
            logit=round(logit, 6),
            metadata={
                "ai_probability": round(ai_score, 4),
                "model_used": settings.llm_model,
                "method": "anthropic_zero_shot" if _is_anthropic_api() else "openai_logprob",
            },
        )

    async def explain(self, input_data: str, output: DetectionOutput) -> dict:
        return {
            "detector": self.name,
            "method": "LLM Zero-Shot 文本检测",
            "metrics": output.metadata,
        }
