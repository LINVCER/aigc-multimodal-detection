# v0.3.0 · 论文检测助手骨架（滚动）

**发布状态**：🚧 滚动中 · 线路已铺通，**不对用户开放**（等新 checkpoint 上线后再放开入口）

## 概要

按 `docs/design/202610-paper-assistant-agent-research.md` 路线 B 落地「论文检测助手」端到端骨架：
Python 侧承载 LLM、工具循环、知识库、会话；Java 侧只做限流 / 审计 / SSE 透传；
uniapp 与 web 各有一个对话入口。零新服务、零新部署单元，LLM 走 DashScope OpenAI 兼容接口。

## 本版改动

### Python · `deploy/inference-python/assistant/`

| 文件 | 职责 |
|---|---|
| `config.py` | 全部 `ASSISTANT_*` 环境变量，单例 `CONFIG` |
| `protocol.py` | `ChatRequest` / SSE 帧编码 / 事件名与错误码常量 |
| `llm.py` | OpenAI 兼容流式客户端，首 token 前失败才重试，401/429/5xx/timeout 归类 |
| `knowledge.py` | Markdown 知识库按 `## ` 切块 + BM25，`search / format_context / reload` |
| `safety.py` | 入口 / 出口内容安全；provider `none` 放行，`wechat` 代理到 Java `sec-check`（未实现时降级放行） |
| `session.py` | 会话存储：Redis（`assistant:conv:{cid}` / `assistant:user:{uid}:convs`）或内存兜底 |
| `tools.py` | 7 个工具：`get_task_detail / list_my_tasks / explain_paragraph / detect_text / get_threshold_policy / search_knowledge / create_appeal` |
| `prompts.py` | 陪伴型人设 + 7 条回答规则 + 边界（原则可以、成品不行）+ 欢迎语 / 快捷问题 |
| `agent.py` | `run_chat`：meta → 入口安全 → 预加载任务上下文与知识 → 工具循环（≤4 轮）→ 出口安全 → done |
| `router.py` | `/api/v1/assistant/{chat,conversations,quick-prompts,health,knowledge/reload}` |
| `knowledge/01-06.md` | 检测原理 / 为什么学术写作易误判 / 政策红线 / 答辩材料 / 学术规范 / 申诉流程，共 32 块 |

- `detectors/text.py` 新增 `surface_profile(text)`：fusion 模型返回 30 维表层特征 z-score，供 `explain_paragraph` 翻成人话
- `main.py` 挂载 assistant router；`requirements.txt` 加 `openai / httpx / redis`；Dockerfile 打包 `assistant/`

### Java · `ruoyi-detect`

- `controller/AssistantController.java`：`POST /api/v1/assistant/chat`（SseEmitter 透传）· `GET/DELETE conversations` · `GET quick-prompts` · `GET health`
- `service/IAssistantService` + `impl/AssistantServiceImpl`：JDK HttpClient 逐行读 Python SSE，按空行切帧原样下发；Caffeine 限流（每用户 8 次/分、100 次/天）；`meta / token / done / error` 事件截审计字段落 `assistant_log`
- `domain/dto/AssistantChatDTO` · `domain/entity/AssistantLog` · `mapper/AssistantLogMapper`
- `ErrorCode` 加 7xxx 段：`ASSISTANT_RATE_LIMITED(7429) / ASSISTANT_UPSTREAM_ERROR(7502) / ASSISTANT_DISABLED(7503)`
- `DetectController` 加 `GET /api/v1/detect/scenario-thresholds`（只读，助手 `get_threshold_policy` 工具取当前生效值）
- `application.yml` 加 `platform.assistant.{base-url,rate-per-minute,rate-per-day,stream-timeout-seconds}`

### 配置与 SQL

- `deploy/docker-compose.yml`：inference 注入 `ASSISTANT_*`（含 `ASSISTANT_JAVA_BASE_URL=http://backend:8080`、`ASSISTANT_REDIS_URL` 用 Redis db1）；backend 注入 `PLATFORM_ASSISTANT_BASE_URL=http://inference:8000`
- `deploy/.env.example` / `deploy/inference-python/.env.example` 加 ASSISTANT 段
- `sql/V0.3.0.001__init_assistant_log.sql` + `backend-java/scripts/patch-schema.sql` 同步 `assistant_log`

### mobile-uniapp

- `utils/request.js` 加 `httpStream`：MP-WEIXIN `enableChunked + onChunkReceived`；H5 `fetch + ReadableStream`；不支持 chunked 时退化为整包回放。跨 chunk 缓冲切帧
- `api/assistant.js`（含 MOCK_MODE 逐字回放）· `pages/assistant/chat.vue`（欢迎卡 / 快捷问题 / 气泡流 / 工具调用提示 / 停止 / 重试 / 新对话 / 免责声明）· `components/AssistantFab.vue`（挂到 4 个 tab 页，`ENABLE_ASSISTANT` 一键隐藏）
- `pages/task/detail.vue`：hero 加「问助手」；段落 `calibratedProb ≥ 0.5` 显示「为什么这段像 AI？」直达对话并自动追问
- `pages.json` 注册 `pages/assistant/chat`

