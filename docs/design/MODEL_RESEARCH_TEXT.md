# MODEL RESEARCH · Text · 中文 AIGC 文本检测调研

> **调研范围**：2023-2026 中文 AIGC 文本检测 SOTA、backbone 选型、零样本白盒方法、对抗鲁棒、数据源
> **服务约束**：云 GPU 按需租（预算不硬）、数据从 0 构建、教育垂直（论文场景优先）
> **知识截止**：Claude 2026-01 训练数据 + 补充调研点会在具体条目注明「需 fork 后 WebFetch 补最新」

---

## 0. 结论先行（TL;DR）

**当前基线**：`hfl/chinese-roberta-wwm-ext`（100M, 2019）+ Focal/R-Drop/EMA/FGM/GRL/SupCon 全套微调。**训练技巧已经饱和，进一步 delta 只能靠换 backbone 或换范式。**

**推荐三层组合**（对应报告 §7 具体方案）：

| 层 | 用法 | 推荐 | 增量 |
|---|---|---|---|
| 主监督分类器 | 论文/新闻/长文本的稳定分类 | **XLM-RoBERTa-Large (550M)** 或 **DeBERTa-v3-Large (multilingual)** | +3-8 pp F1 vs Base |
| 白盒零样本 | 应对 backbone 未见过的新 LLM（GPT-5 / Claude 5 / 未来模型） | **Fast-DetectGPT + Binoculars 双检** | 覆盖 backbone 训练数据外的分布 |
| 对抗鲁棒 | 应对 DIPPER 复述 / 手动改写 | **RADAR 对抗训练** + **paraphrase 数据 augment** | 复述攻击 F1 从 40s → 70s |

**辅助**：加溯源头（识别是 GPT / Claude / Qwen / 哪家产的，教育场景老师会问"是不是 ChatGPT 写的"）。

**升级路径**：Phase 1（1-2 周）先把 backbone 从 RoBERTa-Base 换到 XLM-R-Large，跑现有训练脚本验证 delta；Phase 2（2-3 周）加零样本双检；Phase 3（3-4 周）加对抗鲁棒 + 溯源。

---

## 1. 问题重述与技术光谱

### 1.1 中文 AIGC 文本检测的独特挑战

1. **中文分词与 tokenization**：BPE 在中文上会把常见词切碎，检测器容易被"字面级伪影"欺骗。中文场景必须用中文分词友好的 tokenizer（jieba 分词 + WordPiece 或直接 char-level）
2. **多域覆盖**：论文 / 新闻 / 小说 / 对话 / 政务公文 / 电商评论，风格差异比英文更极端
3. **AIGC 中文化程度低**：GPT-4o / Claude 生成的中文有明显"翻译腔"（例如"值得注意的是"、"综上所述"，代码里 `AI_SAMPLES_GPT` 已经点出）—— 是可利用的偏差，但也是逃避改写的目标
4. **对抗改写盛行**：教育场景学生会用「知网降重」「PaperEasy 降 AIGC」软件洗稿，检测必须对 paraphrase 鲁棒
5. **短文本极难**：<200 字的段落几乎无法可靠检测，这是所有方法共同的下限

### 1.2 技术光谱（2024-2026 主流方向）

| 类别 | 代表方法 | 长处 | 短处 |
|---|---|---|---|
| **监督微调分类器** | RoBERTa / DeBERTa + LoRA | 稳定、可控、易部署 | 需大量标注、易过拟合训练时代的 AI 分布 |
| **白盒零样本** | GLTR / DetectGPT / **Fast-DetectGPT** / **Binoculars** / Ghostbuster | 无需 AI 样本训练、跨模型泛化好 | 需要访问一个"打分 LM"、推理成本高 |
| **对抗鲁棒训练** | **RADAR** / **PaST** / **CoCo** | 抗 paraphrase 和 back-translation | 训练复杂，需生成对抗样本 |
| **LLM-as-Classifier** | Qwen-2.5-7B / Llama-3-8B + prompt | 零样本能力强 | 慢、贵、稳定性差 |
| **水印检测** | Kirchenbauer et al. (2023) / SynthID | 高准确率 | 只对合规厂商加水印的文本有效 |

**我推荐三层组合（监督 + 白盒 + 对抗鲁棒）**，不选 LLM-as-Classifier（成本 & 稳定性差）与水印（在国内 AI 服务不加水印，覆盖为 0）。

---

## 2. Backbone 选型深度对比

