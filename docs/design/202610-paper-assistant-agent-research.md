# 论文助手 Agent · 调研与方案

> 状态：路线 B 已落地骨架（v0.3.0，2026-10-03），§5 W1 全部 + W2 端上部分完成；W2 `sec-check` / 会话历史页、W3 测试集与 prompt 调优待做。代码：`deploy/inference-python/assistant/`、Java `AssistantController`、uniapp `pages/assistant/chat.vue`、web `AssistantDrawer.vue`
> 日期：2026-10-03
> 范围：在现有 app（mobile-uniapp + web）里增加一个围绕「论文 AIGC 检测」的对话式助手——答疑、指导、建议、陪伴式聊天
> 前提：humanize（降 AIGC 改写）处于待定状态。本助手**可以给原则性的写作指导与建议，不产出可直接替换进论文的改写文本**（边界见 §3.3）
> 修订：2026-10-03 定位从「报告解读工具」调整为「论文检测陪伴型助手」

---

## 0. 结论先行

| 问题 | 结论 |
|---|---|
| 用什么引擎 | **路线 B：Python 侧轻量自研**（在 `deploy/inference-python` 加一个 SSE 端点 + 5 个工具），零新框架 |
| 复用 daimai 的 arsmat-ai 吗 | 不复用引擎（重：独立 JDK21 服务 + Redis + 一套 `dy_*` 表 + 9MB 私有 jar）；**复用其前后端 SSE 协议形态与对话面板的交互设计**，便于日后升级 |
| 助手能做什么 | **答疑**（检测原理、为何这段判 AI、红线政策）· **指导**（怎么看报告、答辩材料准备、学术规范、写作习惯）· **建议**（原则性的表达/结构建议，指出问题不给成品）· **陪伴**（情绪安抚、闲聊兜底、拉回主题）· **操作**（即时检测一段、一键申诉、查历史）。**不**代写、不逐句改写、不给「把这段改成…」的成品文本 |
| 挂在哪 | **全局悬浮球**（聊天型不绑定单个任务）+ 报告详情页「问助手」（带 taskId 上下文）两个入口一期同做 |
| 模型 | OpenAI-compatible 接口，首选 DashScope `qwen-plus`（中文闲聊与情绪表达自然，与 daimai 一致）；DeepSeek 作兜底 |
| 工期 | MVP 约 2.5-3 周（后端 1.5 周含知识库与会话存储 + 前端 1 周 + prompt 调优 0.5 周），可与主线并行 |
| 最大风险 | **合规定性上调为确定项**：开放式对话 = 向公众提供生成式 AI 服务，需按此准备；其次是幻觉（编造判定理由/学校政策）与「建议」滑向「改写」。靶向 system prompt + 工具结构化证据 + `msgSecCheck` 一期必接 + 改写边界测试集 |

---

## 1. 现状盘点

### 1.1 aigc app 侧

| 层 | 现状 | 对助手的意义 |
|---|---|---|
| mobile-uniapp | 10 页，无任何 chat / 助手代码；纯手写 SCSS tokens（uni.scss + 15 mixin），**无 uview 等 UI 库** | 新建 1 个 chat 页即可；移植 daimai 组件要去 uview |
| web | 6 页 + admin，`TaskDetail.vue` 已有段级展示 | 可在详情页加侧栏对话 |
| `utils/request.js` | 不支持 chunked / 流式 | 要加 `enableChunked` + `onChunkReceived` 分支（小程序）与 `fetch` ReadableStream（H5） |
| Java 后端 | 23 端点；**无 SSE / WebFlux** | 工具直接复用现有端点；SSE 用 Spring MVC `SseEmitter` 零依赖，或 Nginx 直接把 `/assistant/*` 路由到 Python |
| Python 推理 | FastAPI；`training/requirements.txt` 已有 `openai>=1.40`，`paraphrase_augment.py` 已用 OpenAI-compatible 方式打 Qwen/DeepSeek | **agent 运行时与依赖都已就位** |
| 报告 VO | `aiRate / threshold / scenario / sourceLabels / paragraphs[].{aiProb, calibratedProb, sourceLabel, warnings, sentences[]}` | 这就是助手的上下文，结构化、可直接喂 |
| 详情页 | 已有规则生成的「改进建议」section | 助手可替代/增强这块，用同一数据源 |

