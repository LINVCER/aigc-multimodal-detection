# 论文 AIGC 检测平台 · 五人团队 12 周开发计划

> 周期：2026-09-28（W1 周一）→ 2026-12-18（W12 周五），10 周主线 + 2 周缓冲收尾
> 团队：5 人（算法-数据 A · 算法-推理 B · 后端 C · 前端 D · 测试/DevOps E），产品负责人负责验收
> 节律：周一下发本周任务表 → 周三 15 分钟站会对齐阻塞 → 周五 17:00 前提交交付物，产品负责人按「验收标准」列逐项签收
> 依据：`docs/design/MODEL_UPGRADE_PLAN.md`（M1-M6 选型）· `202609-text-detector-training-pipeline.md`（训练链路）· `docs/research/AIGC文本论文检测-文献精读笔记.md` §8.7 修正清单 · `docs/releases/CHANGELOG.md`（v0.2.0 现状）

---

## 0. 现状盘点（计划的起点）

| 层 | 已完成 | 未完成 / 本计划要做 |
|---|---|---|
| Java 后端 | Phase A 五件套 · Phase B MyBatis-Plus 4 表全落库 · Caffeine 场景阈值缓存 · 23 端点 | Sa-Token 仍 mock · 微信 code2session 未接 · 检测同步执行 · 无人工复核流 · 报告不带区间/阈值 · 存储只有本地实现 · 统计接口全表遍历 |
| Python 推理 | FastAPI 6 端点 · 老 RoBERTa v3_thesis 兜底（校准形同虚设）· 新 checkpoint 契约已适配 | humanize / attribute 仍 stub · 无句子级定位 · 无白盒双检 · 未上新模型 |
| ml/ 训练链路 | 数据构建 / 增强 / 六套评测 / 融合模型 / 训练 / 校准 / 评估 全部实装 | **一次都没跑过**：无 GPU 环境、无数据落地、无 checkpoint、无 MLflow 记录 |
| Web 端 | C 端 4 页 + 运营后台 4 页 | 报告页不展示置信区间 / 阈值 / 溯源 / warning · 无阈值管理 · 无复核工作台 |
| mobile-uniapp | Wave 1-4 · v0.5.0 端上就绪 | 深色模式 / PWA 只有骨架 · 订阅消息服务端未接 · 结果页未对齐新字段 |
| 工程 | 单仓多端 · release 文档中心 | 无 CI · 无接口自动化 · 无 E2E · 无 nightly 模型回归 · 无灰度/监控 |
| 数据合规 | 许可清单（DATASETS.md §5） | CHEAT 商业授权未申请 · human 语料 2020 前红线未落检查脚本 |

## 1. 目标与里程碑

**总目标**：12 周后交付 **v1.0.0 候选**——新一代融合检测模型上线推理服务，报告可解释（区间 + 阈值 + 溯源 + 句子级），人工复核闭环，后端 Phase C 收尾，全链路 CI/E2E/灰度就位。

| 里程碑 | 周 | 交付 | 验收硬指标 |
|---|---|---|---|
| **M1 地基** | W2 末 | GPU 环境 + 数据 v1 入 DVC + smoke 跑通 + v0.1.0 baseline 首个 checkpoint | smoke 无报错；six evalsets 报告产出 |
| **M2 首个可用模型** | W4 末 | v0.2.0 fusion checkpoint 上 dev 推理；报告页新字段；Sa-Token 真接入；检测异步化 | fusion 在 adversarial / polished 上 F1 ≥ baseline + 4pp；dev 真推理 P95 < 1.5s/段（GPU） |
| **M3 产品闭环** | W6 末 | 自建学术数据 v1 并入 → v0.2.1；句子级 beta；人工复核闭环；订阅消息 | in_domain AUROC ≥ 0.98 · ECE ≤ 0.05；复核流 E2E 通 |
| **M4 鲁棒与收尾** | W8 末 | v0.2.2 / v0.3.0 达标版；Luminol 白盒接入决策；Phase C 收尾；深色模式 / PWA | cross_generator F1 ≥ 0.85 · adversarial F1 ≥ 0.70；安全用例通过 |
| **M5 灰度** | W10 末 | humanize 真模型 beta；灰度环境 + 监控；1 家内测客户全流程 | 内测零 P0 缺陷；humanize 改写后判 AI < 30% 且语义保持 ≥ 90% |
| **M6 v1.0.0 候选** | W12 末 | 全量验收、文档、VERSIONS / CHANGELOG / release-notes | 六套评测全过线；验收测试报告签字 |

