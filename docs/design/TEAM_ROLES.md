# TEAM ROLES · 5 人课题组分工（多模态版）

> 项目定位：**多模态 AIGC 检测课题**（文本 + 图像 + 音频），本科毕设 / 硕士课题 / 大创 / 挑战杯级别，不做商用不接客户。
> 目标：技术验证 + 学术产出（论文 / 报告）+ 可演示 demo。
> 参考：[ENTERPRISE_ARCHITECTURE.md](ENTERPRISE_ARCHITECTURE.md) · [MODEL_UPGRADE_PLAN.md](MODEL_UPGRADE_PLAN.md) · [DATASETS.md](DATASETS.md) · [BASELINE.md](BASELINE.md) · [MODEL_RESEARCH_TEXT.md](MODEL_RESEARCH_TEXT.md) · [MODEL_RESEARCH_IMAGE_TAMPERING.md](MODEL_RESEARCH_IMAGE_TAMPERING.md)

---

## 0. 前提

- **课题组 5 人**（学生），隐含 1 位指导老师
- **多模态覆盖**：文本 / 图像（生成 + 篡改）/ 音频
- **交付定义**：能跑通的原型 + 各模态评测数字 + 论文/毕设章节 + 结题演示
- **明确不做**：客户对接 / 售前 / 收费 / 上架 / 私有化 / 等保 / 网信办备案 / 白标定制 / 商务运营
- **时间线**：一学年（约 2 学期，8-10 个月）
- **每人的"课题产出"** = 一个可讲的技术贡献点 + 一篇可投稿的论文（会议或核心期刊）

---

## 1. 五人角色总览（按模态切分）

| 角色 | 主战场 | 学术贡献点（个人课题） | 目标会议/期刊 |
|---|---|---|---|
| **S1 · 系统架构与集成 + Web demo** | 若依基座 + gRPC 网关 + `ruoyi-detect` 检测编排 + Docker 部署 + 现有 `frontend/` 完善 | 「面向多模态 AIGC 检测的 Java + Python 微服务平台架构」 | 毕设章节 / 软件学报应用短文 |
| **S2 · 文本 AIGC 检测** | 主分类器 DeBERTa-v3 + 白盒双检 + 溯源头 + 对抗鲁棒 + 论文场景 6 套 evals | 「基于 DeBERTa-v3 与白盒双检的中文论文 AIGC 检测方法」 | **CCL / NLPCC / EMNLP-short / 中文信息学报** |
| **S3 · 图像 AIGC 检测 + 篡改定位** | CLIP/DINOv2 + 校准（GenImage/GenImage++）+ 篡改定位（ForMa 换掉 Mask R-CNN）+ 论文插图特化 | 「面向学术论文插图的 AIGC 生成检测与篡改定位」 | **CVPR-W / ICME / 中国图象图形学报 / 电子学报** |
| **S4 · 音频 AIGC 检测** | Wav2Vec2 XLS-R / AASIST 中文微调 + RawNet2 融合 + ASVspoof + 中文 TTS 检测 | 「基于 XLS-R + AASIST 融合的中文 TTS 深度伪造检测」 | **ICASSP / Interspeech / SLT / 声学学报** |
| **S5 · 降 AIGC 生成 + 数据构建 + 移动端 demo** | Qwen 2.5-7B LoRA humanizer + 100K 多模态数据集 pipeline + DVC + RN + Expo App | 「基于 Qwen-LoRA 的学术文本人性化改写方法」 或 「多域中文多模态 AIGC 检测数据集构建」 | **CCL / NLPCC / LREC-COLING / 中文信息学报** |

**分工设计原则**：
- 每人绑一个**独立模态或独立任务**，论文选题会议不同，避免共同一作撞车
- S1 兼 Web demo 是因为课题级 UI 不需要设计规范，够用即可
- S5 一人两担（生成 + 数据），因为数据构建横跨所有模态，需要一个"数据 owner"统筹；移动端 RN 相对独立可兼

---

## 2. 阶段推进（一学年 = 2 学期）

### 学期 1 · 前 3 个月（基础建设 + 各模态 baseline）

