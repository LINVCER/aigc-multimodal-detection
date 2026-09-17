# BASELINE · 现有四模态检测器现状快照

> 目的：在做模型调研之前，先把当前项目每个模态的 backbone、损失、训练策略、数据来源、评测指标、已知问题、真实工程成熟度全部摸清，避免调研飘在空中。
>
> 数据来源：`backend/train_*.py` + `backend/app/detectors/*` + `backend/app/services/*` + 近 30 条 git commit 的 fix 主题。

---

## 0. 全局观察

- **训练脚本水平差异非常大**：
  - `train_text_detector.py` 850+ 行，Focal / R-Drop / EMA / FGM / GRL / SupCon 全部落地 —— **教科书级微调工程**
  - `train_image_sd.py` 900+ 行，20 项工程改进（AMP / AUC-EER-TPR@1% / EarlyStopping / feature cache / patch inference）—— **成熟**
  - `train_image_detector.py` 480 行，只做「合成假图 + Linear Probing + 高频 CNN」 —— **代理数据训练，泛化差**
  - `train_audio_detector.py` 410 行，只训分类头（1M 参数），主 backbone Wav2Vec2 全冻结 —— **朴素**
- **数据面几乎全部是从 0 构建**：文本靠合成、图像靠 train2017 + FFT 合成假图、音频靠 AISHELL-3 真人 + 手动 TTS
- **calibration 已被训练脚本调用**（三个 train_*.py 都写了 `ConfidenceCalibrator.fit_temperature` + `fit_platt` 保存到 checkpoint），但**运行时 `apply_calibration` 从未被调**（生产代码零调用）—— 校准参数训完就锁进 pth 里躺着
- **arbitration.py 贝叶斯融合层同样是孤岛**，运行时 0 调用
- **没有 evals/ 离线评测集**：训练脚本自己 split val，但没有跨版本可比的固定测试集，改阈值/换模型无法量化对比
- 近 30 条 commit 主题里出现 5 次 "reduce false positives" / "ViT threshold" / "AI models count as 1.5 votes" —— **在用调阈值和加投票权对抗误报**，说明模型泛化未过关

---

## 1. 文本模态（text）

### 1.1 Backbone 与结构

| 项 | 现状 |
|---|---|
| Backbone | `hfl/chinese-roberta-wwm-ext`（Base，约 100M 参数） |
| 分类头 | 2 层 MLP（hidden→256→num_classes），Dropout 0.1 |
| 领域头（可选） | 2 层 MLP + GRL（Gradient Reversal Layer, λ=0.5） |
| Encoder 微调策略 | 冻结 embedding + 前 4 层，解冻最后 8 层 |
| 输出 | logits [B, 2]，走 argmax + 校准 |

### 1.2 训练策略（`train_text_detector.py`）

| 组件 | 配置 |
|---|---|
| Loss | 主：Focal（γ=2, α=0.25）｜可选 LabelSmoothing（ε=0.1） |
| 一致性正则 | R-Drop（KL alpha=0.5，两次 forward） |
| 对抗训练 | FGM（epsilon=0.5，作用于 embeddings，每 2 步施加一次） |
| 权重平均 | EMA（decay=0.999，val 时切换 shadow 权重） |
| 多任务 | 领域分类头 + 可选 GRL（域对抗） |
| 对比学习 | SupConLoss（temperature=0.07, weight=0.1），CLS token 空间 |
| 数据增强 | 同义词替换（15%）+ 句子打乱（10%）+ 随机删除（5%） |
| Optimizer | AdamW + 分层 LR（bottom=0.25×, mid=0.5×, top=1×, head=5×），weight_decay=0.01 |
| Scheduler | Cosine warmup（total_steps / 10） |
| 梯度累积 | 2 步（等效 batch=32） |
| 校准 | 训完 val 集上 fit Temperature + Platt，存 checkpoint |

### 1.3 数据

| 项 | 现状 |
|---|---|
| 训练集 | `../data/training/aigc_diverse_train.json`（外部依赖，仓库不含） |
| 验证集 | `../data/training/aigc_diverse_val.json` |
| 内置回退 | 8 条 human + 5 条 GPT + 2 条 Claude 样本（仅供烟测） |
| max_samples | 60000（合并样本上限） |
| max_length | 512 token |
| 数据字段 | `text` / `AI_text` / `human_text` / `label` / `domain` 兼容多来源格式 |

### 1.4 评测

