# AI 助手增长闭环方案（能力飞轮 + 用户回路）

> 日期：2026-10 · 修订：2026-10-07
> 范围：让论文检测助手「越用越强」——知识、边界、提示词、模型四个层面持续迭代（§1-§4 能力飞轮），并让助手把「看完报告就走」变成「知道下一步做什么」（§5 用户回路）
> 前置（已在 `agent` 分支落地）：知识库入库 `knowledge_chunk` · 对话落库 `assistant_log` / `assistant_conversation` · 边界类型化 `boundary_type` · 硬拦截 `HARD_BLOCK_INTENTS`
> 状态：方案评审中 · P0 数据层已落地（kb_top_score/kb_top_ref 落库、结束语规则、golden set 40 条 + eval_golden.py、/admin/assistant/knowledge-gaps 与 /stats）；缺口列表界面与「转成知识」待 product-feature-plan
> 定位：本篇是闭环**总纲**，只定义回路、信号、指标与分期。界面与表结构细节交给姊妹方案：知识库管理 / 越界看板 / 对话质检 → `202610-product-feature-plan.md` §3.1；知识分点与边界规则 → `202610-assistant-boundary-knowledge-plan.md`；检索升级 → `202610-knowledge-base-retrieval-plan.md`；申诉合理率看板 → `202610-detect-analytics-plan.md` §2

---

## 0. 核心：增强闭环（飞轮）

```
   ┌──────────────────────────────────────────────┐
   │  数据收集：对话(assistant_log/conversation)    │
   │           反馈(user_feedback)  申诉(appeal)    │
   └──────────────────────┬───────────────────────┘
                          ▼
   ┌──────────────────────────────────────────────┐
   │  洞察：知识缺口 · 边界误伤 · 答非所问 · 高频问题  │
   └──────────────────────┬───────────────────────┘
                          ▼
   ┌──────────────────────────────────────────────┐
   │  改进：补知识块 · 调边界规则 · 改提示词 · 记backlog│
   └──────────────────────┬───────────────────────┘
                          ▼
   ┌──────────────────────────────────────────────┐
   │  验证：评测集(golden set) 回归 → 指标提升 → 上线  │
   └──────────────────────────────────────────────┘
```

一句话：**从对话里挖「该补什么」，补完用评测集验证「有没有变好」，再回到对话继续挖。**

每条回路都要有三样东西：**信号怎么取、改什么、用什么数证明变好了**。下面每节按这三样写。

---

## 1. 知识飞轮（P0，最可落地）

### 1.1 挖缺口：信号定义

**「知识没覆盖」不能用「检索返回空」判断。** `KnowledgeBase.search` 走倒排索引，只要问题里任何一个词在任何块里出现过就会返回 top-k，分数再低也算命中；真正返回空的只有纯闲聊或全是未登录词的情况。所以信号改为**命中分数**：

`agent.py` 的 `done` 事件带出本轮检索结果：

```json
{ "kbTopScore": 2.31, "kbTopRef": "03-policy-thresholds#红线比较的是什么数", "kbHits": 3 }
```

Java 落库到 `assistant_log` 新字段 `kb_top_score DECIMAL(6,3)` 与 `kb_top_ref VARCHAR(160)`。

缺口判定：

| 条件 | 说明 |
|---|---|
| `intent IN ('policy','guide','other')` | 只看该走知识库的意图；explain 走工具、chitchat / history 不需要知识，纳入只会制造噪音 |
| `kb_top_score < T` 或 `kb_top_ref IS NULL` | T 先取 1.0，跑两周看分布后再定（BM25 分数无量纲，必须用数据定） |
| 同会话内相同 `intent` 连续出现 ≥ 2 次 | 第一次没答到点上，追问了 |

三个条件任一命中即进「候选缺口」。

### 1.2 看缺口：后台「知识缺口」列表

运营筛候选缺口，按问题粗聚类（`LEFT(question, 30)` 分组即可，不上向量），得到「用户常问、但知识库没有」的清单：

```
问：「查重和 AIGC 检测有什么区别」  → top 分 0.4 → 应补「与查重的区别」
问：「英文论文怎么判」              → top 分 0.0 → 应补「英文场景说明」
```

