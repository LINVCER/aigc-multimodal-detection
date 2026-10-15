# 学校红线：用户选学校 + 公开查询表

> 2026-10 · 状态：方案，待拍板三项（§9）后开工。
> 关联：`202610-product-feature-plan.md`（场景阈值现状）、`202610-marketing-plan.md` 方向 A / D、`202610-web-visual-style-prompt.md`（文案与视觉规则）。

## 0. 为什么做

- 学生在群里问得最多的是「我们学校 AI 率要求多少」，目前产品只按六个场景给通用红线，报告上写的「低于红线」缺少说服力。
- 把学校做成实体后：报告文案能写成「低于北航硕士红线 15%」；小白回答能带学校上下文；公开查询页天然是 SEO 与分享入口；用户上报形成数据众包，收录越多越难被替代。
- 不代写、不改写的边界不变，这里只做「标准是什么」。

## 1. 现状

| 项 | 现状 |
|---|---|
| 用户 | `auth_user.org_name` 自由文本，可空，无学位字段 |
| 红线 | `detect_scenario_threshold`：academic_bachelor 20 / master 15 / phd 10 / job_report 15 / self_media 30 / other 25 |
| 提交 | `POST /detect/submit` 带 `scenario`、`degreeType`，服务端按场景取阈值写进任务 |
| 前端 | Upload 页场景横滑 chips；报告页 `threshold` 直接显示数字 |

## 2. 数据模型

### 2.1 学校 `edu_school`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | |
| name | VARCHAR(128) | 全称，唯一 |
| short_name | VARCHAR(32) | 短名 |
| aliases | JSON | 别名数组，如 `["北航","BUAA"]` |
| province | VARCHAR(32) | |
| level | VARCHAR(16) | undergrad / vocational / graduate_school |
| logo_url | VARCHAR(256) | 可空 |
| status | VARCHAR(16) | active / hidden |
| created_at / updated_at | DATETIME | |

初始化：教育部全国高校名单一次性导入（约 3000 所），只填 name / short_name / province / level。

### 2.2 红线规则 `edu_school_rule`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | |
| school_id | BIGINT | FK edu_school |
| college | VARCHAR(64) | 学院，NULL 表示全校 |
| degree_type | VARCHAR(16) | bachelor / master / phd |
| ai_rate_limit | DECIMAL(5,2) | AI 率红线，% |
| plagiarism_limit | DECIMAL(5,2) | 查重率红线，可空 |
| platform | VARCHAR(32) | 学校使用的检测平台：cnki / vip / wanfang / gezida / other |
| source_type | VARCHAR(16) | official / user / inferred |
| source_url | VARCHAR(512) | 官方文件链接或上报截图地址 |
| effective_year | SMALLINT | 适用届别 |
| confidence | TINYINT | 0-100，官方 100，用户上报按一致条数累加 |
| status | VARCHAR(16) | pending / published / rejected / stale |
| reported_by | BIGINT | 上报用户，可空 |
| verified_by / verified_at | BIGINT / DATETIME | 审核人与时间 |
| created_at / updated_at | DATETIME | |

索引：`(school_id, degree_type, status)`、`(status, created_at)`。同一学校同一学位可多条：学院级优先于全校级，published 优先于其它。

### 2.3 现有表增量

- `auth_user` + `school_id BIGINT NULL`、`degree_type VARCHAR(16) NULL`；`org_name` 保留做兼容与展示兜底。
- `detect_task` + `school_rule_id BIGINT NULL`、`rule_label VARCHAR(64) NULL`（如「北航 · 硕士」），规则日后修改不影响历史报告的解释。

## 3. 红线解析顺序

提交检测时服务端按下面顺序取第一条命中的：

1. 用户在上传页显式改选的场景（保留现有能力）
2. `edu_school_rule`：school_id + college + degree_type，published
3. `edu_school_rule`：school_id + degree_type，published，college 为空
4. `detect_scenario_threshold` 场景默认

命中第 4 条时任务 `rule_label` 写「通用标准」，报告页提示「你学校的红线还没收录」并给上报入口。

## 4. 用户侧

### 4.1 选学校的时机