- val_acc / val_f1（每 epoch）
- ECE（校准后）
- Per-domain accuracy（打印前 8 域）
- **无固定测试集**，val 自 split 于训练文件

### 1.5 已知问题（从代码与 commit 反推）

- **依赖闭源自建训练数据**，仓库无法开箱训（`aigc_diverse_*.json` 未提供）
- **backbone 上限已见顶**：hfl/chinese-roberta-wwm-ext 是 2019 年的 100M base，2024-2026 中文文本 AIGC 检测 SOTA 已上 XLM-R-Large / DeBERTa-v3-Large / Qwen2.5 / ERNIE-3.0-XL
- **无零样本 / 白盒 detector**：所有能力都在监督分类头上，一旦生成模型换代（如 GPT-5 / Claude 5 / Qwen 3）需要重新构建训练数据
- **没有对抗改写（paraphrase）鲁棒性训练**：GPT/Claude 生成的文本一旦用 DIPPER / 手动改写就大概率漏检
- **域覆盖靠 GRL + 多任务**，但真实域数量有限（论文/新闻/小说/评论/邮件覆盖度未知）

---

## 2. 图像模态（image）

### 2.1 Backbone 与结构（两条并存的路径）

**路径 A：CLIP-ViT-L/14 Linear Probing**（`train_image_detector.py` + `train_image_sd.py` 都做）

- Backbone：OpenAI `clip-vit-large-patch14`（约 300M vision encoder，冻结）
- 头部：Linear(hidden_dim, 1)，取 CLS token 或 pooler_output
- 可选：解冻最后 N 层做 partial finetune（`train_image_sd.py` 支持 `unfreeze_layers`）
- 输入：224×224，CLIP mean/std 标准化

**路径 B：DualBranchCNN + FFT**（`train_image_sd.py` 里的 `DualBranchCNN`）

- RGB branch：输入 12 通道（3 RGB + 9 SRM 残差），4 层 Conv+BN+ReLU→AdaptiveAvgPool
- FFT branch：灰度化 → FFT → log(|·|+ε)，3 层 Conv+BN+ReLU→AdaptiveAvgPool
- 融合：拼接（128+64） → MLP → 1 logit

**路径 C：合成假图训练的高频 CNN**（`train_image_detector.py` 里 `HighFreqCNN`，代理数据）

### 2.2 训练策略

**`train_image_sd.py`（新版，成熟）**

| 组件 | 配置 |
|---|---|
| Loss | BCEWithLogitsLoss（二分类 sigmoid） |
| Optimizer | AdamW (lr=1e-3 head, lr=1e-4 vit)，weight_decay=1e-4 |
| Scheduler | CosineAnnealingLR |
| AMP | 开启（GradScaler） |
| 数据增强 | EXIFStrip + RandomResize(0.8-1.2) + RandomJPEGCompression(70-100) + RandomResizedCrop 224 + HorizontalFlip + ColorJitter + GaussianBlur |
| 特征缓存 | ViT 冻结时预抽 CLS 特征进 `.pt`，训练快 5-10× |
| Early Stopping | patience=3，监控 AUC |
| Patch inference | 4 patches → mean/vote |
| Leak Guard | val 用文件名 md5 hash 去除与 train 重合 |

**`train_image_detector.py`（旧版，代理数据）**

| 组件 | 配置 |
|---|---|
| 数据 | COCO train2017 真图 + **手工合成假图**（FFT 频域噪声 / JPEG artifacts / smooth-sharpen / 周期性噪声） |
| Loss | BCEWithLogitsLoss |
| 无 AMP，无 patch inference |

### 2.3 数据

| 类型 | 现状 |
|---|---|
| `train_image_sd.py` | GenImage 结构（`ai_dirs`, `nature_dirs`），需要**真实 SD/Midjourney/Flux 生成图**（未提供） |
| `train_image_detector.py` | COCO train2017 真图（`D:/AAA/train2017` 硬编码路径），假图靠脚本合成 |

**核心断层**：新版 `train_image_sd.py` 假设有真实 AI 生成图数据（GenImage），旧版 `train_image_detector.py` 用合成假图代理。**仓库里没有任一份数据**。

### 2.4 评测

- **`train_image_sd.py`**：acc / **AUC / EER / TPR@FPR=1% / ECE**（这套指标是行业标准，做得很正规）
- `train_image_detector.py`：只 acc

### 2.5 已知问题