### 1.2 daimai arsmat-ai（可借鉴的现成资产）

**引擎**：`daimai-ai-service` 是 RuoYi 风格 wrapper（77 个 Java 文件，全是框架/登录/系统管理），真正的 agent 引擎在 **`arsmat-ai-3.8.4.jar`（9.1MB，2162 class，私有）**。

| 能力 | 在 jar 里的位置 | 对我们 |
|---|---|---|
| 对话 + SSE 流式 | `core/agent/AgentController` · `/open-api/ai/conversation/{id}/agent-stream` | 协议形态值得照抄 |
| server-to-server 开放 API | `core/openapi/*`（app-key + HMAC 签名，scopes: chat/translate/vision/image/action:*） | 业务系统接入方式 |
| 业务接口注册为工具 | `AiController / AiControllerMethod / AiClientEndpoints`（DB 驱动，管理端配，**业务代码不加注解**） | 工具即 OpenAPI 端点，思路可用 |
| MCP 客户端 | `engine/adapter/impl/McpClientAdapter` | 支持 MCP server 作工具源 |
| 内置工具 | `engine/tool/{websearch, fetchurl, codesource}` | 论文助手不需要 |
| 25 个角色适配器 | `AdminAssistantAdapter / ClientAssistantAdapter / CommonDocAnalystAdapter / TaskOrchestratorAdapter ...` | 「角色 = adapter」的组织方式可借鉴 |
| 知识库 / 记忆 / 翻译 / 多语言 / 转人工 / 计费 | `engine/knowledge`、`OpenApiMemoryController`、`welcome-i18n`、`OpenApiCsController`、`arsmat-billing` | 一期用不上 |
| 模型 | DashScope compatible-mode，`al-qwen-plus-last`；注释提到 coding 专用端点会挂、慢模型首轮 3 分钟超时 | 选型教训直接吸收 |

**前端** `daimai-cloud-h5/components/AiAssistant/`：

| 文件 | 行数 | 依赖 |
|---|---|---|
| `AiChatPanel.vue` | 3,094 | uview（`u-icon`×16, `u-popup`, `u-button`, `u-input`, `u-loading-icon`）、`marked`、`highlight.js` 7 种语言、`phaser`（游戏，无关） |
| `core/*.js` | 7,254 | `useAiChat.core.js` 2,226 行（SSE + 轮询补齐 + 工具回调）、`pageBridge.js` 1,562 行（页面生成，无关）、`pageApi.js` 814 行 |
| `AiAssistant.vue` | 111 | 可拖动悬浮球 + popup/page 双模式 |
| `pages/ai-chat/index.vue` | 67 | 整屏对话页壳 |

**复用判断**：引擎层 **不复用**——为一个「解读报告」的助手引入独立 JDK21 服务、Redis db4、几十张 `dy_*` 表和一个不透明私有 jar，运维与合规面都过大；且其能力（页面生成、源码检索、转人工、计费）95% 用不上。前端 **只借交互设计与 SSE 协议**——7,000 行里和我们相关的约 600 行（SSE 消费、消息列表、markdown 渲染、流式打字），且要换掉 uview，重写比移植快。

---

## 2. 三条路线对比

| | A · 复用 arsmat-ai | **B · Python 轻量自研（推荐）** | C · Java 侧 Spring AI / LangChain4j |
|---|---|---|---|
| 新增部署 | ai-service（JDK21）+ Redis + `dy_*` 表 | **无**（加在现有 `inference-python` 进程） | 无，但 `ruoyi-detect` 加框架依赖 |
| 新增依赖 | 私有 jar、uview | **零**（`openai` SDK 已在 requirements） | spring-ai 或 langchain4j（与 RuoYi 基座 + standalone-app 双构建的版本碰撞风险） |
| 工具接入 | DB 配 OpenAPI 端点 / MCP | 手写 5 个函数（调 Java 端点或直接查库） | `@Tool` 注解 |
| 流式 | 现成 SSE | FastAPI `StreamingResponse` 原生 | `SseEmitter` 或 WebFlux |
| 多轮记忆 | 现成（服务端） | 一期客户端带 history（≤10 轮），二期落 Redis | 自己做 |
| 前端 | 移植 7,000 行 + 去 uview | **新写约 400 行 chat 页**，复用现有 tokens | 同 B |
| 合规面 | 大（web_search/fetch_url 走代理、页面生成、源码读取） | **小**（只有 5 个只读工具 + 1 个申诉写入） | 小 |
| 工期 | 3-4 周 | **1.5-2 周** | 2-3 周 |
| 升级路径 | — | 保持 SSE 协议与 arsmat 形态兼容，日后可切 A | 同 |

