"""助手配置：全部走环境变量，带可运行的默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class AssistantConfig:
    enabled: bool = _env("ASSISTANT_ENABLED", "true").lower() in ("1", "true", "yes")

    # LLM：OpenAI-compatible。DashScope compatible-mode / DeepSeek / 本地 vLLM 均可
    llm_base_url: str = _env("ASSISTANT_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    llm_api_key: str = _env("ASSISTANT_LLM_API_KEY") or _env("DASHSCOPE_API_KEY") or _env("OPENAI_API_KEY")
    llm_model: str = _env("ASSISTANT_LLM_MODEL", "qwen-plus")
    llm_temperature: float = float(_env("ASSISTANT_LLM_TEMPERATURE", "0.6"))
    llm_max_tokens: int = _env_int("ASSISTANT_LLM_MAX_TOKENS", 800)
    # 首 token 超时：daimai 实测慢模型首轮 3 分钟才回，用户体验上超过 15s 就该报错让用户重试
    llm_first_token_timeout_s: float = float(_env("ASSISTANT_LLM_FIRST_TOKEN_TIMEOUT", "15"))
    llm_total_timeout_s: float = float(_env("ASSISTANT_LLM_TOTAL_TIMEOUT", "90"))
    llm_max_retries: int = _env_int("ASSISTANT_LLM_MAX_RETRIES", 2)

    # 工具循环与上下文预算
    max_tool_rounds: int = _env_int("ASSISTANT_MAX_TOOL_ROUNDS", 4)
    history_turns: int = _env_int("ASSISTANT_HISTORY_TURNS", 10)
    context_token_budget: int = _env_int("ASSISTANT_CONTEXT_TOKEN_BUDGET", 6000)
    knowledge_top_k: int = _env_int("ASSISTANT_KNOWLEDGE_TOP_K", 3)

    # 工具回调 Java 业务接口（取报告 / 任务列表 / 阈值 / 申诉）
    java_base_url: str = _env("ASSISTANT_JAVA_BASE_URL", "http://localhost:8080")
    java_timeout_s: float = float(_env("ASSISTANT_JAVA_TIMEOUT", "8"))

    # 会话存储：Redis 不可用时自动退化为进程内内存（重启即丢，只适合联调）
    redis_url: str = _env("ASSISTANT_REDIS_URL") or _env("REDIS_URL")
    session_ttl_days: int = _env_int("ASSISTANT_SESSION_TTL_DAYS", 30)
    session_max_turns: int = _env_int("ASSISTANT_SESSION_MAX_TURNS", 30)

    # 知识库目录（markdown，按 ## 切块）
    knowledge_dir: str = _env(
        "ASSISTANT_KNOWLEDGE_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge"),
    )

    # 内容安全：none | wechat（wechat 需 Java 侧提供 /api/v1/assistant/sec-check 代理，见 safety.py）
    safety_provider: str = _env("ASSISTANT_SAFETY_PROVIDER", "none")

    # 产品命名（进 system prompt 与欢迎语）
    product_name: str = _env("ASSISTANT_PRODUCT_NAME", "论文检测助手")

    extra: dict = field(default_factory=dict)


CONFIG = AssistantConfig()