### 2.1 中文 encoder-only 备选（分类头场景首选）

| Backbone | 参数量 | 上下文 | 中文能力 | 建议 |
|---|---|---|---|---|
| `hfl/chinese-roberta-wwm-ext`（当前）| 102M | 512 | 中等 | 基线，2019 年模型 |
| `hfl/chinese-roberta-wwm-ext-large` | 325M | 512 | 强 | **✅ 最小升级步长**，代码几乎不用改 |
| `xlm-roberta-large` | 550M | 512 | 强（多语言） | **✅ 推荐**，跨域泛化最好，SuperGLUE 顶级 |
| `microsoft/mdeberta-v3-base` | 279M | 512 | 强 | **✅ 首选**（相对成本），DeBERTa-v3 的 disentangled attention 对细粒度语义敏感 |
| `microsoft/deberta-v3-large`（多语言版）| 434M | 512 | 强 | **✅ 首选**（性能上限） |
| `ERNIE 3.0 Zh XL` | ~10B | 512 | 极强 | 百度自研，中文任务 SOTA，但部署重 |
| `hfl/chinese-macbert-large` | 325M | 512 | 强 | 备选，与 RoBERTa 同源族 |

**推荐决策路径**：
- **保守升级**：`chinese-roberta-wwm-ext-large`（同厂同架构，改 model_path 一行即可，训练代码零改）
- **推荐升级**：`microsoft/mdeberta-v3-base` 或 `xlm-roberta-large`（多语言 backbone 在跨域跨代 AI 上更稳）
- **激进升级**：`microsoft/deberta-v3-large`（性能上限，单卡 24GB 可训，需要 fp16/bf16）

### 2.2 中文 decoder-only 备选（可做白盒 + LoRA 分类）

| 模型 | 参数量 | 用法 | 备注 |
|---|---|---|---|
| Qwen 2.5-7B-Instruct | 7B | 白盒 logit / LoRA 分类 | 中文任务 SOTA 之一，Apache-2.0 |
| Qwen 2.5-1.5B | 1.5B | 白盒 logit 打分 | 轻量，可做 Binoculars 的 observer |
| Yi-1.5-6B / 9B | 6B/9B | 分类头 | 中文长文本表现好 |
| InternLM 2.5 | 7B | 分类头 | 上海AI Lab，中文强 |
| ChatGLM 3-6B | 6B | 分类头 | 中文 SFT 数据丰富 |
| Baichuan 2-7B | 7B | 分类头 | 中文商用友好 |

**关键选择**：**Binoculars（Anthropic）** 白盒方法需要**两个不同 LM**（一个 observer, 一个 performer），两者必须能计算 log-likelihood。推荐 **Qwen 2.5-1.5B（observer）+ Qwen 2.5-7B（performer）** 或 **Qwen 2.5-1.5B + Yi-1.5-6B**（跨 vendor 更稳）。

---

## 3. 白盒零样本方法（应对新 LLM 的必要保险）

### 3.1 Fast-DetectGPT（Bao et al., ICLR 2024）

- **原理**：DetectGPT 的加速版。核心假设：AI 文本比人类文本处于**LM 概率曲率的局部最大**。对文本做条件采样扰动，比较原文与扰动样本的 log-prob 差。
- **加速**：DetectGPT 需要 100 次扰动，Fast-DetectGPT 用**采样一次 + 解析式条件方差**替代，加速 340×。
- **效果**：GPT-4 / Claude / PaLM 生成文本上 AUROC 0.95+，比 DetectGPT 高 20-40 pp。
- **中文可用性**：需要一个中文 LM 作 scoring model（Qwen 2.5-1.5B 或更大均可）。
- **推理成本**：一次推理 ~300ms（单卡 A100，1.5B model, 512 token）
- **repo**：https://github.com/baoguangsheng/fast-detect-gpt
- **推荐落地**：作为**主分类器的兜底**，当主分类器 confidence 在 [0.35, 0.65] 灰区时触发。

### 3.2 Binoculars（Hans et al., ICML 2024, Anthropic）

- **原理**：两个 LM（observer + performer）分别对同一段文本算 perplexity，比较其 **cross-perplexity ratio**。人类文本对两个 LM 都"陌生"，AI 文本对同源族 LM"熟悉"。
- **效果**：Falcon-7B/40B pair 在英文上 F1 0.98，跨代 GPT-4 / Claude / PaLM 全线泛化。
- **中文可用性**：**必须用中文 LM 对**。Qwen 2.5-1.5B + Yi-1.5-6B 效果需实测。
- **推理成本**：一次推理 ~500ms（两个 forward，可并行）
- **repo**：https://github.com/ahans30/Binoculars
- **推荐落地**：与 Fast-DetectGPT 组成"零样本双检"，任一触发 AI 判定就升级审查。

