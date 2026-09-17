# ENTERPRISE ARCHITECTURE · 企业级论文 AIGC 检查平台系统架构方案

> **产品定位**：面向中国高校的论文 AIGC 检测 + 降 AIGC 一体化 SaaS
> **政策背景**：教育部 2025 年发布《关于加强高等学校学位论文 AIGC 检测工作的指导意见》，2026 年春季学期起全国高校全面实施；本科 AI 率 ≤ 20% / 硕士 ≤ 15% / 博士 ≤ 10%
> **交付形态**：Web（Vue）+ Mobile App（React Native + Expo）+ Chrome 扩展（引流）
> **技术栈**：Java 后端（Spring Boot 3 + Java 21）+ Python 训练/推理（独立微服务 gRPC/HTTP）+ MySQL/Redis/MinIO + MLflow/DVC/Airflow
> **报告日期**：2026-09-17

---

## 0. TL;DR — 一页纸架构总览

**服务分层**：

1. **用户端层**：Web（Vue 3.5 + TS + Pinia + Element Plus）｜Mobile（React Native + Expo）｜Chrome 扩展
2. **API 网关层**：Nginx / Spring Cloud Gateway，统一 SSL / 限流 / OAuth2 SSO
3. **Java 应用层**（Spring Boot 3 + Java 21）：认证 · 组织 · 任务编排 · 报告 · 账单 · 审计 · 推理网关
4. **推理服务层**（Python）：Triton Inference Server（分类 + embedding 多模型）+ vLLM（Qwen 2.5-7B LoRA 降 AIGC）+ FastAPI（白盒零样本检测）
5. **数据层**：MySQL 8 + Redis 7 + MinIO/OSS/S3
6. **MLOps 层**：MLflow + DVC + Airflow
7. **观测层**：Prometheus + Grafana + Loki + Tempo

**服务通信**：Java ↔ Python 走 gRPC（批推 / streaming）+ HTTP JSON（运维接口）；服务发现走 Nacos 或 K8s DNS。

**部署形态**：K8s（生产）+ docker-compose（开发）；模型热加载走 Triton model repository 挂载 MinIO。

---

## 1. 产品定位与合规

### 1.1 目标客户与场景

**核心客户**：高校教务处 / 研究生院 · 期刊编辑部 · 出版社 · 中小学（辅助线）

**核心 use case**：
- U1 学生上传论文 PDF/Word → AI 率（整体 + 段落级 + 句子级）+ 疑似 AI 段落 + 溯源
- U2 AI 率过高段落 → 降 AIGC 改写（保持学术语义）
- U3 教务批量提交 → 报告压缩包（PDF + Excel 汇总）
- U4 教师查看学生历次检测记录 + 教师 override
- U5 管理员配置院系 / 学位类型 / AI 率阈值（20/15/10%）

### 1.2 合规要求（教育部 2026 新规对齐）

| 要求 | 系统实现 |
|---|---|
| AI 率标准 本科≤20% / 硕士≤15% / 博士≤10% | 按学位类型配置阈值，报告标注达标状态 |
| 检测结果纳入答辩参考 | 报告 PDF 带电子签 + 校方章 + 溯源码 |
| 与传统查重并列 | 「AIGC + 查重」组合接口预留 |
| 数据本地化 | 全栈支持私有化部署 |
| 学生隐私 | 论文加密 at rest/transit；保留 30 天自动删除 |
| 学术不端追溯 | 检测记录归档，支持 5 年 |

### 1.3 认证目标

网信办生成式 AI 备案 · 等保 2.0 三级 · ISO 27001 · GB/T 45438-2025 合规声明

### 1.4 竞品情报与差异化定位（外网调研）

| 平台 | 定位 | 强项 | 弱点 |
|---|---|---|---|
| 知网 AIGC | >50% 高校主流 | 权威、深度学习多维度 | 算法保守，无降 AIGC，无溯源 |
| 维普 AIGC | 二线主流 | 比知网严 10% | 对人写文本误判率高 |
| 万方 AIGC | 中间派 | 平衡 | 无差异化 |
| Turnitin | 国际主流 | 300+ 词 98% 准确 | 中文弱、非母语误判严重 |
| GPTZero | 国际零售王 | 99.5% Booth 基准、句子级解释、免费层 | 无中文特化、无降 AIGC；独立测试 87% + 10% FP |
| Copyleaks | 国际企业 B 端 | 合规完备 | 中文弱 |

