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

# ---------------------------------------------------------------------------
# 边界体系：意图分类（硬拦截）+ 输出后多类型标记（软标记）
#
# 硬拦截：ghostwrite / bypass / appeal_fabricate 命中即拒答，不进 LLM（省 token、保证不越界）。
# 软标记：输出后扫描 BOUNDARY_RULES，把类型写进 done.boundaryType 供审计与人工抽检（流已发出，只能事后标）。
# ---------------------------------------------------------------------------

HARD_BLOCK_INTENTS = {"ghostwrite", "bypass", "appeal_fabricate"}

# 拒答模板：语气对齐「学长学姐」人设——先讲清为什么，再给正确方向
REFUSALS = {
    "ghostwrite": "这个我帮不了。整段或整篇代写既不符合学术规范，写出来也会留下新的痕迹，反而更容易被识破。不过我可以告诉你这类内容一般该怎么组织、用什么结构，你拿自己课题里的具体材料去写。",
    "bypass": "「降 AI 率、让检测查不出来」这个方向我不能帮，绕过检测本身也违反学术诚信。如果你确定是误判——风险最高的几段确实是自己写的——正确的路是申诉加人工复核；如果确实参考了 AI 输出，建议自己重写相关部分。需要的话我可以帮你看看报告里哪几段最该优先处理。",
    "appeal_fabricate": "申诉理由得是真实情况，我不能帮你编，编造材料在复核时会被识破、性质也更严重。你先想清楚哪几段确实是自己写的、有哪些过程证据（草稿、笔记、和导师的沟通记录），把真实理由写出来，我可以帮你确认后再提交。",
}

# 输出后越界标记（软标记）：命中即把类型写进 done.boundaryType
BOUNDARY_RULES = [
    ("rewrite", re.compile(r"(改写后|润色后|修改后的版本|可以改为|改成[:：]|替换为[:：])")),
    ("bypass", re.compile(r"(降 ?AI|洗稿|绕过|躲过检测|查不出|不被检测)")),
    ("ghostwrite", re.compile(r"(下面是我?帮你写的|以下为代写|这是写好的)")),
]

