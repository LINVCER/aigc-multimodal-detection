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

### 增长闭环 P1 · 对话质检 / 复测关联 / 通知占位（方案 §3 / §5）

- SQL `V0.3.0.007`：`assistant_quality_note` 表；`detect_task.parent_task_id` + 索引；`patch-schema.sql` 同步
- Java：`AssistantQualityNote` / `AssistantConversation`（只读）实体 + Mapper；`AdminAssistantController` 加 `GET /admin/assistant/conversations`（含越界过滤）、`GET /conversations/{cid}`、`POST /quality-notes`、`GET /quality-notes/stats`
- 复测：`submit` 多一个 `parentTaskId`（父任务须 DONE 且同用户，否则忽略）；`detail` 返回 `parentAiRate / parentModelVersion / parentPaperTitle / parentCreatedAt`；`DetectTaskVO` 带 `parentTaskId`
- 通知：`INotifyService` + `LogNotifyServiceImpl`（只记日志；模板 id 走 `platform.notify.wechat.*`，真实发送等 W3.c 有 openid 后替换）；钩子在任务 DONE 与申诉 REPLIED
- Python：`get_task_detail / list_my_tasks` 透传 parent 字段，助手能讲「比上次」
- web / uniapp：上传页「这是修改稿？对比上一次」选择器；报告页 hero 显示「比上次 −X%」，模型版本不同时明示不可直接比较
- web 管理端「助手运营」加「对话质检」tab：会话列表（越界过滤）+ 抽屉看完整对话与每轮审计 + 五类标注与评分 + 30 天标签统计。会话落库依赖 Python 配了 `ASSISTANT_KB_DB_*` 且**未配** `ASSISTANT_REDIS_URL`（`session.py` Redis 优先、不落库），compose 已改为不给 inference 注入 Redis

### 增长闭环 P2 · 评测验收线 + 首测欢迎（方案 §4 / §5）

- `ml/evaluation/text/eval.py`：`ACCEPTANCE` 加第七套 `appeal: {fpr ≤ 0.10}`；验收比较改为按 `LOWER_IS_BETTER = (ece, fpr, brier)` 判方向
- web / uniapp 报告页：首次看到 DONE 报告时 hero 下出现助手一句话（达标 / 超标两版文案），点击进对话，关闭后按设备 / 浏览器记一次
- 未做（需外部条件）：golden set `--live`（LLM key）、分享「助手解读卡」（备案后）、订阅消息真实发送（真 openid）

### 助手结构化分析卡（product-feature-plan §2.1）

- Python：`tool_result` 事件对 `explain_paragraph / get_task_detail / detect_text` 三种工具附带 `card`（即工具 data 原样），其余工具不带
- uniapp `components/AssistantAnalysisCard.vue` / web `components/AssistantAnalysisCard.vue`：段卡（校准概率条、疑似来源、表层特征 z 值与人话、最可疑句）、报告卡（AI 率 vs 红线、红黄绿段数、贡献最大的段、上次对比）、即时检测卡；对话页与抽屉在正文前渲染，助手文字作「翻译」
- 卡片随消息一起进 web 抽屉的 localStorage 暂存

### 复测对比视图（product-feature-plan §2.2）

- Java：`GET /api/v1/detect/tasks/{id}/compare`，`ITaskCompareService` 按字符二元组 Jaccard ≥ 0.35 贪心配对正文段，给出 down / up / same / added / removed 与概率差；两次模型版本不同时 `comparable=false`，结论句明示不可直接比较
- web：报告页「比上次」下加「查看段级对比」弹窗（两侧 AI 率、四类计数、逐段表格，降的行绿、涨的行红）
- uniapp：同一入口，底部 sheet 展示

### 检测分析 P0（detect-analytics-plan，按方案推荐：物化表 + 提交时增量）

