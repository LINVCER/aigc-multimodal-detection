# REFACTOR PLAN · aigc-multimodal-detection

> **前置说明**：本 plan 由 Claude Code 生成，用于在 fork/master 上分批实施架构优化，最终整理成多个独立 PR 提给上游。
>
> **约束**：本地无 Python 3.11 环境、无模型权重、无 docker-compose 起 stack 的能力。所有改动靠静态分析 + 代码逻辑保证。fork 后需要人肉跑 `docker compose up` 冒烟。

---

## 0. 先纠正原报告里的三处错判

在动手前，通读代码后发现原进度报告有三处偏差，plan 依据的是纠正后的现状：

| 报告原判断 | 纠正后事实 | 对 plan 的影响 |
|---|---|---|
| 「6 家 LLM 供应商是维护噩梦」 | `config.py` 只接了 DeepSeek + MiMo 两家 LLM + Resemble 一家音频。`.env.example` 里其他四家仅是注释示例。 | Commit 04 从"砍代码"降级为"清理 .env.example 注释 + 加 provider 切换文档" |
| 「当前仲裁靠人肉调阈值」 | `arbitration.py` 已实现贝叶斯 log-sum-exp + EWMA 动态权重 + 冲突检测 + 人工复核建议 | 不需要重构仲裁逻辑本身 |
| 「calibration.py 只有骨架」 | Temperature + Platt + ECE + Redis 同步全部完整实现（240 行代码） | 不需要新写校准算法 |

**真正的问题（arbitration + calibration 两个模块都是这样）**：

> **`Arbitrator.arbitrate()` 在整个 `backend/app/` 生产代码里零调用**
> **`ConfidenceCalibrator.apply_calibration` / `load_from_redis` 在生产代码里零调用**
> 两者都是「完整实现 + 只在 tests/ 被单测 + 主流程从不使用」的孤岛代码

所以 Commit 08 的性质是**"把孤岛接回主流程"**（改 text_service / image_service / audio_service / detection_service 的融合逻辑，让它调 `Arbitrator` 并用校准后的 confidence），不是"引入新算法"。

---

## 1. 严重安全问题（必须优先私下告知原作者）

**`.env.example` 明文泄露两个疑似真实 API key**：

- 第 34 行：`LLM_API_KEY=sk-xxx...`（DeepSeek 格式，现已替换为占位符）
- 第 52 行：`MIMO_API_KEY=tp-xxx...`（MiMo 授权凭证格式，现已替换为占位符）

在公开 GitHub 仓库 3+ 个月，几乎必然已泄露。**PR 前先私下联系 LINVCER**：
1. 立即在 DeepSeek / MiMo 后台 **revoke** 这两个 key
2. 用 `git filter-repo` 或 `bfg` 清理历史（否则 revoke 之后 key 还在 git log 里可搜）
3. 换新 key 后，本 refactor 的 Commit 04 会把 `.env.example` 里所有真实 key 替换为占位符

**这一步不在 12 个 commit 中，属于社会工程环节。**

---

## 2. 分支与 Commit 组织策略

- 所有工作在本地 `master` 直接叠 commit（用户已确认）
- Origin remote 保持只读（不 push），保留原上游做对照
- 每个 commit 独立可 revert，独立可 review
- Commit message 遵循原仓库风格：`type: subject`（feat / fix / docs / refactor / chore / test）
- 拆完 12 commit 后，用户 fork 到自己账号 → `git push` → 按 commit 拆 3-5 组做多个 PR

**建议 PR 分组**（拆到上游时）：

| PR 组 | 包含 commit | 主题 |
|---|---|---|
| PR-1 | 01, 02, 12 | 工程基础：CI + 部署文档 + CHANGELOG |
| PR-2 | 03 | Alembic migration 闭环 |
| PR-3 | 04, 05 | 清理 .env.example + 砍 miniapp |
| PR-4 | 06, 07 | evals 骨架 + model_registry |
| PR-5 | 08 | 把 arbitration + calibration 接回主流程（**核心价值**） |
| PR-6 | 09, 10 | 前端组件抽象 + AdminPanel 拆分 |
| PR-7 | 11 | 支付审计闭环骨架 |