**选 B 的理由**：和你此前「轻量化框架」「最低配置」的倾向一致；agent 的全部上下文（段级结果、表层特征、校准参数）本来就在 Python 推理进程里；零新依赖零新部署；合规面最小。

---

## 3. 路线 B 设计

### 3.1 架构

```
mobile-uniapp / web
  │  POST /api/v1/assistant/chat  (SSE)        Authorization: Bearer <sa-token>
  ▼
Nginx ──► Java (Sa-Token 校验 + 限流 + 审计) ──► Python inference  POST /assistant/chat (SSE)
                                                      │  tool loop (≤4 轮)
                                                      ├─ get_task_detail      → Java GET /detect/tasks/{id}（或直查 DB）
                                                      ├─ explain_paragraph    → 本地：aiProb/calibratedProb/sourceLabel/warnings + 30 维表层特征
                                                      ├─ detect_text          → 本地 TextAIGCDetector.predict_paragraph
                                                      ├─ get_threshold_policy → Java GET detect_scenario_threshold + 教育部红线常量
                                                      └─ create_appeal        → Java POST /api/v1/feedback (category=appeal)
                                                      ▼
                                              OpenAI-compatible LLM（qwen-plus / deepseek-chat）
```

- Java 只做鉴权、限流、审计日志透传，不碰 LLM；用 `SseEmitter` 转发 Python 的 SSE，或 Nginx 直接路由（需 Python 侧校验 token，一期走 Java 透传更稳）。
- Python 侧新模块 `deploy/inference-python/assistant/`：`router.py`（端点）、`tools.py`（5 工具）、`prompts.py`（system prompt）、`llm.py`（OpenAI client + 重试）。
- 多轮：实现上直接落 Redis（`assistant:conv:{cid}`，无 Redis 时内存兜底），服务端取最近 10 轮拼上下文；客户端只带 `conversationId`。

### 3.2 能力矩阵：能做 / 灰区 / 不做

| 类别 | 能做（鼓励） | 灰区（原则性可以，成品不行） | 不做（拒绝 + 引导） |
|---|---|---|---|
| 答疑 | 检测原理、为何这段判 AI、什么是校准概率/置信区间、红线怎么定、报告每个字段啥意思 | — | 评价其它检测工具准不准 |
| 指导 | 怎么看报告、哪些段优先处理、答辩材料怎么准备（报告 + 过程稿 + 参考文献）、学术规范/引用规范、人类写作习惯是什么样 | 「这段连接词模板化，试着用具体案例替代『综上所述』」（指出问题 + 方向） | 「把第 3 段改成：……」（给成品） |
| 建议 | 结构建议（论证顺序、段落长短节奏）、表达习惯建议（多用一手数据、少用套话） | 给 1-2 个**抽象示例**说明什么叫「有个人风格」 | 针对用户原文逐句给替换文本；任何形式的「降 AI 率教程」 |
| 陪伴 | 情绪安抚（「超标不等于作弊，先看是哪几段」）、闲聊兜底、鼓励、把跑题的聊天温和拉回 | — | 替用户做学术不端的决策（「要不要瞒着导师」） |
| 操作 | 加载报告、即时检测一段、查历史任务、一键申诉、查阈值 | — | 删除任务、改阈值（管理端操作） |

**灰区的判定口径**：输出里出现可以直接复制粘贴进论文的、针对用户原文的改写句子 → 越界。只说问题在哪、往哪个方向改、举抽象例子 → 合规。这条线与 humanize 待定一致，也是上线前合规确认的核心问题。

### 3.3 工具清单

