"""
内容安全钩子。

默认 provider=none 放行，日志记录。接微信 msgSecCheck 时 provider=wechat：
小程序 access_token 由 Java 侧持有，Python 调 Java 的 /api/v1/assistant/sec-check 代理（铺线路阶段 Java 端点未实现时降级放行并 WARN）。
两个检查点：用户输入进模型前、模型输出返给用户前（流式场景对完整回答做事后检查并在 done 事件标记）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from .config import CONFIG

log = logging.getLogger("assistant.safety")


@dataclass
class SafetyResult:
    ok: bool
    label: str = "pass"        # pass / blocked / degraded
    reason: str = ""


class SafetyChecker:
    async def check(self, text: str, scene: str, user_id: int | None = None) -> SafetyResult:
        if CONFIG.safety_provider == "none":
            return SafetyResult(ok=True)
        if CONFIG.safety_provider == "wechat":
            return await self._wechat(text, scene, user_id)
        log.warning("未知 safety provider %s，放行", CONFIG.safety_provider)
        return SafetyResult(ok=True, label="degraded", reason="unknown provider")

    async def _wechat(self, text: str, scene: str, user_id: int | None) -> SafetyResult:
        url = f"{CONFIG.java_base_url.rstrip('/')}/api/v1/assistant/sec-check"
        try:
            async with httpx.AsyncClient(timeout=CONFIG.java_timeout_s) as c:
                r = await c.post(url, json={"content": text[:2500], "scene": scene, "userId": user_id})
            if r.status_code == 404:
                log.warning("Java 侧 sec-check 代理未实现，内容安全降级放行")
                return SafetyResult(ok=True, label="degraded", reason="proxy missing")
            r.raise_for_status()
            body = r.json()
            data = body.get("data") if isinstance(body, dict) else None
            if data is None:
                return SafetyResult(ok=True, label="degraded", reason="empty proxy body")
            if data.get("pass", True):
                return SafetyResult(ok=True)
            return SafetyResult(ok=False, label="blocked", reason=str(data.get("label") or "risky"))
        except Exception as e:
            log.warning("sec-check 调用失败，降级放行：%s", e)
            return SafetyResult(ok=True, label="degraded", reason=str(e)[:120])


SAFETY = SafetyChecker()

BLOCKED_REPLY = "这个话题我不方便展开。我们聊回论文检测相关的问题吧，比如报告里哪些段落该优先处理？"