### 3.3 Ghostbuster（Verma et al., ACL 2024, Berkeley）

- **原理**：用一系列 weaker LM（GPT-2 系）算特征，训练一个 shallow 分类器（logistic regression）。**极轻量、极快、cross-domain 好**。
- **效果**：跨域 F1 0.95+，比 DetectGPT 快 100×。
- **中文可用性**：需要中文小 LM 系列（GPT-2-Chinese / Qwen-0.5B / TinyLlama-Chinese），可行但需要重新训分类器。
- **推荐落地**：作为**极端 SLA 场景**（例如 API 高 QPS 需 <50ms）的快检。

### 3.4 GPTZero / Originality.AI / Copyleaks 商业产品

**不推荐研究**，因为闭源、SLA 依赖、中文表现在教育社区已被广泛诟病（误判外语学生的英文写作、误判成语典故为 AI）。

---

## 4. 对抗鲁棒（应对 DIPPER 与手动改写）

### 4.1 攻击面

| 攻击 | 强度 | 现有检测器崩坏程度 |
|---|---|---|
| 同义词替换 | 弱 | RoBERTa 类模型抗性尚可 |
| Back-translation（中→英→中）| 中 | F1 掉 15-25 pp |
| **DIPPER**（专门训练的复述模型）| 强 | F1 掉 30-50 pp，行业公认最难 |
| 人工手改（学生 3-5% 编辑）| 强 | F1 掉 40 pp+，检测几乎失效 |
| 段落级混合（一半 AI 一半 human）| 极强 | 段落级判定必输 |

### 4.2 防御方向

**A. 训练时引入对抗样本**（推荐）

- **DIPPER 增强**（Krishna et al., NeurIPS 2023）：用 DIPPER 中文版把训练集里的 AI 样本改写一遍加进训练。目前无官方中文 DIPPER，但可用 Qwen 2.5-7B / Claude 4 prompt 生成同等强度改写。
- **RADAR**（Hu et al., NeurIPS 2023）：对抗训练框架，检测器 vs 改写器交替优化。检测器学抵抗；改写器学骗过检测器。
- **CoCo**（Kong et al., EMNLP 2023）：coherence-based 对比学习，学习"AI 文本的段落间连贯性异常"。

**B. 段落级 + 文档级双输出**（推荐）

- 不只出「整篇 AI 概率」，同时出「每段 AI 概率」，帮老师定位到具体段落
- 段落级用滑动窗口 + 分类头；文档级用段落聚合（mean / max / voting + Arbitrator 校准）

**C. Stylometric features 融合**（可选）

- 保留 `statistical_features.py` 里的 18 KB 统计特征（Zipf / Burstiness / Slop / Transition 等），作为对抗改写的补充分支。**当前实现已经很好，不需要重写，只需要在融合层给它一个显式权重**。

---

## 5. LLM 溯源（教育场景的加分能力）

**动机**：老师收到 AI 检测报告，下一个问题永远是"是 ChatGPT 还是 Kimi 还是 DeepSeek？"。给出溯源大幅提升产品说服力。

**方法**：在检测头加一个**多类别溯源头**（human / GPT-4-family / Claude-family / Qwen-family / DeepSeek-family / GLM-family / Kimi-family / Other）。共享 backbone，独立分类头。

**已知工作**：
- **TuringBench**（Uchendu et al., 2020）—— 19 个 AI 生成器分类
- **M4**（Wang et al., 2024）—— 多语言多生成器 8-way 分类
- **CoAuthor Attribution**（Zellers et al., 2019）—— 归因基准

**训练要点**：训练数据里必须**均衡覆盖 7-8 家主流中文 LLM**，否则会退化成"能识别 GPT 但把 Kimi 都判成 GPT"。

---

## 6. 中文数据源清单（数据从 0 构建方案）

### 6.1 公开中文 AIGC 检测数据集

