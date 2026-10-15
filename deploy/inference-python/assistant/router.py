"""
FastAPI 路由。main.py 调 mount(app, detector_getter) 挂载。

    POST   /assistant/chat                     SSE
    GET    /assistant/conversations?userId=    会话列表
    GET    /assistant/conversations/{cid}      会话详情
    DELETE /assistant/conversations/{cid}
    GET    /assistant/quick-prompts?taskId=    快捷问题
    GET    /assistant/health
    POST   /assistant/knowledge/reload         运营改完 markdown 热加载
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import run_chat
from .config import CONFIG
from .knowledge import get_kb
from .llm import LLM
from .prompts import (DRAFT_REPLY_SYSTEM, QUICK_PROMPTS_GENERIC, QUICK_PROMPTS_WITH_TASK,
                      WELCOME_GENERIC, WELCOME_WITH_TASK)
from .protocol import ERR_DISABLED, ChatRequest, ConversationDetail, ConversationSummary, sse_error
from .session import SESSIONS
from .tools import DetectorGetter

log = logging.getLogger("assistant.router")

router = APIRouter(prefix="/assistant", tags=["assistant"])
_detector_getter: DetectorGetter = lambda: None

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",   # Nginx 反代时关闭缓冲，否则 token 攒成一坨才下发
    "Connection": "keep-alive",
}


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    if not CONFIG.enabled:
        async def _disabled():
            yield sse_error(ERR_DISABLED, "助手暂未开放")
        return StreamingResponse(_disabled(), media_type="text/event-stream", headers=_SSE_HEADERS)
    return StreamingResponse(run_chat(req, _detector_getter), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(userId: Optional[int] = Query(None), limit: int = Query(20, ge=1, le=50)):
    convs = await SESSIONS.list_for_user(userId, limit)
    return [ConversationSummary(conversationId=c["conversationId"], title=c.get("title") or "新对话",
                                taskId=c.get("taskId"), updatedAt=c["updatedAt"],
                                turns=sum(1 for m in c["messages"] if m["role"] == "user")) for c in convs]


@router.get("/conversations/{cid}", response_model=ConversationDetail)
async def get_conversation(cid: str):
    conv = await SESSIONS.get(cid)
    if not conv:
        raise HTTPException(404, "会话不存在")
    return ConversationDetail(conversationId=cid, taskId=conv.get("taskId"),
                              messages=[{k: v for k, v in m.items() if k != "tools"} for m in conv["messages"]])


@router.delete("/conversations/{cid}")
async def delete_conversation(cid: str):
    await SESSIONS.delete(cid)
    return {"ok": True}


@router.get("/quick-prompts")
async def quick_prompts(taskId: Optional[int] = Query(None)):
    if taskId:
        return {"welcome": WELCOME_WITH_TASK, "prompts": QUICK_PROMPTS_WITH_TASK}
    return {"welcome": WELCOME_GENERIC.format(product=CONFIG.product_name), "prompts": QUICK_PROMPTS_GENERIC}


@router.get("/health")
async def health():
    kb = get_kb()
    await SESSIONS._ensure()
    return {
        "enabled": CONFIG.enabled,
        # provider 明细（含 model / baseUrl / 是否配了 key / 启动期告警），已脱敏不含 key 本身
        **CONFIG.public_dict(),
        "sessionBackend": SESSIONS.kind,
        "knowledgeSource": kb.source,
        "knowledgeChunks": len(kb.chunks),
        "knowledgeDocs": sorted(set(c.doc for c in kb.chunks)),
        "safetyProvider": CONFIG.safety_provider,
        "detectorLoaded": _detector_getter() is not None,
        "javaBaseUrl": CONFIG.java_base_url,
    }


@router.post("/knowledge/reload")
async def reload_knowledge():
    get_kb().reload()
    return {"ok": True, "chunks": len(get_kb().chunks)}


# ---- 反馈 AI 草稿（Java FeedbackController 异步调用；草稿经人工审核后才发给用户） ----

class DraftReplyRequest(BaseModel):
    category: str = "suggestion"          # bug / suggestion / appeal
    content: str
    taskId: Optional[int] = None


@router.post("/draft-reply")
async def draft_reply(req: DraftReplyRequest):
    """生成反馈回复草稿。LLM 不可用时 reply 返回 null，Java 侧静默跳过（不影响反馈提交）。"""
    if not CONFIG.enabled:
        return {"code": 200, "msg": "ok", "data": {"reply": None, "reason": "disabled"}}

    system = DRAFT_REPLY_SYSTEM.format(product=CONFIG.product_name)
    try:
        hits = get_kb().search(req.content, top_k=3)
        kb_ctx = get_kb().format_context(hits)
        if kb_ctx:
            system += "\n\n## 平台资料（优先依据，引用时自然带一句来源）\n" + kb_ctx
    except Exception as e:   # 知识库缺失不影响草稿，只是少了依据
        log.info("draft-reply knowledge skipped: %s", e)

    user = (f"反馈分类：{req.category}\n关联报告编号：{req.taskId or '无'}\n"
            f"用户反馈原文：\n{req.content}\n\n请起草给这位用户的回复。")
    try:
        reply = await LLM.complete_once(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=300)
    except Exception as e:
        log.warning("draft-reply llm failed category=%s: %s", req.category, e)
        return {"code": 200, "msg": "ok", "data": {"reply": None, "reason": "llm_unavailable"}}
    return {"code": 200, "msg": "ok", "data": {"reply": reply or None}}


def mount(app: FastAPI, detector_getter: DetectorGetter) -> None:
    global _detector_getter
    _detector_getter = detector_getter
    app.include_router(router, prefix="/api/v1")
    log.info("assistant 已挂载 /api/v1/assistant/* · provider=%s · model=%s · key=%s · thinking=%s",
             CONFIG.provider_name, CONFIG.resolved_model,
             "yes" if CONFIG.resolved_api_key else "NO", CONFIG.thinking_active)
    # 启动期自检：缺 key / model 名可疑 / provider 不支持 thinking 等，一次说清
    for w in CONFIG.config_warnings():
        log.warning("assistant 配置告警：%s", w)