- SQL `V0.3.0.008`：`detect_statistics_daily`（天 × 场景 × 状态，`all` 表示不分维；比方案多一列 `ai_rate_sum` 以便增量更新平均值）；`patch-schema.sql` 同步
- Java：`DetectStatisticsDaily` + Mapper；`IDetectAnalyticsService`（`record` 终态计入 4 个分片、`revert` 重试 / 删除前扣回、`rebuild` 全量重算、`analytics` 读）；`DetectTaskServiceImpl` 在终态 / 重试 / 删除三处挂钩；`AdminAnalyticsController`：`GET /admin/detect/analytics?dateFrom&dateTo&scenario&status`、`POST /admin/detect/statistics/rebuild?days`
- 明细筛选增强：`DetectTaskQueryDTO` 加 `rateBucket / pass / modelVersion / dateFrom / dateTo`，`/admin/task/list` 生效
- web：新页 `/admin/analytics`（菜单「检测分析」）：日期 / 场景 / 状态筛选，KPI 五卡，趋势折线（检测量 + 平均 AI 率），AI 率分桶、场景、状态、溯源主标签四组分布条，明细表带达标标签；「重算统计」按钮首次上线补历史
- 未做（P1/P2）：CSV 导出、定时重算、模型灰度对比、申诉合理率接入

### 助手对话 Markdown 渲染 + 工具图标（chat-ui-redesign P0 ① ③）

- web `utils/markdown.ts` / uniapp `utils/markdown.js`：极简白名单渲染（标题 / 粗斜体 / 行内与块代码 / 列表 / 引用 / 段落），先整体转义再解析，不引第三方库；助手回复按此渲染，用户消息原样
- 工具调用 chip 加图标（📄 报告 🔍 段落 📚 资料 🚩 申诉 等）
- `knowledge.py`：无 jieba 时回退分词改为字 + 字二元组。注意：本机没有 jieba，此前报告的 golden set 离线基线是回退分词的结果，不代表生产（requirements 有 jieba）

### 助手对话界面重构（chat-ui-redesign §2.2 四区布局，web + uniapp）

- 头部只留头像 / 名称 + 历史 · 新对话 · 关闭 三个图标按钮，报告标题从头部移除
- 报告选择改为一行紧凑下拉（uniapp 为 picker），默认「通用咨询」
- 上下文卡：绑定报告时显示《标题》+ 整体 AI 率 + 红线 + 正文段数 + 达标 / 超标 pp 徽章（绿 / 橙 / 红）+「整体怎么看」与高风险段 chips（红 ≥ 70%、黄 40–70%）
- 工具调用 chip：图标 + 进行中 spinner / 完成 ✓（短标签「已读取报告」）/ 失败 ✕，状态色 蓝 / 绿 / 红
- 助手回复右下角：复制（clipboard）+ 👍 👎，落 `user_feedback`（category=suggestion，内容带问答摘要）供运营质检；本地记标记防重复
- 免责声明移到输入框下方，消息区更宽；历史列表带报告号

### uniapp 助手对话页整页重构（`pages/assistant/chat.vue`）

- 导航：返回 · 头像（在线点）+ 标题 + 状态副文案（在线 / 正在思考）· 历史 · 更多（新对话 / 切换报告 / 清空本地暂存）
- 上下文 pill：当前报告标题 + AI 率 + 达标 / 超 Xpp 徽章 + 「切换」，点开报告面板；绑定报告时下方横滑高风险段 chips
- 空态：问候 + 4 张能力卡（解读报告 / 即时测一段 / 答辩准备 / 申诉指导）+「大家常问」列表
- 对话：日期分隔、助手头像、工具三态 chip、分析卡、Markdown 气泡 + 流式光标、操作行（复制 / 重新生成 / 👍 👎）、长按气泡出操作菜单、回复完成后 2 条追问建议
- 浮条：生成中「停止生成」，离底部远时「回到底部」；发送与完成有轻触感（小程序）
- 输入区：「+」工具面板（换报告 / 粘贴测一段 / 历史 / 新对话）· 自增高 textarea · 圆形发送键（生成中变停止）
- 面板：报告选择 sheet（通用咨询 + 已完成报告，带 AI 率与红线）· 粘贴检测 sheet（≥ 20 字，走助手 detect_text 出分析卡）· 历史右侧抽屉
- 数据链路不变；本地持久化 / 历史恢复 / 直达追问逻辑保留


### 上传页只做论文 + 检测结果页体验强化（web + uniapp）

**上传页**
- uniapp：`pages/upload/text.vue / audio.vue / image.vue` 删除，路由移除；tab「上传」即论文检测页（`upload.vue` 合并原三级页）。首页主 CTA 文案改论文，音频 tile 换成「论文助手」
- 新布局：大标题 + 「上传论文 / 粘贴一段」分段 → 场景横滑 chips（当前红线随动）→ 虚线投放卡（能力徽章）/ 已选文件卡（更换 / 移除）→ 「这是修改稿？」关联上一次 → 最近检测 3 条 → 底部固定 CTA（未选文件时灰态文案「先选择论文文件」）
- 粘贴模式：从剪贴板粘贴、不足 120 字提示、结果卡（校准概率 + 判定 + 一句建议 + 句级高亮 + 分支分数）+「问助手为什么」（storage 带首问进对话页）
- web：双栏，左为场景 / 拖放投放区 / 修改稿 / CTA，右为「报告里有什么」「最近检测」「怎样最不像机器」；粘贴模式同上