| 工具 | 数据源 | 用途 |
|---|---|---|
| `get_task_detail(task_id)` | 现有 `GET /detect/tasks/{id}` | 加载报告：AI 率、阈值、场景、段落列表 |
| `list_my_tasks()` | 现有 `GET /detect/tasks` | 「我上次测的那篇多少」「这周测了几次」 |
| `explain_paragraph(task_id, paragraph_idx)` | 段级 `aiProb / calibratedProb / sourceLabel / warnings` + `surface_features` 30 维（句长 CV、标点节奏、话语标记率、TTR…） | 用**结构化证据**解释「为什么这段像 AI」，杜绝编造 |
| `detect_text(text)` | 本地 `TextAIGCDetector` | 用户粘一段问「这段像 AI 吗」，<120 字带 warning |
| `get_threshold_policy(scenario)` | `detect_scenario_threshold` + 常量 | 「硕士红线多少」「我 18% 过不过」 |
| `search_knowledge(query)` | §3.7 知识库 | 检测原理 FAQ、教育部政策、各校红线、学术规范、答辩材料清单 |
| `create_appeal(task_id, reason)` | 现有 `POST /api/v1/feedback` | 用户认为误判 → 一键申诉（唯一写操作，需二次确认） |

### 3.4 System prompt 要点

1. 角色：一位懂 AIGC 检测、也懂学术写作的**学长/学姐式陪伴者**；语气自然、不说教、短句、先共情再给信息。不是客服机器人，也不是写作外包
2. 开场感知情绪：用户带着超标报告来，先一句安抚 + 把问题拆小（「先看哪几段贡献最大」），再给数据
3. 只基于工具返回的数据下结论；没有工具证据的判断一律说「我不确定，但可以这样验证」
4. 解释判定必须引用具体特征（「这段句长变化系数 0.12，人类写作常见 0.4 以上，读起来就会很『匀』」），把术语翻成人话
5. 写作指导只讲**原则与方向**，可以举抽象例子，**绝不**针对用户原文输出替换句。被要求改写时：说明为什么不直接改 + 给方向 + 引导人工复核/申诉
6. 政策类：给数据 + 「以你学校的最新规定为准」；不替用户做学术不端相关的决定
7. 闲聊：接得住，三轮内自然带回检测/写作话题；不装人，被问「你是 AI 吗」直接承认
8. 置信度表述永远带区间与「仅供参考，建议人工复核」
9. 输出 markdown，短段落、少列表，手机可读；一次回答不超过约 300 字，用户追问再展开

### 3.5 前端

**mobile-uniapp**（新增约 500 行）
- `pages/assistant/chat.vue`：消息列表（用户/助手气泡）、流式打字、markdown 轻渲染（标题/加粗/列表/代码即可，不引 marked）、底部输入框 + `cursor-spacing`、「快捷问题」chip 按进入场景变化：
  - 从详情页进（带 taskId）：「为什么第 3 段被判 AI」「我 18% 硕士能过吗」「先改哪几段」「怎么申诉」
  - 从悬浮球进（无 task）：「AI 检测是怎么判的」「答辩要带什么材料」「我上次测的结果」「随便聊聊」
- `components/AssistantFab.vue`：全局可拖动悬浮球，`App.vue` 挂载，登录态可见，详情页自动隐藏（避免与「问助手」按钮重复）
- `pages/task/detail.vue`：hero 区加「问助手」按钮，带 `taskId` 跳转；段落卡长按菜单加「问助手：为什么这段像 AI」
- `utils/request.js`：加 `httpStream(opts, onChunk)`——小程序 `uni.request({ enableChunked: true })` + `requestTask.onChunkReceived`（基础库 ≥ 2.20.1）；H5 `fetch` + `ReadableStream`；都不支持时退化为非流式一次性返回
- `api/assistant.js`：`chatStream({ conversationId, taskId, message }, onToken, onDone, onError)`、`listConversations()`、`getHistory(conversationId)`
- `pages.json` 加路由；复用 `uni.scss` tokens，不引新 UI 库

**web**：`TaskDetail.vue` 右侧抽屉 + 全局右下角入口，复用同一 SSE 协议，Element Plus 已有，约 300 行。

### 3.6 会话与记忆（聊天型必须服务端落会话）