**差异化 5 张牌**：中文学术语料原生训练 · 溯源能力 · 降 AIGC 一体化 · 句子级解释 · 企业级私有化

---

## 2. Java 后端分层与模块划分

### 2.1 技术栈定选

| 项 | 选型 | 理由 |
|---|---|---|
| 语言 | Java 21 (LTS) | 虚拟线程 + record，适合 IO 密集检测网关 |
| 框架 | Spring Boot 3.3+ | 生态最厚 |
| 构建 | Maven | 运维栈熟悉 |
| 数据访问 | MyBatis-Plus 3.5+ | RuoYi 生态一致 |
| RPC | grpc-java + protobuf | 与 Python 通信 |
| 消息队列 | Redis Streams（P0）→ RocketMQ（P1） | 起步简单 |
| 缓存 | Redis 7 + Caffeine | 两级缓存 |
| 配置中心 | Nacos（可选） | 私有化首选 |
| 分布式锁 | Redisson | 事实标准 |
| 认证 | Spring Security 6 + JWT + OAuth2 SSO | CAS / OIDC 对接学校 |
| 权限 | RBAC + 数据权限（组织树） | 院系隔离 |
| 调度 | XXL-Job | 分布式任务 |
| Excel/PDF | EasyExcel + iText 8 | 报告导出 |
| Trace | Micrometer + OTel | Grafana Tempo 兼容 |

### 2.2 Maven 多模块

```
aigc-detect-platform/
├── platform-bom          依赖版本统一管理
├── platform-common       工具类 / 异常 / 响应体 / 枚举
├── platform-security     认证授权 / JWT / SSO / RBAC
├── platform-user         用户 / 组织 / 角色
├── platform-detect       检测任务编排 / 状态机 / 分块 / 重试
├── platform-report       报告 / PDF / Excel / 电子签
├── platform-billing      额度 / 订单 / 流水 / 对账
├── platform-inference    推理网关 (gRPC/HTTP 调 Python)
├── platform-audit        审计日志 / 归档
├── platform-notify       通知（站内信 / 邮件 / 短信 / 微信模板）
├── platform-admin        管理后台
├── platform-api-web      Web REST API
├── platform-api-mobile   Mobile REST API
└── platform-api-openapi  第三方 OpenAPI（查重系统对接）
```

### 2.3 关键领域模型

```sql
-- 组织与用户
sys_org (id, code, name, parent_id, type=UNIVERSITY|COLLEGE|DEPARTMENT|CLASS, level)
sys_user (id, org_id, role, username, real_name, student_no, ...)
sys_role (id, code, name, permissions_json)

-- 论文与检测
paper (id, user_id, title, degree_type=BACHELOR|MASTER|PHD, file_url, sha256, page_count, word_count, created_at)
detect_task (id, paper_id, status=PENDING|RUNNING|DONE|FAILED, ai_rate, source_labels_json, cost_credit, created_at, finished_at, model_version)
detect_paragraph_result (id, task_id, paragraph_idx, offset_start, offset_end, ai_prob, source_label, calibrated_prob, warnings_json)
detect_sentence_result (id, paragraph_id, sentence_idx, offset_start, offset_end, ai_prob)

-- 降 AIGC
humanize_task (id, source_task_id, original_text, rewritten_text, model_version, quality_score, cost_credit, created_at)

-- 报告
report (id, task_id, pdf_url, excel_url, signed_pdf_url, generated_at, expire_at)

-- 计费
credit_account (id, org_id | user_id, balance, updated_at)
credit_transaction (id, account_id, delta, reason=RECHARGE|CONSUME|REFUND|GRANT, ref_id, ref_type, created_at)
payment_order (id, account_id, amount, method=WECHAT|ALIPAY|OFFLINE, status, third_party_no, created_at)

-- 审计与模型
audit_log (id, user_id, action, entity_type, entity_id, ip, ua, created_at)
model_version (id, name, version, sha256, calibration_params_json, val_metrics_json, deployed_at)
```

### 2.4 检测任务编排（Java 侧）

**状态机**：PENDING → RUNNING → DONE / FAILED（可重试）