- **两版训练脚本并存**（旧版 + 新版），运行时用哪个不明，`config.py` 指向 `../models/image/cnn_detection.pth` 但训练脚本存在同名文件的话会互相覆盖
- **旧版代理数据严重误导**：手工合成的 FFT/JPEG 假图 ≠ 真实 SD 生成图的伪影分布，训完在真实 AI 图上会误报或漏检
- **CLIP-ViT-L 是 2021 年模型**，未针对 diffusion 训练；2023-2025 SOTA 已切到 DINOv2 / SAM2 / EVA-02 或 diffusion-specific 检测器（DIRE, NPR, AIDE, RINE）
- 近 commit 「ViT threshold changed to 50%」「AI models count as 1.5 votes」→ **说明 ViT 分支在真实数据上判分偏向 real，靠调阈值和加权硬拉**

---

## 3. 音频模态（audio）

### 3.1 Backbone 与结构

- Backbone：**Wav2Vec2-base**（英文预训练，本地路径 `../models/audio/wav2vec2-base`）
- 冻结：全部冻结，只训分类头
- 分类头：3 层 MLP（hidden=1024 → 256 → 64 → 1），Dropout 0.3 / 0.2
- 特征聚合：`last_hidden_state.mean(dim=1)`
- 采样率：16 kHz mono

**另有独立分支**：`detectors/audio/rawnet2_detector.py`（RawNet2）+ `resemble_client.py`（云 API），但**训练脚本只训 Wav2Vec2 分类头**，RawNet2 直接拿现成 pth 用。

### 3.2 训练策略

| 组件 | 配置 |
|---|---|
| Loss | BCEWithLogitsLoss |
| Optimizer | AdamW（lr=1e-3, wd=0.01） |
| Scheduler | CosineAnnealingLR |
| 数据增强 | 加噪（σ=0.005）｜ 音量缩放（0.7-1.3）｜ 变速（0.95-1.05） |
| Crop | 随机 3-5 秒 |
| Batch | 8（小 batch，因 backbone 大） |
| **无 EMA / FGM / R-Drop / mixup / SpecAugment**（比文本朴素很多） |

### 3.3 数据

| 项 | 现状 |
|---|---|
| 训练 real | `../data/audio/real`（可用 AISHELL-3） |
| 训练 fake | `../data/audio/fake`（需手动用 ChatTTS/CosyVoice 生成） |
| 测试集 | `test_real/`、`test_fake/` 可选 |
| build_testset | 提供从 AISHELL-3 抽 200 条真实语音的辅助函数 |

**核心问题**：假语音数据全靠用户自己生成，没有 ASVspoof / FoR / MLAAD 等公开集接入。

### 3.4 评测

- val_acc / test_acc（如果有独立 test 集）
- **无 EER / AUC**（音频对抗检测的标准指标缺失）

### 3.5 已知问题

- **Wav2Vec2-base 是英文预训练**，中文表现天然弱；2023-2025 中文 anti-spoofing SOTA 走 **XLS-R (300M/1B/2B, 128 语言)** 或 **HuBERT-Chinese** 或 **WavLM**
- **只训线性头**（1M 参数），无 fine-tune 后端，表征上限受限
- **无 SpecAugment / MixUp / RawBoost**（音频领域标配增强缺失）
- **没接 AASIST / SLIM / SFR-CM 等 SOTA 分类头**
- **RawNet2 分支独立于训练脚本**，权重从哪来、什么数据训的完全不透明
- 依赖 `librosa` + `ffmpeg` 双路径 fallback，部署环境要求较高

---

## 4. 图像篡改检测模态（tampering）

### 4.1 Backbone 与结构（**未见训练脚本**，纯运行时组件）

`backend/app/detectors/tampering/` 目录里 6 路检测器 + 融合：

| 分支 | 文件 | 说明 |
|---|---|---|
| Mask R-CNN | `maskrcnn_branch.py` (4.8 KB) | 实例分割定位篡改区域，用现成 checkpoint（`tampering_maskrcnn_checkpoint`） |
| ELA | `ela_branch.py` (1.6 KB) | 误差水平分析（Error Level Analysis） |
| FFT 频域 | `frequency_branch.py` (1.6 KB) | 频域异常 |
| 噪声 | `noise_branch.py` (1.5 KB) | 噪声不一致检测 |
| EXIF | `exif_branch.py` (2.7 KB) | 元数据一致性 |
| 融合 | `fusion.py` (2.5 KB) + `engine.py` (4.9 KB) | 加权融合 + support_ratio 判定 |