---

## 3. Commit 顺序与详细内容

### Commit 01 — `ci: add GitHub Actions for backend/frontend/docker smoke`

**目标**：0 CI → 有基础质量门。

**文件**：
- 新增 `.github/workflows/backend-ci.yml`：pip install → pytest → alembic upgrade head（连 sqlite mem 库）
- 新增 `.github/workflows/frontend-ci.yml`：pnpm install → tsc --noEmit → vite build
- 新增 `.github/workflows/docker-smoke.yml`：docker-compose up -d → curl /api/health → down
- 新增 `.github/dependabot.yml`：pip / npm 每周更新

**风险**：docker-smoke 会依赖模型权重下载，可能超时。**做法**：给 backend 加 `SKIP_MODEL_LOAD=1` 环境变量，CI 里跳过重模型加载，仅验证服务启停。

---

### Commit 02 — `docs: add deployment guide with model weight placement`

**目标**：README 只说"docker-compose up"，实际起不来。补齐部署 doc。

**文件**：
- 新增 `docs/DEPLOY.md`：
  - Prerequisites（Python 3.11 / Node 18 / Docker）
  - 模型权重放置（`../models/` 目录结构 + 每个 checkpoint 的 HuggingFace 拉取命令）
  - `.env` 配置指引（哪些必填 / 哪些可选）
  - LLM 供应商切换指南（DeepSeek vs MiMo，何时用哪个）
  - `docker compose up` 起停 + 常见错误排查
  - 管理员账号初始化（`backend/scripts/create_admin.py` 用法）
- README.md 顶部加 "Deploy → docs/DEPLOY.md" 链接

---

### Commit 03 — `refactor(db): move signup schema drift into alembic revision`

**目标**：清掉 `main.py` 里的 `create_all` + 手工 `ALTER TABLE` 兜底。

**文件**：
- `main.py` lifespan 删除 22-25 行的 `ALTER TABLE` 和 18 行的 `create_all`
- 新增 `backend/alembic/env.py`（如未有）+ `backend/alembic/versions/0001_initial.py`（从当前 metadata 生成）
- 新增 `backend/alembic/versions/0002_add_checkin_fields.py`（add `last_checkin_date` + `checkin_streak`）
- `docker-compose.yml` backend 服务启动命令改为 `alembic upgrade head && uvicorn ...`
- `docs/DEPLOY.md` 补 migration 章节

**风险**：alembic autogenerate 需要连活的数据库。**做法**：手写 revision，不用 autogenerate。

---

### Commit 04 — `chore: sanitize .env.example and clarify LLM provider choice`

**目标**：清理注释乱、恢复占位符、明确 provider 选型。

**文件**：
- `.env.example`：
  - `LLM_API_KEY` / `MIMO_API_KEY` 全部替换为占位符（`sk-xxxxxxxx` / `tp-xxxxxxxx`）
  - 42-42 行 OpenAI/阿里/智谱/月之暗面注释移到 `docs/DEPLOY.md` 的「LLM 供应商切换指南」
  - 加分组注释头：`# ── Primary LLM (文本/图像/论文降 AIGC) ──`
- `README.md`：LLM 章节链接到 DEPLOY.md 的指南

**不做**：不动 `config.py`（`llm_*` 和 `mimo_*` 字段并存本来就有历史设计意图，可能是路由到不同 provider，不动业务）。

---

### Commit 05 — `chore: remove miniapp scaffold, focus on web + extension`

**目标**：miniapp 只是骨架（页面 2-3 KB）、微信 appid 已注册但业务未接。资源不足别双端并行。

**文件**：
- 删除 `miniapp/` 整个目录
- `README.md`：
  - "端形态"章节从「Web + 小程序 + 扩展」改为「Web + Chrome 扩展」
  - 尾部加一段「历史设计：微信小程序骨架已归档，appid `wx5dede2e8d33e3f15` 保留，等待未来重启」
- 新增 `docs/history/miniapp-archived.md`：记录 6 个页面目录、appid、砍除决策原因

**如果用户不同意砍 miniapp**：这个 commit 改为「移动 miniapp/ 到 archived/miniapp/ 并加 README 说明冻结」。

---