- **注册完成后独立一步**，不进注册表单。标题「你在哪所学校？」，搜索框支持别名；下面学位三选一。可跳过。
- **上传页**：已选学校的用户，场景 chips 行替换为一张卡「北航 · 硕士 · 红线 15%」+「换」；未选的保持原六个场景，卡片右侧放一行「选学校后按你学校的标准算」。
- **个人中心**：可改学校与学位，改后只影响新任务。
- **报告页**：达标文案改为「低于北航硕士红线 15%」/「超过北航硕士红线 2.4 个百分点」；通用标准时保留现文案并加上报入口。
- **小白**：回答时注入 `school / degree / rule` 上下文，例如「你们学校盲审前要求 ≤15%，初稿这个数还有余量」。

### 4.2 公开查询页

- 路由 `/schools`（列表，按省份、层次筛，搜索带别名）与 `/schools/:id`（详情）。不登录可看。
- 详情页：各学位红线、查重率、检测平台、来源链接、最后核实时间；底部 CTA「用这个标准测一篇」直达上传并预填学校。
- 未收录学校：显示「暂无官方数据，按教育部通用口径」+ 上报入口。
- SEO：`<title>` 形如「XX大学 2026 毕业论文 AI 率要求」，详情页注入 FAQ 结构化数据。

### 4.3 文案规则

沿用 style-prompt：口语、不用「您 / 请勿 / 提交」；上报按钮写「告诉我们」；审核通过后给上报人一条小白消息「你报的北航硕士红线核实了，已经上线」。

## 5. 数据来源与维护

| 来源 | 流程 | source_type |
|---|---|---|
| 官方文件 | 运营从研究生院 / 教务处通知录入，必须带 source_url | official |
| 用户上报 | 表单填数值 + 学位 + 截图或链接 → pending → 后台审核发布 | user |
| 推断默认 | 不建规则，前端标注「通用口径」 | — |

- 同一学校同一学位三条以上数值一致的 pending 上报，confidence 自动加到 80 并置顶审核队列。
- published 规则满一年自动置 stale，列表显示「待复核」，不下线。
- 首批人工录入 50 所目标用户最多的学校（见 §9 决策一）。

## 6. 接口增量

| 接口 | 用途 |
|---|---|
| `GET /api/v1/schools?q=&province=&level=` | 学校搜索（name / short_name / aliases） |
| `GET /api/v1/schools/{id}` | 学校详情 + published 规则 |
| `POST /api/v1/schools/{id}/rules/report` | 用户上报，需登录 |
| `PUT /api/v1/me/school` | 设置 school_id / degree_type |
| `GET /api/v1/me/rule` | 当前用户生效的红线（上传页卡片用） |
| `GET /api/v1/admin/school-rules?status=` | 后台审核列表 |
| `PUT /api/v1/admin/school-rules/{id}` | 审核、编辑、发布、驳回 |
| `POST /api/v1/admin/schools/import` | 高校名单导入 |

`POST /detect/submit` 参数不变；`DetectTask` 响应增加 `ruleLabel`、`schoolRuleId`。

## 7. 后台

运营后台新增「学校与红线」菜单：学校列表（搜索、隐藏）、规则审核队列（pending 优先，显示上报数与一致性）、规则编辑（来源、年份、学院）、上报记录。KPI：已收录学校数、published 规则数、待审核数、选了学校的用户占比。

## 8. 分期

| 期 | 内容 | 涉及 |
|---|---|---|
| 一 | 两张表 + auth_user / detect_task 增列；高校名单导入；注册后选学校；上传页与报告页显示学校红线；后台录入；首批 50 所 | SQL、ruoyi-detect、web、mobile-uniapp |
| 二 | 公开查询页 + SEO；用户上报与审核队列；上报人通知 | web、后台 |
| 三 | 学院级规则；stale 复核；小白注入学校上下文；查询页分享卡 | assistant、web |

## 9. 待拍板

| 决策 | 选项 | 建议 |
|---|---|---|
| 一 · 学校列表来源 | A 教育部名单一次性导入 3000 所 / B 先手工录 50 所，搜不到就上报 | A，搜不到会直接流失；50 所只是红线数据的首批 |
| 二 · 未选学校的用户 | A 首次上传强制选一次 / B 不强制，用报告页提示引导 | B，减少首次检测的阻力 |
| 三 · 收录范围 | A 只收 AI 率 / B 连查重率与检测平台一起收 | B，录入成本相同，查询页价值翻倍 |

## 10. 验收

1. 选了学校的用户，上传页和报告页显示带学校名的红线，任务记录 `rule_label`。
2. 规则解析按 §3 顺序，单测覆盖四级回退。
3. `/schools/:id` 不登录可访问，未收录学校有上报入口。
4. 后台能审核上报并发布，发布后前端即时生效。
5. 文案无「您 / 请勿 / 提交」。

