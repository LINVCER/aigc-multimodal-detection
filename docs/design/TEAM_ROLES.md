# TEAM ROLES · 5 人实施期分工

> 项目当前状态：架构方案 / 骨架 / 训练环境 / 数据集清单已齐，进入实施期。本文档定 5 人纯技术团队分工与阶段产出。
> 参考：[ENTERPRISE_ARCHITECTURE.md](ENTERPRISE_ARCHITECTURE.md) §11 · [MODEL_UPGRADE_PLAN.md](MODEL_UPGRADE_PLAN.md) §4 阶段路线

---

## 0. 前提

- **不含专职 PM**：需求 / 客户对接由项目发起人或 R1 兼
- **收费功能不做**（P0-P3 全阶段）：credit_account / credit_transaction / payment_order 三张表暂不启用，`ruoyi-billing` 模块不建；未来商业化再启用
- **移动端 P1 同步上线**：R5 从 P0 就启动，与 Web 同步交付
- **DevOps 不独立成岗**：归 R2 兼；P2 以后产品上量再考虑拆独立岗

---

## 1. 五人职责总览

| 角色 | 主战场 | 关键 owner |
|---|---|---|
| **R1 · Java 后端 Lead + 架构** | 若依基座落地 + `ruoyi-detect` 检测编排 + `ruoyi-inference` gRPC 网关融合层 + DBA + 接口治理 | 系统架构、接口签字、model_version 灰度、跨模块协作 |
| **R2 · Java 后端 + 合规/报告 + DevOps** | 审计日志 / 报告 PDF/Excel / 电子签 / SSO CAS-OIDC / 私有化部署 / K8s / CI/CD | 教育部合规报告模板、私有化交付手册、发布流水线 |
| **R3 · Python 算法 + MLOps** | 训练脚本改造（mDeBERTa / Qwen LoRA）+ MLflow / DVC / Airflow + 6 套 evals + Triton/vLLM 部署 + 校准/仲裁接线 | 模型效果指标、evals 数字、Model Registry 状态流转 |
| **R4 · 全栈前端** | 现有 `frontend/` 8 个公共组件抽取 + 句子级 diff 视图 + AdminPanel 拆分 5 子页 + plus-ui 二次开发 | Web UI 完成度、国标红黄绿视觉规范、跨浏览器兼容 |
| **R5 · 移动端 + Python 推理胶水** | `mobile-app/` RN 全链路 + Python 推理 stub 到真实模型的胶水层 + Chrome 扩展（选做，引流） | Mobile 交付、gRPC/HTTP 客户端稳定性、推理服务对外契约 |

---

## 2. 阶段产出（对齐 UPGRADE_PLAN Phase 0-3）

| Phase | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|
| **P0 骨架**（2026 Q4） | 若依落地 + gRPC 编排骨架 + `docker-compose` 全栈起 | 审计日志表 + 基础 CI/CD + 数据备份策略 | 训练环境 + MLflow + HC3-Chinese 首基线 | 现有 frontend 联调 + AdminPanel 首拆 | RN 登录/上传/详情联调（mock 走通） |
| **P1 首版**（2027 Q1） | 检测状态机全流程 + gRPC 融合 + 报告服务 | 报告 PDF/Excel 模板 + SSO 骨架 | mDeBERTa 首版 + 溯源头 + 6 套 evals 建成 | 句子级高亮 + 降 AIGC UI + plus-ui 集成 | Mobile MVP 完整交付 |
| **P2 加固**（2027 Q2） | 灰度 / 熔断 / 限流 / 高可用 | K8s 上线 + 私有化脚本 + 电子签 PDF | 白盒双检（Fast-DetectGPT + Binoculars） + RADAR 对抗 + Airflow 全流水线 | 前端组件库 v2 + i18n + AdminPanel 完整 | 推送 + 离线草稿 + 报告分享 + 生物识别 |
| **P3 商用**（2027 Q3） | 万方 / 知网 API 对接 + OpenAPI | 等保三级 / 网信办备案 + 客户定制主题 | Qwen 2.5-7B LoRA humanizer + 学术图特化（P3.5 若延） | 定制主题 + 白标能力 | App Store / Google Play 上架 |

---

## 3. 关键 owner 与协作机制

### 3.1 单点决策 owner（争议时最终拍板人）