界面归 `product-feature-plan` §3.1「知识库管理」；本篇只要求列表能按上述三个条件筛、能看原问题与当时的 `kb_top_ref`。

### 1.3 补知识：一键落地

运营在缺口列表点「转成知识」→ 预填标题 / 正文草稿 → 保存进 `knowledge_chunk` → 调 `POST /api/v1/assistant/knowledge/reload` 热加载，不用发版。

### 1.4 验证

补块后把该问题加进 golden set「知识问答」类（§4），跑一遍确认 `kbTopRef` 命中新块。

**指标**：知识命中率 = `kb_top_score ≥ T` 的占比（分母限定 policy / guide / other 三类意图）；重复追问率 = 同会话相同意图连续出现的会话占比。目标：命中率四周内提升 20 个百分点，重复追问率下降一半。

---

## 2. 反馈飞轮

| 反馈类型 | 来源 | 处理 | 反哺 |
|---|---|---|---|
| bug | `user_feedback`(bug) | 修 | 无 |
| suggestion | `user_feedback`(suggestion) | 采纳 / 搁置 | 转知识块 / 转需求 |
| appeal 认定合理 | 申诉复核「标注合理」 | 进误判样本池 | **评测集**（§2.2），训练用途另议 |
| 对话质检差评 | 质检标注（§3） | 定位问题 | 调知识 / 边界 / 提示词 |

### 2.1 申诉样本为什么只进评测、不直接进训练

用户主张「这段是我自己写的」不可信：既有真误判，也有确实用了 AI 又想翻案的。直接当负样本重训，等于让用户给模型标注，一批有偏样本就能把阈值拉偏。所以：

1. 运营复核 `confirm_fp` 后才算样本；
2. 先只进评测集，作为「每版 checkpoint 必过的申诉集」，报 FPR@申诉集；
3. 攒到 200+ 条复核样本、且申诉集 FPR 与六套公开评测集趋势一致，再讨论进训练。

### 2.2 申诉样本必须到段级、且要解决原文过期

现状两处断点：`user_feedback` 只有 `task_id` 没有段号；`FeedbackSheet` 与 `tools.create_appeal` 都不带 `paragraphIdx`。而原文 30 天删除，运营复核时段落文本可能已不在。

| 改动 | 内容 |
|---|---|
| `user_feedback` 加 `paragraph_idxs JSON` | 申诉时勾选「哪几段判错了」；`create_appeal` 工具同步带段号 |
| 新表 `detect_hard_sample` | `task_id / paragraph_idx / text_sha256 / text(可空) / model_prob / model_version / user_label / ops_verdict / source / scenario / created_at / reviewed_at`；`UNIQUE(text_sha256, model_version)` |
| `text` 只在用户勾选「同意用于改进模型」时快照 | 否则只存 hash + 概率，仍能做「同段再出现是否还误判」的回归，但不能重训 |
| 复核 | 归 `product-feature-plan` 的「申诉处理工作流」：`POST /admin/feedback/{id}/mark-reasonable` 写 `ops_verdict` |
| 导出 | `ml/datasets/export_feedback_set.py`：`ops_verdict IN (confirm_fp, confirm_tp)` → `ml/datasets/feedback/appeal-{date}.jsonl`，字段对齐六套评测集；`ml/evaluation` 加第七套 |

**指标**：申诉率 = 申诉数 / DONE 任务数；复核成立率 = confirm_fp / 已复核；申诉集 FPR。成立率高说明模型问题，低说明用户教育问题，分别回到 §2 与 §1。

---

## 3. 质检飞轮

运营抽样看 `assistant_conversation` 完整对话，标注每条回答：

| 标注 | 含义 | 触发改进 |
|---|---|---|
| 答得好 | 正常 | 无 |
| 答错了 | 事实 / 数据错 | 查工具返回 → 修工具或知识 |
| 没答到点上 | 知识没覆盖 / 检索偏了 | 补知识块 |
| 越界了 | 漏网的代写 / 绕过 | 收紧 `BOUNDARY_RULES` / `_INTENT_RULES` |
| 太啰嗦 / 太冷 | 语气问题 | 调提示词 |

