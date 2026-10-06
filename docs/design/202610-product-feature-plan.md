# 论文 AIGC 检测平台 · 完整功能方案（C 端体验 + 后台管理）

> 日期：2026-10
> 范围：基于现有产品（检测 + 溯源 + 降 AIGC + 论文检测助手）的功能蓝图
> 原则：对齐 `OPERATIONS_REQUIREMENTS.md` 的「明确不做」清单；C 端做体验，运营端做可控性
> 状态：方案评审中 · 未实施

---

## 0. 现状盘点（已有 vs 缺口）

| 域 | 已有 | 关键缺口 |
|---|---|---|
| C 端 · 检测 | 上传、任务列表、报告（段落/句子高亮、溯源、红黄绿、PDF） | 无前后对比、无完成通知、无个人统计 |
| C 端 · 助手 | 对话、报告选择、历史记录（7 天）、边界硬拦截 | **分析结果仍是纯文字，未结构化可视化** |
| 后台 · 运营 | 大盘、任务、用户、反馈 4 页 | **助手运营（知识库/会话/质检）完全缺失**；阈值/模型/误判无管理界面 |

**核心判断**：C 端缺「体验纵深」（报告与助手融合、对比、通知），后台缺「助手运营闭环」——而助手恰恰是当前投入最大、却最不可运营的一块。

---

## 1. 设计原则

1. **C 端做「看懂」，不做「代写」**：一切功能帮用户理解报告、证明原创，边界与降 AIGC 待定一致。
2. **后台做「可控」**：运营能改知识、看对话、调阈值、跟模型、处理申诉——**但不改用户报告结论**（无 override）。
3. **复用已落库的数据**：`knowledge_chunk`、`assistant_log`（含 `boundary_type`）、`assistant_conversation`、`detect_scenario_threshold`、`model_version`、`user_abnormal_flag`、`user_feedback`——表都建了，缺的是界面。
4. **分期**：先做「助手运营 + 分析卡」（当前主线），再做「对比 + 通知」，最后做「模型灰度 + 误判闭环」。

---

## 2. C 端用户体验（新功能）

### 2.1 助手结构化分析卡（P0，体验纵深）

**问题**：`explain_paragraph` 返回了概率、表层特征 z-score、溯源、句子级打分，但助手只用文字描述，信息被「翻译」损失。

**设计**：当助手调 `explain_paragraph` / `get_task_detail` 后，气泡内嵌一张**分析卡**：

```
┌─ 段 3 · 疑似 AI ─────────────┐
│ 校准概率 87%  ████████░░ [红]  │
│ 疑似来源  通义千问 · 置信区间 0.80–0.94 │
│ 表层特征                       │
│  · 句长变化 z=-1.6 → 句子很「平」  │
│  · 套话连接词 z=+2.1 → 模板感强   │
│  · 用词丰富度 z=-0.9 → 词汇重复    │
└──────────────────────────────┘
```

**实现**：`tool_result` 事件目前只带 `summary`，需扩展为**携带完整数据**（段落概率/表层特征/句子级）；前端把 `tool_result` 的结构化数据渲染成卡片，助手文字作为「翻译」。

### 2.2 对比检测（重写前后）