## 2. 分工

| 代号 | 角色 | 主责 | 备份 |
|---|---|---|---|
| **A** | 算法 · 数据与训练 | 数据构建 / 增强 / 自建学术集 / 训练迭代 / 校准 / 特征审查 / 模型卡 | B |
| **B** | 算法 · 推理与平台 | GPU 环境 / MLflow · DVC / 推理服务 / 句子级 / 白盒双检 / humanize LoRA / 性能 | A |
| **C** | Java 后端 | Phase C（Sa-Token · 微信 · Redis · MinIO）/ 异步检测 / 报告契约 / 复核工作流 / 订阅推送 / 统计 SQL | E |
| **D** | 前端（Web + uniapp） | 报告页新字段 / 阈值管理 / 复核工作台 / 句子级高亮 / 深色模式 / PWA / humanize 页 | C |
| **E** | 测试 / DevOps | CI/CD / 接口自动化 / E2E / nightly 模型回归 / 合规脚本 / 灰度与监控 / 测试报告 | D |
| **产品负责人** | 验收 | 周一下发、周五验收、里程碑评审、优先级裁决、外部资源（GPU / API 预算 / 微信资质 / CHEAT 授权） | — |

**契约先行**：W1 冻结三份契约，后续任何改动走评审：① 报告响应字段（`interval / threshold_key / threshold / source_probs / warning / sentences[].boundary`）② checkpoint 契约（已在 `ml/common/checkpoint.py`）③ 复核工作流状态机。

## 3. 每周任务表

> 格式：**成员 → 任务 → 交付物 → 验收标准**。验收标准是产品负责人周五对照检查的唯一依据，必须可观察（commit / 报告文件 / 指标数值 / 演示录屏）。

### W1（09-28 → 10-02）· 地基

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | `build_dataset --sources hc3,csl,m4 --held-out-sources qwen,deepseek`；DVC 登记推 MinIO；人工抽检 200 条核 label / PII | `ml/datasets/text/data/stats.json` · DVC 推送记录 · 抽检表 | train/val/test 三分齐全；label 比例在 1:3 内；PII 抽检 0 泄漏；short / held_out 文件产出 |
| B | 云 GPU（A100 40GB）跑 `training/setup_env.sh`；MLflow 起；`train_baseline.sh smoke` 跑通并修暴露的 bug | smoke 日志 · MLflow run · 修复 commit | smoke 全程无 Traceback；dry-run 产出 config.snapshot.yaml |
| C | 冻结三份契约（报告字段 / 复核状态机 / 阈值键）；`DetectTaskDetailVO` 加新字段；`config-patches.md` 列 @SaIgnore 收敛清单 | 契约文档 PR · VO 改动 | 契约评审会通过（产品 + A/B/D 到场）；`/detect/tasks/{id}` 返回新字段（可为空） |
| D | Web 报告页 + uniapp 详情页按契约展示 `warning` 与 `interval`（先接 stub）；评估 SCSS → CSS var 改造工作量 | dev 环境可见 · 工作量评估文档 | 短文本请求页面出现 warning 文案；评估给出文件数与人日 |
| E | GitHub Actions：Python `py_compile + ruff`、Java `mvn -q compile`、web / uniapp build；测试报告模板；接口用例清单 v1 | `.github/workflows/ci.yml` · 模板 · 清单 | 任意 PR 触发 CI 且全绿；清单覆盖 23 端点 |