| 事项 | Owner |
|---|---|
| Java-Python gRPC proto 变更 | R1 签字 |
| 任何模型改动上 Staging / Production | R3 签字（必须先跑完 6 套 evals） |
| CI/CD 流水线变更 | R2（P0-P1）→ R3（P2 起随 MLOps 移交） |
| 数据合规（论文加密 / 过期 / 审计） | R2 |
| UI 视觉规范 / 组件设计 | R4（RN 侧 R5 复用其规范） |
| 数据集变更（DVC 加删） | R3 |

### 3.2 周协作节奏

- 周一：**evals 数字复盘**（R3 主讲，全员到；未达门槛的模型不上）
- 周二：**sprint review**（R1 主持，讲下周投入产出）
- 周五：**跨模块联调时间**（R1+R3 对齐 gRPC 契约 / R4+R5 对齐 UI 组件 / R2 汇报部署与合规进展）
- 全员：日常异步（企业微信 / 飞书），代码 review 24h SLA

### 3.3 交叉备份

- R1 出差 → R2 顶架构 review
- R3 出差 → R1 兜 evals 数字读取（不做训练）
- R4 出差 → R5 顶 Web 小 bug fix
- R2 出差 → R1 顶部署与 CI 应急

---

## 4. 招聘画像（外招用）

| 角色 | 技能硬门槛 | 加分项 |
|---|---|---|
| R1 | Java 8+ 年，Spring Boot 3 + gRPC + K8s + 若依（RuoYi-Vue-Plus）经验，能独立设计跨服务架构 | 有 SaaS 后端架构落地经验，做过多租户 |
| R2 | Java 5+ 年，做过合规/报告/文件处理，熟悉 Nginx / Docker / K8s，懂 SSO(CAS/OIDC) | 有教育行业交付经验（等保 / 网信办备案） |
| R3 | Python + PyTorch 3+ 年 + HuggingFace fine-tuning 履历 + 至少一次落地过 NLP 项目 | 会 vLLM/Triton 部署，做过 MLflow/DVC 全流水线 |
| R4 | Vue 3 + TS 3+ 年，做过复杂后台管理系统，会自己抽组件设计 | 熟悉若依 plus-ui 或类似基座，懂 i18n / a11y |
| R5 | React Native 2+ 年 或 Vue → RN 转型，懂 Python 基础 | 有 App Store / Google Play 上架经验 |

---

## 5. 明确不做（本团队规模的负向清单）

- ❌ **付费/账单/发票/微信支付宝对接** —— 用户已确认收费功能先不做
- ❌ 视频检测 / 音频检测 / deepfake 换脸 —— 场景无关
- ❌ 自训 backbone 大模型（10B+）—— 不在 5 人能力范围
- ❌ 多语言（英/日/韩）—— P0-P3 只做中文
- ❌ 专职测试 QA —— 每人对自己代码负责，R1 抽查
- ❌ 数据标注团队 —— 训练数据靠 LLM 自动生成 + spot check，标注量控制在 5% 以内
- ❌ 独立 UI 设计师 —— R4 出组件规范，实在需要精修再找外包

---

## 6. 数据模型调整（收费砍除对应）

原 `docs/sql/init.sql` 里以下三张表标记为 **P2+ 未启用**（DDL 保留、代码不引用）：

```sql
credit_account         -- 额度账户
credit_transaction     -- 额度流水
payment_order          -- 支付订单
```

对应 `platform-billing` Maven 模块 **不建**。前端「充值」入口 **不加**。

未来商业化重启时，从 DDL 直接激活即可（表结构本身合理）。

---

## 7. 里程碑（团队级）

| 时间 | 里程碑 | 验收人 |
|---|---|---|
| 2026-12 底 | P0：docker compose up 全栈起，Web+App 登录 + 上传 + stub 检测结果 | 全员 |
| 2027-03 底 | P1：内测 1 客户跑通「上传 → AI 率报告 + 段落定位 + 降 AIGC」 | R1 + R3 |
| 2027-06 底 | P2：DIPPER 中文攻击后 F1 > 0.7；新 LLM 零样本 F1 > 0.85；3-5 家 pilot | R3 |
| 2027-09 底 | P3：等保三级 + 网信办备案通过；私有化一键部署验收；行业客户 20+ | R2 |