1. `POST /api/v1/detect` 上传，存 MinIO + 落库 + 建任务
2. 抽文本（Apache Tika），按 512-1024 token 切段，再切句
3. gRPC 批量调推理：
   - 每 32 段一批 → Triton 主分类头
   - 灰区（conf ∈ [0.35, 0.65]）段落 → FastAPI 白盒双检
   - Triton 溯源头 → source_label
   - 句子级独立评分（前端高亮）
4. 融合：句 → 段 → 文档（长度加权 mean）
5. 报告（PDF + Excel）+ 通知
6. 扣费 + 失败自动退款

**性能**：50 页论文 ≈ 200 段落 ≈ 1500 句 ≈ 15-30 秒（GPU 充足）。虚拟线程支撑单机 500+ QPS。

---

## 3. Python 推理服务架构

### 3.1 三层推理

```
① Triton Inference Server (:8001 gRPC / :8000 HTTP)
   - text_detector_deberta_v3/    ONNX 主分类头
   - source_attribution_deberta/  ONNX 溯源多分类
   - embedding_bge_zh/            ONNX 段落 embedding
   - image_detector_clip/         ONNX 论文插图检测
   动态批处理 / 多模型并发 / TensorRT / metrics

② vLLM (:8002)
   Qwen 2.5-7B-Instruct + LoRA (humanize_academic_v1)
   降 AIGC 改写；PagedAttention + continuous batching
   Warm start: HF 现成 arunsingh80475/qwen2.5-14b-humanizer-v3-lora

③ FastAPI 白盒服务 (:8003)
   Qwen 2.5-1.5B (observer) + Yi-1.5-6B (performer)
   Fast-DetectGPT + Binoculars；仅灰区触发
```

**为什么不用 TorchServe**：TorchServe 2025-08 已归档进入 Limited Maintenance，新项目不能选。

### 3.2 Triton Model Repository

```
/models/
├── text_detector_deberta_v3/
│   ├── config.pbtxt          max batch=32, dynamic batching
│   ├── 1/model.onnx + tokenizer/
│   └── labels.txt
├── source_attribution_deberta/
└── ...
```

**热更新**：checkpoint → MLflow Registry → CI 导 ONNX → MinIO → Triton 自动加载新 version（不重启）。

### 3.3 gRPC proto 骨架

```protobuf
service DetectionService {
  rpc DetectParagraph(DetectParagraphRequest) returns (DetectParagraphResponse);
  rpc DetectBatch(DetectBatchRequest) returns (DetectBatchResponse);
  rpc DetectWhitebox(DetectWhiteboxRequest) returns (DetectWhiteboxResponse);
  rpc HumanizeStream(HumanizeRequest) returns (stream HumanizeChunk);
  rpc AttributeSource(AttributeRequest) returns (AttributeResponse);
}

message DetectParagraphResponse {
  double ai_prob = 1;
  double calibrated_prob = 2;
  ConfidenceInterval interval = 3;
  string risk_level = 4;
  optional string warning = 5;
  map<string, double> branch_scores = 6;
}
```

### 3.4 Java gRPC 客户端 wrapper

负载均衡（K8s Service round-robin）· 熔断（Resilience4j，超时 3s）· 降级（fallback backup 模型）· 限流（Bucket4j 60 段/分/用户）· 重试（指数退避 ×3）· 观测（P50/P95/P99 + error rate）

---

## 4. 模型选型（论文场景特化，外网调研支撑）

### 4.1 主分类器 —— DeBERTa-v3 系

**依据**：
- DeBERTa-Sentinel（arxiv 2608.01046）在 GLC-AIText 28K 上 val_acc 98.21%，超 RoBERTa-Sentinel（NeurIPS 2025 baseline）
- desklib/ai-text-detector-v1.01（DeBERTa-v3-large 430M）RAID benchmark 排 5，HF 第一

**决策**：P0 `microsoft/mdeberta-v3-base`（279M，兼容现有训练脚本）→ P1 `deberta-v3-large` / `xlm-roberta-large` → P2 Qwen 2.5-1.5B/3B decoder-only detector（数据 500K+ 后）

### 4.2 句子级检测（差异化能力）