**结果页**
- 两端：滚过 hero 出现紧凑摘要（标题 · AI 率 · 达标 / 超线 · 问助手）；hero 加红黄绿分布条；「比上次」可点进逐段对比；锚点 tabs 概览 / 段落 / 来源
- 「先改这几段」：按贡献排前 3 的高风险段，带段号 / 概率 / 疑似来源 / 预览，点段跳转、点「为什么」直达助手
- 段落区：筛选 chips（全部 / 高 / 中 / 低 / 已排除，带计数）、全部展开 / 收起、左侧风险色条、章节名、复制、问助手
- 处理中：四步进度（上传 → 解析 → 推理 → 汇总）按已用时间推进；失败态文案细化
- web：≥ 1000px 双栏，右侧固定「来源分布 + 下一步（问助手 / 再测一次 / 申诉 / 下载）」；章节视图保留；humanize 死代码移除
- uniapp：段落预览 72 字、句级高亮图例、底部 meta 行（模型版本 / 时间 / 复核提示）

### 可解释证据链 L1（explainable-evidence-plan §5 L1 / §7）

- `ml/common/surface_features.py`：`surface_facts()` 事实读数、`document_baseline_zscores()` 文档内基线、`load_surface_baseline()` 外置基线
- `ml/datasets/text/build_surface_baseline.py`：从人类语料拟合 30 维 mean/std，产出 JSON；推理服务用 `TEXT_SURFACE_BASELINE_PATH` 挂载
- 助手 `tools.py`：三级基线（checkpoint scaler > 外置基线 > 同篇其它正文段），工具结果新增 `evidenceBasis / evidenceBasisKey / surfaceFacts`；`explain_paragraph` 把同篇其它正文段作为参考集
- `prompts.py` 规则 2：翻译 z 值必须带比较对象；无 z 值引用事实读数，不编数
- web / uniapp `AssistantAnalysisCard.vue`：表层特征标题带基线限定，底部一行事实读数
- 金标集新增 e06（问「跟谁比的」须答出比较对象）

### 营销起盘：落地页 + SEO + 第一批内容（marketing-plan §9）

- web 新增公开路由 `/` → `Landing.vue`（原 `/` 重定向到 dashboard 取消；已登录用户落地页右上「进入工作台」）
- `index.html` 补 description / keywords / og meta；FAQ 注入 schema.org FAQPage
- `docs/operation/202610-marketing-content-seeds.md`：10 个选题 + 2 篇成稿 + 发布前检查
- 竞品 gap 文档：PDF 导出 / 粘贴模式 / 改进建议卡标记已落地

### 登录 / 注册完善（三端 + 后端）

**后端**
- `LoginAttemptGuard`：按用户名连续失败 5 次锁 15 分钟（Caffeine 内存），剩余 ≤ 2 次时提示次数；成功即清零
- 验证码改为可配置强制（`platform.auth.captcha-required`，默认 true）；不带 captchaId 返回 2011「请输入验证码」
- 密码策略：6-32 位、含字母和数字、不等于用户名（注册与改密共用）；用户名限 `[A-Za-z0-9_.@-]{2,64}`
- `POST /api/v1/auth/password` 修改密码：校验原密码，成功后当前 token 作废
- `auth_user` 新增 `status`（0 停用拒登）/ `last_login_at`（V0.3.0.010，patch-schema 同步）
- token 仓储换 Caffeine，`platform.auth.token-ttl-days`（默认 7 天）闲置失效；`LoginVO.expiresIn`
- 新错误码 2007-2012

**web**
- 登录页：双栏（品牌 + 价值主张 / 表单），行内校验，密码显示切换，注册密码强度条与隐私协议勾选，记住账号，验证码加载 / 失败 / 点击刷新三态，服务端错误行内展示（锁定、验证码、停用），`?mode=register` 直达注册
- 启动用 `/me` 校验本地 token 并刷新角色；401 跳登录带 `redirect` 回原页
- 新公开页 `/privacy`；我的页加「修改密码」弹窗、隐私政策与历史报告跳转