| 数据集 | 规模 | 域 | 生成器 | 许可 | 备注 |
|---|---|---|---|---|---|
| **HC3-Chinese** | 24K 对 | 问答 | ChatGPT | CC-BY-SA | 最经典中文集，2023-01 |
| **HC3-Plus** | 200K | 多域 | ChatGPT | CC-BY-SA | HC3 扩充版 |
| **CHEAT** | 35K | 学术论文摘要 | ChatGPT | 研究用 | **教育路径必备** |
| **MULTITuDE** | 74K | 新闻 | 多生成器 | 多语言 | 含中文子集 |
| **M4** | 122K | 多域 | 8 个 LLM | 研究用 | 支持溯源训练 |
| **AITextDetect** | 1M+ | 综合 | 多生成器 | Apache | HuggingFace hub |
| **MAGE** | 400K | 综合 | 27 个 LLM | 研究用 | 溯源训练金标准 |
| **CCL2024 CTG-AI** | 竞赛集 | 多域 | 多生成器 | 竞赛用 | 中文最新（2024） |
| **NLPCC 2024 AIGC 检测** | 竞赛集 | 学术 | 多生成器 | 竞赛用 | 中文 |

### 6.2 自建数据方案（教育路径深度定制）

**核心目标**：覆盖 5 种真实使用场景 × 6 家主流中文 LLM = 30 种组合，每种 3000-5000 条。总规模 100K+ 平衡数据集。

**场景清单（教育向）**
1. 论文摘要（中文核心期刊风格）
2. 论文正文段落（引言 / 方法 / 结论 分开采样）
3. 课程作业 / 实验报告
4. 议论文 / 议政评论
5. 学术翻译（英译中，最难识别）

**生成器清单**（2026 主流中文可用）
- Qwen 2.5-Max / Qwen 3
- DeepSeek V3 / R1
- GLM-4 / GLM-4.5
- Kimi K1.5
- 文心一言 4.5 / 5
- Baichuan 3
- （国际）GPT-4o / Claude Opus 4 / Gemini 2.0（走 API）

**Human 端来源**
- 中国知网 CNKI 公开摘要（合规抓取）
- 教育部本科毕业论文抽检数据（如可获取）
- 汉语语言学教材 / 权威教科书段落
- 早于 2020 年的博客与论坛（AIGC 出现前的"纯人类"文本）—— **关键**

**对抗改写生成**（20% 训练数据比例）
- 用 Qwen 2.5-7B / GLM-4 对 AI 文本做 3 种改写：
  - 同义改写（弱）
  - "以更口语化 / 学术化的方式改写"（中）
  - "改写以避免 AI 检测"（强，就是 DIPPER 目标）

**总数据规模估算**
- 30 场景组合 × 3-5K = 90-150K AI 样本
- Human 样本同规模 = 90-150K
- 对抗改写 = 30K
- **合计 ~250K 样本 = 单机训 1 epoch 约 4-6 小时（A100）**

**标注成本**：几乎全自动（生成即打标），只需要 1-2 人 spot check 5% 样本质量。**远远低于图像/音频的人工标注成本**。

---

## 7. 落地方案（三阶段升级路径）

### Phase 1 · Backbone 升级（推荐 1-2 周）

**动作**：
1. `train_text_detector.py` 里 `model_path` 从 `hfl/chinese-roberta-wwm-ext` 换到 `microsoft/mdeberta-v3-base` 或 `xlm-roberta-large`
2. `unfreeze_layers` 从 8 调到 12-14（更大模型有更多可微调空间）
3. `layerwise_lr` 的 `bottom_lr_factor` 从 0.25 → 0.1（更大模型 bottom 更稳）
4. `batch_size` 从 16 → 8（吃显存），`grad_accum_steps` 从 2 → 4（保持等效 batch 32）
5. `max_length` 保持 512

**预期 delta**：val F1 +3-8 pp（in-domain），OOD 泛化 +5-15 pp

**风险**：无，最小改动、纯换 backbone

**验收**：新旧模型在同一份 CHEAT + HC3-Chinese 测试集上跑，AUC / F1 / ECE 全线上涨

### Phase 2 · 零样本双检（2-3 周）

**动作**：
1. 新增 `detectors/text/fast_detectgpt_branch.py`（wrap Fast-DetectGPT 官方实现）
2. 新增 `detectors/text/binoculars_branch.py`（wrap Binoculars）
3. 更新 `detectors/text/ensemble.py`：主分类器 + Fast-DetectGPT + Binoculars 三票融合
4. 灰区（主分类器 confidence ∈ [0.35, 0.65]）才触发零样本双检（成本控制）
5. 加载两个中文 scoring LM（Qwen 2.5-1.5B + Yi-1.5-6B）到 model_registry

