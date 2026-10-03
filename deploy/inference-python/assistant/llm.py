"""
OpenAI-compatible 流式客户端。

只依赖 `openai` SDK（training/requirements 已有，推理 requirements 本次补上）。
职责：重试 / 首 token 超时 / 把 SDK 的 chunk 归一成 (kind, payload)：
    ("token", str)                       正文增量
    ("tool_calls", list[ToolCall])       本轮模型要调工具（已把分片 arguments 拼完整）
    ("finish", {"reason", "usage"})
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from .config import CONFIG

log = logging.getLogger("assistant.llm")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = ""   # JSON 字符串，流式分片拼接


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens}


class LLMError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class LLMClient:
    def __init__(self) -> None:
        self._client = None

    def _get(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as e:   # pragma: no cover
                raise LLMError("LLM_UNAVAILABLE", "推理镜像缺少 openai 依赖") from e
            if not CONFIG.llm_api_key:
                raise LLMError("LLM_UNAVAILABLE", "未配置 ASSISTANT_LLM_API_KEY")
            self._client = AsyncOpenAI(
                base_url=CONFIG.llm_base_url,
                api_key=CONFIG.llm_api_key,
                timeout=CONFIG.llm_total_timeout_s,
                max_retries=0,   # 重试自己做，才能区分「首 token 超时」与「中途断流」
            )
        return self._client

    async def stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
                     ) -> AsyncIterator[tuple[str, Any]]:
        """带重试的流式调用。只在拿到首 token 之前失败才重试，避免给用户重复输出。"""
        last_err: Exception | None = None
        for attempt in range(CONFIG.llm_max_retries + 1):
            got_first = False
            try:
                async for kind, payload in self._stream_once(messages, tools):
                    got_first = True
                    yield kind, payload
                return
            except LLMError as e:
                last_err = e
                if got_first or not e.retryable or attempt == CONFIG.llm_max_retries:
                    raise
                delay = 1.0 * (2 ** attempt)
                log.warning("LLM 调用失败（%s），%.1fs 后重试 %d/%d", e, delay, attempt + 1, CONFIG.llm_max_retries)
                await asyncio.sleep(delay)
        if last_err:
            raise last_err

    async def _stream_once(self, messages, tools) -> AsyncIterator[tuple[str, Any]]:
        client = self._get()
        kwargs: dict[str, Any] = dict(
            model=CONFIG.llm_model,
            messages=messages,
            temperature=CONFIG.llm_temperature,
            max_tokens=CONFIG.llm_max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        t0 = time.monotonic()
        try:
            resp = await asyncio.wait_for(client.chat.completions.create(**kwargs), CONFIG.llm_first_token_timeout_s)
        except asyncio.TimeoutError as e:
            raise LLMError("LLM_TIMEOUT", "模型响应超时，请稍后重试", retryable=True) from e
        except Exception as e:   # 鉴权 / 网络 / 4xx
            raise _classify(e) from e

        pending: dict[int, ToolCall] = {}
        finish_reason = None
        usage = LLMUsage()
        first = True
        try:
            async for chunk in resp:
                if first:
                    first = False
                    if time.monotonic() - t0 > CONFIG.llm_first_token_timeout_s:
                        raise LLMError("LLM_TIMEOUT", "模型首字响应超时", retryable=True)
                if getattr(chunk, "usage", None):
                    usage.prompt_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
                    usage.completion_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta and delta.content:
                    yield "token", delta.content
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index if tc.index is not None else 0
                        slot = pending.setdefault(idx, ToolCall(id=tc.id or f"call_{idx}", name=""))
                        if tc.id:
                            slot.id = tc.id
                        if tc.function:
                            if tc.function.name:
                                slot.name = tc.function.name
                            if tc.function.arguments:
                                slot.arguments += tc.function.arguments
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
        except LLMError:
            raise
        except Exception as e:
            raise LLMError("LLM_UNAVAILABLE", f"模型流中断：{type(e).__name__}", retryable=False) from e

        if pending:
            yield "tool_calls", [pending[k] for k in sorted(pending)]
        yield "finish", {"reason": finish_reason or ("tool_calls" if pending else "stop"), "usage": usage}


def _classify(e: Exception) -> LLMError:
    name = type(e).__name__
    msg = str(e)
    status = getattr(e, "status_code", None)
    if status in (401, 403) or "api_key" in msg.lower():
        return LLMError("LLM_UNAVAILABLE", "模型服务鉴权失败，请检查 ASSISTANT_LLM_API_KEY", retryable=False)
    if status == 429 or "rate" in msg.lower():
        return LLMError("LLM_UNAVAILABLE", "模型服务限流，请稍后重试", retryable=True)
    if status and 500 <= status < 600:
        return LLMError("LLM_UNAVAILABLE", "模型服务暂时不可用", retryable=True)
    if "timeout" in name.lower() or "timeout" in msg.lower():
        return LLMError("LLM_TIMEOUT", "模型响应超时，请稍后重试", retryable=True)
    return LLMError("LLM_UNAVAILABLE", f"模型调用失败：{name}", retryable=True)


LLM = LLMClient()