**uniapp**
- 登录页同上（无双栏）；请求层 401 / 1401 / 2401 统一清态并记 `pending_login_redirect`，登录后回原页；App 启动 `validate()`
- 我的页「修改密码」底部 sheet；退出登录调服务端 logout

**RN**
- 登录页同上：行内校验、显示密码、强度条、协议勾选、记住账号（SecureStore）、验证码三态、键盘避让

### 后台账号管理 + 报告只读分享链接

**账号管理（auth_user）**
- `GET /admin/account/list`、`POST /admin/account/{id}/status|reset-password|role`、`POST /admin/account` 新建；停用 / 重置密码 / 改角色都会作废该用户在线 token（`IAuthTokenRepository.removeByUser`）
- 临时密码由服务端生成，只在响应里出现一次；不能停用或改自己的角色
- `PasswordHasher` 抽出共用（登录 / 注册 / 改密 / 重置）
- web 后台「用户管理」改两 tab：平台账号（真实凭据）/ 用户画像（原 demo）；重置密码与新建弹出一次性临时密码并可复制

**只读分享**
- `report_share` 表（V0.3.0.011，patch-schema 同步）：token / 任务 / 有效期 1·7·30 天 / 水印 / 浏览数 / 撤销
- `POST /api/v1/report/tasks/{id}/share`、`GET …/shares`、`POST /api/v1/report/share/{token}/revoke`；公开 `GET /api/v1/share/{token}` 返不含任务 id / 用户 / 文件信息的只读报告并计浏览
- 链接 URL 由 `platform.web.base-url`（`WEB_BASE_URL`）拼成 `/s/{token}`
- web：公开页 `/s/:token`（斜向水印、只读、底部引流），结果页「分享」按钮 → 弹窗选有效期 / 水印、生成即复制、列表可撤销
- uniapp：结果页「只读链接」→ 底部 sheet 同上，复制到剪贴板（小程序原生 open-type=share 按钮改为此入口）

### 登录页二次优化（web + uniapp）

- `username-available` 按客户端 IP 限流：`IpRateLimiter`（Caffeine 1 分钟窗口）+ `ClientIpUtils`（X-Forwarded-For 首跳 > X-Real-IP > remoteAddr），`platform.auth.username-check-per-minute` 默认 20，超限返回 2429；前端查重失败静默忽略，由注册接口兜底判重
- 逻辑：已登录直跳；验证码 5 分钟过期后禁提交并提示刷新；服务端锁定文案解析成倒计时，倒计时内禁用按钮；注册用户名实时查重（新接口 `GET /api/v1/auth/username-available`，防抖 400ms）；密码规则逐条勾选；`redirect` 只接受站内单斜杠路径（uniapp 只接受 `/pages/` 路径）；提交中屏蔽重复提交；密码错误后清空密码重输；Caps Lock 提示（web）
- 视觉：web 左栏渐变 + 光斑 + 玻璃卡价值主张 + 小白气泡，右栏白卡、滑块分段、48px 输入框聚焦光环、SVG 眼睛、验证码悬浮「换一张」、自绘复选框、渐变主按钮；uniapp 渐变头图 + 上浮白卡，同一套控件语言

### 后台用户管理页优化

- 后端：列表改 SQL 分页（count + LIMIT）、排序白名单（最近登录 / 创建时间 / 用户名）、当前页账号一次聚合 detect_task 出检测数与最近检测；新增 `GET /admin/account/stats`（总数 / 正常 / 停用 / 今日新增 / 7 日活跃 / 按角色）、`GET /admin/account/{id}`、`PUT /admin/account/{id}`（姓名 / 组织）、`POST /admin/account/batch-status`（批量停用启用，自动跳过操作者）
- web：顶部 5 张 KPI 卡 + 角色分布；筛选条 + 排序；多选批量停用 / 启用；表格头像首字母、角色色签、检测数可点、相对时间；账号详情抽屉（可编辑姓名 / 组织、角色、状态、重置密码、最近检测任务列表直达报告）；导出当前筛选结果 CSV；用户画像 demo 退为次 tab

### 后台数据页面完善（任务 / 反馈 / 大盘 / 布局）