**预期 delta**：新 LLM（Claude 5 / GPT-5 / Qwen 3）零样本 F1 从 60s → 85+

**风险**：显存占用 +10-15 GB（两个 LM 常驻），推理时延 +300-800ms（灰区触发）

**验收**：拉一批 backbone 训练时**没见过**的 LLM 生成的文本（例如 Claude Opus 5 / Qwen 3-32B）测试

### Phase 3 · 对抗鲁棒 + 溯源（3-4 周）

**动作**：
1. 数据集扩充 30K 对抗改写样本（DIPPER-style，用 GLM-4 生成）
2. 加溯源头（多类分类头，共享 backbone）
3. 训练时 loss = 二分类 loss + 0.3 × 溯源 loss
4. 前端结果展示新增「疑似来源：Qwen / DeepSeek / GPT」标签

**预期 delta**：DIPPER 攻击下 F1 从 40s → 70s；溯源 top-1 acc 70+%（human vs 7 家）

**风险**：训练数据构建工作量最大（此阶段 1-2 周花在数据 pipeline 上）

**验收**：手动构造 100 条"DIPPER-style 复述后的 AI 文本"，检测 F1 > 0.7

---

## 8. 论文特化路径（thesis_reducer + thesis_detector 的升级）

**当前**：`services/thesis_reducer.py` (16 KB) + `thesis_detector.py` (17 KB) 是最大的两个服务文件，说明「论文降 AIGC + 论文检测」是主推付费场景。

**降 AIGC 的模型选型**（之前用户曾提"用自己模型"）：

原方案（依赖 LLM 改写）→ 新方案（本地 seq2seq）候选：

| 方案 | 模型 | 参数 | 中文能力 | 部署成本 | 效果 |
|---|---|---|---|---|---|
| Qwen 2.5-7B-Instruct **LoRA 微调** | 7B + 40M LoRA | 24GB VRAM 推理 | 极强 | 中 | 强 |
| ChatGLM 3-6B **LoRA 微调** | 6B + 30M LoRA | 16GB VRAM 推理 | 强 | 中 | 强 |
| mT5-Large + 微调 | 1.2B | 8GB VRAM | 中 | 低 | 中 |
| Chinese-BART-Large | 400M | 4GB VRAM | 中 | 低 | 中 |

**推荐**：Qwen 2.5-7B LoRA 微调，训练数据用「AI 原文 → 更像人类的改写」pairs（可以用 Claude 4 生成，5-10K 对足够 LoRA）

**「更像人类」的定义**：改写后的文本被 Phase 1 分类器判为 AI 的概率 < 30%

---

## 9. 评测基线（P3 需要构建）

**四个测试集必须**：
1. **In-domain**：CHEAT-test + HC3-Chinese-test（现成）
2. **Cross-generator**：训练时见过的 3 家 LLM + 训练时**没见过**的 3 家 LLM 各 500 条
3. **Adversarial**：DIPPER-style 复述 500 条 + 手动 spot 修改 300 条
4. **Short-text**：50-200 字段落各 300 条（检测器的天然弱点）

**指标**：AUC / F1 / TPR@FPR=1% / ECE / **每个子测试集独立报告**

---

## 10. 风险与坑

| 风险 | 严重度 | 缓解 |
|---|---|---|
| 大 backbone 训练慢（每 epoch 从 20 分钟→2 小时） | 中 | 上 A100 40GB / 用 DeepSpeed ZeRO / gradient checkpointing |
| Binoculars 中文效果无 paper 支撑 | 高 | Phase 2 前先做一次 100 条 spot 测试再定 |
| DIPPER 无中文官方版 | 中 | 用 Qwen 2.5-7B + prompt template 自建 |
| 溯源头训练数据不均衡（GPT/Claude 好搞、Kimi/文心难搞） | 中 | 用「Other」类兜底，均衡类别权重 |
| 校准（calibration.py）目前接不进运行时 | 中 | 属于工程债，放到"支线任务"，与模型升级并行 |
| 训练数据里"人类文本"可能污染（2023 后的博客/知乎已被 AI 污染） | 高 | **严格用 2020 年前的 human 数据 + 手工校对 5% 样本** |

---

## 11. 参考文献与资源

**关键论文（Phase 1-3 都要看）**

