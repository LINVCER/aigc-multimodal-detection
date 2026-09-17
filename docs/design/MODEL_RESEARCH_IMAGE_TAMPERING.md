# MODEL RESEARCH · Image + Tampering · 论文插图 AI 生成与篡改检测调研

> **场景限定**：企业级论文检查平台的图像能力 —— 不做泛用图像检测，只做「学术论文插图」的 AI 生成识别与篡改定位
> **两个子问题**：① 插图是不是 AI 生成的（AIGC detection）② 插图有没有被篡改/复用（integrity / forensics）
> **报告日期**：2026-09-17，外网调研 3 组

---

## 0. 结论先行（TL;DR)

**论文插图完整性检测是一个已被商业验证的细分市场**（Proofig / ImageTwin 两家头部），且与文本 AIGC 检测在客户（出版社/高校/期刊）上完全重合 —— **是我们平台天然的第二增长曲线，但优先级排在文本主线之后**。

| 子能力 | 推荐方案 | 阶段 |
|---|---|---|
| 插图 AI 生成检测 | CLIP/DINOv2 backbone + 校准（外网证实"校准即 SOTA"）+ GenImage++ 训练 | P2（文本上线后） |
| 通用篡改定位 | **ForMa (Vision Mamba)** 或 SparseViT（AAAI'25），弃现有 Mask R-CNN | P2 |
| 学术特化（western blot / 显微图） | domain-specific 微调 + 复用检测（copy-move / splicing 热图） | P3（对标 Proofig/ImageTwin） |
| 主动标识 | 保留现有 C2PA + GB45438 检测（LINVCER 代码直接借鉴） | P0 就带上 |

---

## 1. 市场验证（这个方向值得做的证据）

- **Proofig**：商业产品，检测论文图像复用/篡改；新功能「AI 生成显微镜图像检测」宣称 **98% 成功率 + 低误报**
- **ImageTwin**：检测 western blot 拼接（垂直/水平 splicing）、copy-move 伪造、局部改动，**彩色热图定位**；参展 WCRI 2026（世界科研诚信大会）
- **市场规模信号**：研究表明 **每 25 篇含 western blot 的论文中就有 1 篇存在数据异常**
- **技术难点确认**：「AI detectors are poor western blot classifiers」（PMC11847483）—— 通用 AI 图像检测器直接用在学术图像上准确率差，**必须 domain-specific 训练**，这既是壁垒也是机会

**对我们的定位**：文本检测主打「学生毕业论文」，图像完整性主打「期刊编辑部 / 出版社」—— 同一平台两个客群，报告合并成「论文全维度诚信报告」。

---

## 2. 子问题 ①：插图 AI 生成检测

### 2.1 基准与数据

| 数据集 | 规模 | 说明 |
|---|---|---|
| **GenImage** | 270 万图 | ImageNet-1K 对齐，含 ADM/GLIDE/VQDM/SD1.4/SD1.5/Wukong/Midjourney 七代生成器 |
| **GenImage++** | test-only | 新增 **Flux.1 / SD3** + 长 prompt + 183 风格模板，专门对抗记忆效应和 shortcut learning |
| **AI-GenBench**（arxiv 2504.20865） | 持续更新 | ongoing benchmark，按生成器时间轴增量评测（模拟"新生成器出现"场景） |
| 学术特化 | 需自建 | AI 生成的显微图/图表/流程图（用 SD3/Flux 生成 + 论文真图对照） |

### 2.2 2025-2026 方法要点

| 论文 | 要点 | 借鉴价值 |
|---|---|---|
| **"Your AI-Generated Image Detector Can Secretly Achieve SOTA Accuracy, If Calibrated"**（arxiv 2602.01973） | **校准（calibration）而非重训**即可把现有检测器拉到 SOTA | **与我们文本侧的 calibration 战略完全一致** —— 图像侧同样先接校准再谈换模型 |
| Orthogonal Subspace Decomposition（arxiv 2411.15633） | 正交子空间分解提升跨生成器泛化 | 训练策略参考 |
| **Fleet**（arxiv 2606.31082） | few-shot 快速适配新生成器 | 应对"新生成器出现"的快速响应机制 |
| SICA（arxiv 2602.06676） | 单一模型统一检测多种 fake（AIGC + 篡改） | P3 阶段"一个模型管两件事"的可能性 |
| Training-free Cropping Robustness（arxiv 2511.14030） | 免训练、抗裁剪 | 论文插图常被裁剪排版，此特性重要 |
| 开源检测器 out-of-box 评测（arxiv 2602.07814） | 开源模型开箱即用普遍拉胯 | 证明必须自己微调，不能拿来主义 |

### 2.3 现有代码资产的处置