**对齐**：GPTZero 的 [Compare with AI Text](https://gptzero.me/news/inside-our-new-compare-with-ai-text-tool/)。

**设计**：用户重写后再次检测，报告页给「对比视图」：

- 同一论文的两个版本并排：AI 率从 26.4% → 9.2%；
- 变化的段落标绿（降了）/ 标红（反而涨了）；
- 一句话结论：「重写了 8 段，整体 AI 率下降 17.2pp，已低于红线」。

**数据**：`detect_task` 加 `compare_to_task_id`，或前端按 `paperTitle` 分组最近两次检测。**不需要新表**，复用任务列表按标题聚合即可。

### 2.3 检测完成通知

**问题**：检测是同步的（当前），但前端要 4s 轮询；未来异步化后必须通知。

**设计**：
- Web：任务完成 → 页面内 toast + 列表红点；
- 微信小程序：订阅消息「检测完成，AI 率 X%，点击查看」；
- 站内信（若依 `sys_notice` 已有）。

**数据**：复用 `detect_task.finishedAt`，触发时发通知。

### 2.4 个人中心（历史统计 + 额度）

**设计**：
- 我的检测：累计次数、平均 AI 率、达标率、30 天趋势（复用 `getStatistics`）；
- 额度（若做付费）：余额、消费明细——**暂缓**（`TEAM_ROLES` 明确「不做收费」）。

---

## 3. 后台管理（新功能，重点）

### 3.1 助手运营后台（P0，当前最缺）

| 子模块 | 功能 | 支撑 |
|---|---|---|
| **知识库管理** | `knowledge_chunk` 增删改查 + 「重新加载」按钮；分块内联编辑正文/标签/上下线 | 表已建 + `/knowledge/reload` 已实现 |
| **对话质检** | 抽样看 `assistant_conversation` 完整对话；标注「回答质量」 | 表已建 |
| **越界告警看板** | `assistant_log` 按 `boundary_type` 统计（代写/绕过/编申诉 各多少）；`boundary_flag=1` 的对话一键定位 | `boundary_type` 已落库 |
| **意图分布** | `intent` 分布（explain/policy/guide/appeal/rewrite_request…），识别「改写请求占比」——作为 humanize 是否重启的依据 | `intent` 已落库 |
| **快捷问题配置** | 欢迎语 + 快捷问题（`quick-prompts`）运营可改 | 需加配置表或复用 `sys_config` |

### 3.2 检测运营

| 子模块 | 功能 | 支撑 |
|---|---|---|
| **场景阈值配置** | 6 场景红线（本科20/硕士15/博士10/职业15/自媒体30/其他25）运营可调，改动实时生效 | `detect_scenario_threshold` 已建 |
| **模型灰度** | `model_version` 列表 + 激活/回滚 + 版本对应的评测指标 | 表已建，需补界面 |
| **误判率分析** | 申诉「认定合理」占比 → 按场景/模型维度看误判率 → 导出模型改进 backlog | `user_feedback` 的 appeal 分类 + 处理状态 |

### 3.3 用户运营

| 子模块 | 功能 | 支撑 |
|---|---|---|
| **申诉处理工作流** | 申诉关联完整报告（已有）+ 「标注申诉合理」按钮（记入模型 backlog，**不改报告结论**） | `user_feedback` + `detect_task` |
| **异常账号** | `user_abnormal_flag` 的 SUSPICIOUS 列表 + 一键封禁 + 关联任务 | 表已建，缺界面 |

---

## 4. 数据模型 / 接口增量

**新增表**（少量）：

| 表 | 用途 |
|---|---|
| `assistant_quality_note` | 对话质检标注（conversation_id + 评分 + 备注 + 运营人） |
| （可选）`quick_prompt_config` | 欢迎语/快捷问题运营配置；或直接复用若依 `sys_config` |

**接口增量**（`/admin/**`，若依 Sa-Token）：

| 接口 | 对应功能 |
|---|---|
| `GET/POST/PUT/DELETE /admin/knowledge/chunks` + `POST /admin/knowledge/reload` | 知识库管理 |
| `GET /admin/assistant/logs`（含 boundary_type/intent 筛选）· `GET /admin/assistant/conversations/{id}` | 越界看板 + 对话质检 |
| `GET/PUT /admin/threshold` | 场景阈值配置 |
| `GET /admin/model/versions` · `POST /admin/model/versions/{id}/activate` | 模型灰度 |
| `GET/POST /admin/abnormal-users` | 异常账号 |
| `POST /admin/feedback/{id}/mark-reasonable` | 申诉「认定合理」→ 记 backlog |

> 大部分接口在 `API_CONTRACT.md §6.2` 已规划（`/admin/threshold`、`/admin/model/versions`、`/admin/detect/tasks/{id}/override` 中的 override 已砍），只差实现与落库。

---

## 5. 路线图（三期）

| 期 | 主题 | 内容 |
|---|---|---|
| **P0 · 助手闭环** | 助手运营后台 + 结构化分析卡 | 知识库管理、越界看板、对话质检、分析卡 |
| **P1 · 体验纵深** | 对比检测 + 完成通知 + 个人统计 | 复用任务数据，纯前端为主 |
| **P2 · 运营可控** | 阈值配置 + 模型灰度 + 误判闭环 | 依赖模型 v0.2.0 训练产出后启用灰度 |

---

## 6. 需要你拍板

1. **P0 范围**：助手运营后台（知识库管理 + 越界看板 + 对话质检）三件，是否作为第一批？
2. **分析卡**：`tool_result` 扩展携带完整数据（前后端联动）——同意吗？还是先只做纯前端（把助手文字排版得更像卡片）？
3. **对比检测**：复用「按标题分组最近两次」的轻量方案（不加表），还是加 `compare_to_task_id` 字段做显式对比？