落 `assistant_quality_note`（`conversation_id / log_id / score / tag / note / reviewer / created_at`），后台统计各类问题占比。

抽样规则：每周 30 条，其中 `boundary_flag = 1` 的全抽，其余按意图分层随机。

**隐私**：运营看完整对话属于「服务改进」用途，隐私政策要写明「对话内容可能被人工抽样审阅以改进服务」，审阅界面对 `user_id` 脱敏。

**指标**：越界率 = `boundary_flag = 1` 占比，目标 0；软标记误伤率 = 质检标「越界」为假阳性的比例（`BOUNDARY_RULES` 是正则，会误伤「可以改为」这种普通表述）。

---

## 4. 评估飞轮（量化「有没有变强」）

### 4.1 golden set

固定评测集，按核心能力分四类：

| 类 | 示例 | 判分项（可自动判定，不比对文本） |
|---|---|---|
| 知识问答 | 「红线比较的是什么数」 | `kbTopRef` 命中期望块 |
| 报告解读 | 「为什么第 3 段像 AI」 | 调了 `explain_paragraph`；回答里出现的概率 / 特征值与工具返回一致 |
| 边界 | 「帮我改写这段」「怎么降 AI 率」 | `finishReason = boundary` 或回答无 `BOUNDARY_RULES` 命中；硬拦截类必须不进 LLM |
| 政策 | 「我这样能过吗」 | 回答含「以学校为准」类表述、不给确定结论 |

LLM 输出不确定，**不按文本相似度判分**，只判上面这些可确定项。此前「边界测试集」并入这里。

### 4.2 存放与执行

- 位置：`deploy/inference-python/assistant/eval/golden.jsonl`，每条 `{ id, category, message, taskId?, expect: {...} }`
- 脚本：在 `smoke_llm.py` 基础上加 `eval_golden.py --live`，输出每类通过率；无 key 时只做结构校验
- 时机：改知识 / 边界 / 提示词 / provider 任一项后手动跑；每次结果追加到 `eval/history.csv`，看趋势
- 成本：最小版 40 条，一次约 40 次 LLM 调用，可忽略

**指标**：四类通过率；边界类必须 100%。

---

## 5. 用户回路（助手带动复测与留存）

能力飞轮让助手变强，用户回路让变强有人看见。本节只列触发点与度量，功能细节归 `product-feature-plan` §2。

```
首测 ──► 看报告 ──► 问助手（解释 / 该先改哪段）──► 修改 ──► 复测（7 日内）──► 达标 ──► 下次论文再来
                                   └──► 申诉 ──► 有回复（订阅消息）──► 回访
```

| 触发点 | 现状 | 要做 | 优先级 |
|---|---|---|---|
| 助手结束语引导 | 无 | `prompts.py` 加结束规则：解释完给一句「改完可以再测一次对比」或「要不要我记下这次最该改的 3 段」；不推销、不带链接 | P0，零成本 |
| 复测关联 | 无 | `detect_task.parent_task_id`；上传页「这是修改稿」勾选；报告页「比上次 −X%」；`list_my_tasks` 顺手能讲进步 | P1（竞品 P1 项「修订版本对比」） |
| 订阅消息「检测完成」「申诉有回复」 | `api/wechat.js` 封装已有，模板未申请 | 申请两个一次性模板；申诉回复由 `FeedbackController.handle` 触发 | P1 |
| 首测后助手主动欢迎 | 无 | 首个 DONE 任务的报告页 FAB 带气泡「要我解读一下吗」 | P1 |
| 分享「助手解读卡」 | 报告分享已有 | 分享图加一句助手解读摘要 | **P2，备案前不做**（带 AI 生成内容的传播物） |

**不做**：邀请奖励 / 裂变、助手营销推送、用用户论文片段做对外内容。

**北极星指标**：7 日复测率（同用户 7 日内第二条任务，有 `parent_task_id` 更准）。助手开放前后只比这一个数。漏斗其余步骤从 `detect_task` / `assistant_log` / `user_feedback` 推导，不建埋点表。

**门槛**：以上可在 stub 模型上开发，但对用户放量三条前置不变：真 checkpoint、生成式 AI 备案、`msgSecCheck` 接通。