- LINVCER `train_image_sd.py`（DualBranchCNN + CLIP-ViT partial finetune + AUC/EER/TPR@FPR/ECE 指标）**训练框架保留**，换数据（GenImage → GenImage++ 增强）+ 换 backbone 选项（DINOv2-L 加入对比）
- `train_image_detector.py`（手工合成假图版）**废弃** —— 合成假图代理偏差已被 v1 报告证实
- 现有 `detectors/image/fusion.py` 融合逻辑接入 `calibration.py`（图像侧同样是"校准即免费涨点"）

### 2.4 论文场景特化要求

1. **图表类型分类前置**：先分类（照片 / 显微图 / western blot / 统计图表 / 流程图 / 截图），不同类型走不同检测器 —— 统计图表和流程图天然"AI 风格"，通用检测器会大量误报
2. **矢量图豁免**：论文里的 matplotlib/Visio 图表是程序生成的，不应判 AI —— 需要「程序生成 vs 生成模型生成」的区分
3. **抗排版扰动**：论文插图经历裁剪/压缩/缩放，检测器必须做 JPEG/resize/crop 增强训练（`train_image_sd.py` 已有这套增强，保留）

---

## 3. 子问题 ②：篡改检测与定位

### 3.1 通用篡改定位 SOTA 演进（2023 → 2026）

| 方法 | 年份 | 架构 | 性能 |
|---|---|---|---|
| CAT-Net | 2022 | CNN（JPEG 压缩感知） | CNN 系最佳 |
| TruFor | CVPR 2023 | Transformer + 噪声指纹 | 长期霸榜 |
| IML-ViT（arxiv 2307.14863） | 2023 | ViT + 高分辨率 + 边缘监督 | ViT 基准范式 |
| SparseViT | AAAI 2025 | 稀疏自注意力提取非语义特征 | 2025 新锐 |
| Mesorch | 2025 | CNN+Transformer 并行多尺度 | 介观视角 |
| **ForMa**（arxiv 2502.09941） | 2025 | **Vision Mamba** | **10 数据集平均 F1 64.1% / IoU 56.2%，超 TruFor +4.3%/+4.9%，超 CAT-Net +6.5%/+24.2%** |

**选型**：P2 用 **ForMa**（轻量 + 最优）起步，**TruFor** 做对照基线；现有 Mask R-CNN 分支**退役**（2019 年代方案，落后两代）。

**统一基准**：**ForensicHub**（arxiv 2505.11003）—— 全域 fake image 检测统一 benchmark + codebase，直接用它做我们的图像 evals 基础设施。

### 3.2 学术图像特化（对标 Proofig / ImageTwin 的核心）

| 论文/资源 | 要点 |
|---|---|
| **Localization of Synthetic Manipulations in Western Blot Images**（arxiv 2408.13786） | western blot 合成篡改定位专门方法 |
| **Explainable Artifacts for Synthetic Western Blot Source Attribution**（arxiv 2409.18881） | western blot 溯源（哪个生成器产的）+ 可解释伪影 |
| AI detectors are poor western blot classifiers（PMC11847483） | 通用检测器在 blot 上失效的实证 —— **domain 训练数据是壁垒** |
| Zooming In on Fakes（arxiv 2504.11922) | 局部 AI 生成区域检测数据集 + 伪造放大方法（局部 AI inpainting 场景） |

**学术特化三件套**（P3 逐步落地）：
1. **复用检测（duplication）**：同文/跨文图像 copy-move、旋转、翻转、缩放后复用 —— 用 embedding 检索（DINOv2 特征 + FAISS）+ 关键点匹配（SIFT/LoFTR 验证），这是 ImageTwin 的主战场
2. **拼接检测（splicing）**：western blot 条带拼接 —— ForMa/TruFor 微调 + 条带级分割
3. **AI 生成学术图**：SD/Flux 生成的假显微图/假 blot —— 用 2408.13786 + 2409.18881 方案微调

### 3.3 数据从 0 构建方案（学术特化）

- **真图来源**：PubMed Central 开放获取论文的图像（合规抓取）+ 公开显微图数据集
- **篡改样本**：程序化生成（copy-move / splicing / inpainting 脚本，参考 ForensicHub 的数据合成工具）
- **AI 生成样本**：SD3 / Flux 生成显微图和 blot（prompt 工程 + ControlNet 引导）
- **规模目标**：P2 阶段 5 万张（通用篡改），P3 阶段 +2 万张（western blot / 显微图特化）

---

## 4. 与平台架构的集成（对齐 ENTERPRISE_ARCHITECTURE.md）