### Commit 06 — `feat(evals): add offline evaluation suite skeleton for text/image/audio`

**目标**：现在改阈值靠拍脑袋，加评测集让后续调优有数据支撑。

**文件**：
- 新增 `backend/evals/README.md`：目录说明 + 样本贡献指南
- 新增 `backend/evals/text/README.md` + `backend/evals/text/sample.jsonl`（10 条示例，含 label + source）
- 新增 `backend/evals/image/README.md` + `backend/evals/image/sample.jsonl`
- 新增 `backend/evals/audio/README.md` + `backend/evals/audio/sample.jsonl`
- 新增 `backend/evals/runner.py`：读 jsonl → 调对应 service → 输出 accuracy / F1 / ECE / confusion matrix 到 `backend/evals/reports/YYYY-MM-DD.md`
- `.github/workflows/backend-ci.yml`：加一个 optional job 跑 evals（可以标 `if: contains(github.event.pull_request.labels.*.name, 'run-evals')`）

**不做**：不真的补齐 500 条样本（那是数据工作，不是代码工作）；只提供框架和 10 条示例，让原作者/未来贡献者补。

---

### Commit 07 — `feat(models): add model registry with SHA256 verification`

**目标**：现在 checkpoint 走本地 `../models` 挂载、无版本、无校验。加 registry 后续可以灰度换模型 + 快速回滚。

**文件**：
- 新增 `backend/model_registry.yaml`：
  ```yaml
  text_roberta_v3_thesis:
    path: text/aigc_detector_v3_thesis.pth
    sha256: <TBD>
    val_f1: <TBD>
    trained_on: hfl/chinese-roberta-wwm-ext
    notes: 论文场景微调
  image_cnn_high_freq_v1:
    path: image/cnn_detection.pth
    ...
  ```
- 新增 `backend/app/utils/model_registry.py`：`load_registry()` + `verify_checkpoint(name)` + `get_active(name)`
- `main.py` lifespan 加 `verify_all_registered_models()`，log warning 而非 crash（生产可切换成 crash 模式）
- `docs/DEPLOY.md` 加 "模型 registry" 章节

**风险**：SHA256 需要现有 checkpoint 才能算，我这里填 `<TBD>`，让原作者跑 `sha256sum` 补齐。

---

### Commit 08 — `refactor(fusion): wire arbitration + calibration into detection services`

**目标**（**本次重构的核心价值**）：把两个孤岛接回主流程。

**做法**：
1. 每个 `detectors/{text,image,audio}/*_detector.py` 输出加 `logit` 字段（不仅是 confidence）
2. `services/text_service.py` / `image_service.py` / `audio_service.py` 融合前：
   - `params = ConfidenceCalibrator().load_from_redis(f"{detector_id}") or CalibrationParams()`
   - `calibrated = ConfidenceCalibrator.apply_calibration(logit, params)`
   - 用 `calibrated["calibrated_confidence"]` 替换原来的 `confidence` 传给融合
3. `services/detection_service.py` 是聚合入口，改为：
   - 单模态：直接返回校准后 confidence
   - 多模态（跨模态融合场景）：包装成 `ModalityResult`，调 `Arbitrator().arbitrate(...)`
4. `api/v1/detection.py` 响应体加 `calibrated_confidence` / `confidence_interval` / `conflict_detected` / `warning` 字段（原字段保留兼容）
5. 前端 `ResultCard.vue` 展示 warning（如果有）

**风险**：不知道 detector 的 `logit` 计算方式是否统一，可能需要给每个 detector 加 `to_logit()` 方法。改动跨 15+ 文件，最容易出问题的 commit。**做法**：先在这个 commit 里只做 text 模态的接线（跑通打样），image / audio 拆到 Commit 08b / 08c。

**拆分建议**：Commit 08 → 08a (text) / 08b (image) / 08c (audio) 三个 commit，总数从 12 变 14。

---

### Commit 09 — `refactor(frontend): extract shared detection components`

**目标**：15 个 view 每个都在写自己的上传 / 结果展示；改一次阈值展示逻辑要改 15 处。

