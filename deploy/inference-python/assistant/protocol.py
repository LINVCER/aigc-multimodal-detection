"""
请求模型与 SSE 事件编码。

事件（与 daimai arsmat-ai 的 agent-stream 形态兼容，便于日后切换引擎）：
    meta         {"conversationId", "model"}                      首个事件，前端拿到会话 id
    token        {"delta": "..."}                                  正文增量
    tool_call    {"name", "args", "label"}                         开始调用工具（前端可显示「正在分析第 3 段…」）
    tool_result  {"name", "ok", "summary"}                         工具返回摘要（不含大对象）
    done         {"usage": {...}, "model", "finishReason", "elapsedMs", "intent"}
    error        {"code", "message", "retryable"}
"""
from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversationId: Optional[str] = None
    taskId: Optional[int] = None               # 从报告详情页进入时带上，作为默认上下文
    paragraphIdx: Optional[int] = None         # 「为什么这段像 AI」直达
    userId: Optional[int] = None               # Java 透传（W3.c 前）；Sa-Token 接入后由 Java 从上下文填
    locale: str = "zh-CN"
    clientContext: dict[str, Any] = Field(default_factory=dict)   # 端 / 页面 / 版本等，仅审计


class ConversationSummary(BaseModel):
    conversationId: str
    title: str
    taskId: Optional[int] = None
    updatedAt: float
    turns: int


class ConversationDetail(BaseModel):
    conversationId: str
    taskId: Optional[int] = None
    messages: list[dict[str, Any]]


EventName = Literal["meta", "token", "tool_call", "tool_result", "done", "error"]


def sse(event: EventName, data: dict[str, Any]) -> str:
    """编码单条 SSE 帧。data 单行 JSON，保证中文不转义便于肉眼调试。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_error(code: str, message: str, retryable: bool = False) -> str:
    return sse("error", {"code": code, "message": message, "retryable": retryable})


# 错误码（Java 侧映射到 6xxx 段）
ERR_DISABLED = "ASSISTANT_DISABLED"
ERR_LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
ERR_LLM_TIMEOUT = "LLM_TIMEOUT"
ERR_SAFETY_BLOCKED = "SAFETY_BLOCKED"
ERR_TOOL_FAILED = "TOOL_FAILED"
ERR_BAD_REQUEST = "BAD_REQUEST"