**依据**：
- arxiv 2509.17830：Transformer encoder + CRF 的句子级 sequence labeling，专门做人机混写边界分割
- GPTZero 官方论文（arxiv 2602.13042）：文档 = 句子序列，句子级 perplexity + burstiness，同时输出文档级 + 句子级
- HACo-Det（arxiv 2506.02959）：人机共写细粒度检测研究

**决策**：P1 实现「句级打分 + CRF 边界分割」，报告支持"这段的前两句是人写、后三句是 AI"的精细定位。

### 4.3 白盒零样本双检

Fast-DetectGPT（ICLR 2024，快 340×）+ Binoculars（ICML 2024，跨代泛化）+ DAMAGE（arxiv 2501.03437，抗对抗改写）

### 4.4 降 AIGC —— Qwen 2.5-7B/14B LoRA

**依据**：
- CCL25-Eval Task 5：LoRA 微调 Qwen2.5-14B 比 baseline +9.7%（arxiv 2606.12392 / ACL 2025.ccl-2.24）
- HF 现成 `arunsingh80475/qwen2.5-14b-humanizer-v3-lora` 可 warm start
- XiangJinyu/humanize-zh：CSL 学术摘要合成 18K 训练对 + 双向 rejected data

**决策**：P0 Qwen 2.5-7B + LoRA（r=16, alpha=32）；vLLM 部署，A100 40GB 支持 40+ 并发。

### 4.5 溯源头

8-way：`human / GPT / Claude / Qwen / DeepSeek / GLM / Kimi / 文心 / 其他`。**Qwen 是最难检测的生成器**（DetectRL-X），Qwen 样本必须充足。

### 4.6 对抗鲁棒

- 攻击面：Adversarial Paraphrasing（arxiv 2506.07001）是 2025 通用攻击；DIPPER 能把 DetectGPT 从 70.3% 打到 4.6%
- 防御：RADAR 对抗训练（+31.64% acc）+ DIPPER-style 中文数据增强（GLM-4 生成）+ Fight-Poison-with-Poison 少样本对抗训练（arxiv 2605.02374）

### 4.7 训练数据（从 0 构建，教育路径特化）

**公开集起步**：
- HC3-Chinese（24.3K，含 finance/medicine/open_qa/wiki 子集，HF `Hello-SimpleAI/HC3-Chinese`）
- HC3-Plus（语义不变扩充版）
- CHEAT（35K ChatGPT 学术摘要）
- M4 / MAGE（溯源多生成器）
- C-ReD（2026 中文真实 prompt 基准，arxiv 2604.11796）
- MAGA-Bench（2026 机器增强文本基准）

**自建（100K+ 目标）**：
- 5 场景（论文摘要 / 正文段落 / 实验报告 / 议论文 / 学术翻译）× 6-8 家中文 LLM × 3-5K 条
- Human 端：CNKI 公开摘要 + 教材 + **2020 年前语料**（防 AI 污染）
- 对抗改写 20%：GLM-4 / Qwen 三档强度改写
- 标注成本接近 0（生成即打标），spot check 5%

---

## 5. React Native + Expo 移动端

- Expo SDK 51+ · TS 严格模式 · Zustand · Tamagui/NativeBase · Expo Router · TanStack Query
- expo-secure-store + AsyncStorage · expo-document-picker · Expo Push · i18next
- **MVP**：登录/SSO · 上传（≤20MB）· 任务列表/详情 · AI 率卡 + 段/句级高亮 · 降 AIGC · 报告 PDF
- **P1**：离线草稿 · 推送 · 生物识别 · 分享微信/钉钉
- **不做**：拍照识字 / 语音 / 社交
- API：`/api/v1/mobile/*` 独立版本，字段精简 + top-20 段分页 + gzip/HTTP2

---

## 6. Web 前端（Vue 3.5 + TS）

1. 拆 AdminPanel 63 KB → `/admin/*` 5 子页
2. 抽 8 个公共组件（DetectionForm / ResultPanel / ConfidenceBar / AIRateBadge / ConflictWarning / DetectionHistory / ParagraphList / SentenceHighlight）
3. 国标红黄绿视觉（≤阈值绿 / [阈值,1.5×] 黄 / >1.5× 红）
4. 段落级 + 句子级 diff 视图（原文 + AI 高亮 + 降 AIGC 版对比）

