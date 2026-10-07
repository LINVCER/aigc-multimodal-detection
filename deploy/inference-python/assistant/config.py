"""助手配置：全部走环境变量，带可运行的默认值。

provider 解析顺序（见 providers.py）：
    ASSISTANT_LLM_PROVIDER 显式指定 > 由已配置的 API key 推断 > DEFAULT_PROVIDER(deepseek)

显式指定优先，是为了避免「机器上恰好有一个 DASHSCOPE_API_KEY」就悄悄换了家。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from .providers import (DEFAULT_PROVIDER, PROVIDERS, ProviderProfile, get_profile,
                        pick_api_key, validate_model)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _resolve_provider_name() -> str:
    """显式 > 推断 > 默认。"""
    explicit = _env("ASSISTANT_LLM_PROVIDER").lower()
    if explicit:
        return explicit
    # 没显式指定时，按各家专属 key 是否存在来推断（ASSISTANT_LLM_API_KEY 是通用的，不作为线索）
    for name, profile in PROVIDERS.items():
        for env_name in profile.api_key_envs:
            if env_name == "ASSISTANT_LLM_API_KEY":
                continue
            if _env(env_name):
                return name
    return DEFAULT_PROVIDER


@dataclass(frozen=True)
class AssistantConfig:
    enabled: bool = _env("ASSISTANT_ENABLED", "true").lower() in ("1", "true", "yes")

    # ---- LLM provider ----
    provider_name: str = _resolve_provider_name()
    llm_base_url: str = ""          # 空 → 用 profile 默认
    llm_api_key: str = ""           # 空 → 按 profile 的 env 列表找
    llm_model: str = ""             # 空 → 用 profile 默认
    llm_temperature: float = float(_env("ASSISTANT_LLM_TEMPERATURE", "0.6"))
    llm_max_tokens: int = _env_int("ASSISTANT_LLM_MAX_TOKENS", 800)
    # 首 token 超时：慢模型首轮 3 分钟才回，超过 15s 就该报错让用户重试
    llm_first_token_timeout_s: float = float(_env("ASSISTANT_LLM_FIRST_TOKEN_TIMEOUT", "15"))
    llm_total_timeout_s: float = float(_env("ASSISTANT_LLM_TOTAL_TIMEOUT", "90"))
    llm_max_retries: int = _env_int("ASSISTANT_LLM_MAX_RETRIES", 2)

    # ---- 思考模式（仅 DeepSeek 系）----
    # 默认关：M1）思考模式忽略 temperature，M2）带 tools 时必须回传 reasoning_content
    # （见 docs/guides/thinking_mode，「若未正确回传 API 会返回 400」）。关掉两者都绕开了。
    thinking_enabled: bool = _env_bool("ASSISTANT_LLM_THINKING", False)
    reasoning_effort: str = _env("ASSISTANT_LLM_REASONING_EFFORT", "high")   # low|high|max

    # 工具循环与上下文预算
    max_tool_rounds: int = _env_int("ASSISTANT_MAX_TOOL_ROUNDS", 4)
    history_turns: int = _env_int("ASSISTANT_HISTORY_TURNS", 10)
    context_token_budget: int = _env_int("ASSISTANT_CONTEXT_TOKEN_BUDGET", 6000)
    knowledge_top_k: int = _env_int("ASSISTANT_KNOWLEDGE_TOP_K", 3)

    # 工具回调 Java 业务接口（取报告 / 任务列表 / 阈值 / 申诉）
    java_base_url: str = _env("ASSISTANT_JAVA_BASE_URL", "http://localhost:8080")
    java_timeout_s: float = float(_env("ASSISTANT_JAVA_TIMEOUT", "8"))

    # 会话存储：Redis 优先，MySQL 次之（复用 KB DB 配置），都不可用退化为进程内内存（重启即丢）
    redis_url: str = _env("ASSISTANT_REDIS_URL") or _env("REDIS_URL")
    session_ttl_days: int = _env_int("ASSISTANT_SESSION_TTL_DAYS", 7)
    session_max_turns: int = _env_int("ASSISTANT_SESSION_MAX_TURNS", 30)

    # 知识库目录（markdown，按 ## 切块）。这是 DB 不可用时的回退来源
    knowledge_dir: str = _env(
        "ASSISTANT_KNOWLEDGE_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge"),
    )

    # 知识库持久化（可选）：配了 host 才从 MySQL 读 knowledge_chunk 表，否则回退 markdown
    kb_db_host: str = _env("ASSISTANT_KB_DB_HOST")
    kb_db_port: int = _env_int("ASSISTANT_KB_DB_PORT", 3306)
    kb_db_user: str = _env("ASSISTANT_KB_DB_USER", "root")
    kb_db_password: str = _env("ASSISTANT_KB_DB_PASSWORD")
    kb_db_name: str = _env("ASSISTANT_KB_DB_NAME", "ry-vue")

    # 内容安全：none | wechat（wechat 需 Java 侧提供 /api/v1/assistant/sec-check 代理，见 safety.py）
    safety_provider: str = _env("ASSISTANT_SAFETY_PROVIDER", "none")

    # 产品命名（进 system prompt 与欢迎语）
    product_name: str = _env("ASSISTANT_PRODUCT_NAME", "小白")
    # build_surface_baseline.py 产出的 30 维表层特征基线；cls_only 模型解释「为什么像 AI」时的次选基线
    surface_baseline_path: str = _env("TEXT_SURFACE_BASELINE_PATH")

    extra: dict = field(default_factory=dict)

    # ---- 派生（dataclass 只读属性）----

    @property
    def profile(self) -> ProviderProfile:
        return get_profile(self.provider_name)

    @property
    def resolved_base_url(self) -> str:
        """显式 env > profile 默认。custom profile 没默认值，必须显式给。"""
        return self.llm_base_url or self.profile.base_url

    @property
    def resolved_model(self) -> str:
        return self.llm_model or self.profile.default_model

    @property
    def resolved_api_key(self) -> str:
        return pick_api_key(self.profile, self.llm_api_key)

    @property
    def thinking_active(self) -> bool:
        """provider 不支持时，即使用户开了也视为关，避免把不认识的参数发出去。"""
        return self.thinking_enabled and self.profile.supports_thinking

    @property
    def kb_db_enabled(self) -> bool:
        """配了 ASSISTANT_KB_DB_HOST 才走数据库加载，否则回退本地 markdown。"""
        return bool(self.kb_db_host)

    def model_warning(self) -> Optional[str]:
        """启动期校验：模型名不在已知清单里就提醒（挡已退役名字的静默 404）。"""
        return validate_model(self.profile, self.resolved_model)

    def config_warnings(self) -> list[str]:
        """启动期自检，返回人类可读的告警列表（空 = 配置没问题）。"""
        warns: list[str] = []
        if not self.resolved_api_key:
            envs = " / ".join(self.profile.api_key_envs)
            warns.append(f"provider={self.profile.name} 未配置 API key（可设 {envs}），/chat 将返回 LLM_UNAVAILABLE")
        if not self.resolved_base_url:
            warns.append(f"provider={self.profile.name} 的 base_url 为空，必须设 ASSISTANT_LLM_BASE_URL")
        mw = self.model_warning()
        if mw:
            warns.append(mw)
        if self.thinking_enabled and not self.profile.supports_thinking:
            warns.append(f"provider={self.profile.name} 不支持思考模式，ASSISTANT_LLM_THINKING 已忽略")
        return warns

    def public_dict(self) -> dict:
        """给 /health 用的脱敏视图 —— 绝不含 api key。"""
        p = self.profile
        return {
            "provider": p.name,
            "providerLabel": p.label,
            "model": self.resolved_model,
            "baseUrl": self.resolved_base_url,
            "llmKeyConfigured": bool(self.resolved_api_key),
            "thinkingEnabled": self.thinking_active,
            "reasoningEffort": self.reasoning_effort if self.thinking_active else None,
            "supportsTools": p.supports_tools,
            "supportsStreamUsage": p.supports_stream_usage,
            "docsUrl": p.docs_url,
            "warnings": self.config_warnings(),
        }


CONFIG = AssistantConfig()


def reload_config() -> AssistantConfig:
    """重建 CONFIG（测试用；生产走进程重启）。"""
    global CONFIG
    CONFIG = AssistantConfig()
    return CONFIG
