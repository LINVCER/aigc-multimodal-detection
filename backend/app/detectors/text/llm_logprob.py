"""
大模型 log-probability 分析 — 困惑度与概率曲率检测

调用 OpenAI API 获取每个 token 的对数概率，计算:
  - 困惑度 (Perplexity): AI 文本对自身模型有更低的困惑度
  - 概率曲率 (Probability Curvature): 类似 DetectGPT，检测概率空间的局部曲率

注意: 此模块需要 OpenAI API 学术额度。若未配置 API Key，自动降级为不可用状态。
"""

import math
from dataclasses import dataclass

from app.detectors.base import DetectionPipeline, DetectionOutput
from app.config import get_settings

settings = get_settings()


@dataclass
class LogprobResult:
    perplexity: float
    avg_logprob: float
    token_count: int
    probability_curvature: float | None = None


class LLMLogprobDetector(DetectionPipeline):
    """基于大模型 log-probability 的文本检测器"""

    name = "llm_logprob_analysis"
    modality = "text"
    version = "0.1.0"

    def __init__(self):
        super().__init__()
        self._client = None

    def _ensure_client(self):
        if self._client is None and settings.llm_api_key:
            import httpx
            from openai import OpenAI
            http_client = httpx.Client(proxy=None, timeout=30.0)
            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base,
                http_client=http_client,
            )

    async def _get_logprobs(self, text: str) -> LogprobResult | None:
        """
        调用 DeepSeek API: 让模型判断文本是否为 AI 生成，通过 YES/NO 的 logprob 计算置信度
        """
        self._ensure_client()
        if not self._client:
            return None

        sample = text[:800]
        prompt = (
            "请判断以下文本是否为 AI 生成。只回答 YES 或 NO。\n\n"
            f"文本: {sample}\n\n"
            "回答:"
        )
        try:
            response = self._client.chat.completions.create(
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

            # 从 top_logprobs 中提取 YES/NO 的概率
            top_tokens = lp_content.content[0].top_logprobs
            if not top_tokens:
                return None

            yes_logprob = None
            no_logprob = None
            for t in top_tokens:
                token_str = t.token.strip().upper()
                if token_str in ('YES', ' YES'):
                    if yes_logprob is None or t.logprob > yes_logprob:
                        yes_logprob = t.logprob
                elif token_str in ('NO', ' NO'):
                    if no_logprob is None or t.logprob > no_logprob:
                        no_logprob = t.logprob

            if yes_logprob is None and no_logprob is None:
                return None
            # 只有一个 token 的情况：用 -10 作为对立面的默认 logprob
            if yes_logprob is None:
                yes_logprob = -10.0
            if no_logprob is None:
                no_logprob = -10.0

            ai_prob = math.exp(yes_logprob) / (math.exp(yes_logprob) + math.exp(no_logprob))
            avg_logprob = yes_logprob

            return LogprobResult(
                perplexity=round(ai_prob, 4),  # 复用字段存 AI 概率
                avg_logprob=round(yes_logprob, 4),
                token_count=2,
            )
        except Exception as e:
            print(f"[LLMLogprobDetector] API 调用失败: {e}")
            return None

    async def _compute_probability_curvature(self, text: str) -> float | None:
        """
        概率曲率计算 (DetectGPT 简化版)
        对原始文本和局部扰动文本的 log-probability 差值进行检测
        """
        self._ensure_client()
        if not self._client:
            return None

        try:
            # 原始文本 logprob
            orig_result = await self._get_logprobs(text)
            if not orig_result:
                return None

            # 简单扰动: 删除 10% 随机字符后重新计算
            import random
            chars = list(text)
            perturbed = [
                c for i, c in enumerate(chars)
                if random.random() > 0.1
            ]
            pert_text = "".join(perturbed) if perturbed else text

            pert_result = await self._get_logprobs(pert_text)
            if not pert_result:
                return None

            # 曲率 = perturbed_perplexity - original_perplexity
            # AI 文本在扰动后困惑度显著上升 (曲率大)
            # 人类文本困惑度变化较小 (曲率小)
            curvature = pert_result.perplexity - orig_result.perplexity
            return round(curvature, 4)
        except Exception:
            return None

    async def detect(self, input_data: str) -> DetectionOutput:
        import asyncio

        try:
            result = await asyncio.wait_for(self._get_logprobs(input_data), timeout=10)
        except (asyncio.TimeoutError, Exception):
            result = None

        if result is None:
            return DetectionOutput(
                is_ai_generated=False, confidence=0.5, logit=0.0,
                metadata={"status": "api_unavailable", "note": "LLM API 不可用或无法判定"},
            )

        ai_score = result.perplexity  # 直接使用 YES/NO 概率
        ai_score = max(0.05, min(0.95, ai_score))
        logit = math.log(ai_score / (1 - ai_score)) if 0 < ai_score < 1 else 0.0

        return DetectionOutput(
            is_ai_generated=ai_score > 0.3,
            confidence=round(ai_score, 4),
            logit=round(logit, 6),
            metadata={
                "ai_probability": round(ai_score, 4),
                "yes_logprob": result.avg_logprob,
                "model_used": settings.llm_model,
                "method": "zero_shot_yes_no_logprob",
            },
        )

    async def explain(self, input_data: str, output: DetectionOutput) -> dict:
        return {
            "detector": self.name,
            "method": "OpenAI API Log-probability + Probability Curvature (DetectGPT-like)",
            "metrics": output.metadata,
        }
