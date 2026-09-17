# MODEL UPGRADE PLAN · 综合选型与实施计划（P3 最终版）

> **本文档是决策层入口**：整合 `BASELINE.md`（现状）+ `MODEL_RESEARCH_TEXT.md`（文本调研 v1+v2）+ `MODEL_RESEARCH_IMAGE_TAMPERING.md`（图像/篡改调研）+ `ENTERPRISE_ARCHITECTURE.md`（系统架构），输出每个模型的最终选型、训练数据方案、超参起点、里程碑与验收标准。
> **报告日期**：2026-09-17

---

## 0. 最终选型总表（一页纸）

| # | 能力 | 最终选型 | 训练数据 | 部署 | 阶段 |
|---|---|---|---|---|---|
| M1 | 文本主分类器 | **mDeBERTa-v3-base → deberta-v3-large** | HC3-Chinese + CHEAT + C-ReD + 自建 100K | Triton (ONNX) | Phase 1 |
| M2 | 句子级检测 | **Transformer + CRF 边界分割**（2509.17830 方案） | M1 数据切句 + MAGA-Bench 混写集 | Triton (ONNX) | Phase 2 |
| M3 | 白盒零样本 | **Fast-DetectGPT + Binoculars**（Qwen 2.5-1.5B + Yi-1.5-6B） | 无需训练（零样本） | FastAPI | Phase 2 |
| M4 | 溯源头 | **8-way 多分类**（共享 M1 backbone） | M4/MAGE + 自建 6-8 家 LLM 均衡集 | Triton (ONNX) | Phase 1 |
| M5 | 降 AIGC | **Qwen 2.5-7B + LoRA (r=16, α=32)** | CSL 改写 pairs 20-50K；warm start HF 14B LoRA | vLLM | Phase 1 |
| M6 | 对抗鲁棒 | **RADAR 对抗训练 + DIPPER-style 增强** | GLM-4 生成对抗改写 30K | （融入 M1 训练） | Phase 2 |
| M7 | 图表类型分类 | 轻量 ViT-S / EfficientNet | 自建 6 类图表 2 万张 | Triton (ONNX) | Phase 0 |
| M8 | 插图 AI 检测 | **CLIP-L / DINOv2-L + Linear + 校准** | GenImage + GenImage++ | Triton (ONNX) | Phase 2 |
| M9 | 篡改定位 | **ForMa (Vision Mamba)**，TruFor 对照 | ForensicHub 合成 + 自建 5 万 | Triton (ONNX) | Phase 2 |
| M10 | 学术图特化 | western blot / 显微图微调 + FAISS 复用检索 | PMC 真图 + SD3/Flux 生成 2 万 | Triton + FAISS | Phase 3 |
| — | 主动标识 | C2PA + GB45438（借 LINVCER 代码） | 无需训练 | Java/Python 库 | Phase 0 |
| — | 校准与融合 | Temperature + Platt（借 calibration.py）+ 贝叶斯仲裁（借 arbitration.py） | 各模型 val 集 | 全链路 | Phase 1 |

---

## 1. 决策依据回顾（每个选型为什么）

### M1 文本主分类器：为什么是 DeBERTa-v3 系

- DeBERTa-Sentinel（2608.01046）98.21% val_acc，超 RoBERTa 基线 —— disentangled attention 对 AI 文本的细粒度结构异常敏感
- desklib DeBERTa-v3-large 是 RAID 公开榜 HF 第一
- **弃 Qwen-as-classifier**（P0/P1 阶段）：decoder-only 分类推理成本 5-10×，收益未证实；数据到 500K+ 再评估
- **弃现有 chinese-roberta-wwm-ext**：2019 年 backbone，上限已被 v1 报告证实见顶

### M2 句子级：为什么必须做

- GPTZero 的核心竞争力就是句子级解释（99.5% Booth 基准 + 教师采纳率高）
- 知网/维普/万方全都没有 → 首发差异化
- 论文场景大量「人机混写」（MAGA-Bench 证实是趋势），文档级单一分数没法用

### M3 白盒：为什么是零样本双检

- 监督分类器天然过拟合训练时代的生成器；GPT-5 / Qwen 4 出现时会失效
- Fast-DetectGPT（340× 加速）+ Binoculars（跨代泛化）互补；只在灰区触发控制成本

### M5 降 AIGC：为什么是 Qwen LoRA

- CCL25-Eval Task 5 硬证据：Qwen2.5-14B LoRA +9.7%
- HF 现成 `qwen2.5-14b-humanizer-v3-lora` warm start，冷启动成本极低
- 训练配方已被 humanize-zh 验证（CSL → LLM 改写 → pairs）

### M8/M9 图像：为什么先校准后换模型