---

# 11. 爬虫接入与按需爬取闭环（highschool-spider）

数据从哪来：`tools/highschool-spider/`（礼貌版爬虫，仅爬高校公开通知页，遵守 robots、限速限页、只读 HTML）。
四张表见 `docs/releases/v0.3.0/sql/V0.3.0.014__init_school_redline.sql`：
`edu_school`（学校）、`edu_school_rule`（已发布规则）、`edu_school_rule_candidate`（爬虫候选 = 审核队列）、`edu_school_crawl_seed`（爬取种子）。

## 11.1 两条数据通道

- **批量离线**：运营拿目标学校清单跑 `spider.py`，`to_sql.py` 转成 `edu_school_rule_candidate` 的 INSERT，上库进审核队列。首批 50 所走这条。
- **按需触发**（用户填学校后）：见 §11.2。

## 11.2 按需爬取闭环（用户填学校 → 触发 → 爬取 → 转化 → 入库 → 生效）

借 spider-v2 的 task + worker 模型，把爬虫做成一个可被后台触发的异步作业，而不是只有 CLI：

```
用户在 App/Web 填「我是北航·硕士」 (PUT /me/school)
        │
        ▼
后台解析该校红线：命中 published 规则？
  命中 → 直接返回，报告按校红线算（闭环结束）
  未命中 → 若该校有 crawl_seed 且近 N 天未爬 → 投一个爬取任务 crawl_job(school_id)
        │
        ▼
爬虫 worker 领任务：按 seed.entry_url 跑 highschool-spider（限速礼貌），产出候选
        │
        ▼
候选转化入 edu_school_rule_candidate（status=pending）
        │
        ├─ 高置信直通（见决策四）：confidence≥90 且同校同学位同指标无冲突 → 自动合并成 edu_school_rule(status=published, source_type=user_triggered)
        └─ 否则留审核队列，前端先给用户「通用口径」并提示「你学校的红线我们正在收录，核实后通知你」
        │
        ▼
规则落库后：① 该用户下次检测按校红线算；② 转成知识库块供小白检索（§14）；③ 若之前给了通用口径，推一条小白消息「北航硕士红线核实了，15%」
```

关键约束：
- 爬虫作业**全局限频**（每校最多每 7 天触发一次，整体并发 1~2），避免用户一填学校就猛爬；触发只入队，不同步等结果。
- 用户侧**绝不阻塞**：填完学校立即返回通用口径或已有规则，爬取是后台补齐，异步通知。
- 爬虫 worker 本身不写 `edu_school_rule`，只写候选；是否自动发布由转化层按决策四定。

## 11.3 作业载体

一期可不引入独立服务：后台用一张 `crawl_job` 轻表（或复用现有异步任务机制）+ 一个定时/队列 worker，worker 内部 `subprocess` 调 `spider.py --seeds <临时单校种子> --out <临时目录>` 再读 `candidates.csv` 转化入库。
二期若量大，再把 highschool-spider 拆成常驻服务（对齐 spider-v2 的 uvicorn + worker + HTTP 提交），后台只投任务。

# 12. 后台管理页面（运营后台新增「学校红线」）

三个 tab，对应你要的「管理爬取的高校」+「数据维护」：

| tab | 功能 |
|---|---|
| 学校 | `edu_school` 列表：搜索、按省/层次筛、新增/编辑/隐藏；显示每校已发布规则数与待审候选数 |
| 爬取种子 | `edu_school_crawl_seed` 列表：维护 entry_url / adapter / 开关；「立即爬取」按钮投一个 crawl_job；显示 last_crawl_at / last_status |
| 数据维护 | `edu_school_rule_candidate` 审核队列（pending 优先、按 confidence 降序）：每条显示 snippet + 打开 source_url；操作「合并发布」「驳回」「改学校/学位」；已发布 `edu_school_rule` 列表可编辑/下线/标 stale |

KPI：已收录学校数、published 规则数、待审候选数、选了学校的用户占比、近 7 天触发爬取数。
页面与现有 admin 风格一致（已按知源小白主题改过），按钮不用 pill，候选置信度用语义色标签。

# 13. 预留接口清单

C 端 / 公开（§6 已列的基础上补全）：