1. **Fast-DetectGPT** — Bao G. et al. "Fast-DetectGPT: Efficient Zero-Shot Detection of Machine-Generated Text via Conditional Probability Curvature." ICLR 2024. https://arxiv.org/abs/2310.05130
2. **Binoculars** — Hans A. et al. "Spotting LLMs With Binoculars: Zero-Shot Detection of Machine-Generated Text." ICML 2024. https://arxiv.org/abs/2401.12070
3. **DetectGPT** — Mitchell E. et al. "DetectGPT: Zero-Shot Machine-Generated Text Detection using Probability Curvature." ICML 2023. https://arxiv.org/abs/2301.11305
4. **RADAR** — Hu X. et al. "RADAR: Robust AI-Text Detection via Adversarial Learning." NeurIPS 2023. https://arxiv.org/abs/2307.03838
5. **DIPPER** — Krishna K. et al. "Paraphrasing evades detectors of AI-generated text, but retrieval is an effective defense." NeurIPS 2023. https://arxiv.org/abs/2303.13408
6. **Ghostbuster** — Verma V. et al. "Ghostbuster: Detecting Text Ghostwritten by Large Language Models." ACL 2024. https://arxiv.org/abs/2305.15047
7. **MAGE** — Li Y. et al. "MAGE: Machine-generated Text Detection in the Wild." ACL 2024. https://arxiv.org/abs/2305.13242
8. **M4** — Wang Y. et al. "M4: Multi-generator, Multi-domain, and Multi-lingual Black-Box Machine-Generated Text Detection." EACL 2024. https://arxiv.org/abs/2305.14902

**中文特化**

9. **HC3-Chinese** — Guo B. et al. "How Close is ChatGPT to Human Experts? Comparison Corpus, Evaluation, and Detection." 2023. https://arxiv.org/abs/2301.07597 · https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese
10. **CHEAT** — Yu P. et al. "CHEAT: A Large-scale Dataset for Detecting ChatGPT-writtEn AbsTracts." arxiv 2023. https://arxiv.org/abs/2304.12008

**Backbone HuggingFace 页**

- microsoft/mdeberta-v3-base: https://huggingface.co/microsoft/mdeberta-v3-base
- microsoft/deberta-v3-large: https://huggingface.co/microsoft/deberta-v3-large
- FacebookAI/xlm-roberta-large: https://huggingface.co/FacebookAI/xlm-roberta-large
- Qwen/Qwen2.5-1.5B-Instruct: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct
- Qwen/Qwen2.5-7B-Instruct: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct

**开源实现**

- Fast-DetectGPT: https://github.com/baoguangsheng/fast-detect-gpt
- Binoculars: https://github.com/ahans30/Binoculars
- Ghostbuster: https://github.com/vivek3141/ghostbuster
- DIPPER: https://github.com/martiansideofthemoon/ai-detection-paraphrases
- RADAR: https://github.com/IBM/RADAR

**中文竞赛与 leaderboard**

- CCL 2024 AI-Text Detection: http://cips-cl.org/static/CCL2024/
- NLPCC 2024 Shared Task on Detection of Machine-generated Chinese Text
- HuggingFace zh-aigc-text leaderboard（社区）

---

## 12. 结论表（给决策者的一页纸）

| 决策项 | 建议 | 依据 |
|---|---|---|
| 保留 `train_text_detector.py` 训练框架吗？ | **保留**，只换 backbone 与 unfreeze 层数 | 该脚本工程质量教科书级，不需要重写 |
| 主 backbone 换哪个？ | **microsoft/mdeberta-v3-base** 首选性价比，或 **xlm-roberta-large** 首选性能 | 中文任务 SOTA，训练兼容现有代码 |
| 是否引入白盒零样本？ | **是**，Fast-DetectGPT + Binoculars 双检 | 应对新 LLM 迭代，防止训练数据老化 |
| 对抗鲁棒方案？ | **数据侧 DIPPER-style 增强** + **RADAR 对抗训练** | 教育场景 paraphrase 是最大失效原因 |
| 溯源头？ | **加**，8-way 分类 | 教育场景强需求，能明显提升产品说服力 |
| 论文降 AIGC 用什么模型？ | **Qwen 2.5-7B LoRA 微调** | 中文改写能力最强的开源模型 |
| 数据规模目标？ | **250K 训练 + 4 套测试集** | 覆盖 5 场景 × 6 生成器 × human/AI，加对抗改写 |
| GPU 需求？ | **单卡 A100 40GB 训主 backbone，A100 80GB 训 7B LoRA** | 云按需租，训练一轮 6-10 小时 |
| 时间预算？ | **总 6-9 周**（Phase 1: 2周，Phase 2: 3周，Phase 3: 4周，可并行） |  |