- 2602.01973 证实「校准即 SOTA」—— 与文本侧策略统一，先接 calibration.py 再谈重训
- ForMa 是 2025 篡改定位最优（F1 64.1%，超 TruFor +4.3%），且 Vision Mamba 轻量利于部署
- 现有 Mask R-CNN 退役（落后两代）

---

## 2. 训练数据总体方案

### 2.1 文本（Phase 1 启动，总 ~250K）

| 来源 | 规模 | 用途 |
|---|---|---|
| HC3-Chinese | 24.3K | 基线训练 |
| CHEAT | 35K | 学术摘要特化 |
| M4 / MAGE | subset | 溯源多生成器 |
| C-ReD | test-only | 评测基准 |
| MAGA-Bench | test-only | 混写评测 |
| 自建生成 | 90-150K | 5 场景 × 6-8 家 LLM |
| 自建 human | 90-150K | CNKI 摘要 + 教材 + 2020 前语料（防污染） |
| 对抗改写 | 30K | GLM-4 三档强度 |

**红线**：human 语料必须 2020 年以前或人工核验，防 AI 污染标签。

### 2.2 降 AIGC pairs（Phase 1，20-50K）

CSL 学术摘要 → GPT-4o / Claude / DeepSeek 改写成 AI 风格 → (AI 版, human 原版) 有监督对 + 双向 rejected data（防单向口语化漂移）

### 2.3 图像（Phase 2-3，~7 万张）

GenImage / GenImage++（现成）+ ForensicHub 合成工具（篡改样本）+ PMC 开放论文真图 + SD3/Flux 生成学术假图

### 2.4 评测集（全部 Phase 1 建成，固定不动）

1. **In-domain**：CHEAT-test + HC3-Chinese-test
2. **Cross-generator**：训练见过 3 家 + 没见过 3 家，各 500 条
3. **Adversarial**：DIPPER-style 500 + 人工 spot 修改 300
4. **Short-text**：50-200 字段落 300 条
5. **Mixed（混写）**：MAGA-Bench + 自建人机混写 300 篇
6. **图像**：C-ReD 图像子集（如有）+ GenImage++ test + ForensicHub

**规矩**：任何模型改动必须全量跑 6 套，分套报告 AUC / F1 / TPR@FPR=1% / ECE，进 MLflow 对比。

---

## 3. 训练超参起点（M1 为例，其余类推）

基于 LINVCER `train_text_detector.py` 改造（保留其全套技巧），换 backbone 后的起点：

```
model_path        = microsoft/mdeberta-v3-base   # Phase 1 后期换 deberta-v3-large
max_length        = 512
batch_size        = 8          # large 模型吃显存
grad_accum_steps  = 4          # 等效 batch 32
lr                = 1e-5       # DeBERTa-v3 比 RoBERTa 低半档
layerwise_lr      = true, bottom=0.1x, mid=0.5x, top=1x, head=5x
unfreeze_layers   = 12
epochs            = 4          # 早停 patience=2，监控 val AUC
loss              = Focal(γ=2) # 保留
use_rdrop         = true (α=0.5)
use_ema           = true (decay=0.999)
use_fgm           = true (ε=0.5)
use_grl           = true (λ=0.5)   # 论文域对抗，多域数据下开启
use_contrastive   = true (w=0.1)   # SupCon
警告: DeBERTa-v3 用 sentencepiece tokenizer，与 BERT tokenizer 不兼容，
      数据管道里 tokenize 部分需要适配（train_text_detector.py 用 AutoTokenizer 已兼容）
```

**LoRA（M5）起点**：r=16, alpha=32, dropout=0.05, target=q/k/v/o + gate/up/down, lr=1e-4, cosine, 2-3 epochs, bf16, DeepSpeed ZeRO-2（A100 80GB 单卡可跑 7B）

---

## 4. 里程碑与验收（对齐架构文档 Phase 0-3）

### Phase 0（2026-10 → 12）：地基
- 交付：Java 骨架 + Triton/FastAPI stub + RN 骨架 + CI/CD + M7 图表分类器 + C2PA/GB45438
- **模型侧验收**：MLflow + DVC 可用；6 套评测集数据管道建成（评测集本身 Phase 1 完成）

### Phase 1（2027-01 → 03）：文本基线
- 交付：M1 主分类器 + M4 溯源 + M5 降 AIGC + 校准/仲裁接线 + 评测集全量建成
- **验收硬指标**：
  - In-domain AUC ≥ 0.98（对标 DeBERTa-Sentinel）
  - Cross-generator（未见 3 家）F1 ≥ 0.85
  - ECE ≤ 0.05（校准后）
  - 溯源 top-1 acc ≥ 0.70（8-way）
  - 降 AIGC：改写后被 M1 判 AI 概率 < 30% 且人工质检语义保持率 ≥ 90%
  - 内测 1 客户全流程跑通

