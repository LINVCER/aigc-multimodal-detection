"""
工具循环主体：组上下文 → 流式调模型 → 有 tool_calls 就执行再回喂 → 直到模型产出最终文本。

每一步都 yield SSE 帧字符串，router 直接透传给 StreamingResponse。
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, AsyncIterator, Optional

from .config import CONFIG
from .knowledge import get_kb
from .llm import LLM, LLMError
from .prompts import build_system_prompt
from .protocol import (ERR_LLM_TIMEOUT, ERR_LLM_UNAVAILABLE, ERR_SAFETY_BLOCKED, ERR_TOOL_FAILED, ChatRequest, sse, sse_error)
from .safety import BLOCKED_REPLY, SAFETY
from .session import SESSIONS
from .tools import TOOL_LABELS, TOOL_SCHEMAS, DetectorGetter, ToolRunner

log = logging.getLogger("assistant.agent")

# 越界兜底：模型偶尔不听话，输出里出现「改写后：」这类成品改写的标志词就在 done 里打标，供审计统计与人工复核
_REWRITE_MARKERS = re.compile(r"(改写后|润色后|修改后的版本|可以改为|改成[:：]|替换为[:：])")
_INTENT_RULES = [
    ("appeal", re.compile(r"申诉|复核|误判|不服")),
    ("rewrite_request", re.compile(r"帮我改|改写|润色|换个说法|怎么改|降.{0,3}AI|像人一点")),
    ("explain", re.compile(r"为什么|为何|怎么判|依据|像 ?AI")),
    ("policy", re.compile(r"红线|阈值|能过|过不过|多少算|规定|学校")),
    ("guide", re.compile(r"答辩|材料|怎么准备|规范|引用|格式")),
    ("history", re.compile(r"上次|之前|记录|测了")),
    ("chitchat", re.compile(r"你好|在吗|聊聊|谢谢|你是谁|你是 ?AI")),
]


def classify_intent(text: str) -> str:
    for name, rx in _INTENT_RULES:
        if rx.search(text):
            return name
    return "other"


async def run_chat(req: ChatRequest, detector_getter: DetectorGetter) -> AsyncIterator[str]:
    t0 = time.monotonic()
    intent = classify_intent(req.message)

    # 1) 会话
    conv = await SESSIONS.load_or_create(req.conversationId, req.userId, req.taskId)
    cid = conv["conversationId"]
    yield sse("meta", {"conversationId": cid, "model": CONFIG.llm_model, "intent": intent})

    # 2) 入口内容安全
    guard = await SAFETY.check(req.message, scene="input", user_id=req.userId)
    if not guard.ok:
        await SESSIONS.append(conv, "user", req.message, blocked=True)
        await SESSIONS.append(conv, "assistant", BLOCKED_REPLY, blocked=True)
        await SESSIONS.save(conv)
        yield sse("token", {"delta": BLOCKED_REPLY})
        yield sse("done", {"usage": {}, "model": CONFIG.llm_model, "finishReason": "safety",
                           "elapsedMs": int((time.monotonic() - t0) * 1000), "intent": intent, "safety": "blocked"})
        return

    # 3) 上下文：任务预加载 + 知识库预检索
    runner = ToolRunner(detector_getter, req.userId, conv.get("taskId"))
    task_ctx: Optional[dict[str, Any]] = None
    if conv.get("taskId"):
        res = await runner.run("get_task_detail", "{}")
        if res.ok:
            task_ctx = res.data
    kb_hits = get_kb().search(req.message)
    knowledge_ctx = get_kb().format_context(kb_hits) if kb_hits else ""

    messages: list[dict[str, Any]] = [{"role": "system", "content": build_system_prompt(task_ctx, knowledge_ctx)}]
    messages.extend(SESSIONS.recent_history(conv, CONFIG.history_turns))
    user_text = req.message
    if req.paragraphIdx is not None:
        user_text = f"[用户正在看第 {req.paragraphIdx} 段（idx={req.paragraphIdx}）] {user_text}"
    messages.append({"role": "user", "content": user_text})
    await SESSIONS.append(conv, "user", req.message, taskId=req.taskId, paragraphIdx=req.paragraphIdx)

    # 4) 工具循环
    full_text: list[str] = []
    tool_trace: list[dict[str, Any]] = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0}
    finish_reason = "stop"
    try:
        for round_no in range(CONFIG.max_tool_rounds + 1):
            pending_calls = None
            async for kind, payload in LLM.stream(messages, TOOL_SCHEMAS):
                if kind == "token":
                    full_text.append(payload)
                    yield sse("token", {"delta": payload})
                elif kind == "tool_calls":
                    pending_calls = payload
                elif kind == "finish":
                    finish_reason = payload["reason"]
                    u = payload["usage"]
                    usage_total["prompt_tokens"] += u.prompt_tokens
                    usage_total["completion_tokens"] += u.completion_tokens

            if not pending_calls:
                break
            if round_no >= CONFIG.max_tool_rounds:
                log.warning("工具循环超过 %d 轮，强制结束", CONFIG.max_tool_rounds)
                finish_reason = "tool_rounds_exceeded"
                break

            # 把本轮 assistant 的 tool_calls 原样放回，再逐个执行追加 tool 消息
            messages.append({"role": "assistant", "content": "".join(full_text) or None,
                             "tool_calls": [{"id": c.id, "type": "function",
                                             "function": {"name": c.name, "arguments": c.arguments or "{}"}}
                                            for c in pending_calls]})
            full_text = []   # 工具前的碎片文本不算最终回答
            for call in pending_calls:
                yield sse("tool_call", {"name": call.name, "args": _safe_args(call.arguments),
                                        "label": TOOL_LABELS.get(call.name, "正在处理…")})
                res = await runner.run(call.name, call.arguments or "{}")
                tool_trace.append({"name": call.name, "ok": res.ok, "summary": res.summary})
                yield sse("tool_result", {"name": call.name, "ok": res.ok, "summary": res.summary})
                messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name,
                                 "content": res.to_model_content()})
    except LLMError as e:
        code = ERR_LLM_TIMEOUT if e.code == "LLM_TIMEOUT" else ERR_LLM_UNAVAILABLE
        await SESSIONS.save(conv)
        yield sse_error(code, str(e), retryable=e.retryable)
        return
    except Exception as e:   # 兜底：不让异常把 SSE 连接吞掉
        log.exception("agent 异常")
        await SESSIONS.save(conv)
        yield sse_error(ERR_TOOL_FAILED, f"处理失败：{type(e).__name__}", retryable=True)
        return

    answer = "".join(full_text).strip()
    if not answer:
        answer = "我这边没拿到完整回复，可以换个问法再试一次。"
        yield sse("token", {"delta": answer})

    # 5) 出口内容安全 + 越界标记（流式已发出，只做事后标记供审计）
    out_guard = await SAFETY.check(answer, scene="output", user_id=req.userId)
    boundary_flag = bool(_REWRITE_MARKERS.search(answer)) and intent == "rewrite_request"

    await SESSIONS.append(conv, "assistant", answer, tools=tool_trace or None)
    await SESSIONS.save(conv)
    yield sse("done", {
        "usage": {**usage_total, "total_tokens": usage_total["prompt_tokens"] + usage_total["completion_tokens"]},
        "model": CONFIG.llm_model, "finishReason": finish_reason,
        "elapsedMs": int((time.monotonic() - t0) * 1000),
        "intent": intent, "tools": [t["name"] for t in tool_trace],
        "safety": out_guard.label, "boundaryFlag": boundary_flag,
    })


def _safe_args(raw: str) -> Any:
    import json
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"_raw": raw[:200]}