| S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|
| 若依基座 + Docker 全栈起 + gRPC proto 编排通 | 现有 `train_text_detector.py` 跑 baseline（RoBERTa on HC3-Chinese） | 现有 `train_image_sd.py` 跑 baseline（CLIP-ViT on GenImage 子集） | 恢复并跑 Wav2Vec2 音频检测 baseline（ASVspoof 或小样本） | 拉 HC3-Chinese + CHEAT + M4 + GenImage 入 DVC，跑通训练数据管道 |

**中期检查（第 3 个月末）**：全栈 `docker compose up` 起来 + 三模态各出第一份 baseline val_acc / AUC 数字。

### 学期 1 · 后 3 个月（模态主线 + demo 雏形）

| S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|
| 检测状态机 + 报告服务 + 三模态融合接口 | mDeBERTa-v3-base 训练 + 溯源头 8-way + 文本 evals | CLIP-L + Linear 校准 + ForMa 篡改定位 + 图像 evals | XLS-R 中文微调 + AASIST 融合 + 音频 evals | Qwen 2.5-7B LoRA humanizer 首版 + 自建数据扩到 30-50K |

**学期 1 结题**：完整技术 demo（三模态都能跑通 上传→检测→报告），学期报告，中期答辩材料。

### 学期 2 · 前 3 个月（论文实验 + 对抗鲁棒）

| S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|
| 系统稳定性 + 消融实验平台支持 | 白盒 Fast-DetectGPT + Binoculars 集成 + RADAR 对抗 + 论文实验 + 初稿 | GenImage++ 泛化 + 学术图 western blot 特化 + 论文实验 + 初稿 | 中文 TTS 生成集扩充（ChatTTS / CosyVoice）+ 对抗训练 + 论文实验 + 初稿 | LoRA 迭代 + 100K 数据完成 + 移动端 RN demo 开工 |

### 学期 2 · 后 3 个月（论文投稿 + 结题）

| S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|
| 集成 demo 精修 + 开源 repo 整理 | 论文投稿 + 毕设 | 论文投稿 + 毕设 | 论文投稿 + 毕设 | 数据集论文 or 降 AIGC 论文 + 毕设 + 移动端 demo 完成 |

**结题（学期 2 末）**：全员毕设过 + 至少 3 篇论文投稿或收录 + 开源 GitHub 仓库。

---

## 3. 关键协作与 owner

| 事项 | Owner |
|---|---|
| 系统接口（gRPC proto / REST API） | S1 |
| 文本模型指标 | S2 |
| 图像模型指标 | S3 |
| 音频模型指标 | S4 |
| 降 AIGC 效果评估 | S5 |
| 数据集质量与均衡（防 label 噪声） | S5（跨模态统筹） |
| 三模态融合决策层 (`arbitration.py`) | S1 + S2/S3/S4 联合，S1 拍板 |
| 论文写作时间表 | 各人负责自己论文，老师统筹投稿排期 |
| 开源仓库整理 | S1 + S5 |

**协作节奏**（课题组）：
- 每周一次组会：轮流讲进展 + 老师 review + 定下周工作
- 每月一次跨模态联调：S1 系统 + S2/S3/S4 模型 + S5 数据 一起，重点对齐 gRPC 接口和融合层数据结构
- 论文投稿高峰期（一般是 5-7 月 CCL / 9-10 月 EMNLP / 3 月 Interspeech）：老师主导，全员配合复现实验

---

## 4. 明确不做（课题级负向清单）

- ❌ 客户对接 / 售前 / 商务 / 收费
- ❌ 上架 App Store / Google Play（demo 只跑 Expo 预览就够）
- ❌ 私有化部署 / 等保 / 网信办备案
- ❌ 高可用 / 灰度发布 / 熔断限流（demo 单机跑即可）
- ❌ K8s 集群部署（docker-compose 单机足够）
- ❌ 微信 / 支付宝 / SSO 集成
- ❌ 白标 / 主题定制
- ❌ 万方 / 知网 API 对接
- ❌ App 推送 / 生物识别 / 深链
- ❌ 视频检测 / deepfake 换脸 —— 音频与图像已覆盖，视频超出算力
- ❌ 自训 backbone 大模型（10B+，算力不允许）
- ❌ 商业英文 / 多语言 UI