---

## 7. 数据层（保 MySQL + Redis + MinIO）

- **MySQL 8**：InnoDB + utf8mb4；P1 读写分离（ShardingSphere-JDBC）；P2 分库分表（detect_task 按 org_id+created_at）；xtrabackup 全量 + binlog 增量
- **Redis Cluster**（3 主 3 从）：会话 / 缓存 / 限流 / Streams 队列 / 分布式锁 / Calibration 参数 / EWMA 权重
- **MinIO** 分布式 4 节点（可切 OSS/S3）：SSE-S3 + 客户端 AES-256；论文 30 天删；报告 3 年；权重永久；报告走 CDN

---

## 8. MLOps 层

- **MLflow**：Tracking（MySQL + MinIO artifact）+ Registry（Staging → Production → Archived）；CI 自动比较 val_metrics，优于 Prod 建 Staging，人工 approve
- **DVC**：训练/评测/对抗数据全 track（MinIO backend）；PR 触发 `dvc pull` + sample eval
- **Airflow 4 DAG**：公开数据周同步 / 每日增量训练 / 每周对抗生成（GLM-4 3K 条）/ 每周全量 evals 报告
- **GPU**：A100 40GB（backbone）+ A100 80GB ×2-4（LoRA + eval）；**阿里云 PAI + OSS**（教育信任 + 数据不出境），备选腾讯云 TI-ONE

---

## 9. 部署与运维

- **环境**：dev（compose）/ test（K8s 3 节点 + T4）/ staging（5 节点 + 2 GPU）/ prod（10+ 节点 + 4 A100）/ prod-edu-{校}（私有化）
- **K8s**：ingress-nginx · java-api ×3 (HPA) · web ×2 · mysql 主从 · redis ×6 · minio ×4 · triton ×2 · vllm ×1 (A100 80GB) · fastapi-whitebox ×2 · mlflow · airflow · CronJob（周评测 / 日清理）
- **CI/CD**：PR（编译+单测+Sonar / lint+unit+safety）→ develop（test 环境）→ tag（staging → approve → prod）；Argo Rollouts 5%→25%→100%
- **观测**：Prometheus + Grafana + Loki + Tempo + OTel；SkyWalking 可选；Alertmanager → 钉钉/企微；大盘含 GPU 利用率 / P99 / 队列 / 错误率 / 每日检测量

---

## 10. 安全

- **数据**：TLS 1.3 全站；论文 AES-256-GCM + KMS；MySQL TDE；加密备份跨区域
- **应用**：JWT RS256 + Refresh；SSO CAS/OIDC；RBAC + org_id 隔离；API HMAC 签名防重放；三级限流；CSP；MyBatis 参数化禁 `${}`；上传 MIME 白名单 + magic number + ClamAV；内容审核 API
- **模型**：定期 DIPPER 对抗测试（F1 掉 >10 pp 告警）；query rate limit + 异常访问检测；差分隐私训练（P2 可选）

---

## 11. 团队规划

**8-12 人**：PM 1 · Java 3 · Python 算法/MLOps 2 · Web 1 · RN 1 · SRE 1 · QA 1 ·（可选 UI 0.5 + 标注 2）
**3-5 人 MVP**：PM 1 + Java 2 + Python 1 + Web 1（Mobile 延后）

---

## 12. 12 个月实施路线

### Phase 0 · 架构落地（2026-10 → 2026-12）
- [ ] 决策 fork vs 重开新仓（建议重开）
- [ ] Java 骨架（Spring Boot 3 + Maven 多模块 + 数据层 compose）
- [ ] Triton + FastAPI 基础推理服务
- [ ] gRPC proto + Java 客户端 wrapper
- [ ] RN + Expo 初始化 + 登录 + 上传骨架
- [ ] Web AdminPanel 拆分
- [ ] CI/CD 基础流水线
- [ ] docker-compose 全栈可起

**验收**：compose 起全栈，Web + App 登录 + 上传论文 + 拿到 stub 检测结果