### W2（10-05 → 10-09）· 首训 · M1

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | `paraphrase_augment --engine rule` 跑通 + `--merge`；`build_evalsets`；接 LLM API（Qwen / DeepSeek）跑 500 条三模式小样验证质量 | augment 目录 · 抽检 50 条语义保持表 · API 费用记录 | 六套 evalset 文件产出；LLM 改写语义保持抽检 ≥ 90% |
| B | `train baseline`（v0.1.0）全量首训 + `eval` 六套；`ml/VERSIONS.md` 登记 | `ml/checkpoints/text/v0.1.0-baseline/{best.pth, metrics.json, eval-report.json}` | eval-report 六套齐全（缺的说明原因）；VERSIONS 有 T / Platt / AUROC 数值 |
| C | Sa-Token 真接入 dev（替 mock）；删 `InMemoryAuthTokenRepository`；`/auth/wechat/login` 走 code2session（需产品提供 AppID / Secret） | 代码 PR · Postman 集合 | 登录拿 token → 带 token 调 `/detect/submit` 通；无 token 401 |
| D | 运营后台「场景阈值管理」页（CRUD `detect_scenario_threshold`，含 `fpr_1pct / fpr_5pct` 阈值键选择）；报告页溯源条形图（`source_probs`） | dev 页面 | 改阈值后 ≤ 5 分钟生效（Caffeine TTL）；溯源图在 stub 数据下渲染 |
| E | 接口自动化（pytest + requests 或 rest-assured）覆盖 23 端点；推理 Docker 镜像构建入 CI（build context 仓库根） | 用例仓 · CI 镜像产物 | 用例通过率报告；CI 产出 `paperaigc-inference:sha` 镜像 |

### W3（10-12 → 10-16）· 增强数据 + fusion 首训

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | LLM 增强全量：train 侧 paraphrase 6000×3 档 / polish 4000 / mixcase 2000，test 侧 800 / 600 / 400；`--merge`；重建 evalsets | 增强数据 + `stats` · 费用记录 | 各 augment 类型数量达标；adversarial / polished / mixed 三套评测集各 ≥ 300 条 |
| B | `train fusion`（v0.2.0）首训 + 六套 eval；写 baseline vs fusion A/B 报告 | `v0.2.0-fusion-mdeberta/` 三件 · A/B 报告 | A/B 报告含六套逐项差值；若 fusion 在 adversarial / polished 未达 +4pp 要给归因 |
| C | Redis 接入（Sa-Token 会话）；检测提交改异步（`@Async` + 状态 PENDING → RUNNING → DONE，失败 FAILED） | 代码 PR | `/detect/submit` 200ms 内返回 PENDING；轮询 `/tasks/{id}` 状态变化正确；并发 20 提交无丢单 |
| D | uniapp 结果页对齐新字段；任务列表轮询 RUNNING；Web 任务列表状态实时 | 真机录屏 | 提交后列表出现 RUNNING → DONE 变化 |
| E | nightly 模型回归：定时跑 `eval.py` 对最新 checkpoint，与上次对比，退化 > 1pp 告警；数据合规脚本（human 语料日期字段、PII 正则扫描） | workflow · 脚本 · 首次 nightly 报告 | nightly 报告推送到群；合规脚本对 data/ 全量扫描 0 命中 |