| 接口 | 用途 |
|---|---|
| `PUT /api/v1/me/school` | 用户设学校+学位；内部触发 §11.2 的红线解析与按需爬取 |
| `GET /api/v1/me/rule` | 当前用户生效红线（上传页卡片/报告页） |
| `GET /api/v1/schools?q=&province=&level=` | 学校搜索（含别名） |
| `GET /api/v1/schools/{id}` | 学校详情 + published 规则（公开查询页） |
| `POST /api/v1/schools/{id}/rules/report` | 用户上报红线 |

后台：

| 接口 | 用途 |
|---|---|
| `GET /api/v1/admin/schools` `POST/PUT /.../{id}` | 学校 CRUD |
| `POST /api/v1/admin/schools/import` | 高校名单批量导入 |
| `GET/POST/PUT /api/v1/admin/crawl-seeds` | 爬取种子维护 |
| `POST /api/v1/admin/crawl-seeds/{id}/run` | 立即投爬取任务（返回 jobId） |
| `GET /api/v1/admin/crawl-jobs?status=` | 爬取任务状态 |
| `GET /api/v1/admin/rule-candidates?status=` | 候选审核队列 |
| `POST /api/v1/admin/rule-candidates/{id}/merge` | 合并发布为 edu_school_rule |
| `POST /api/v1/admin/rule-candidates/{id}/reject` | 驳回 |

爬虫 worker ↔ 后台（内部，预留）：

| 接口 | 用途 |
|---|---|
| `POST /internal/crawl-jobs/claim` | worker 领任务 |
| `POST /internal/crawl-jobs/{id}/result` | 回传候选（等价 to_sql 的入库动作，带内部鉴权） |

# 14. 知识库转化（edu_school_rule → knowledge_chunk）

规则发布后，同步镜像一条知识块进 `knowledge_chunk`（现有助手知识库，推理服务启动全量载入 + 运营可编辑）：

- `doc = school-redline`，`title = "<学校短名>-<学位>红线"`（如「北航-硕士红线」），`tags = 学校名,别名,学位,AI率,查重`
- `body` 用口语模板拼：「北京航空航天大学 硕士学位论文：AIGC 率不超过 15%，查重率不超过 15%，用知网检测；来源：<source_url>，2026 届。」
- `enabled` 跟随规则 status；规则改/下线时同步刷新或下线对应块。

好处：小白的既有 `search_knowledge` 工具不用改就能答「北航硕士查重多少」，而精确结构化回答走 §15 的专用工具。

## 14.1 转化触发

规则 `merge/publish` 时在 service 层同步 upsert knowledge_chunk（`uk_doc_title` 保证幂等）；下线/stale 时置 `enabled=0`。

# 15. 小白接入

两条路径互补：

1. **结构化专用工具 `get_school_policy`**（预留，优先）：入参 `school`(可空，默认取当前用户的 school_id) + `degree`(可空)，返回 `{ai_rate_limit, plagiarism_limit, platform, effective_year, source_url, resolved_label, source_type}`。命中 published 规则时小白直接口语回答并给来源；未命中时回「还没收录，我帮你记下来去查」，并触发 §11.2 的按需爬取。
2. **知识库兜底**：§14 的镜像块让 `search_knowledge` 也能召回，用于模糊问法（「航空航天大学那个要求」）。

上下文注入：用户已设学校时，助手系统提示带上「当前用户：北航·硕士，红线 AI 15% / 查重 15%」，让小白所有回答自带校情，不必每次调工具。

工具实现位置与现有 `get_threshold_policy` / `search_knowledge` 同层（推理侧工具执行 + Java 侧 `AssistantServiceImpl` 审计），新增 `get_school_policy` 走同一注册路径。

# 16. 构建顺序（代码分批，均不本地构建，静态检查后分批提交）

1. SQL 迁移（已出 `V0.3.0.014`）+ highschool-spider 爬虫与候选转 SQL（已出，带自测）。
2. Java：`edu_school` / `edu_school_rule` / `candidate` / `crawl_seed` 实体 + mapper + service + 后台 controller（§12/§13）。
3. Java：`PUT /me/school` 红线解析 + 按需触发 + `crawl_job` worker（§11.2）+ 规则→知识块转化（§14）。
4. Web 后台「学校红线」三 tab（§12）；C 端选学校、上传页/报告页按校红线、公开查询页（§4）。
5. 小白 `get_school_policy` 工具与上下文注入（§15）。

# 17. 待拍板（补充）