**metadata 目录额外的两个**：
- `c2pa_detector.py` (9 KB) — C2PA 内容凭证检测
- `gb45438_detector.py` (8 KB) — 国标 GB45438-2025 标识识别

### 4.2 训练策略

**无**。所有 checkpoint 都是外部拉现成的，仓库无篡改检测的训练脚本。

### 4.3 数据

无（依赖外部预训练 Mask R-CNN checkpoint）。

### 4.4 评测

**无**（无独立评测脚本，也无固定测试集）。

### 4.5 已知问题

- **没有训练闭环**：想升级 Mask R-CNN 权重必须自己去找外部资源或另起项目训
- **主要是「传统图像取证」组合**（ELA / FFT / EXIF / 噪声），2023-2025 SOTA 已切到端到端深度学习（CAT-Net / TruFor / MVSS-Net / IML-ViT / EditGuard）
- **没有针对 diffusion inpainting 的检测器**（AI 局部改图是当前最大威胁类型，比拷贝-粘贴更难）
- **C2PA / GB45438 属于「主动标识识别」，不是「检测」**：仅在图像被生成方主动加了 C2PA/GB45438 manifest 时才有用，AI 生成方不合规就完全失效

---

## 5. 融合与决策层（跨模态）

### 5.1 现状

- `arbitration.py` 已实现完整贝叶斯融合（log-sum-exp + EWMA 动态权重 + 冲突检测）
- `calibration.py` 已实现 Temperature + Platt + ECE + Redis 同步
- **两个模块在生产代码零调用**（tests/ 里有单测，仅此而已）
- 融合真实入口在 `services/text_service.py` / `image_service.py` / `audio_service.py` / `detection_service.py`，走的是 **detector 层自己内部的 fusion**（例如 `detectors/image/fusion.py` 的加权投票）

### 5.2 已知问题

- 训练时算出的 `temperature / platt_a / platt_b` 存在 checkpoint 里，运行时没被读出用于校准 → **calibration 完全走空**
- 跨模态融合（比如"同时检测一段视频里的字幕+画面+声音"）用不了 `Arbitrator`，因为没被接线
- 阈值/权重的调优靠手工改代码（近 commit 有大量证据），没有 A/B 自动化框架

---

## 6. 评测缺口清单（这是所有优化的前置门槛）

| 模态 | 缺什么 |
|---|---|
| 文本 | 固定测试集、跨代模型对比集（GPT-3.5/4/5、Claude 3/4/5、Qwen 2/2.5/3、Kimi 等）、对抗改写集（DIPPER） |
| 图像 | GenImage / DiffusionForensics / SDXL-Detection 等真实生成图 test split；跨扰动（JPEG-90/70/50、resize 0.5×、blur、crop）鲁棒集 |
| 音频 | ASVspoof 2019 LA / 2021 DF / 2024、FoR、MLAAD、In-the-Wild、CFAD（中文） |
| 篡改 | CASIA v1/v2、Coverage、Columbia、CocoGlide、AutoSplice、diffusion inpainting 集 |

**必须先建这套测试基线，才能量化任何模型升级的 delta。**

---

## 7. 一句话总结每模态

| 模态 | 当前基线一句话 | 主要瓶颈 |
|---|---|---|
| **文本** | RoBERTa-Base + 全套微调技巧的教科书级实现 | Backbone 上限；数据不含对抗改写；无零样本能力 |
| **图像** | CLIP-ViT-L Linear Probing + Dual-branch CNN + FFT + SRM，工程成熟 | 一半训练用手工合成假图（严重代理偏差）；未接 diffusion-specific 检测器 |
| **音频** | Wav2Vec2-base（英文预训练）冻结 + 1M 参数分类头，工程朴素 | Backbone 语言不匹配；无 SpecAugment；无 SOTA anti-spoofing 头 |
| **篡改** | 6 路传统图像取证组合 + Mask R-CNN + C2PA/GB45438 主动标识 | 无训练脚本 / 无数据 / 无评测；未接 diffusion inpainting 检测 |

---

## 8. 与调研的接口

下一步 P2 阶段（先文本），每个模态调研报告都要回答同一个问题：

> **假设现有基线的评测数据是 X（P1 未见 → P2 需要人肉跑一遍或直接拉公开数据集算），已知瓶颈是 Y，2024-2026 SOTA 能达到 Z，Z-X 的 gap 值不值得升级？升级成本多少？**

BASELINE 到此结束。下一份产出：`MODEL_RESEARCH_TEXT.md`。
