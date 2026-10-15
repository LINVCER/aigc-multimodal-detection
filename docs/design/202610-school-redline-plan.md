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