| 决策 | 选项 | 建议 |
|---|---|---|
| 四 · 按需爬取的候选是否自动发布 | A 高置信(≥90、无冲突)直通发布，其余人工 / B 一律人工审核 | A，否则「填完学校马上要看红线」的闭环断在人工环节；A 也保留冲突与低置信走人工 |
| 五 · 爬虫作业载体 | A 一期 subprocess 调 CLI + 轻 crawl_job 表 / B 直接上常驻服务（对齐 spider-v2） | A，先跑通闭环，量大再拆服务 |

## 11.4 一校一适配器的操作流程（运营/研发）

爬取不是对所有学校盲爬一套，而是**一校一确认、一校一脚本**（对齐 spider-v2 的 platforms/<name>/）：

1. 人工去该校研究生院/教务处确认：检测通知在哪个栏目、阈值在正文还是附件红头文件、用什么平台、适用哪些学位；
2. 复制 `tools/highschool-spider/adapters/example_school.py` 为 `<school>.py`，改入口与跟进规则，特殊结构再覆盖 `extract`；
3. 注册进 `adapters/__init__.py` 的 `_REGISTRY`；
4. 先单校跑 `spider.py --deep` 验证候选，OK 再提交爬取器（批量或 §11.2 按需触发）。

`edu_school_crawl_seed.adapter` 字段记录每所学校用哪个适配器；没写专属适配器的学校走 `generic` 兜底。
后台「爬取种子」tab 维护 entry_url 与 adapter，「立即爬取」即把该校提交到爬取器。

---

# 18. 决策已定（2026-10-15）

| 决策 | 定稿 | 影响 |
|---|---|---|
| 学校名单来源 | **先手录 50 所**（全量导入延后） | §5 首批 50 所人工录入；`edu_school` 不做 3000 全量，搜不到走上报 |
| 按需爬取候选 | **一律人工审核，必带原文地址** | §11.2 去掉「高置信直通发布」分支；候选只产 `pending`，发布全在后台人工，`source_url` 强制非空 |
| 爬虫作业载体 | **定时批量，不常驻**（每 2~5 天刷新；2026-10-15 修订，原「常驻服务」改回） | highschool-spider `schedule.py` 交计划任务每 2~5 天跑；service/ FastAPI 保留但仅后台「立即爬一所」时临时起，不 7×24 在线 |

§11.2 的闭环据此简化：用户填学校未命中规则 → 后台投爬取任务 → 服务产候选（pending）→ 后台人工核对 source_url 发布 → 规则生效并转知识库 → 通知用户。中间**不自动发布**，用户侧先给通用口径兜底。

# 19. 常驻爬虫服务（已实现并自测）

`tools/highschool-spider/service/`（FastAPI，对齐 spider-v2 的 app + worker + 队列）：

- `app.py`：`POST /api/v1/crawl` 投任务、`GET /api/v1/crawl/{id}` 查状态、`GET /api/v1/candidates?status=pending` 拉候选、`GET /health`；lifespan 内起后台 worker 线程。
- `worker.py`：领 queued 任务 → 跑 highschool-spider（共享 Politeness 限速）→ 候选落库。
- `store.py`：SQLite 持久化 job 与候选；候选强制 `source_url`、只写 `pending`；重启把 running 任务回 queued 重跑。
- 离线冒烟 `service/smoke_test.py` 通过：selftest 任务 → job done → 6 候选均 pending 且带 source_url。

后台集成契约：Java 侧 `PUT /me/school` 未命中规则时 `POST /api/v1/crawl` 投任务（带 school_id / entry_url / adapter，entry_url 取 `edu_school_crawl_seed`）；定时或回调拉 `GET /api/v1/candidates` 入 MySQL 审核队列；全局限频（每校 7 天一次）在后台投递侧控制。


# 20. 运行方式修订（2026-10-15）

红线几乎不变，无需常驻。默认走 `tools/highschool-spider/schedule.py`：计划任务每 2~5 天刷新一次种子清单，跳过近 N 天已爬的学校，候选去重后进人工审核队列。常驻 FastAPI 服务（§19）降级为可选：仅后台「立即爬取某校」时临时拉起处理单个任务，用完即停，不必 7×24 在线。
按需爬取闭环（§11.2）相应放宽：用户填学校**不**触发实时爬取，直接给已发布规则或通用口径兜底；新学校的红线靠定时批量补齐，核实发布后再通知用户。
