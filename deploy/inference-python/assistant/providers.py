"""
LLM provider 定义（显式适配层）。

为什么需要这一层：`llm.py` 是通用 OpenAI 兼容客户端，改 base_url + key + model 确实就能换家，
但每家有三类**不一致的地方**光靠 .env 盖不住：

1. **模型名会退役**。DeepSeek 的 legacy 名（deepseek-chat / -reasoner）已被退役，
   当前是 deepseek-flash / deepseek-v4-pro —— 名字写死在 .env 里，退役后没人会发现，
   只会得到 404 model not found。
2. **思考模式（thinking）是 DeepSeek 独有的开关**，且有两个硬约束：
   - 思考模式**忽略 temperature**（不报错，静默失效）；
   - 请求带 `tools` 时，**`reasoning_content` 必须原样回传**，否则 API 直接 400。
3. **key 的环境变量名各家不同**（DEEPSEEK_API_KEY vs DASHSCOPE_API_KEY），
   但语义都是「该 provider 的凭据」。

所以把「每家的默认 base_url / 模型 / 取舍」收敛成数据（ProviderProfile），
llm.py 只负责按 profile 发请求。新增一家 = 加一个 profile + 在 PROVIDERS 注册。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ProviderProfile:
    """一家的接入画像。全部字段都可被环境变量覆盖。"""

    name: str
    label: str
    base_url: str
    default_model: str
    # 依次尝试的凭据环境变量（第一个非空的胜出）
    api_key_envs: tuple[str, ...] = ()
    # 该 provider 支持的模型白名单；非空时用于启动期校验，挡住已退役的模型名
    known_models: tuple[str, ...] = ()
    # 是否支持 OpenAI 的 stream_options={"include_usage": true}
    supports_stream_usage: bool = True
    # 是否支持 thinking / reasoning_effort（仅 DeepSeek 系）
    supports_thinking: bool = False
    # 是否支持 tools（工具调用）
    supports_tools: bool = True
    # 文档链接，排障时直接看
    docs_url: str = ""
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

DEEPSEEK = ProviderProfile(
    name="deepseek",
    label="DeepSeek 开放平台",
    base_url="https://api.deepseek.com",
    # 注意：deepseek-chat / deepseek-reasoner 已退役；当前为 flash / v4-pro
    default_model="deepseek-flash",
    api_key_envs=("ASSISTANT_LLM_API_KEY", "DEEPSEEK_API_KEY"),
    known_models=("deepseek-flash", "deepseek-v4-pro"),
    supports_thinking=True,
    supports_tools=True,
    docs_url="https://api-docs.deepseek.com/",
    notes="思考模式默认开启且忽略 temperature；带 tools 时必须回传 reasoning_content",
)

DASHSCOPE = ProviderProfile(
    name="dashscope",
    label="阿里云百炼（DashScope OpenAI 兼容）",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    default_model="qwen-plus",
    api_key_envs=("ASSISTANT_LLM_API_KEY", "DASHSCOPE_API_KEY"),
    known_models=("qwen-plus", "qwen-max", "qwen-turbo", "qwen2.5-7b-instruct"),
    supports_thinking=False,
    supports_tools=True,
    docs_url="https://help.aliyun.com/zh/model-studio/",
    notes="OpenAI 兼容模式；不支持 thinking 参数",
)

OPENAI = ProviderProfile(
    name="openai",
    label="OpenAI",
    base_url="https://api.openai.com/v1",
    default_model="gpt-4o-mini",
    api_key_envs=("ASSISTANT_LLM_API_KEY", "OPENAI_API_KEY"),
    known_models=(),
    supports_thinking=False,
    supports_tools=True,
    docs_url="https://platform.openai.com/docs/api-reference",
    notes="通用兜底；也适合指向任意自建 OpenAI 兼容端点",
)

# local / vLLM 之类自建端点：base_url 必须由环境变量给，否则无意义
CUSTOM = ProviderProfile(
    name="custom",
    label="自定义 OpenAI 兼容端点",
    base_url="",   # 必须配 ASSISTANT_LLM_BASE_URL
    default_model="",
    api_key_envs=("ASSISTANT_LLM_API_KEY",),
    known_models=(),
    supports_thinking=False,
    supports_tools=True,
    notes="自建 vLLM / Ollama / one-api 等，必须同时配 ASSISTANT_LLM_BASE_URL 与 ASSISTANT_LLM_MODEL",
)

PROVIDERS: dict[str, ProviderProfile] = {
    p.name: p for p in (DEEPSEEK, DASHSCOPE, OPENAI, CUSTOM)
}

DEFAULT_PROVIDER = DEEPSEEK.name


def get_profile(name: Optional[str]) -> ProviderProfile:
    """按名取 profile；未知名字回落到 custom（并保留用户给的 base_url）。"""
    if not name:
        return PROVIDERS[DEFAULT_PROVIDER]
    return PROVIDERS.get(name.strip().lower(), CUSTOM)


def pick_api_key(profile: ProviderProfile, explicit: str = "") -> str:
    """显式值优先，其次按 profile 声明的顺序找环境变量。"""
    import os

    if explicit:
        return explicit
    for env_name in profile.api_key_envs:
        v = (os.getenv(env_name) or "").strip()
        if v:
            return v
    return ""


def validate_model(profile: ProviderProfile, model: str) -> Optional[str]:
    """返回告警文案（None = 没问题）。挡已退役模型名这类静默 404。"""
    if not model:
        return f"provider={profile.name} 未指定模型名"
    if profile.known_models and model not in profile.known_models:
        return (f"模型 '{model}' 不在 provider={profile.name} 的已知清单 "
                f"{list(profile.known_models)} 内；若是新模型可忽略，"
                f"若已退役会得到 404 model not found")
    return None
