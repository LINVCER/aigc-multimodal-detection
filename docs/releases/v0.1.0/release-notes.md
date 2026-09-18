# v0.1.0 · Baseline

**发布日期**：2026-09-18
**Codename**：baseline
**Git tag**：`v0.1.0`（拟）

## 概要

首个规范化版本，把 Wave 1–4 已完成内容整体归档为 baseline，正式启动版本管理路线：
- 版本文档中心（`docs/releases/`）就位，之后每次发版走这里
- 模型迭代目录（`ml/`）与旧 `legacy/algorithms/` 严格分离
- DB 变更改走 Flyway 命名规范（`V*` 增量、`R*` 幂等）

## Added

- **C 端**：使用场景 6 分类（本科/硕士/博士/职业/自媒体/其他）取代旧学位红线
- **反馈模块** (W3.d)：C 端提交 + 后台处置 + Profile / 报告详情双入口
- **运营后台** (W3.e)：大盘 KPI · 用户列表 · 任务列表 · 反馈处置四页
- **推理链路**：Java 侧 IInferenceClient 抽象 + Python 侧 detector 加载器
- **文件存储**：IStorageService 抽象 + 本地 FS 兜底实现
- **mobile-uniapp iOS 精致化**：Design Tokens + 主列表/报告页/上传页全量重写

## Changed

- **Java 后端 3 层规范化**（Phase A · Task #61）：
  - Controller → Service (I+Impl) → Repository (I+Impl)
  - Entity / DTO / VO 三种数据类型分离
  - 全局异常处理器 + ErrorCode 4 段编码
  - `DetectController` 从 708 行瘦身到 130 行
- **数据库 schema** 从散装 `patch-schema.sql` 迁到 `sql/V0.1.0.*.sql`

## Fixed

- 🔴 Sa-Token 拦截 `/api/v1/auth/**` → 加 `@SaIgnore`
- 🟠 retry() 不重跑推理（永久 PENDING）→ 从 IStorageService 反读原稿重跑
- 🟠 submit userId 恒空 → 前后端 hotfix 补透传
- 🟠 GlobalExceptionHandler 无 `@Order` → 加 `HIGHEST_PRECEDENCE`
- 🟠 推理全失败仍 DONE → 改置 FAILED
- 🟡 legacy `entity/DetectTask.java` 同名类残留 → 删除
- 🟡 包扫描问题 → `DetectAutoConfiguration` + Spring Boot 3 AutoConfiguration SPI

## Breaking

无。首个规范化版本。

## Known Issues

- **推理挂 legacy checkpoint 兜底**：新一代模型 (`v0.1.0-baseline` on `ml/`) 训练计划待启动，
  当前推理层加载的 `aigc_detector_v3_thesis.pth` 是老实验产物，见 `ml/VERSIONS.md`
- **DB migration 首次跑**：本版 SQL 为 baseline 全量，未来增量走单独文件
- **Docker 不用**：本版按本地环境走，MinIO 用本地 FS 兜底

## 升级步骤

见 [`migration.md`](migration.md)

## SQL 变更

见 `sql/` 目录：
- `V0.1.0.001__init_ops_backend_schema.sql`   运营后台 4 张表
- `V0.1.0.002__init_detect_task_schema.sql`   检测任务 3 张表
- `R__seed_scenario_threshold.sql`            6 场景阈值默认值（幂等）