**新增到 `frontend/src/components/detection/`**：
- `DetectionForm.vue` —— 通用上传表单（file drop / 参数配置 / 提交按钮）
- `ResultPanel.vue` —— 通用结果面板（AI 率 / risk badge / warning / expand for details）
- `UploadDropzone.vue` —— 拆自 DetectionForm 的上传区
- `AIRateBadge.vue` —— 从各 view 抽出的 AI 率标签
- `ConflictWarning.vue` —— 展示 Arbitrator 冲突警告（对应 Commit 08 的新字段）
- `DetectionHistory.vue` —— 抽取自 History.vue，可复用在其他 view

**改造对应 view**：TextDetection / ImageDetection / AudioDetection / TamperingDetection / ThesisDetection 全部替换为使用共享组件。**BatchDetection / ReduceAIGC 暂不动**（业务逻辑差异大，留后期）。

**风险**：视觉 diff 需要真人跑起来对比。做法：commit message 里明确说"未做视觉回归，需 fork 后 vite dev 手工对比"。

---

### Commit 10 — `refactor(admin): split 63 KB AdminPanel into 5 subpages`

**目标**：AdminPanel.vue 63 KB 单文件不可持续。

**新目录 `frontend/src/views/admin/`**：
- `AdminLayout.vue` —— 侧栏 + 路由出口
- `UserManagement.vue` —— 用户管理
- `OrderManagement.vue` —— 订单/额度管理
- `DetectionRecords.vue` —— 检测记录审计
- `ModelConfig.vue` —— 模型配置 + registry
- `SystemSettings.vue` —— 系统设置 / 阈值调整

**路由改造**：`frontend/src/router/index.ts` `/admin` 路由改为嵌套路由，5 个子路由。

**做法**：不是删 AdminPanel.vue 重写，而是**按现有 tab 结构切成 5 份**，最大程度保留原代码。原文件保留作 `AdminPanel.legacy.vue` 引用，收到 warning 后移除（下一个 minor 版本）。

**风险**：AdminPanel 内的 emit / props / state 可能跨 tab 共享，拆时要小心。**做法**：如果共享状态多，抽 `useAdminStore()` (Pinia) 承载。

---

### Commit 11 — `feat(payment): add credit transaction ledger for audit`

**目标**：`payment.py` 只有 854 字节，`model.Payment` 没有消耗流水表。To B 商用必备审计闭环。

**文件**：
- 新增 `backend/app/models/credit_transaction.py`：`CreditTransaction` 表（id / user_id / delta / reason / detection_id / created_at）
- 修改 `backend/app/services/detection_service.py`：每次消耗额度写一条 `delta=-N, reason='text_detection', detection_id=xxx`
- 修改 `backend/app/services/auth_service.py`：签到 / 打赏充值写 `delta=+N, reason='checkin/donate'`
- 新增 API `GET /api/v1/admin/users/:id/credit-history?from=&to=` 对账查询
- 新增 alembic revision `0003_add_credit_transaction.py`
- **退款策略**：修改 `workers/*_worker.py`，检测超时 / 抛异常时自动写补偿流水
- 前端 `admin/UserManagement.vue` 加"额度流水"tab

**不做**：不接微信/支付宝真实支付（超范围）；只做内部账本，后续接支付网关时数据模型已就绪。

---

### Commit 12 — `docs: refresh README and add CHANGELOG`

**目标**：整体反映架构变动。

**文件**：
- `README.md` 全面更新：
  - "端形态"改为 Web + Chrome 扩展
  - "架构图" 更新（含 Arbitrator + Calibrator 在流程图中显式出现）
  - "路线图"链接到 progress-report §10
  - "License" 明确当前状态（等原作者决策）
- 新增 `CHANGELOG.md`：本次 12 commit 全部条目
- 新增 `CONTRIBUTING.md`：如何贡献 evals 样本 / 如何加检测器 / commit message 规范
- 新增 `.github/ISSUE_TEMPLATE/bug_report.md` + `feature_request.md`

---

## 4. 每个 commit 的验收 checklist

每个 commit 完成前，Claude 会自查（人类 review 时也照单核对）：