---

**下一步**：确认本调研方向后，进入 P2-image（图像模态）。或者你选择先跳到 P3 出综合选型方案，再一次性看四模态。

---

# v2 增补 · 2026-09-17 外网最新调研（企业级论文检查特化）

> v1 基于 Claude 2026-01 知识写成；本节为 WebSearch 实时拉取的 2025-2026 最新论文与市场情报，聚焦「企业级论文检查」场景。系统架构见 `ENTERPRISE_ARCHITECTURE.md`。

## A. 政策确认（商业化的直接推力）

- 教育部 2025 年发布《关于加强高等学校学位论文 AIGC 检测工作的指导意见》，**2026 年春季学期起全国高校全面实施**
- **AI 率红线：本科 ≤ 20% / 硕士 ≤ 15% / 博士 ≤ 10%**
- 高校个例：清华 ≤20%；北大硕博强制检测结果作答辩参考；人大 AIGC >30% 不予通过
- 结论：**产品必须支持按学位类型配置阈值 + 检测报告作为答辩材料的电子签形态**

## B. 2026 最新论文（v1 未覆盖）

| 论文 | 要点 | 对我们的价值 |
|---|---|---|
| **C-ReD**（arxiv 2604.11796） | 2026 中文 AI 文本检测综合基准，源自真实世界 prompts | 直接作为我们的 evals 核心测试集 |
| **MAGA-Bench**（arxiv 2601.04633） | 「机器增强生成」（human 草稿 + AI 润色）检测基准 | 论文场景大量是这种混写，比纯 AI 更常见 |
| **DeBERTa-Sentinel**（arxiv 2608.01046） | DeBERTa-v3 disentangled attention 检测，val_acc 98.21% | 主分类器 backbone 直接依据 |
| **DetectRL-X**（arxiv 2605.15518） | 多语言真实场景检测基准；发现 **Qwen 生成文本最难检测** | 溯源头训练时 Qwen 样本必须充足 |
| **HACo-Det**（arxiv 2506.02959） | 人机共写（co-authoring）细粒度检测 | 支撑句子级混写边界定位 |
| **Fine-Grained Sentence-Level Segmentation**（arxiv 2509.17830） | Transformer + CRF 句子级 authorship 边界分割 | 句子级检测（差异化能力）的方法论 |
| **GPTZero 官方论文**（arxiv 2602.13042） | 公开句子级 perplexity + burstiness 融合方法 | 可复现其句子级解释能力 |
| **Adversarial Paraphrasing**（arxiv 2506.07001） | 2025 通用「人性化」攻击，绕过几乎所有检测器 | 必须纳入对抗测试集 |
| **DAMAGE**（arxiv 2501.03437) | 检测「对抗改写后的 AI 文本」 | 白盒防御方案新增成员 |
| **Fight Poison with Poison**（arxiv 2605.02374） | 少样本对抗训练提升鲁棒 | RADAR 的轻量替代 |
| **Reasoning-Aware AIGC Detection**（arxiv 2604.19172） | 推理对齐 + 强化学习检测 | 2026 前沿方向，P2 关注 |
| **CCL25-Eval Task 5**（arxiv 2606.12392 / ACL 2025.ccl-2.24） | LoRA 微调 Qwen2.5-14B 比 baseline +9.7% | 降 AIGC 训练方案的中文最强证据 |

## C. 降 AIGC 生态确认（用户主打功能）

- **HF 现成模型**：`arunsingh80475/qwen2.5-14b-humanizer-v3-lora` —— Qwen2.5-14B LoRA humanizer，可直接 warm start
- **开源项目 XiangJinyu/humanize-zh**：从 CSL 学术摘要合成 18K 训练对（AI 改写版, human 原版），双向 rejected data 4K，Qwen 3.5-9B 训 0.8 epoch
- **市场热度证明**：aigc-humanizer-zh MCP server（宣称降 22-53 个点 AI 率）、humanize-chinese 等多个开源工具，商业需求真实存在
- **训练数据配方已被验证**：CSL/学术语料 → LLM 改写 → (AI 版, human 版) pairs → LoRA。我们的方案与最佳实践一致

## D. 竞品市场格局（2026 实测数据）