- 一期就落 **Redis**（compose 里已有）：`assistant:conv:{conversationId}` 存最近 30 轮，TTL 30 天；`assistant:user:{userId}:convs` 存会话列表
- 每次请求服务端拼上下文：system prompt + 知识库命中片段 + 当前 task 摘要（若有）+ 最近 10 轮；超 6K tokens 时对更早的轮次做一次摘要压缩
- 用户侧可「新对话」「查看历史」；详情页进入默认续接该 task 的最近会话
- 二期考虑跨会话长期记忆（用户学段、学校、关心的场景），一期不做

### 3.7 知识库（答疑/指导的内容来源，一期不用向量库）

| 内容块 | 来源 | 维护方 |
|---|---|---|
| 检测原理 FAQ（约 30 条）：什么是 AI 率、校准概率、置信区间、为什么短段落不可靠、为什么规范化的学术文体容易被误判（Chen 2026 错误分析、Style as a Confound） | 文献笔记 + 设计文档 | 算法 |
| 政策：教育部 2026 指导意见、本科/硕士/博士红线、清华/北大/人大等个例 | `MODEL_RESEARCH_TEXT.md` §A | 产品，每学期核一次 |
| 答辩材料清单：检测报告、过程稿、文献管理记录、导师沟通记录 | 新写 | 产品 |
| 学术规范与引用规范要点 | 新写 | 产品 |
| 人类写作特征科普（节奏、细节、个人经验、不规则性）—— 这是「指导」的理论基础 | 文献笔记 §五 Chen 表 1 | 算法 |
| 申诉/人工复核流程说明 | 对齐复核工作流 | 产品 |

实现：markdown 文件按块切（每块 200-500 字 + 标题 + 标签），启动加载进内存；`search_knowledge` 用标题/标签关键词 + 简单 BM25 取 top-3 塞进上下文。总量几万字，不值得上向量库。运营可改 markdown 热更新。

### 3.8 SSE 协议（与 arsmat 形态兼容，便于日后切换）

```
event: token      data: {"delta": "这段"}
event: tool_call  data: {"name": "explain_paragraph", "args": {...}}      # 前端可显示「正在分析第 3 段…」
event: tool_result data: {"name": "...", "summary": "..."}
event: done       data: {"usage": {"prompt_tokens": 2310, "completion_tokens": 420}, "model": "qwen-plus"}
event: error      data: {"code": "RATE_LIMITED", "message": "问得太快了，请 30 秒后再试"}
```

### 3.9 限流 / 成本 / 可观测

- 每用户每分钟 8 次、每日 100 次（聊天型用量比工具型高；Java 侧 Caffeine 计数）
- 单次对话上下文 ≤ 6K tokens（知识库片段 + 报告摘要 + 最近 10 轮），工具循环 ≤ 4 轮
- 成本：qwen-plus 约 ¥0.0008/K 输入、¥0.002/K 输出 → 每轮 ¥0.008-0.03；日活 200 人 × 8 轮 ≈ ¥15-50/天
- 审计：Java 侧落 `assistant_log`（user_id, conversation_id, task_id, tokens, latency, tool_calls, 意图标签, 截断后的 Q/A），供三件事：误报分析、合规追溯、**统计「要求改写」类请求比例**作为 humanize 是否重启的依据
- 内容安全：用户输入与模型输出都过 `msgSecCheck`（小程序）/ 等价接口（H5）；命中则替换为固定文案并记日志

---

## 4. 风险