### web

- `api/assistant.ts`（fetch 流）· `components/AssistantDrawer.vue`（右侧抽屉）· `TaskDetail.vue` 头部「问助手」+ 段级「为什么这段像 AI？」

### 增长闭环 P0（`202610-assistant-growth-loop-plan.md`）

- Python：`agent.py` done 事件带 `kbHits / kbTopScore / kbTopRef`（知识缺口信号看 top-1 分数，不看是否为空）；`prompts.py` 加第 8 条「结尾给一句下一步」
- golden set：`assistant/eval/golden.jsonl` 40 条（知识 / 解读 / 边界 / 政策各 10）+ `eval_golden.py`（离线验规则层，`--live` 真跑 run_chat 判可确定项，结果追加 `history.csv`）。离线基线：知识 9/10（k09「写作过程材料」检索偏到答辩材料块，真实检索缺口，留给检索升级方案）、边界硬拦截 7/7
- Java：`AssistantLog.kbTopScore / kbTopRef` 落库；新增 `AdminAssistantController`：`GET /admin/assistant/knowledge-gaps?days&threshold&limit`、`GET /admin/assistant/stats?days&threshold`
- SQL：`V0.3.0.005__add_assistant_kb_score.sql`（两列 + `idx_intent_kb`），`patch-schema.sql` 同步
- 知识库管理：`KnowledgeChunk` 实体 + Mapper + `KnowledgeChunkDTO`；`AdminAssistantController` 加 `GET/POST /admin/assistant/knowledge`、`GET/PUT /knowledge/{id}`、`POST /knowledge/{id}/enabled`、`POST /knowledge/reload`、`GET /knowledge-gaps/{logId}/draft`（转成知识草稿）；写库后通知 Python `knowledge/reload`，失败不回滚（块已入库，可手动重载）
- compose：inference 注入 `ASSISTANT_KB_DB_*` 指向 mysql，知识库从 `knowledge_chunk` 读，reload 才真正生效
- web 管理端：新页 `/admin/assistant`（菜单「助手运营」）三个 tab：概览 KPI / 知识缺口（转成知识）/ 知识库（新增、编辑、上下线、热加载）

### 增长闭环 P1 · 申诉到段级 + 误判样本池（方案 §2.2）

- SQL `V0.3.0.006`：`user_feedback` 加 `paragraph_idxs JSON / consent_improve`；新表 `detect_hard_sample`（hash+版本唯一，原文仅授权时存）；`patch-schema.sql` 同步
- Java：`Feedback.paragraphIdxs/consentImprove`（JSON 列）、`HardSample` + Mapper、`IHardSampleService`（申诉落库后自动采样、复核、列表、导出）；`FeedbackController` 加 `GET /admin/feedback/{id}/samples`、`POST /admin/hard-samples/{id}/verdict`、`GET /admin/hard-samples`、`GET /admin/hard-samples/export`（JSONL 下载）
- Python：`create_appeal` 工具加 `paragraph_idxs / consent_improve`，prompts 要求提交前问一句授权
- web / uniapp 申诉表单：列出 ≥ 50% 的正文段供勾选「哪几段判错了」+「同意用于改进模型」勾选（默认不勾）；报告页把段落传给表单
- 管理端反馈处理弹窗：申诉显示勾选段与样本，三键复核（确认误判 / 确认是 AI / 拿不准），结论只进样本池不改报告
- `ml/datasets/text/build_appeal_evalset.py`：导出 JSONL → `eval_appeal.jsonl`（confirm_fp→0，confirm_tp→1，unsure 丢弃），`eval.py --evalset-dir` 自动纳入为第七套；只进评测不进训练

## 验证状态

- Python：`compileall` 通过；知识库 32 块可加载。未在本机起服务（无 torch / 无 LLM key）
- Java：本机 Maven 本地仓库无 Spring Boot 3.3.4，**未编译**；代码按 Java 21 / RuoYi-Vue-Plus 5.x 写法人工复核
- 前端：未跑 `vue-tsc`（web 无 node_modules）；uniapp 未真机

## 已知未做（按调研 §5 排期归属 W2/W3）

- Java `POST /api/v1/assistant/sec-check` 代理（微信 `msgSecCheck`）：Python 侧已留降级路径
- 会话列表 / 历史页（接口已有，端上没做页面）
- Sa-Token 真接入后 `userId` 改从上下文取，去掉请求透传
- 边界测试集（50 条改写请求 + 30 条情绪开场）与 prompt 调优
- 生成式 AI 服务备案材料

## 开放条件

`AssistantFab.vue` 的 `ENABLE_ASSISTANT` 与 web 入口当前为 true 仅便于联调；**上线前若新 checkpoint 未就位，须置 false**。
`explain_paragraph` 在 MD5 stub 上解释的是随机数。