### Phase 2（2027-04 → 06）：鲁棒与差异化
- 交付：M2 句子级 + M3 白盒双检 + M6 对抗鲁棒 + M8 插图检测 + M9 篡改定位
- **验收硬指标**：
  - DIPPER 中文攻击后 F1 ≥ 0.70
  - 新 LLM 零样本（白盒兜底）F1 ≥ 0.85
  - 句子级边界分割 F1 ≥ 0.60
  - 插图 AI 检测 GenImage++ acc ≥ 0.85
  - 篡改定位 ForensicHub F1 ≥ 0.60（对标 ForMa 64.1%）
  - 3-5 家 pilot

### Phase 3（2027-07 → 09）：学术图特化与商业化
- 交付：M10 western blot / 显微图特化 + FAISS 复用检索 + 私有化 + 等保/备案
- **验收硬指标**：
  - blot 篡改检测对标 Proofig 公布口径（98% 级别成功率是目标线）
  - 商业客户 20+

---

## 5. 预算量级（云 GPU 按需，粗估）

| 项 | 配置 | 时长 | 说明 |
|---|---|---|---|
| M1 训练迭代 | A100 40GB ×1 | 每轮 6-10h × ~15 轮 | 含调参试错 |
| M5 LoRA | A100 80GB ×1 | 每轮 4-8h × ~8 轮 | |
| M2/M4/M6 | A100 40GB ×1 | 合计 ~80h | |
| M8/M9 | A100 40GB ×1 | 合计 ~120h | 图像训练慢 |
| 评测（持续） | T4/A10 ×1 | 每周 4-6h | 可用竞价实例 |
| 推理（生产） | A100 80GB ×1 + A100 40GB ×2 | 常驻 | vLLM + Triton + FastAPI |

**训练总量级**：~600-800 A100-小时（含试错），阿里云 PAI 按量约数万元人民币量级；生产推理是大头（3 卡常驻）。

---

## 6. 现有资产处置清单（LINVCER 仓库）

| 资产 | 处置 |
|---|---|
| `train_text_detector.py` | **保留改造**：换 backbone 支持 + MLflow logging + DVC 数据引用 |
| `train_image_sd.py` | **保留改造**：数据源换 GenImage++，backbone 加 DINOv2 选项 |
| `train_image_detector.py` | **废弃**（合成假图代理偏差） |
| `train_audio_detector.py` | **归档**（论文场景无音频） |
| `calibration.py` | **直接复用**（图文两侧都接） |
| `arbitration.py` | **直接复用**（多分支融合层） |
| `detectors/metadata/`（C2PA + GB45438） | **直接复用** |
| `detectors/tampering/`（Mask R-CNN + ELA + FFT…） | **退役**，换 ForMa；ELA/EXIF 可作辅助特征保留 |
| `statistical_features.py`（18 KB 统计特征） | **保留**作为 M1 的辅助分支（对抗改写下的兜底信号） |
| 其余（audio / assistant / miniapp / extension / benchmark…） | 不迁移 |

---

## 7. 立即可开工的三件事（本周）

1. **拉数据**：HC3-Chinese + CHEAT + M4 下载入 DVC；开始爬 CNKI 公开摘要（合规）
2. **训练环境**：云上开 A100 环境（阿里云 PAI），跑通 `train_text_detector.py` 现状基线（chinese-roberta-wwm-ext + HC3-Chinese），拿到第一个 MLflow 基线数字
3. **backbone A/B**：同一数据换 `mdeberta-v3-base` 跑对比，验证 v2 调研的「+3-8 pp」预期 —— **这是整个升级计划的第一个假设检验**

---

## 8. 文档索引

| 文档 | 内容 |
|---|---|
| `BASELINE.md` | 四模态现状快照（P1 产物） |
| `MODEL_RESEARCH_TEXT.md` | 文本调研 v1 + v2 增补（12 篇 2025-2026 论文） |
| `MODEL_RESEARCH_IMAGE_TAMPERING.md` | 论文插图 AI 检测 + 篡改定位调研 |
| `ENTERPRISE_ARCHITECTURE.md` | 系统架构（Java + Python + RN + MLOps + K8s） |
| `MODEL_UPGRADE_PLAN.md` | 本文档 —— 综合选型与实施计划 |
| `REFACTOR_PLAN.md` | （历史）单体重构方案，已被企业级方案取代，部分工程项仍可参考 |
| `aigc-multimodal-detection-progress-report.md`（daimai/.tmp） | （历史）上游仓库进度分析 |