```
论文上传 → Java 抽图（Apache PDFBox / POI 提取嵌入图像）
   │
   ▼
图表类型分类器 (Triton, ONNX)         ← 前置路由
   ├── 统计图表/流程图 → 豁免（程序生成）
   ├── 照片/显微图/blot → AI 生成检测 (Triton) + 篡改定位 (ForMa, Triton)
   └── 可疑图 → 复用检索 (DINOv2 embedding + FAISS 库内检索)
   │
   ▼
结果并入检测报告：图像诚信章节（AI 生成概率 + 篡改热图 + 复用比对图）
```

- 全部模型 ONNX 导出进 Triton（与文本检测同一套推理设施）
- FAISS 复用检索库随客户数据增长（期刊客户价值最大：投稿图与已发表库比对）
- 热图渲染在 Java 报告侧合成（篡改区域红色 overlay，模仿 ImageTwin 的呈现）

---

## 5. 优先级与阶段划分

| 阶段 | 内容 | 依赖 |
|---|---|---|
| **P0**（随平台上线） | C2PA + GB45438 主动标识检测（借 LINVCER 代码）；图表类型分类器 | 无 |
| **P2**（文本主线跑通后） | 插图 AI 生成检测（GenImage++ 训练 + 校准）；ForMa 通用篡改定位 | 文本主线验收 |
| **P3**（期刊客户进入后） | western blot / 显微图特化；复用检索库（FAISS）；溯源 | P2 + 期刊客户数据 |

**明确不做**：人脸 deepfake（场景无关）、视频检测（场景无关）、艺术图像鉴定（场景无关）。

---

## 6. Sources

**AI 生成图像检测**
- [GenImage Benchmark](https://www.emergentmind.com/topics/genimage-benchmark)
- [GenImage Dataset](https://www.emergentmind.com/topics/genimage-dataset)
- [Your AI-Generated Image Detector Can Secretly Achieve SOTA Accuracy, If Calibrated](https://arxiv.org/pdf/2602.01973)
- [Orthogonal Subspace Decomposition for Generalizable AI-Generated Image Detection](https://arxiv.org/pdf/2411.15633)
- [Fleet: Few Shots Lead Effective AI-generated Image Detection](https://arxiv.org/pdf/2606.31082)
- [SICA: Semantic-Induced Constrained Adaptation](https://arxiv.org/pdf/2602.06676)
- [Training-free Detection of AI-generated images via Cropping Robustness](https://arxiv.org/pdf/2511.14030)
- [GenShield: Unified Detection and Artifact Correction](https://arxiv.org/pdf/2605.16122)
- [AI-GenBench: Ongoing Benchmark for AI-Generated Image Detection](https://arxiv.org/html/2504.20865v3)
- [How well are open sourced AI-generated image detection models out-of-the-box](https://arxiv.org/html/2602.07814v1)

**学术图像造假**
- [Proofig AI: Detecting AI-Generated Images in Scientific Research](https://www.proofig.com/news/how-ai-is-fighting-back-against-ai-generated-image-fraud-in-scientific-research/)
- [ImageTwin: Image Manipulation Detection Software](https://imagetwin.ai/image-manipulation-detection/)
- [ImageTwin at WCRI 2026](https://imagetwin.ai/posts/wcri-2026-the-world-conference-on-research-integrity-in-vancouver/)
- [Genuine images in 2024 (Science)](https://www.science.org/doi/10.1126/science.adn7530)
- [Localization of Synthetic Manipulations in Western Blot Images](https://arxiv.org/pdf/2408.13786)
- [Explainable Artifacts for Synthetic Western Blot Source Attribution](https://arxiv.org/pdf/2409.18881)
- [AI detectors are poor western blot classifiers (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11847483/)
- [Emerging Concern of Scientific Fraud: Deep Learning and Image Manipulation](https://www.biorxiv.org/content/10.1101/2020.11.24.395319.full.pdf)

**篡改定位**
- [ForMa: Lightweight Image Tampering Localization with Vision Mamba](https://arxiv.org/pdf/2502.09941)
- [TruFor (CVPR 2023)](https://www.researchgate.net/publication/373327248_TruFor_Leveraging_All-Round_Clues_for_Trustworthy_Image_Forgery_Detection_and_Localization)
- [IML-ViT](https://arxiv.org/pdf/2307.14863)
- [ForensicHub: Unified Benchmark & Codebase](https://arxiv.org/html/2505.11003v1)
- [Zooming In on Fakes: Localized AI-Generated Image Detection](https://arxiv.org/pdf/2504.11922)
- [Learning Universal Features for Generalizable Image Forgery Localization](https://arxiv.org/pdf/2504.07462)
- [Image Forgery Detection Papers List (GitHub)](https://github.com/greatzh/Papers)
