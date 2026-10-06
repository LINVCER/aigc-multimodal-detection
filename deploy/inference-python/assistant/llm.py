"""
OpenAI-compatible 流式客户端（provider 感知）。

只依赖 `openai` SDK。职责：按 provider profile 组请求 / 重试 / 首 token 超时 /
把 SDK 的 chunk 归一成 (kind, payload)：
    ("token", str)                       正文增量
    ("reasoning", str)                   思考增量（仅 thinking 开启；调用方必须回传）
    ("tool_calls", list[ToolCall])       本轮模型要调工具（已把分片 arguments 拼完整）
    ("finish", {"reason", "usage"})

provider 差异收敛在 providers.py，本文件不写死任何一家的 base_url / 模型名。
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


def build_request_kwargs(messages: list[dict[str, Any]],
                         tools: list[dict[str, Any]] | None,
                         thinking: bool | None = None) -> dict[str, Any]:
    """按当前 provider profile 组 chat.completions.create 的参数。

    单独抽出来是为了能单测「参数是否符合该家文档」，不必真发请求。
    thinking=None 时用 CONFIG.thinking_active；显式传值可覆盖（自检脚本用，
    避免为了改一个开关去重建整个 CONFIG）。
    """
    p = CONFIG.profile
    thinking_active = CONFIG.thinking_active if thinking is None else (thinking and p.supports_thinking)
    kwargs: dict[str, Any] = {
        "model": CONFIG.resolved_model,
        "messages": messages,
        "max_tokens": CONFIG.llm_max_tokens,
        "stream": True,
    }
    if p.supports_stream_usage:
        kwargs["stream_options"] = {"include_usage": True}

    if tools and p.supports_tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    if thinking_active:
        # 思考模式**忽略 temperature**（官方文档：设了不报错但无效），所以干脆不发，免得误导
        kwargs["reasoning_effort"] = CONFIG.reasoning_effort
        kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
    else:
        kwargs["temperature"] = CONFIG.llm_temperature
        if p.supports_thinking:
            # 明确关闭（DeepSeek 默认是开的），避免默认值漂移后行为突变
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return kwargs


class LLMClient:
    def __init__(self) -> None:
        self._client = None
        self._client_key = None   # (base_url, api_key) —— 变了要重建

    def _get(self):
        base_url = CONFIG.resolved_base_url
        api_key = CONFIG.resolved_api_key
        cache_key = (base_url, api_key)
        if self._client is not None and self._client_key == cache_key:
            return self._client
        try:
            from openai import AsyncOpenAI
        except ImportError as e:   # pragma: no cover
            raise LLMError("LLM_UNAVAILABLE", "推理镜像缺少 openai 依赖") from e
        if not api_key:
            envs = " / ".join(CONFIG.profile.api_key_envs)
            raise LLMError("LLM_UNAVAILABLE", f"未配置 API key（provider={CONFIG.provider_name}，可设 {envs}）")
        if not base_url:
            raise LLMError("LLM_UNAVAILABLE",
                           f"provider={CONFIG.provider_name} 未配置 base_url（设 ASSISTANT_LLM_BASE_URL）")
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=CONFIG.llm_total_timeout_s,
            max_retries=0,   # 重试自己做，才能区分「首 token 超时」与「中途断流」
        )
        self._client_key = cache_key
        return self._client

    async def stream(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
                     thinking: bool | None = None) -> AsyncIterator[tuple[str, Any]]:
        """带重试的流式调用。只在拿到首 token 之前失败才重试，避免给用户重复输出。"""
        last_err: Exception | None = None
        for attempt in range(CONFIG.llm_max_retries + 1):
            got_first = False
            try:
                async for kind, payload in self._stream_once(messages, tools, thinking):
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

    async def _stream_once(self, messages, tools, thinking=None) -> AsyncIterator[tuple[str, Any]]:
        client = self._get()
        kwargs = build_request_kwargs(messages, tools, thinking)

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

                # DeepSeek 思考模式：reasoning_content 与 content 同级。
                # 文档明确「请求带 tools 时必须把 reasoning_content 完整回传，否则 400」，
                # 所以这里单独 yield，由 agent 累积后随 assistant 消息回传。
                reasoning = getattr(delta, "reasoning_content", None) if delta else None
                if reasoning:
                    yield "reasoning", reasoning

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
    """错误归类。注意 DeepSeek 的 400 常表示「请求构造不对」（例如 thinking+tools 没回传
    reasoning_content），要给出可诊断的文案而不是笼统的「服务不可用」。"""
    name = type(e).__name__
    msg = str(e)
    status = getattr(e, "status_code", None)
    low = msg.lower()
    if status in (401, 403) or "api_key" in low or "authentication" in low:
        envs = " / ".join(CONFIG.profile.api_key_envs)
        return LLMError("LLM_UNAVAILABLE", f"模型服务鉴权失败，请检查 {envs}", retryable=False)
    if status == 404 or "model not found" in low or "does not exist" in low:
        return LLMError("LLM_UNAVAILABLE",
                        f"模型 '{CONFIG.resolved_model}' 不存在（provider={CONFIG.provider_name}）。"
                        f"模型名可能已退役，见 {CONFIG.profile.docs_url}", retryable=False)
    if status == 400:
        return LLMError("LLM_UNAVAILABLE", f"请求被模型服务拒绝（400）：{msg[:200]}", retryable=False)
    if status == 429 or "rate" in low:
        return LLMError("LLM_UNAVAILABLE", "模型服务限流，请稍后重试", retryable=True)
    if status and 500 <= status < 600:
        return LLMError("LLM_UNAVAILABLE", "模型服务暂时不可用", retryable=True)
    if "timeout" in name.lower() or "timeout" in low:
        return LLMError("LLM_TIMEOUT", "模型响应超时，请稍后重试", retryable=True)
    return LLMError("LLM_UNAVAILABLE", f"模型调用失败：{name}", retryable=True)


LLM = LLMClient()