### W4（10-19 → 10-23）· M2 首个可用模型

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | 30 维表层特征 SHAP / permutation importance；按 `origin` 分 F1 找数据集偏差；校准核查（对照老 v3_thesis 未校准问题） | 特征审查报告 · 剔除 / 保留决策 | 报告列出每维重要性与跨 origin 稳定性；给出 sf-v2 候选清单 |
| B | 新 checkpoint 上 dev 推理（只配 `TEXT_CHECKPOINT_PATH`）；性能测试（CPU / GPU 延迟、并发 10 / 50）；`/attribute` 切 `source_probs` | dev 部署 · 性能报告 | `/health` 显示 `arch=fusion`；GPU P95 < 1.5s/段；`/attribute` 返回真实分布 |
| C | 报告 PDF 加区间 / 阈值 / 场景 / 模型版本 / warning；场景 → 阈值键映射（`academic_*` → `fpr_1pct`，其它 `fpr_5pct`）；人工复核数据模型（`detect_review` 表 + 状态机）+ 迁移 SQL | PDF 样例 · 表结构评审 · V0.3.0.001 迁移 | PDF 含全部新字段；博士场景任务用 `fpr_1pct`；表结构评审通过 |
| D | Web 报告页最终版：区间条 / 阈值线 / 溯源图 / warning / 「申请人工复核」按钮 | dev 演示 | 走查通过；按钮调用复核接口（W5 出）先 mock |
| E | M2 全量回归（接口 + 手工）；性能基线报告；缺陷清单 | 测试报告 `test/reports/2026-10/1023_M2_*` | 报告齐全；P0 = 0，P1 有 owner 与期限 |

**M2 评审（10-23）**：产品负责人对照第 1 节硬指标签收。

### W5（10-26 → 10-30）· 自建数据 + 复核流

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | 自建学术数据 v1：CSL 摘要 + 教材段落 → 6 家 LLM（Qwen 占 20%）× 5 场景生成 30K；prompt 库；生成质检 | `raw/custom/*.jsonl` · prompt 库 · 质检表 · 费用 | 30K 达标；6 场景 × 6 家分布表；抽检 100 条无明显模板腔 / 乱码 |
| B | 三分类扩展（human / ai / collaborative）实现 + yaml；`unfreeze_layers: 0` 探针对照实验 | 两组 MLflow run · 实验小结 | 在 held_out 生成器上给出 探针 vs 全微调 vs fusion 的 AUROC 对比 |
| C | 人工复核工作流 API：创建 / 分派 / 结论 / override 结果；feedback appeal 与复核关联 | 代码 PR · Postman | 状态机全路径用例通过；override 后 `/tasks/{id}` 返回复核结论 |
| D | 运营后台复核工作台（列表 / 详情 / 结论录入）；C 端「申请复核」真调 | dev 演示 | 复核全流程可走通 |
| E | E2E（Playwright）：登录 → 提交 → 报告 → 申请复核 → 运营结论 → C 端看到结果；uniapp 真机回归清单 | E2E 仓 · 清单 | E2E 在 CI 绿；清单覆盖 uniapp 全部页面 |

### W6（11-02 → 11-06）· M3 产品闭环

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | 自建 v1 并入训练 → v0.2.1；`build_evalsets` 按 `meta.ai_sentence_idx` AI 覆盖比例分桶（mixed 拆 3 档）；编辑前 / 后配对小集 500 对（人写 → LLM 润色） | `v0.2.1/` 三件 · 新评测集 · VERSIONS | in_domain AUROC ≥ 0.98 · ECE ≤ 0.05；mixed 三档分报；配对集 FPR 漂移数值 |
| B | 句子级 beta：fusion 逐句打分 + 变点 / Lepski 平滑（免标注）；`return_sentences` 响应加 `boundary` | 代码 · 混写样本演示 | 10 条混写样本人工看边界命中 ≥ 7 |
| C | 订阅消息服务端推送（检测完成通知，微信模板消息 API）；统计接口 SQL `GROUP BY` 替全表遍历 | 代码 PR | 真机收到通知；`/detect/statistics` 10 万任务下 < 200ms |
| D | uniapp 句子级高亮升级（边界）+ 订阅消息接线；深色模式第一批（tokens → CSS var，5 页） | 真机录屏 | 深色下 5 页无白底闪烁 |
| E | M3 回归；推理并发压测（50 / 100）；依赖漏洞扫描（pip-audit / OWASP dependency-check） | 报告 | 压测无 5xx；高危漏洞 0 |

**M3 评审（11-06）**。