- [ ] 单文件改动都能独立解释（无搭车修改）
- [ ] 无未使用 import / 无死代码
- [ ] 无 `print()` / 无 console.log
- [ ] 无 API key / password / secret（`git diff | grep -E "(sk-|tp-|password=|api_key=)"` 为空）
- [ ] `git diff --stat` 行数合理（Commit 08 除外，08 会跨 15+ 文件）
- [ ] 对应文档（README / DEPLOY / CHANGELOG）同步更新
- [ ] Commit message 满足 `type: subject`，body 说清"为什么"

**Commit 08 额外**：因为跨文件多、无法本地跑，会在 commit body 里显式列出所有改动点，方便 fork 后手工对比。

---

## 5. 不做的事（负向清单）

在动手过程中，如果遇到以下诱惑，一律停手：

1. **不改 detectors/ 里的检测算法**（RoBERTa / ViT / RawNet2 / MaskRCNN 等），只改融合调用
2. **不动训练脚本**（`train_*.py`），那是离线工作
3. **不接支付网关**（微信/支付宝 SDK），只做内部账本
4. **不动 defense/ 与 metadata/ 目录**（字形归一化、C2PA、GB45438），这些实现属于差异化能力，不重构
5. **不加新的 LLM 供应商**
6. **不重命名文件**（除非 Commit 10 的 AdminPanel 拆分绝对必要），避免 PR review 时 diff 满屏红绿
7. **不改数据库表命名**（`users` 而不是 `dm_users` 等），保持与原作者约定
8. **不做视觉回归**（无浏览器环境）—— 前端改动会在 commit body 里明确"需人肉验证"

---

## 6. 时间预估

按每天 6h 有效工作、无中断：

| Commit | 预估工时 | 累计 |
|---|---|---|
| 01 CI | 2h | 2h |
| 02 DEPLOY | 3h | 5h |
| 03 Alembic | 3h | 8h |
| 04 .env 清理 | 1h | 9h |
| 05 砍 miniapp | 1h | 10h |
| 06 evals 骨架 | 4h | 14h |
| 07 model_registry | 3h | 17h |
| 08 arbitration/calibration 接线（含 08a/b/c 三段） | 8h | 25h |
| 09 前端组件抽象 | 6h | 31h |
| 10 AdminPanel 拆分 | 6h | 37h |
| 11 支付审计闭环 | 6h | 43h |
| 12 README/CHANGELOG | 2h | 45h |

**总计约 45h ≈ 1.5 周（连续做）** ≈ 2 周（现实节奏）。

---

## 7. 鸡肋 / 冗余功能删除清单（用户已授权「直接删」）

用户明确原则："鸡肋无用或影响整体效果的功能可以直接删"。以下 10 项是我通读代码后标记的**候选删除**，请你逐项确认 **删 / 留 / 归档** 三选一。**默认全删**（除非你圈出「留」或「归档」）。

删除会替代或合并进原 12 commit（不再单独占编号），最终 commit 数可能变成 14-15。