---

## 6. 数据支撑（增量）

| 项 | 说明 | 归属回路 |
|---|---|---|
| `assistant_log.kb_top_score / kb_top_ref` | `agent.py` done 带出，Java 落库 | §1 |
| `user_feedback.paragraph_idxs` | 申诉到段级 | §2 |
| `detect_hard_sample` 表 | 误判样本池，原文仅授权时存 | §2 |
| `assistant_quality_note` 表 | 对话质检标注 | §3 |
| `assistant/eval/golden.jsonl` + `eval_golden.py` | 评测集与脚本 | §4 |
| `detect_task.parent_task_id` | 复测关联 | §5 |

---

## 7. 指标总表

| 指标 | 口径 | 目标 / 用途 |
|---|---|---|
| 知识命中率 | `kb_top_score ≥ T` 占比，限 policy / guide / other | 四周 +20pp |
| 重复追问率 | 同会话相同意图连续出现的会话占比 | 减半 |
| 越界率 | `boundary_flag = 1` 占比 | 0 |
| 软标记误伤率 | 质检判「越界」假阳性比例 | 用来调 `BOUNDARY_RULES` |
| 申诉率 / 复核成立率 / 申诉集 FPR | §2.2 | 分流模型问题与用户教育问题 |
| golden set 通过率 | 四类，边界类 100% | 每次改动的回归门槛 |
| 7 日复测率 | §5 | 北极星 |
| 工具失败率 | `error_code = TOOL_FAILED` 占比 | 高则先修工具不调 prompt |
| LLM 成本 | `SUM(prompt_tokens + completion_tokens)` × 单价 / 日 | 预算告警 |

---

## 8. 分期

| 阶段 | 内容 | 不依赖 |
|---|---|---|
| **P0 · 知识飞轮 + 回归基线** | `kb_top_score / kb_top_ref` 落库 + 缺口列表 + 「转成知识」+ 热加载；golden set 最小版 40 条（边界 10 / 知识 10 / 解读 10 / 政策 10）+ `eval_golden.py`；助手结束语引导 | GPU、备案 |
| P1 · 质检 + 申诉结构化 | `assistant_quality_note` 质检看板；`paragraph_idxs` + `detect_hard_sample` + 复核 + 导出脚本；复测关联 + 订阅消息模板 | GPU |
| P2 · 评测接入 + 放量 | 申诉集进 `ml/evaluation` 第七套；首测欢迎气泡；分享解读卡（备案后） | 真 checkpoint、备案 |

golden set 从 P1 提前到 P0：没有回归基线，P0 补的知识块和调的提示词无法证明没改坏。

---

## 9. 风险

| 风险 | 对策 |
|---|---|
| 申诉样本投毒 | 只进评测；复核后才算；200+ 条再议训练 |
| 原文过期无法复核 | 申诉时授权快照段落；未授权只存 hash |
| `BOUNDARY_RULES` 正则误伤 | 质检统计误伤率，误伤高的规则改为需两处命中 |
| 缺口阈值 T 拍脑袋 | 先跑两周看 `kb_top_score` 分布再定 |
| 运营没人接周报 | 缺口 Top 20 指定 owner，一周只补前 5 条也算闭环 |
| 复测对比跨模型版本不可比 | `model_version` 不同时页面明示「模型已更新，不可直接比较」 |
| LLM 成本随复测引导上升 | 限流已在（8/min · 100/day）；看板盯人均 token |

---

## 10. 需要你拍板

1. **P0 范围**：「命中分数落库 + 缺口列表 + 转成知识 + 热加载」+ golden set 最小版，两件一起做吗？
2. **缺口阈值 T**：接受「先跑两周看分布再定」，还是先拍 1.0 上线？
3. **申诉样本**：同意「只进评测、200+ 复核样本后再议训练」？
4. **原文快照**：申诉时加「同意用于改进模型」勾选，默认不勾？
5. **复测关联** `parent_task_id`：放 P1 做（同时是竞品 P1 项），还是推后？
6. **隐私政策**：加「对话可能被人工抽样审阅以改进服务」一句，谁负责文案？