---

## 5. 数据模型调整（对应课题定位）

原 `docs/sql/init.sql` 中以下表 **不启用**（DDL 保留作参考）：

```sql
credit_account         -- 无收费
credit_transaction     -- 无流水
payment_order          -- 无支付
```

前端「充值 / 支付 / SSO 登录」入口 **不加**。用最简单的账号密码登录即可。

---

## 6. 里程碑（学术级）

| 时间 | 里程碑 | 验收 |
|---|---|---|
| 第 3 个月末 | 中期：全栈起 + 三模态各出 baseline 数字 | 老师 review |
| 学期 1 结题 | 完整三模态 demo + 第一份技术报告 | 学院答辩 / 组会 |
| 学期 2 中期 | 各模态论文初稿 + 对抗鲁棒实验 | 老师 review |
| 学期 2 结题 | 全员毕设过 + 至少 3 篇论文投稿 + 开源仓库 | 答辩委员会 |

---

## 7. 论文选题与投稿建议

| 学生 | 论文选题 | 目标会议/期刊 | 投稿窗口 |
|---|---|---|---|
| S2 文本 | 「基于 DeBERTa-v3 + 白盒双检的中文论文 AIGC 检测」 | CCL / NLPCC / EMNLP-short / 中文信息学报 | CCL 5-7 月 / EMNLP 6 月 |
| S3 图像 | 「面向学术论文插图的 AIGC 生成检测与篡改定位」 | CVPR-W / ICME / 中国图象图形学报 | CVPR-W 3 月 / ICME 12 月 |
| S4 音频 | 「基于 XLS-R + AASIST 融合的中文 TTS 深度伪造检测」 | ICASSP / Interspeech / SLT / 声学学报 | ICASSP 9 月 / Interspeech 3 月 |
| S5 生成/数据 | 「基于 Qwen-LoRA 的学术文本人性化改写」或「多域中文多模态 AIGC 检测数据集」 | CCL / NLPCC / LREC-COLING | CCL 5-7 月 / LREC 10 月 |
| S1 系统 | 系统类难独立发表，可作为毕设章节 或 与其他学生合作出应用型论文 | 软件学报应用短文 / 毕设 | — |

**投稿多样化好处**：5 人不同会议不同截止时间，避免全员在同一 deadline 死磕；且每篇论文有独立第一作者。

---

## 8. 各模态调研文档索引

- 文本：[MODEL_RESEARCH_TEXT.md](MODEL_RESEARCH_TEXT.md)（v1 + v2 增补，2025-2026 SOTA + 中文数据集 + 对抗鲁棒）
- 图像 + 篡改：[MODEL_RESEARCH_IMAGE_TAMPERING.md](MODEL_RESEARCH_IMAGE_TAMPERING.md)（GenImage / ForMa / 学术图特化 Proofig/ImageTwin 对标）
- 音频：**待补 `MODEL_RESEARCH_AUDIO.md`**（S4 学期 1 前 3 个月产出：调研 XLS-R / AASIST / TITANet / RawBoost / ASVspoof / 中文 CFAD 等）
- 数据集：[DATASETS.md](DATASETS.md)（三档清单 + 商用许可核对）
- 基线：[BASELINE.md](BASELINE.md)（原 LINVCER 四模态现状快照）

---

## 9. 与商用架构文档的关系

`ENTERPRISE_ARCHITECTURE.md` 和 `MODEL_UPGRADE_PLAN.md` 里的**技术方案**（Java 后端结构、模型选型、Python 推理架构、MLOps）在课题版**照搬**——都是学术方案层面成立的。

**只砍**：
- 商业化章节（客户、计费、合规、私有化、SSO）
- 团队规模（8-12 人 → 5 学生）
- 时间线（12 个月 商业 → 一学年学术）

未来结题后想孵化商业化，架构不用动，只需把砍的商业化能力补回来 —— 这也是「课题→创业」的常见路径。