- 任务：`AdminTaskServiceImpl` 全部条件下推 SQL（状态 / 场景 / 用户 / 标题 / AI 率区间 / 达标 / 分桶 / 模型 / 日期）+ 排序白名单 + count/LIMIT；用户标识优先 auth_user；`GET /admin/task/stats`、`POST /admin/task/batch-delete|batch-retry`。页面：状态 KPI 可点筛选、超线占比、日期 / 达标 / 模型筛选、服务端排序、多选批量重试 / 删除、行内重试 / 取消 / 删除、详情抽屉、导出 CSV、`?status=` `?userId=` 直达
- 反馈：查询加分类 / 任务 / 日期；`GET /admin/feedback/stats`、`POST /admin/feedback/batch-handle`。页面：待处理申诉优先 KPI、分类 / 状态 / 日期筛选、多选统一回复 / 置处理中 / 批量忽略、处理抽屉（原文 · 段级复核 · 5 条快捷回复模板 · handledBy 记录操作者）、新增「误判样本池」tab（结论统计 / 筛选 / 行内复核 / 导出 JSONL）
- 大盘：用户口径切 auth_user；KPI 新增超线占比、失败任务、排队中、待处理反馈，卡片可点跳转；待处理反馈列表带「处理」
- 布局：品牌换知源 logo，侧栏「用户反馈」带待处理角标

### 报告溯源凭证与真伪验证（PDF + web + uniapp）

- `detect_task` 新增 `report_no / verify_code / report_sign / signed_at / verify_count`（V0.3.0.012，patch-schema 同步）
- `ReportCredentialService`：任务完成即签发编号（`ZY-yyyyMMdd-XXXXXX`）+ 8 位验证码 + HMAC-SHA256 签名（覆盖编号 / 任务 / AI 率 / 红线 / 场景 / 模型 / 完成时间 / 字数 / 段落结果摘要）；老任务在打开详情或导出 PDF 时回填；重试后结果变化自动重签；密钥 `platform.report.sign-secret`（`REPORT_SIGN_SECRET`，默认值会打 warn）
- 公开验证 `GET /api/v1/verify/{reportNo}?code=` / `POST /api/v1/verify`：编号 + 验证码匹配才返回摘要（标题 / AI 率 / 红线 / 达标 / 模型 / 时间 / 签名指纹 / 被验证次数），签名重算不一致提示「内容与签发时不一致」；编号不存在与验证码错误同一句；按 IP 每分钟 30 次
- PDF：封面下方「报告溯源凭证」块（编号 / 验证码 / 签名指纹 / 验证方式）+ 验证页二维码；页脚改报告编号
- web：公开页 `/verify/:reportNo?`（表单 + 结果卡，扫码链接直达自动验证），结果页 hero 凭证行（复制 / 验证页 / 被验证次数），落地页导航与我的页入口，只读分享页显示编号
- uniapp：`pages/verify/verify`（输入 + 小程序扫码直填 + 结果卡），首页与我的页入口，结果页凭证行一键复制

### UI 入口三端对齐

统一入口表：首页 / 工作台 = 上传论文 · 粘贴一段 · 问小白 · 检测记录 · 验证报告；报告页 = 问小白 · 下载 PDF · 只读分享 · 申诉 · 凭证；我的 = 修改密码 · 验证报告真伪 · 意见反馈 · 隐私政策 · 退出
- web：工作台头部加导航（检测记录 / 上传论文 / 问小白 / 验证报告 / 运营后台），标题行加「粘贴一段试试」；工作台挂助手抽屉；上传页支持 `?mode=paste`
- uniapp：此前已对齐（首页 2×2 + 验证入口、我的页全部入口、报告页动作条）
- RN：补齐 `verify` / `feedback` / `privacy` / `account/password` 四个页面；记录页顶部快捷条（上传 / 问小白 / 验证报告）；我的页分组菜单；报告页动作条（问小白 / 下载 PDF / 只读分享 / 申诉）+ 凭证行 + 红黄绿分布 + 已排除段，去掉改写按钮；`api/report.ts`（PDF 地址 / 分享 / 验证 / 改密 / 反馈）；任务类型兼容 scenario

## 验证状态

- Python：`compileall` 通过；知识库 32 块可加载。未在本机起服务（无 torch / 无 LLM key / 无 numpy，`surface_facts` 与文档内基线未本机跑过，逻辑复用已有 `extract_surface_features` 与 `SurfaceScaler`）
- Java：本机 Maven 本地仓库无 Spring Boot 3.3.4，**未编译**；代码按 Java 21 / RuoYi-Vue-Plus 5.x 写法人工复核。远程跑前先执行 V0.3.0.009 / 010
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