### Phase 1 · 模型基线上线（2027-01 → 2027-03）
- [ ] mDeBERTa-v3-base 主分类器训练（HC3-Chinese + CHEAT + 自建）
- [ ] Qwen 2.5-7B LoRA humanizer（20K 学术改写 pairs）
- [ ] 溯源头（8-way）
- [ ] 4 个 evals 测试集（in-domain / cross-gen / adversarial / short-text）
- [ ] Calibration + Arbitrator 接线
- [ ] Java 完整检测流程 + 报告
- [ ] 内测 1 客户

**验收**：内测客户跑通「上传 → AI 率报告 + 段落定位 + 降 AIGC」

### Phase 2 · 白盒 + 对抗鲁棒 + 句子级（2027-04 → 2027-06）
- [ ] Fast-DetectGPT / Binoculars 中文集成（灰区触发）
- [ ] 句子级 CRF 边界分割（arxiv 2509.17830 方案）
- [ ] RADAR 对抗训练 + DIPPER-style 中文增强
- [ ] MLflow + DVC + Airflow 全流水线
- [ ] 移动端功能完整
- [ ] 3-5 家 pilot

**验收**：DIPPER 中文攻击后 F1 > 0.7；新 LLM 零样本 F1 > 0.85；句子级边界 F1 > 0.6

### Phase 3 · 企业化 + 商业化（2027-07 → 2027-09）
- [ ] 私有化一键部署（K8s + Swarm 精简版）
- [ ] SSO CAS/OIDC · 电子签 + 校方章
- [ ] 计费/对账/发票
- [ ] 等保三级 + 网信办备案
- [ ] 知网/万方 API 对接（AIGC + 查重双检）
- [ ] 商业客户 20+

---

## 13. 风险清单

| 风险 | 严重度 | 缓解 |
|---|---|---|
| 教育部政策变动 | 高 | 阈值可配 + 报告模板版本化 |
| 新代 LLM 检测失效 | 高 | 白盒双检兜底 + 季度重训 |
| 私有化交付慢 | 中 | Swarm 精简版 + 部署脚本 |
| GPU 成本失控 | 中 | vLLM 大 batch + 灰区触发 + 缓存 |
| 学生对抗改写工具进步 | 高 | RADAR + DIPPER 增强 + 持续对抗训练 |
| 论文原文泄露 | 极高 | AES-256 + KMS + 30 天过期 + 审计 |
| 与知网/维普/万方竞争 | 高 | 定位"交叉验证 + 降 AIGC 一体化" |
| 教师端误判信任危机 | 高 | 置信区间 + 教师 override + 溯源解释（GPTZero 独立测试也只有 87% + 10% FP，误判管理是行业共同课题） |
| 团队 GPU 训练经验不足 | 中 | Phase 1 招 1 位 senior 算法工程师 |

---

## 14. 与 LINVCER 上游仓库的关系

**建议：不 fork，从头建仓**。

理由：主线 3.5 个月未动 + License「仅供学术研究」商用障碍 + API key 泄露 + 企业级架构与单体 Python 差距过大（重构成本 > 重写）。

**保留借鉴**（算法起点）：
- `train_text_detector.py`：Focal / R-Drop / EMA / FGM / GRL / SupCon 全套微调技巧
- `arbitration.py`：贝叶斯融合（log-sum-exp + EWMA + 冲突检测）
- `calibration.py`：Temperature + Platt + ECE
- `train_image_sd.py`：AUC / EER / TPR@FPR / ECE 评测代码
- C2PA + GB45438 元数据检测

**动作**：建独立仓库（`paper-aigc-detect` / `academic-aigc`）· Java 从 0 建（参考 RuoYi / pig4cloud）· Python 训练脚本借来改造成 MLflow-friendly · License 换 Apache 2.0 + 商业授权

---

## 15. 立即下一步（0-2 周）

1. 决策 fork vs 从头建仓（推荐从头建）
2. 注册域名 + 云账号（阿里云 / 腾讯云）
3. 搭 Java 骨架（Spring Boot 3 + Java 21 + Maven + 数据层 compose）
4. 搭 Python 训练环境（Conda + PyTorch + Transformers + MLflow + DVC）
5. 拉中文 AIGC 公开数据集（HC3-Chinese / CHEAT / M4 / C-ReD）
6. 决定团队规模与招聘

---

## 16. Sources（外网调研）