### W7（11-09 → 11-13）· 特征与白盒

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | `sf-v2`：加 surprisal 波动 6 维（小 LM 打分）；与 sf-v1 对比训练 | 实验报告 · `SURFACE_FEATURE_VERSION` bump | adversarial / polished 上给出增量数值与推理成本 |
| B | Luminol 白盒中文 spot 验证（100 条）；灰区触发逻辑设计（主分类器 0.35-0.65 触发） | spot 报告 · 设计稿 | 给出接 / 不接决策与依据 |
| C | MinIO `IStorageService` 实现 + 历史文件迁移脚本；`AdminUser → UserProfile` rename | 代码 PR | 上传落 MinIO；旧任务 retry 能读到文件 |
| D | 深色模式第二批（余下页面 + 组件）；PWA `vite-plugin-pwa` 接入 | 真机 · Lighthouse | Lighthouse PWA 可安装；全页深色走查通过 |
| E | 数据合规审计（CHEAT 授权状态、许可清单对照实际训练集来源）；发布流程文档（灰度 / 回滚 / 模型切换） | 审计报告 · 流程文档 | 训练 checkpoint 只含 ✅ 许可数据源；文档评审通过 |

### W8（11-16 → 11-20）· M4 鲁棒收尾

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | 若 v0.2.x 在 cross_generator 未达 0.85 → 训 v0.3.0 deberta-large；否则 v0.2.2 调优；模型卡 | 达标版 checkpoint · 模型卡 | cross_generator F1 ≥ 0.85 · adversarial F1 ≥ 0.70 · polished / mixed F1 ≥ 0.60 |
| B | 句子级正式版；Luminol 接入（若 W7 通过）；推理镜像 v1；ONNX 导出可行性 | dev 部署 · 镜像 | 灰区样本触发白盒且总延迟 P95 < 3s |
| C | Phase C 收尾：@SaIgnore 收敛、权限矩阵、审计日志 | 代码 PR · 权限矩阵表 | 越权用例全部 403 |
| D | Web / uniapp 全功能对齐走查；文案与空态；无障碍基础 | 走查清单 | 清单 100% 关闭 |
| E | M4 全量回归 + 性能 + 安全报告；灰度候选 checklist | 报告 · checklist | P0 = 0；checklist 评审通过 |

**M4 评审（11-20）**。

### W9（11-23 → 11-27）· 对抗与降 AIGC

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | 对抗评测加强改写 500 条（策略优化改写器或 DIPPER-style 强 prompt）；鲁棒性报告；内测阈值建议 | 评测集 · 报告 | 强改写下 F1 数值与归因 |
| B | humanize：`qwen2.5-14b-humanizer-v3-lora` warm start → vLLM；`/humanize` 切真模型 beta | 部署 · 抽检表 | 改写后被 M1 判 AI < 30%；语义保持抽检 ≥ 90% |
| C | 模型版本 / 灰度表（`model_version`）接入；A/B 路由；接口限流 | 代码 PR | 按用户比例路由到两个 checkpoint；限流触发 429 |
| D | humanize 产品页（论文降 AIGC：原文 / 改写对照 / 再检测） | dev 演示 | 走通 改写 → 再检测 |
| E | 灰度环境搭建；监控告警（推理错误率 / 延迟 / 5xx） | 环境 · 告警规则 | 人为制造错误触发告警 |

### W10（11-30 → 12-04）· M5 灰度

| 成员 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| A | 内测反馈回流 → 误报 / 漏报分析；阈值微调建议 | 分析报告 | 每条 P1 反馈有归因 |
| B | humanize 正式；推理性能优化（动态 batch / 结果缓存） | 部署 · 性能对比 | 吞吐提升数值 |
| C | 内测客户账号 / 配额；报告导出电子签形态（答辩材料） | 代码 PR · 样例 | 内测账号全流程通 |
| D | 内测问题修复；引导 / 帮助页 | 修复清单 | 内测反馈 UI 类全部关闭 |
| E | 组织 1 家内测客户全流程；缺陷跟踪；灰度回归 | 内测报告 | 零 P0；P1 有期限 |

**M5 评审（12-04）**。

### W11（12-07 → 12-11）· 收敛

