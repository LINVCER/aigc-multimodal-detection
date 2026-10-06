r"""
助手 LLM provider 适配层自检。

用法（在 deploy/inference-python 下）：
    .\.venv\Scripts\python.exe smoke_llm.py            # 离线参数校验
    .\.venv\Scripts\python.exe smoke_llm.py --thinking # 按思考模式再校验一遍
    .\.venv\Scripts\python.exe smoke_llm.py --live     # 真发一次请求（需 API key）

不需要 API key 也能跑：默认只做离线参数校验（provider 解析 / 请求体是否符合各家文档）。
退出码：0 = 全部通过；1 = 有失败项。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FAILURES: list[str] = []


def _load_dotenv() -> None:
    """加载同目录 .env 到进程环境变量（setdefault 不覆盖已有值），等效 uvicorn --env-file .env。"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def offline_checks(thinking_override: bool | None) -> None:
    from assistant.config import CONFIG
    from assistant.llm import build_request_kwargs

    thinking_active = CONFIG.thinking_active if thinking_override is None else (
        thinking_override and CONFIG.profile.supports_thinking)

    print("=" * 68)
    print("离线参数校验")
    print("=" * 68)
    print(f"provider       = {CONFIG.provider_name} ({CONFIG.profile.label})")
    print(f"resolved model = {CONFIG.resolved_model}")
    print(f"resolved url   = {CONFIG.resolved_base_url}")
    print(f"thinking       = {thinking_active}")
    print(f"key configured = {bool(CONFIG.resolved_api_key)}")
    for w in CONFIG.config_warnings():
        print(f"  ! {w}")
    print()

    kw = build_request_kwargs([{"role": "user", "content": "hi"}], None, thinking_override)

    check("请求含 model", bool(kw.get("model")), str(kw.get("model", "")))
    check("请求含 stream=True", kw.get("stream") is True)
    check("请求含 messages", isinstance(kw.get("messages"), list))
    check("请求含 max_tokens", "max_tokens" in kw, str(kw.get("max_tokens")))

    if thinking_active:
        check("思考模式: 不发送 temperature（官方称忽略）", "temperature" not in kw)
        check("思考模式: 发送 reasoning_effort", "reasoning_effort" in kw, str(kw.get("reasoning_effort")))
        check("思考模式: extra_body.thinking.type=enabled",
              (kw.get("extra_body") or {}).get("thinking", {}).get("type") == "enabled")
    else:
        check("非思考模式: 发送 temperature", "temperature" in kw, str(kw.get("temperature")))
        if CONFIG.profile.supports_thinking:
            check("非思考模式: 显式 thinking.type=disabled（DeepSeek 默认开着）",
                  (kw.get("extra_body") or {}).get("thinking", {}).get("type") == "disabled")
        else:
            check("非该家能力: 不发 extra_body.thinking", "thinking" not in (kw.get("extra_body") or {}))

    if CONFIG.profile.supports_stream_usage:
        check("请求含 stream_options.include_usage",
              (kw.get("stream_options") or {}).get("include_usage") is True)

    tools = [{"type": "function",
              "function": {"name": "noop", "description": "noop",
                           "parameters": {"type": "object", "properties": {}}}}]
    kw_t = build_request_kwargs([{"role": "user", "content": "hi"}], tools, thinking_override)
    if CONFIG.profile.supports_tools:
        check("带 tools: 透传 tools", kw_t.get("tools") == tools)
        check("带 tools: tool_choice=auto", kw_t.get("tool_choice") == "auto")

    from assistant.providers import get_profile, validate_model
    warn = validate_model(get_profile("deepseek"), "deepseek-chat")
    check("退役模型名会被拦下告警", warn is not None, (warn or "")[:70])


async def live_check(thinking_override: bool | None) -> None:
    from assistant.config import CONFIG
    from assistant.llm import LLM, LLMError
    from assistant.tools import TOOL_SCHEMAS

    print()
    print("=" * 68)
    print("在线校验（--live）")
    print("=" * 68)
    if not CONFIG.resolved_api_key:
        check("在线校验需要 API key", False, "未配置")
        return

    print(f"向 {CONFIG.resolved_base_url} 请求 model={CONFIG.resolved_model} …")
    text_parts, reasoning_parts = [], []
    tool_calls = None
    finish = None
    try:
        async for kind, payload in LLM.stream(
            [{"role": "user", "content": "用一句话说明什么是 AIGC 检测。不要调用工具。"}],
            TOOL_SCHEMAS,
            thinking_override,
        ):
            if kind == "token":
                text_parts.append(payload)
            elif kind == "reasoning":
                reasoning_parts.append(payload)
            elif kind == "tool_calls":
                tool_calls = payload
            elif kind == "finish":
                finish = payload
    except LLMError as e:
        check("在线请求成功", False, f"{e.code}: {e}")
        return

    answer = "".join(text_parts)
    check("在线请求成功", True)
    check("拿到正文", bool(answer.strip()), f"{len(answer)} 字")
    if thinking_override is True and CONFIG.profile.supports_thinking:
        check("思考模式返回了 reasoning_content", bool(reasoning_parts), f"{len(''.join(reasoning_parts))} 字")
    print(f"  finish_reason = {(finish or {}).get('reason')}")
    usage = (finish or {}).get("usage")
    if usage is not None:
        print(f"  usage = {usage.as_dict()}")
    if tool_calls:
        print(f"  （模型主动要求调工具：{[c.name for c in tool_calls]}，本次未执行）")
    print()
    print("模型回答预览：")
    print("  " + answer.strip().replace("\n", "\n  ")[:400])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="真发一次请求（需要 API key）")
    ap.add_argument("--thinking", action="store_true", help="按思考模式校验")
    args = ap.parse_args()

    _load_dotenv()

    override = True if args.thinking else None
    offline_checks(override)
    if args.live:
        asyncio.run(live_check(override))

    print()
    print("=" * 68)
    if FAILURES:
        print(f"结果：{len(FAILURES)} 项失败 -> {FAILURES}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