| 风险 | 等级 | 应对 |
|---|---|---|
| **合规定性**：开放式对话 = 向公众提供生成式 AI 服务，按确定项准备 | **确定** | ① 按《生成式人工智能服务管理暂行办法》准备备案材料（与 humanize 合并评估，一次过）；② `msgSecCheck` 一期必接，双向过滤；③ system prompt 限定域 + 改写边界；④ 页面显著位置标注「AI 生成内容，仅供参考」；⑤ 对话日志留存 ≥ 6 个月；⑥ 首版用「论文检测助手」命名，不用「写作助手」 |
| **「建议」滑向「改写」** | 高 | 建 50 条边界测试集（「帮我改一下这段」「换个说法」「这句怎么写更像人」…）每次 prompt 改动跑回归；灰区判定口径见 §3.2；日志统计越界率 |
| **幻觉**：编造判定理由、编造学校政策 | 高 | 工具返回结构化证据，prompt 要求引用具体数值；政策类只从知识库取、固定模板 + 「以学校规定为准」 |
| 情绪场景处理不当 | 中 | 焦虑/愤怒/求助类开场的回复模板走人工评审；涉及极端情绪表达时固定回复心理援助资源并记日志 |
| 小程序流式兼容 | 中 | `enableChunked` 需基础库 2.20.1+，`pages.json` 设最低版本；不支持时退化非流式 |
| 与检测队列抢资源 | 中 | LLM 调用是 IO 等待不占 GPU/CPU，但要独立线程池 + 独立限流；Python 侧用 `asyncio` 不阻塞检测 worker |
| 模型供应商不稳定 / 慢模型超时 | 中 | daimai 实测教训：避开 coding 专用端点；首 token 超时 15s 即报错；配置可切 DeepSeek 兜底 |
| 用户把助手当「降 AI 率」工具 | 中 | 拒绝话术 + 引导申诉；日志里统计此类请求比例，作为 humanize 是否重启的依据 |
| prompt 注入（用户在论文里埋指令） | 低 | 论文正文只经工具以结构化字段进入上下文，不直接拼全文 |

---

## 5. MVP 排期（2.5-3 周，可与主线并行）

| 周 | 后端（Python + Java） | 前端（uniapp + web） | 内容 | 验收 |
|---|---|---|---|---|
| W1 | `assistant/` 模块：SSE 端点 + 7 工具 + LLM 客户端重试 + Redis 会话；Java `/api/v1/assistant/*` SseEmitter 透传 + Sa-Token + 限流 + 审计表 | `request.js` 加 `httpStream`；`api/assistant.js` | 知识库 6 个内容块初稿（约 2 万字） | curl 能流式拿到带 tool_call 事件的回答；多轮上下文正确；限流 429；审计有记录 |
| W2 | `search_knowledge` BM25；`msgSecCheck` 双向接入；错误码与文案；意图标签 | `pages/assistant/chat.vue` + `AssistantFab` 悬浮球 + detail 入口 + 场景化快捷问题；会话列表/历史 | 50 条改写边界测试集；30 条情绪开场测试集 | 真机流式无乱序；悬浮球可拖动不挡关键按钮；「为什么第 N 段像 AI」引用具体特征 |
| W3（半周） | prompt 调优：跑边界集 + 情绪集 + 20 条真实问题，越界率 0、情绪回复人工评审通过 | web 抽屉 + 全局入口；文案与免责 | 知识库校对 | 三套测试集全过；合规材料初稿 |

**前置条件**：主线 P0（有一个真实 checkpoint）。没有真模型时，`explain_paragraph` 解释的是 stub 的随机数，助手会一本正经地胡说——**助手必须在新模型上线后再对用户开放**，开发可并行。

---

## 6. 待拍板

1. ~~路线 A / **B** / C~~ → 已按 B 落地
2. ~~一期入口~~ → 已定：悬浮球 + 详情页按钮两者同做
3. 模型：DashScope qwen-plus（中文闲聊自然、与 daimai 共用经验，**推荐**）/ DeepSeek（便宜约 1/3，兜底）
4. ~~是否一期接 `msgSecCheck`~~ → 已定：开放对话必接
5. 产品命名：「论文检测助手」（推荐）/ 「学术小助手」/ 其它
6. **灰区尺度**：§3.2 的「原则性建议可以、成品不行」这条线你是否认可；若希望更开放（允许对用户原文给示范性改法），就和 humanize 一起过合规而不是单独放行
7. 生成式 AI 服务备案：是否现在启动（流程数周，建议与域名备案并行）

---

## 7. 参考

- daimai：`src/daimai-ai-service/`（wrapper）· `module-web/lib/arsmat-ai-3.8.4.jar`（引擎）· `src/daimai-cloud-h5/components/AiAssistant/`（前端面板）· `deploy/ai-freeze/README.md`（部署与踩坑）
- aigc：`deploy/inference-python/detectors/text.py`（`TextAIGCDetector.predict_paragraph`）· `ml/common/surface_features.py`（30 维证据）· `domain/vo/DetectTaskDetailVO.java`（上下文字段）· `mobile-uniapp/pages/task/detail.vue`（挂载点）
- 框架对比（未选用，备查）：Spring AI vs LangChain4j vs PydanticAI 2026 选型文章见下方来源
