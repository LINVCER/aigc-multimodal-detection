"""
DeepSeek API 检测器 — 通过 OpenAI 兼容接口调用 DeepSeek 进行文本鉴别

使用 logprobs 获取 YES/NO 概率，独立于 MiMo Anthropic API。
"""

import math
from app.detectors.base import DetectionPipeline, DetectionOutput
from app.config import get_settings

settings = get_settings()


class DeepSeekDetector(DetectionPipeline):
    name = "deepseek_logprob"
    modality = "text"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self._client = None

    def _ensure_client(self):
        if self._client is None and settings.deepseek_api_key:
            import httpx
            from openai import OpenAI
            http_client = httpx.Client(proxy=None, timeout=30.0)
            self._client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_api_base,
                http_client=http_client,
            )

    async def detect(self, input_data: str) -> DetectionOutput:
        import asyncio

        if not settings.deepseek_api_key:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "api_unavailable", "note": "DeepSeek API Key 未配置"},
            )

        try:
            self._ensure_client()
            if not self._client:
                return DetectionOutput(
                    is_ai_generated=False, confidence=0.5, logit=0.0,
                    metadata={"status": "api_unavailable"},
                )

            sample = input_data[:800]
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._client.chat.completions.create(
                        model=settings.deepseek_model,
                        messages=[{
                            "role": "user",
                            "content": f"请判断以下文本是否为 AI 生成。只回答 YES 或 NO。\n\n文本: {sample}\n\n回答:",
                        }],
                        max_tokens=1,
                        temperature=0.0,
                        logprobs=True,
                        top_logprobs=20,
                        timeout=30,
                    ),
                ),
                timeout=25,
            )

            lp_content = response.choices[0].logprobs
            if not lp_content or not lp_content.content:
                return DetectionOutput(
                    is_ai_generated=False, confidence=0.5, logit=0.0,
                    metadata={"status": "no_logprobs"},
                )

            top_tokens = lp_content.content[0].top_logprobs
            if not top_tokens:
                return DetectionOutput(
                    is_ai_generated=False, confidence=0.5, logit=0.0,
                    metadata={"status": "no_tokens"},
                )

            yes_lp = -10.0
            no_lp = -10.0
            for t in top_tokens:
                token_str = t.token.strip().upper()
                if token_str in ("YES", "YES"):
                    yes_lp = max(yes_lp, t.logprob) if yes_lp != -10.0 else t.logprob
                elif token_str in ("NO", "NO"):
                    no_lp = max(no_lp, t.logprob) if no_lp != -10.0 else t.logprob

            if yes_lp == -10.0 and no_lp == -10.0:
                return DetectionOutput(
                    is_ai_generated=False, confidence=0.5, logit=0.0,
                    metadata={"status": "no_yes_no_token"},
                )

            if yes_lp == -10.0:
                yes_lp = -10.0
            if no_lp == -10.0:
                no_lp = -10.0

            ai_prob = math.exp(yes_lp) / (math.exp(yes_lp) + math.exp(no_lp))
            ai_prob = max(0.05, min(0.95, ai_prob))
            logit = math.log(ai_prob / (1 - ai_prob)) if 0 < ai_prob < 1 else 0.0

            return DetectionOutput(
                is_ai_generated=ai_prob > 0.3,
                confidence=round(ai_prob, 4),
                logit=round(logit, 6),
                metadata={
                    "ai_probability": round(ai_prob, 4),
                    "yes_logprob": round(yes_lp, 4),
                    "no_logprob": round(no_lp, 4),
                    "margin": round(abs(yes_lp - no_lp), 4),
                    "method": "deepseek_logprob",
                    "model": settings.deepseek_model,
                },
            )

        except (asyncio.TimeoutError, Exception):
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "api_unavailable", "note": "DeepSeek API 调用失败"},
            )

    async def explain(self, input_data: str, output: DetectionOutput) -> dict:
        return {
            "detector": self.name,
            "method": "DeepSeek API Log-probability",
            "metrics": output.metadata,
        }