| # | 目标 | 现状证据 | 我的判断 | 建议 |
|---|---|---|---|---|
| D1 | **miniapp/ 整个目录** | 页面 2-3 KB 骨架、微信 appid 已注册但无业务链路、单人 4 个月只做了目录结构 | 已彻底停滞，微信开发链路复杂养不起 | **删** |
| D2 | **extension/ 整个目录** | content.js 3.7 KB + popup.js 1.8 KB + service-worker.js 0.6 KB 全是骨架、host_permissions 里挂了生产 API 但代码只做「抓当前页文本发后端」 | 教育路径 extension 无引流价值（无客户无流量），媒体路径也用不上 | **删**（可保留 manifest 到 docs/history） |
| D3 | **backend/train_*.py 四个训练脚本 + cloud_train.sh** | `train_text_detector.py` 36 KB / `train_image_sd.py` 31 KB / `train_image_detector.py` 17 KB / `train_audio_detector.py` 15 KB，属离线训练资产 | 混在服务代码里污染 backend 目录，训练是独立工作流 | **移**到独立仓库或 `training/` 目录（不 import 到运行时） |
| D4 | **backend/benchmark_*.py 两个** | benchmark_cred.py 11 KB / benchmark_cudrt.py 3 KB，一次性 benchmark | 跑过就完了，留着增加 review 面 | **删** |
| D5 | **backend/eval_text_detector.py** | 20 KB，一次性评测脚本 | Commit 06 的 evals/ 会替代它 | **删**（迁到 evals/text/legacy_eval.py 保留一份） |
| D6 | **AI Assistant 功能** | `api/v1/assistant.py` 12.5 KB + `AIAssistant.vue` 8 KB | 与"内容鉴伪"主线无直接关系，像是「顺手做的对话框」 | **删**，聚焦检测主业 |
| D7 | **identifier 路由** | `api/v1/identifier.py` 4.5 KB | 从命名看是"标识识别"，能力弱、疑似 metadata 检测的重复入口 | **删**（把独有逻辑合并到 tampering） |
| D8 | **RechargePage.vue** | 3.8 KB 骨架，付费真链路未接 | Commit 11 支付审计闭环会重建 | **删** |
| D9 | **StandardsCompliance.vue** | 9 KB，疑似国标信息静态展示页 | 如果没交互只是文档静态页，应迁到 docs/ 或删 | **需先看代码判断**，倾向删 |
| D10 | **History.vue** | 3 KB 骨架 | Commit 09 组件抽象会重建通用 HistoryList | **删** |
| D11 | **Resemble AI 音频** | `detectors/audio/resemble_client.py` 3 KB，config 有 monthly_limit（付费额度） | 若接了主流程就留（跟 wav2vec2/rawnet2 组三路）；若未接就删 | **待确认**：commit 08 接线前先 grep，未调用就删 |

**处置动作对应的新 commit**（合并到原 12 commit 或新增）：

- **新增 Commit 04b** `chore: remove miniapp/extension/legacy scripts`：处理 D1, D2, D3, D4, D5（一次性大清理，纯文件删除，review 快）
- **新增 Commit 04c** `refactor: remove AI assistant, identifier, standalone recharge/history/standards pages`：处理 D6, D7, D8, D9, D10（涉及路由删除，前后端联动）
- D11（Resemble）纳入 Commit 08 判断

**新的 commit 总表**：

| # | Commit | 说明 |
|---|---|---|
| 01 | ci: add GitHub Actions | |
| 02 | docs: add deployment guide | |
| 03 | refactor(db): alembic migration | |
| 04 | chore: sanitize .env.example | |
| 04b | chore: remove miniapp/extension/legacy scripts | **新增** |
| 04c | refactor: remove assistant/identifier/recharge/history/standards | **新增** |
| 05 | (原 miniapp) 并入 04b | 编号回收 |
| 06 | feat(evals): eval suite skeleton | |
| 07 | feat(models): model registry | |
| 08a | refactor(fusion): wire arbitration for text | **08 拆三段** |
| 08b | refactor(fusion): wire arbitration for image | |
| 08c | refactor(fusion): wire arbitration for audio | |
| 09 | refactor(frontend): shared components | |
| 10 | refactor(admin): split AdminPanel | |
| 11 | feat(payment): credit transaction ledger | |
| 12 | docs: README + CHANGELOG | |

**总数 15 commit**。

---

## 8. 你需要 confirm 的四个决策点

### Q0（新增）：鸡肋清单 D1-D11 逐项 confirm

- [ ] 全部按建议处理（推荐）
- [ ] 圈出想「留」或「归档」的编号：__

### Q1：API key 泄露处理

- [ ] **A**：Commit 04 只替换 `.env.example` 为占位符，git history 里的老 key 让你自己联系 LINVCER 处理（推荐 — 分工清晰）
- [ ] **B**：本次重构不动 `.env.example`，等原作者 revoke 后再改（避免"改了但历史里还在"的假安全感）

### Q2：Commit 08 拆分粒度

- [ ] 拆成 08a/08b/08c 三段（推荐 — 风险隔离）
- [ ] 合并成一个大 commit

### Q3：训练脚本 D3 迁移位置

- [ ] 迁到本仓库 `training/` 子目录（推荐 — 保留可追溯）
- [ ] 从主仓库彻底删除、单独开 repo（更干净但迁移工作在原作者侧）

---

**Confirm 之后我按 Commit 01 → 12 的顺序动手。中途你可以随时喊停 / 插队 / 改优先级。**
