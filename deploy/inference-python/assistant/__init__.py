"""
论文检测助手（陪伴型 agent）
============================

设计见 docs/design/202610-paper-assistant-agent-research.md。路线 B：在推理进程内用 OpenAI-compatible
接口做工具循环，SSE 流式输出；Java 侧只做鉴权/限流/审计透传。

模块：
    config      环境变量 + provider 解析（provider > key 推断 > 默认）
    providers   各家 LLM 的接入画像（base_url / 模型 / key env / 能力位），新增一家只改这里
    protocol    请求模型 + SSE 事件编码
    llm         OpenAI-compatible 流式客户端（provider 感知 / 重试 / 首 token 超时 / 思考模式）
    knowledge   markdown 知识块 + BM25 检索
    tools       7 个工具的 schema 与执行器（含 create_appeal → Java /api/v1/feedback）
    prompts     system prompt（角色 / 边界 / 任务上下文）
    session     会话存储（Redis，缺失时内存兜底）
    safety      内容安全钩子（默认放行；接 msgSecCheck 替换实现）
    agent       工具循环主体（含 reasoning_content 回传）
    router      FastAPI 路由
"""