**国际**：
- GPTZero：Booth 商学院基准 99.5%（GPT-4.1/Claude Opus 4/Gemini 2.0 全测），**但独立 2400 样本混合测试仅 87% + 10% 误报**
- Turnitin：300+ 词 98% 准确、<1% FP（官方口径）；对非母语学生 FP 高达 **61.3%**（TOEFL 中国学生 essay），Vanderbilt/Yale/JHU 等多校已禁用其 AI 检测
- 对轻度编辑后的 AI 文本，所有检测器掉 10-30 pp

**国内**：
- 知网：>50% 高校主流，深度学习多维度（perplexity + burstiness + semantic coherence），判定偏保守
- 维普：比知网严 ~10%，但人写文本误判率也更高
- 万方：居中
- **知网/维普/万方都没有：溯源、降 AIGC、句子级解释** —— 这就是我们的空间

**启示**：
1. 「误判管理」是全行业痛点 → 我们的校准置信区间 + 教师 override + 溯源解释是信任卖点
2. 高校对 AI 检测信任度在下降（多校禁用 Turnitin）→ 报告透明度（句子级 + 分支得分 + 置信区间）比"一个分数"更有说服力
3. 混写检测（MAGA-Bench 场景）是下一代竞争焦点，纯 AI 检测已是红海

## E. 更新后的推荐组合（覆盖 v1 结论）

| 层 | v1 推荐 | v2 更新 | 变化原因 |
|---|---|---|---|
| 主分类器 | mDeBERTa-v3-base / XLM-R-large | 不变，另加 **RAID 榜单对标**（desklib v1.01 是公开第一，我们的目标是在中文子集超它） | 外网证实 DeBERTa-v3 系仍是 2026 最佳监督基线 |
| 句子级 | （v1 未包含） | **新增**：Transformer + CRF 边界分割（2509.17830）+ GPTZero 式句子 perplexity | 竞品分析确认这是核心差异化 |
| 白盒 | Fast-DetectGPT + Binoculars | + **DAMAGE**（抗改写检测）| 2025 新方法补位 |
| 对抗 | RADAR + DIPPER 增强 | + **Fight-Poison-with-Poison**（少样本对抗）+ **Adversarial Paraphrasing** 纳入测试集 | 2025-2026 攻击演进 |
| 降 AIGC | Qwen 2.5-7B LoRA | 不变 + **HF 14B LoRA warm start** + CCL25 证据 | 中文最强证据落实 |
| 评测集 | 4 套自建 | + **C-ReD** + **MAGA-Bench**（公开基准直接用） | 2026 新基准可直接引用，节省自建成本 |
| 混写检测 | （v1 未包含） | **新增关注**：MAGA-Bench + HACo-Det 的 human-AI coauthoring 场景 | 论文实际场景大多是混写 |

## F. v2 参考文献（新增部分）

- [C-ReD](https://arxiv.org/pdf/2604.11796) · [MAGA-Bench](https://arxiv.org/pdf/2601.04633) · [DeBERTa-Sentinel](https://arxiv.org/html/2608.01046v1) · [DetectRL-X](https://arxiv.org/pdf/2605.15518) · [HACo-Det](https://arxiv.org/pdf/2506.02959)
- [Sentence-Level Segmentation](https://arxiv.org/html/2509.17830v2) · [GPTZero 官方论文](https://arxiv.org/pdf/2602.13042)
- [Adversarial Paraphrasing](https://arxiv.org/pdf/2506.07001) · [DAMAGE](https://arxiv.org/pdf/2501.03437) · [Fight Poison with Poison](https://arxiv.org/pdf/2605.02374) · [Reasoning-Aware Detection](https://arxiv.org/pdf/2604.19172)
- [CCL25-Eval Task 5](https://arxiv.org/abs/2606.12392) · [qwen2.5-14b-humanizer-v3-lora](https://huggingface.co/arunsingh80475/qwen2.5-14b-humanizer-v3-lora) · [humanize-zh](https://github.com/XiangJinyu/humanize-zh)
- [HC3-Chinese](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese) · [HC3 Plus](https://arxiv.org/html/2309.02731v2)
- [Turnitin vs Copyleaks vs GPTZero 2026](https://www.browse-ai.tools/blog/turnitin-vs-copyleaks-vs-gptzero-2026-ai-detection-guide-for-educators) · [知网 vs 维普 vs 万方](https://blog.csdn.net/aigccleaner/article/details/158237711) · [2026 高校 AI 率新规](https://blog.csdn.net/aigccleaner/article/details/158815343)