# 意图分类：硬边界放最前（否则「编申诉理由」会被 appeal 先命中）
_INTENT_RULES = [
    ("ghostwrite", re.compile(r"帮我写|替我写|写一段|写一篇|续写|代写|生成.{0,6}(引言|摘要|正文|结论|致谢|文献综述)")),
    ("bypass", re.compile(r"降.{0,3}AI|去 ?AI ?味|洗稿|绕过检测|躲过检测|不被查|查不出|降低.{0,4}(检测|风险).{0,6}(率|概率)")),
    ("appeal_fabricate", re.compile(r"编.{0,4}(申诉|理由)|伪造.{0,4}(理由|过程|材料)|(申诉理由|理由).{0,6}(帮我|替我)")),
    ("appeal", re.compile(r"申诉|复核|误判|不服")),
    ("rewrite_request", re.compile(r"帮我改|改写|润色|换个说法|怎么改|像人一点")),
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


def detect_boundary(text: str) -> Optional[str]:
    """输出后扫描，返回第一个命中的越界类型（None = 无）。"""
    for btype, rx in BOUNDARY_RULES:
        if rx.search(text):
            return btype
    return None


async def run_chat(req: ChatRequest, detector_getter: DetectorGetter) -> AsyncIterator[str]:
    t0 = time.monotonic()
    intent = classify_intent(req.message)

    # 1) 会话
    conv = await SESSIONS.load_or_create(req.conversationId, req.userId, req.taskId)
    cid = conv["conversationId"]
    yield sse("meta", {"conversationId": cid, "model": CONFIG.resolved_model, "intent": intent, "provider": CONFIG.provider_name})

    # 2) 入口内容安全
    guard = await SAFETY.check(req.message, scene="input", user_id=req.userId)
    if not guard.ok:
        await SESSIONS.append(conv, "user", req.message, blocked=True)
        await SESSIONS.append(conv, "assistant", BLOCKED_REPLY, blocked=True)
        await SESSIONS.save(conv)
        yield sse("token", {"delta": BLOCKED_REPLY})
        yield sse("done", {"usage": {}, "model": CONFIG.resolved_model, "finishReason": "safety",
                           "elapsedMs": int((time.monotonic() - t0) * 1000), "intent": intent, "safety": "blocked"})
        return

    # 2.5) 学术边界硬拦截：代写 / 绕过检测 / 编申诉理由 —— 不进 LLM，直接拒答
    if intent in HARD_BLOCK_INTENTS:
        reply = REFUSALS[intent]
        await SESSIONS.append(conv, "user", req.message)
        await SESSIONS.append(conv, "assistant", reply)
        await SESSIONS.save(conv)
        yield sse("token", {"delta": reply})
        yield sse("done", {"usage": {}, "model": CONFIG.resolved_model, "finishReason": "boundary",
                           "elapsedMs": int((time.monotonic() - t0) * 1000), "intent": intent,
                           "boundaryType": intent, "boundaryFlag": True, "safety": "pass"})
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
    kb_meta = _kb_meta(kb_hits)

    messages: list[dict[str, Any]] = [{"role": "system", "content": build_system_prompt(task_ctx, knowledge_ctx)}]
    messages.extend(SESSIONS.recent_history(conv, CONFIG.history_turns))
    user_text = req.message
    if req.paragraphIdx is not None:
        user_text = f"[用户正在看第 {req.paragraphIdx} 段（idx={req.paragraphIdx}）] {user_text}"
    messages.append({"role": "user", "content": user_text})
    await SESSIONS.append(conv, "user", req.message, taskId=req.taskId, paragraphIdx=req.paragraphIdx)

    # 4) 工具循环
    full_text: list[str] = []
    reasoning_text: list[str] = []   # DeepSeek thinking：带 tools 时必须回传，否则 400
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
                elif kind == "reasoning":
                    # 思考内容不推给用户（只体现为等待时长），但必须留存以便回传
                    reasoning_text.append(payload)
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
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": "".join(full_text) or None,
                "tool_calls": [{"id": c.id, "type": "function",
                                "function": {"name": c.name, "arguments": c.arguments or "{}"}}
                               for c in pending_calls],
            }
            # 思考模式下必须带上 reasoning_content，否则下一轮请求被拒（400）
            if reasoning_text:
                assistant_msg["reasoning_content"] = "".join(reasoning_text)
            messages.append(assistant_msg)
            full_text = []   # 工具前的碎片文本不算最终回答
            for call in pending_calls:
                yield sse("tool_call", {"name": call.name, "args": _safe_args(call.arguments),
                                        "label": TOOL_LABELS.get(call.name, "正在处理…")})
                res = await runner.run(call.name, call.arguments or "{}")
                tool_trace.append({"name": call.name, "ok": res.ok, "summary": res.summary})
                yield sse("tool_result", {"name": call.name, "ok": res.ok, "summary": res.summary,
                                          "card": _card_payload(call.name, res)})
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
    boundary_type = detect_boundary(answer)

    await SESSIONS.append(conv, "assistant", answer, tools=tool_trace or None)
    await SESSIONS.save(conv)
    yield sse("done", {
        "usage": {**usage_total, "total_tokens": usage_total["prompt_tokens"] + usage_total["completion_tokens"]},
        "model": CONFIG.resolved_model, "finishReason": finish_reason,
        "elapsedMs": int((time.monotonic() - t0) * 1000),
        "intent": intent, "tools": [t["name"] for t in tool_trace],
        "safety": out_guard.label,
        "boundaryFlag": boundary_type is not None,   # bool，兼容 Java 侧 assistant_log.boundary_flag
        "boundaryType": boundary_type,               # 类型：rewrite / bypass / ghostwrite / null
        **kb_meta,                                   # kbHits / kbTopScore / kbTopRef：知识缺口信号（增长闭环 §1.1）
    })


# 结构化分析卡（product-feature-plan §2.1）：这三种工具的 data 原样给前端渲染，助手文字作「翻译」
CARD_TOOLS = {"explain_paragraph", "get_task_detail", "detect_text", "compare_revision"}


def _card_payload(tool: str, res: Any) -> Optional[dict[str, Any]]:
    if tool not in CARD_TOOLS or not res.ok or not isinstance(res.data, dict):
        return None
    return res.data


def _kb_meta(hits: list) -> dict[str, Any]:
    """知识检索元数据。search 走倒排索引几乎总会返回 top-k，缺口要看 top-1 分数而不是是否为空。"""
    if not hits:
        return {"kbHits": 0, "kbTopScore": None, "kbTopRef": None}
    chunk, score = hits[0]
    return {"kbHits": len(hits), "kbTopScore": round(float(score), 3), "kbTopRef": chunk.ref[:160]}


def _safe_args(raw: str) -> Any:
    import json
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"_raw": raw[:200]}