| 成员 | 任务 | 交付物 |
|---|---|---|
| A | 缺陷修复；模型卡终版；六套评测终版报告 | 模型卡 · eval-report 终版 |
| B | 运维手册（部署 / 模型切换 / 回滚 / 监控）；推理镜像 rc | 手册 · 镜像 |
| C | 接口文档（openapi.yaml）终版；缺陷修复 | 文档 |
| D | 前端文档；缺陷修复 | 文档 |
| E | 验收测试报告草稿；全量回归 | 报告草稿 |

### W12（12-14 → 12-18）· M6 v1.0.0 候选

| 全员 | 任务 | 验收 |
|---|---|---|
| 全员 | 发布评审；`ml/VERSIONS.md` / `docs/releases/CHANGELOG.md` / `v1.0.0/release-notes.md`；回顾会 | 产品负责人签收验收测试报告；六套评测全过线；release-notes 齐全 |

## 4. 验收机制

**周五验收单**（产品负责人填）：

| 成员 | 任务 | 交付物链接 | 验收标准 | 结论（通过 / 有条件通过 / 不通过） | 备注 |
|---|---|---|---|---|---|

- 「通过」：交付物存在且验收标准全部满足
- 「有条件通过」：核心满足、边角待补，下周任务表首行列补项
- 「不通过」：下周任务表首行重做，并在周三站会说明原因
- 里程碑评审额外对照第 1 节硬指标；任一硬指标未达则里程碑延后，不压缩后续周

**固定交付位置**：模型 → `ml/checkpoints/text/{version}/` + `VERSIONS.md`；测试 → `test/reports/YYYY-MM/`；文档 → `docs/design/` `docs/releases/`；实验 → MLflow `text_detector`。

## 5. 依赖与外部资源（产品负责人 W1 前落实）

| 资源 | 用途 | 需要时间 |
|---|---|---|
| 云 GPU A100 40GB × 1（W1-W12 常驻）+ A100 80GB × 1（W9-W10 humanize） | 训练 / 推理 | W1 周一 |
| LLM API（Qwen / DeepSeek / GLM）预算约 ¥1,500 | 增强 3 万次 + 自建 30K 生成 | W2 |
| 微信小程序 AppID / Secret · 订阅消息模板审核 | code2session · 推送 | W2 / W6 |
| CHEAT 数据集商业授权申请 | 进训练（否则只做 evals） | W1 发起 |
| MinIO / 对象存储 | DVC · 文件存储 | W1 |
| 1 家内测客户 | 灰度 | W9 前确认 |

## 6. 风险

| 风险 | 影响 | 应对 |
|---|---|---|
| ml/ 链路从未运行，首跑必然暴露 bug | W1-W2 排期滑 | A/B 结对；W1 只求 smoke 通；W2 baseline 结果不设指标线 |
| fusion 相对 baseline 无显著增益（Amplifying no-go） | 模型路线调整 | W3 A/B 报告即决策点：无增益则 v0.2.x 转 cls_only + 更强数据，产品侧加码区间 / 复核 |
| 公开集场景标签是弱映射 | 6 场景验收无意义 | W5 自建数据是唯一解，优先级最高 |
| 学术文本高假阳是结构性的 | 客户投诉 | 产品定位「疑似 + 复核」；`academic_*` 用 `fpr_1pct`；报告给区间 |
| 微信资质 / CHEAT 授权 / GPU 预算不到位 | 对应任务空转 | 产品负责人 W1 前落实；缺哪项对应任务后移，不换人顶 |
| 五人跨端并行，契约漂移 | 联调返工 | W1 冻结契约，改动走评审；E 的接口自动化做契约守卫 |

## 7. 沟通与工具

- 任务下发：本文件第 3 节按周切片，周一由产品负责人贴到群 / 看板
- 看板：GitHub Projects（列：本周 / 进行中 / 待验收 / 通过 / 不通过）
- 代码：单仓 `master`，功能分支 + PR，CI 绿才可合；commit 格式「【模块】动作」
- 实验：MLflow experiment `text_detector`，run_name = yaml version
- 周三站会 15 分钟：只讲阻塞，不汇报进度