**模型 / 论文**
- [C-ReD: Chinese Benchmark for AI-Generated Text Detection](https://arxiv.org/pdf/2604.11796)
- [MAGA-Bench](https://arxiv.org/pdf/2601.04633)
- [DeBERTa-Sentinel](https://arxiv.org/html/2608.01046v1)
- [On the Effectiveness of LLM-Specific Fine-Tuning](https://arxiv.org/html/2601.20006v1)
- [DetectRL-X](https://arxiv.org/pdf/2605.15518)
- [HACo-Det](https://arxiv.org/pdf/2506.02959)
- [Dynamic perturbations detection](https://arxiv.org/pdf/2504.21019)
- [Reasoning-Aware AIGC Detection](https://arxiv.org/pdf/2604.19172)
- [Adversarial Paraphrasing](https://arxiv.org/pdf/2506.07001)
- [DAMAGE](https://arxiv.org/pdf/2501.03437)
- [Fight Poison with Poison](https://arxiv.org/pdf/2605.02374)
- [Paraphrasing Attack Resilience](https://arxiv.org/html/2605.14240v1)
- [DIPPER](https://arxiv.org/pdf/2303.13408v2)
- [XtraGPT](https://arxiv.org/pdf/2505.11336)
- [CCL25-Eval Task 5: LoRA-Fine-Tuned Qwen2.5](https://arxiv.org/abs/2606.12392)
- [qwen2.5-14b-humanizer-v3-lora (HuggingFace)](https://huggingface.co/arunsingh80475/qwen2.5-14b-humanizer-v3-lora)
- [XiangJinyu/humanize-zh](https://github.com/XiangJinyu/humanize-zh)
- [aigc-humanizer-zh MCP server](https://glama.ai/mcp/servers/shuohui-air-technology/aigc-humanizer-zh)
- [Multiscale Positive-Unlabeled Detection (ICLR'24 Spotlight)](https://github.com/YuchuanTian/AIGC_text_detector)
- [DetectRL](https://arxiv.org/pdf/2410.23746)
- [AIGCDetectBenchmark](https://github.com/Ekko-zn/AIGCDetectBenchmark)
- [Fine-Grained Detection Using Sentence-Level Segmentation](https://arxiv.org/html/2509.17830v2)
- [GPTZero: Robust Detection of LLM-Generated Texts（官方论文）](https://arxiv.org/pdf/2602.13042)

**数据集**
- [HC3-Chinese (HuggingFace)](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese)
- [HC3 Plus](https://arxiv.org/html/2309.02731v2)
- [Hello-SimpleAI/chatgpt-comparison-detection](https://github.com/Hello-SimpleAI/chatgpt-comparison-detection/blob/main/HC3/README.md)

**推理框架**
- [Triton vs vLLM](https://kubernetes.recipes/recipes/ai/triton-inference-server-vs-vllm-comparison/)
- [vLLM vs Triton 企业对比](https://gigagpu.com/vllm-vs-triton-inference-server/)
- [TorchServe Limited Maintenance](https://theneuralbase.com/torchserve/learn/advanced/vs-triton-inference-server/)

**政策与竞品**
- [2026 高校论文 AI 率新规（CSDN）](https://blog.csdn.net/aigccleaner/article/details/158815343)
- [2026 高校 AIGC 检测新规（cnblogs）](https://www.cnblogs.com/humanizeai/p/19684404)
- [Turnitin vs Copyleaks vs GPTZero 2026](https://www.browse-ai.tools/blog/turnitin-vs-copyleaks-vs-gptzero-2026-ai-detection-guide-for-educators)
- [GPTZero vs Turnitin vs Copyleaks](https://www.thehumanizer.ai/blog/gptzero-vs-turnitin-vs-copyleaks-which-is-strictest)
- [GPTZero Review 2026](https://fast.io/resources/gptzero-ai-detector-review-2026/)
- [知网 vs 维普 vs 万方（CSDN）](https://blog.csdn.net/aigccleaner/article/details/158237711)
- [知网/维普/万方各平台标准对比](https://www.cnblogs.com/humanizeai/p/19684527)
- [知网 vs 维普 vs 万方 AIGC 检测区别](https://www.cnblogs.com/humanizeai/p/19684335)

---

**架构方案 v1 完毕。下一步可选：Java 模块 skeleton / Triton 配置样板 / RN 初始化脚本 / 训练数据 pipeline 详细方案。**
