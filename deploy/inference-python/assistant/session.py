"""
会话存储：Redis（redis.asyncio）优先，缺失或连不上退化为进程内字典。

键：
    assistant:conv:{cid}              JSON {conversationId, userId, taskId, title, createdAt, updatedAt, messages[]}
    assistant:user:{uid}:convs        zset  score=updatedAt member=cid

messages 只存 role=user/assistant 的可见消息 + 工具调用摘要（不存工具的大对象返回），
每会话最多 session_max_turns 轮，超出丢最早的。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional

from .config import CONFIG

log = logging.getLogger("assistant.session")


def new_conversation_id() -> str:
    return uuid.uuid4().hex[:24]


class _MemoryStore:
    def __init__(self) -> None:
        self.conv: dict[str, dict[str, Any]] = {}
        self.user: dict[str, dict[str, float]] = {}

    async def get(self, cid: str) -> Optional[dict[str, Any]]:
        return self.conv.get(cid)

    async def put(self, conv: dict[str, Any]) -> None:
        self.conv[conv["conversationId"]] = conv
        uid = str(conv.get("userId") or "anon")
        self.user.setdefault(uid, {})[conv["conversationId"]] = conv["updatedAt"]

    async def list_for_user(self, uid: str, limit: int) -> list[dict[str, Any]]:
        cids = sorted(self.user.get(uid, {}).items(), key=lambda kv: -kv[1])[:limit]
        return [self.conv[c] for c, _ in cids if c in self.conv]

    async def delete(self, cid: str) -> None:
        conv = self.conv.pop(cid, None)
        if conv:
            self.user.get(str(conv.get("userId") or "anon"), {}).pop(cid, None)


class _RedisStore:
    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis  # type: ignore
        self.r = aioredis.from_url(url, decode_responses=True)
        self.ttl = CONFIG.session_ttl_days * 86400

    @staticmethod
    def _k(cid: str) -> str:
        return f"assistant:conv:{cid}"

    @staticmethod
    def _u(uid: str) -> str:
        return f"assistant:user:{uid}:convs"

    async def get(self, cid: str) -> Optional[dict[str, Any]]:
        raw = await self.r.get(self._k(cid))
        return json.loads(raw) if raw else None

    async def put(self, conv: dict[str, Any]) -> None:
        cid = conv["conversationId"]
        uid = str(conv.get("userId") or "anon")
        pipe = self.r.pipeline()
        pipe.set(self._k(cid), json.dumps(conv, ensure_ascii=False), ex=self.ttl)
        pipe.zadd(self._u(uid), {cid: conv["updatedAt"]})
        pipe.expire(self._u(uid), self.ttl)
        await pipe.execute()

    async def list_for_user(self, uid: str, limit: int) -> list[dict[str, Any]]:
        cids = await self.r.zrevrange(self._u(uid), 0, limit - 1)
        out = []
        for cid in cids:
            c = await self.get(cid)
            if c:
                out.append(c)
        return out

    async def delete(self, cid: str) -> None:
        conv = await self.get(cid)
        pipe = self.r.pipeline()
        pipe.delete(self._k(cid))
        if conv:
            pipe.zrem(self._u(str(conv.get("userId") or "anon")), cid)
        await pipe.execute()


class _MysqlStore:
    """MySQL 后端：会话持久化（保留 session_ttl_days 天）。pymysql 同步，用 asyncio.to_thread 丢线程池避免阻塞事件循环。"""

    def __init__(self, host: str, port: int, user: str, password: str, db: str) -> None:
        self._cfg = dict(host=host, port=port, user=user, password=password,
                         database=db, charset="utf8mb4", autocommit=True)

    def _conn(self):
        import pymysql
        return pymysql.connect(**self._cfg)

    async def ping(self) -> None:
        def _p() -> None:
            conn = self._conn()
            try:
                conn.ping()
            finally:
                conn.close()
        await asyncio.to_thread(_p)

    async def get(self, cid: str) -> Optional[dict[str, Any]]:
        return await asyncio.to_thread(self._get_sync, cid)

    def _get_sync(self, cid: str) -> Optional[dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT messages_json FROM assistant_conversation WHERE conversation_id=%s", (cid,))
                row = cur.fetchone()
            return json.loads(row[0]) if row else None
        finally:
            conn.close()

    async def put(self, conv: dict[str, Any]) -> None:
        await asyncio.to_thread(self._put_sync, conv)

    def _put_sync(self, conv: dict[str, Any]) -> None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO assistant_conversation (conversation_id, user_id, task_id, title, messages_json) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE user_id=VALUES(user_id), task_id=VALUES(task_id), "
                    "title=VALUES(title), messages_json=VALUES(messages_json)",
                    (conv["conversationId"], conv.get("userId"), conv.get("taskId"),
                     conv.get("title") or "", json.dumps(conv, ensure_ascii=False)),
                )
        finally:
            conn.close()

    async def list_for_user(self, uid: str, limit: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._list_sync, uid, limit)

    def _list_sync(self, uid: str, limit: int) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT messages_json FROM assistant_conversation "
                    "WHERE user_id=%s AND updated_at >= NOW() - INTERVAL %s DAY "
                    "ORDER BY updated_at DESC LIMIT %s",
                    (uid, CONFIG.session_ttl_days, limit),
                )
                rows = cur.fetchall()
            return [json.loads(r[0]) for r in rows]
        finally:
            conn.close()

    async def delete(self, cid: str) -> None:
        await asyncio.to_thread(self._delete_sync, cid)

    def _delete_sync(self, cid: str) -> None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM assistant_conversation WHERE conversation_id=%s", (cid,))
        finally:
            conn.close()


class SessionStore:
    def __init__(self) -> None:
        self.backend: Any = None
        self.kind = "memory"

    async def _ensure(self):
        if self.backend is not None:
            return self.backend
        # 1) Redis 优先
        if CONFIG.redis_url:
            try:
                store = _RedisStore(CONFIG.redis_url)
                await store.r.ping()
                self.backend, self.kind = store, "redis"
                log.info("会话存储：redis %s", CONFIG.redis_url.split("@")[-1])
                return self.backend
            except Exception as e:
                log.warning("Redis 不可用（%s）", e)
        # 2) MySQL 次之（复用知识库 DB 配置，会话持久化保留 N 天）
        if CONFIG.kb_db_enabled:
            try:
                store = _MysqlStore(CONFIG.kb_db_host, CONFIG.kb_db_port,
                                    CONFIG.kb_db_user, CONFIG.kb_db_password, CONFIG.kb_db_name)
                await store.ping()
                self.backend, self.kind = store, "mysql"
                log.info("会话存储：mysql %s/%s（保留 %d 天）",
                         CONFIG.kb_db_host, CONFIG.kb_db_name, CONFIG.session_ttl_days)
                return self.backend
            except Exception as e:
                log.warning("MySQL 不可用（%s），会话退化为进程内内存", e)
        # 3) 内存兜底（重启即丢）
        self.backend, self.kind = _MemoryStore(), "memory"
        return self.backend

    async def load_or_create(self, cid: Optional[str], user_id: Optional[int], task_id: Optional[int]) -> dict[str, Any]:
        b = await self._ensure()
        conv = await b.get(cid) if cid else None
        now = time.time()
        if conv is None:
            conv = {
                "conversationId": cid or new_conversation_id(),
                "userId": user_id, "taskId": task_id, "title": "",
                "createdAt": now, "updatedAt": now, "messages": [],
            }
        else:
            # 同一会话里后续带了 taskId，就把上下文切到新任务
            if task_id and conv.get("taskId") != task_id:
                conv["taskId"] = task_id
        return conv

    async def append(self, conv: dict[str, Any], role: str, content: str, **extra: Any) -> None:
        msg = {"role": role, "content": content, "ts": time.time()}
        msg.update({k: v for k, v in extra.items() if v is not None})
        conv["messages"].append(msg)
        # 只保留最近 N 轮（user+assistant 算一轮）
        limit = CONFIG.session_max_turns * 2
        if len(conv["messages"]) > limit:
            conv["messages"] = conv["messages"][-limit:]
        if not conv.get("title") and role == "user":
            conv["title"] = content.strip().replace("\n", " ")[:30]
        conv["updatedAt"] = time.time()

    async def save(self, conv: dict[str, Any]) -> None:
        b = await self._ensure()
        await b.put(conv)

    async def list_for_user(self, user_id: Optional[int], limit: int = 20) -> list[dict[str, Any]]:
        b = await self._ensure()
        return await b.list_for_user(str(user_id or "anon"), limit)

    async def get(self, cid: str) -> Optional[dict[str, Any]]:
        b = await self._ensure()
        return await b.get(cid)

    async def delete(self, cid: str) -> None:
        b = await self._ensure()
        await b.delete(cid)

    def recent_history(self, conv: dict[str, Any], turns: int) -> list[dict[str, str]]:
        """喂给模型的历史：只取 user/assistant 文本，最近 turns 轮。"""
        msgs = [m for m in conv["messages"] if m["role"] in ("user", "assistant") and m.get("content")]
        return [{"role": m["role"], "content": m["content"]} for m in msgs[-turns * 2:]]


SESSIONS = SessionStore()
