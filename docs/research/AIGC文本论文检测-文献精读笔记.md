# AIGC 文本 / 论文检测 —— 文献精读笔记

> 范围：仅针对「AIGC 文本/论文检测」方向提取归纳。原始 7 个文件中有 2 篇为图像检测（Bammey 2023、Guillaro 2025），与本方向无关，已排除；本文仅收录 5 篇相关文献，并附原文关键段落（英文原文摘录 + 中文译注）。

---

## 一、《AIGC 检测方法与重要 SCI 文献汇编》—— 技术路线谱系

**性质**：检索汇编（非单篇论文），价值在于把文本检测路线梳理成六条，并指明商用主流路线。

### 原文核心（六条文本检测路线）

> 当前国内外文本类 AIGC 检测方法大致可归为六条技术路线：
> 1. **统计度量与语言模型打分法**：困惑度（Perplexity）、对数秩（Log-Rank）、突发度（Burstiness）等；代表 GLTR、GPTZero。
> 2. **零样本检测法**：DetectGPT（概率曲率）、Fast-DetectGPT、Binoculars（双模型困惑度比）、Raidar（重写编辑距离）。
> 3. **有监督微调分类器**：在"人类—机器"标注语料上微调 BERT/RoBERTa，**是目前商用系统的主流路线**；国内知网、万方、维普普遍采用微调 BERT/RoBERTa 并融合篇章级特征。
> 4. **特征工程 + 传统 ML / 群智能优化**：TF-IDF、词嵌入 + SVM/LSTM + 群智能调参（Katib 的 TSA-LSTMRNN 即属此列）。
> 5. **水印与溯源**：绿名单水印、C2PA；Sadasivan 论证了强对抗场景下检测的固有局限。
> 6. **句级/混合检测 + 检索比对**：SeqXGPT（句级）、Krishna（改写可规避、检索比对是有效防御）。

### 对本项目的结论

原文第 3 条明确点名「微调 BERT/RoBERTa 分类器是商用系统主流路线」—— 你的项目以 `hfl/chinese-roberta-wwm-ext` 为骨干做微调分类，方向与商用共识一致。

---

## 二、Crothers 2023《Machine-Generated Text: A Comprehensive Survey of Threat Models and Detection Methods》

**出处**：*IEEE Access*, Vol. 11, pp. 70977–71002, 2023 | DOI: 10.1109/ACCESS.2023.3294090
**定位**：威胁模型 + 检测方法四大类的权威综述（被引 400+）。

### 2.1 威胁模型：学术不端被单列（§3.4.1）

> Use of algorithms to generate scientific papers has been well-established since **SCIgen** was created in 2005 to produce nonsensical papers that nevertheless **sometimes passed peer review**. These papers continue to emerge in respected publications, many years later...
> （自 2005 年 SCIgen 问世，算法生成科学论文已根深蒂固——它能产出一本正经胡说八道的论文，有时甚至通过同行评审；多年后这类论文仍在权威刊物出现。）

> Threat actors submitting AI-generated papers are typically either 1) **academics attempting to inflate publication statistics** ... or 2) well-meaning researchers probing the publication standards of a potentially disreputable conference.
> （提交 AI 生成论文的往往是：1) 为凑发表量/评聘指标而注水的学者；2) 试探低口碑会议审稿底线的研究者。）

> Mitigation measures should include **flagging likely machine-authored publications** ... Human reviewers can more carefully review flagged articles...
> （应对措施：标记疑似机器撰写的投稿，再由人工仔细复核。）

### 2.2 检测方法四大类（§4）

**（A）基于特征的分类器（§4.1）**—— 原文列出五类特征并有明确价值判断：

> Feature-based approaches ... may provide benefits such as **improved robustness against adversarial attacks** targeting neural networks, or better explainability.
> （基于特征的方法具备的优势：对针对神经网络的对抗攻击鲁棒性更强、可解释性更好。）

五类特征（§4.1.1–4.1.5）：
1. **频率特征**：偏离 Zipf 定律、TF-IDF、词元间 n-gram 重叠、最高频重复子串；
   > Human-written text often conforms with Zipf's Law... Machine generated text does not perfectly mirror the distribution of tokens in human text.
2. **流畅度/可读性特征**：Gunning-Fog 指数、Flesch 指数；
3. **辅助模型语言学特征**：POS 分布、命名实体、共指消解、Yule's Q；
4. **复杂短语特征**：idiomatic 短语（对当代 Transformer 模型在短文本上效果已下降）；
5. **基础文本特征**：标点数、句子/段落长度。

**（B）神经网络检测器（§4.2）—— 关键结论是 RoBERTa 微调 = SOTA：**

> The **state-of-the-art approach for neural detection** of machine generated text is based around **fine-tuning of large bi-directional language models**. ... RoBERTa — a masked general-purpose language model based on BERT — is fine-tuned to differentiate between NLG model output and human-written training samples.
> （神经检测的 SOTA 是对大型**双向**语言模型的微调；RoBERTa 是基于 BERT 的掩码通用语言模型，被微调用于区分生成文本与人类文本。）

> The pre-trained detection models available are based on the **RoBERTa-base (123M parameter) and RoBERTa-large (354M parameter)** architectures.
> （可用的预训练检测模型基于 RoBERTa-base 123M 与 RoBERTa-large 354M。）

> The strong performance of fine-tuned bi-directional NLM models — **and RoBERTa in particular** — has led to these models being well-represented in applied detection research...
> （微调双向 NLM——尤其 RoBERTa——的强性能，使其在应用检测研究中占据主导。）

**（C）一条对你直接有用的跨域结论（§4.3.1 技术文本）：**

> A RoBERTa-based detector could be **adapted from one academic technical writing domain (physics) to another (biomedicine)** with large improvements made with a number of **SME-labelled examples numbering in the hundreds**.
> （RoBERTa 检测器能从物理跨域适配到生物医学，仅需数百个专家标注样本即可大幅提升 —— 跨域适配成本很低。）

**（D）公平性警示（§3.3）**：非英语母语者文本易被误判为机器生成，与 Fraser §5.2 互为印证（见下）。

### 2.3 对本项目论文检测的借鉴

- 「RoBERTa 微调」的 SOTA 地位再次确认，主线无偏。
- 「基于特征的分类器」的**可解释性 + 对抗鲁棒性**优势，是论文检测（需要给出可解释的判定依据）值得补充的一路。
- 「物理→生物医学」跨域适配只需数百样本 —— 你从通用中文检测迁移到「学术论文」领域，成本可控。

---

## 三、Fraser 2025《Detecting AI-Generated Text: Factors Influencing Detectability with Current Methods》

**出处**：*Journal of Artificial Intelligence Research* (JAIR), Vol. 82, pp. 2233–2278, 2025 | DOI: 10.1613/jair.1.16665
**定位**：**对论文检测价值最高的一篇** —— 直接回答「为什么论文/学术文本难检测」。

核心命题：**AIGT 是一条谱系，检测难度由多个因素共同决定；论文恰好处在最难的一端。**

### 3.1 §5.1 生成模型规模 + 解码策略

> Detectability is related to model size by a **power law**, meaning that detection accuracy decreases linearly as the number of model parameters increases exponentially.
> （可检测性与模型规模呈幂律关系：参数量指数级增大，检测精度线性下降。）

> **nucleus sampling output is the most difficult to detect**, and detectors trained on nucleus-sampled data also generalize the best across other sampling methods.
> （nucleus sampling 输出最难检测；但用 nucleus 采样数据训练的检测器泛化反而最好。）

> A decrease of 21% is observed when the detector is trained on top-k decoding output and tested on nucleus sampling output.
> （训练用 top-k、测试用 nucleus 时，检测精度降 21%。）

### 3.2 §5.2 语言 —— 公平性硬伤（论文场景尤其要警惕）

> Texts written by **non-native English speakers are more likely to be falsely classified as AI**. Using seven publicly available detection tools, including GPTZero and ZeroGPT, they find that detection accuracy is almost perfect on US 8th-grade student essays whereas **TOEFL essays written by Chinese English learners have a false positive rate close to 60%**.
> （非英语母语者文本更易被误判为 AI。用 GPTZero、ZeroGPT 等 7 款工具测试：美国八年级作文几乎全对，但**中国英语学习者的 TOEFL 作文假阳率接近 60%**。）

> Detection methods are generally **biased against those with less varied linguistic expression**.
> （检测方法对语言表达较单一的人群存在系统性偏差。）

### 3.3 §5.3 文档长度

> Approximately **120 words are sufficient** for both statistical (GLTR, DetectGPT) and finetuning-based classifiers to reach their full potential... approximately **200 words** are sufficient to detect powerful LLMs such as ChatGPT-turbo and GPT-4.
> （约 120 词即可让统计法/微调法发挥完整潜力；检测 ChatGPT-turbo/GPT-4 约需 200 词。）

> A sequence length of around **500 words** should be sufficient [theoretically].
> （理论界：约 500 词足够。）

> It is still possible to improve detection by **concatenating disjoint posts from the same author**.
> （短文本可通过对同一作者的碎片拼接来提升可检测性。）

### 3.4 §5.5 人工影响程度（★ 论文检测的核心难点）

> The **GPT-polished** category contains abstracts that were **fully written by humans and then rewritten by ChatGPT for clarity**. As expected, **GPT-polished text is the hardest to detect; the evaluated methods (including GPTZero, ZeroGPT, and OpenAI's detector) perform worse than random guessing**.
> （"GPT-polished"= 人类写完整篇、再交给 ChatGPT 润色清晰度的摘要。结果正如预期：GPT-polished 文本最难检测，**包括 GPTZero、ZeroGPT、OpenAI 检测器在内的方法表现差于随机猜测**。）

> On scientific papers that were human-written, and then paraphrased by ChatGPT ... They obtain a detection accuracy of **75% on this dataset by finetuning RoBERTa with access to human-AI paraphrased data** during training.
> （在"人类撰写、ChatGPT 改写"的学术论文上，用含人机改写样本的数据微调 RoBERTa，可得 75% 准确率 —— 即**在训练中见到改写样本是关键**。）

> None are able to perform well at binary AIGT detection **if mixcase examples are not seen during training**. ... when mixcase examples are seen during training, the **Radar detector achieves approximately 88% detection accuracy** across all mixcase categories.
> （若训练中未见过"混合人机"样本，所有方法在二分类上表现都很差；而当训练中见到 mixcase 样本时，RADAR 检测器跨所有混合类别的准确率约 88%。）

> AI polishing at the **sentence level** worsens detectability more than polishing at the **word level**. The finetuned detectors seem especially brittle to typos, and threshold-based detectors are especially brittle to AI paraphrasing.
> （句级润色比词级润色更伤可检测性；微调检测器对拼写错误特别脆弱，阈值法对 AI 改写特别脆弱。）

### 3.5 §6 建议 —— 落地策略

> **Threshold-based methods can be calibrated to have low false positive rates** in their specialized detection setting. ... A large ensemble of **differently calibrated metrics for known detection cases, along with the more generally applicable language model-based classifiers for unknown detection cases**, will most likely be needed for robust AIGT detection.
> （阈值法可被校准到极低假阳；对已知场景用多个差异化校准的统计指标，对未知场景用通用 LM 分类器，二者组合是稳健检测最可能的方案。）

训练数据建议（原文条目）：语言匹配、**长度分布均衡（否则对短 AIGT/长人类文本会失效）**、域内生成、多作者（含不同风格与语言水平）、多 prompt、必要时用 nucleus sampling 生成、**若需检测人机混合必须把 mixcase 加入训练**。

### 3.6 对本项目论文检测的借鉴

- **论文 AIGC 的典型场景 = GPT-polished / 人机混合**，恰是 Fraser 反复强调的「最难检测、现有工具差于随机」区间。
- **必须把改写/润色/paraphrase 样本纳入训练**（否则检测在改写端崩盘；RADAR 见 mixcase 后约 88%）。
- **低假阳校准 + 集成**：论文场景误伤真论文代价高，统计阈值法校准到低假阳 + 微调分类器集成的组合值得落地。
- **公平性**：中文（母语）论文检测需警惕「语言表达规范/单一」导致的假阳，阈值不能一刀切。

---

## 四、Katib 2023《Differentiating Chat Generative Pretrained Transformer from Humans (TSA-LSTMRNN)》

**出处**：*Mathematics* (MDPI), 2023, 11(15), 3400 | DOI: 10.3390/math11153400
**定位**：传统特征 + 传统/浅层神经网络 + 元启发调参的代表，对论文检测参考价值低。

### 4.1 方法（原文三段式）

> The TSA-LSTMRNN technique focuses on designing **TF-IDF, word embedding, and count vectorizers** for the feature extraction process. For the detection and classification processes, the **LSTMRNN model** is used. Finally, the **TSA is employed for selecting the parameters** for the LSTMRNN approach.
> （特征提取用 TF-IDF + 词嵌入 + 计数向量化；检测分类用 LSTM-RNN；最后用海鞘群算法 TSA 优选 LSTM-RNN 的超参数。）

> the current study used the word embedding method for feature extraction, namely **Glove, pretrained model, FastText, and Word2Vec embedding with 300-D vectors**.
> （词嵌入用 GloVe、预训练模型、FastText、Word2Vec，均为 300 维向量。）

> The LSTM-RNN approach ... utilizes the **attention layers** so as to enhance the learning of the features as well as the feature weights.
> （LSTM-RNN 内含注意力层以增强特征与权重学习。）

### 4.2 数据与结果（暴露其局限）

样本原文是**餐厅评论**风格，与学术论文无关：

> Human-generated text: *The selection on the menu was great and so were the prices.*
> ChatGPT-generated text: *The menu had a great selection and the prices were good.*

结果（原文 Table 1/2/3）：

| 对比方法 | 人工文本准确率 | ChatGPT 文本准确率 |
|---|---|---|
| Decision Tree | 86.70% | 88.01% |
| SVM | 86.72% | 82.30% |
| XGBoost | 83.86% | 84.96% |
| CNN | 84.08% | 86.93% |
| ELM | 89.80% | 86.34% |
| **TSA-LSTMRNN（本文）** | **93.17%** | **93.83%** |

（文中参考文献 [11] 引用了 CHEAT 数据集 "a total of 35,304 synthetic abstracts"，但本文自用数据只是成对的餐厅评论样本。）

### 4.3 对本项目论文检测的借鉴（结论：可跳过）

- 数据是短评论、非学术论文；无任何改写鲁棒性验证；方法上元启发调参（TSA）也非主流。
- 对「论文检测」**参考价值低**，仅作为「特征工程 + 传统 ML」这条路线的反面注脚存在。

---

## 五、Chen 2026《ChatGPT Generated Text Detection Model Based on Phonetic Feature Extraction and Semantic Features》★

**出处**：*Scientific Reports*, 2026, 16:18827 | DOI: 10.1038/s41598-026-49952-8
**定位**：**5 篇里借鉴价值最高** —— 直接针对「改写鲁棒性」做特征级融合，且是国内团队、实验含学术摘要场景。

### 5.1 核心动机（与 Fraser 互为印证）

> Existing detection methods often rely solely on semantic representations and exhibit limited robustness, particularly **when texts are paraphrased or rewritten**. ... current methods rely heavily on deep semantic representations while largely overlooking **surface-level regularities that remain relatively stable under text transformations**.
> （现有方法多只依赖语义表示，在文本被转述/改写时鲁棒性有限；深层语义表示被过度依赖，而**在文本变换下相对稳定的表层规律被忽视**。）

### 5.2 方法：三层特征级融合

> The final representation of a document is constructed by concatenating the CLS embedding, the convolutional features, and the auxiliary surface-level feature vector:
> **h = [h_cls ; h_cnn ; f]**
> （最终表示 = RoBERTa 的 [CLS] 语义向量 + CNN 多尺度卷积特征 + 辅助表层特征向量，三层拼接。）

表层特征 f 的三类（原文 Table 1）：

| 特征类型 | 具体特征 |
|---|---|
| 结构特征（Structural） | 人称代词、标点、特殊符号、停用词、话语标记、词性标注 |
| 词汇特征（Lexical） | 段落/句子长度、句内唯一词数、空格数、词汇复杂度 |
| 语言多样性特征（Language diversity） | 阅读难度、复杂词汇、可读性、情感因素 |

其中「发音相关文本代理特征」单独成类，抓取的是**节奏、重复、风格一致性**等表层规律：

> We extract statistics from character and token sequences ... including: (i) distributions of word and character lengths, (ii) frequencies of repeated n-grams, (iii) punctuation density and interval patterns that approximate pause and rhythm structures, and (iv) token-level repetition rates and boundary regularities.
> （发音相关代理特征：①词/字符长度分布 ②重复 n-gram 频率 ③近似停顿与节奏的标点密度/间隔 ④token 重复率与边界规律。）

> ChatGPT tends to generate concise and direct texts, with low vocabulary diversity, while the texts written by humans pay more attention to details and modification, with high vocabulary change and complexity.
> （ChatGPT 文本倾向简洁直接、词汇多样性低；人类文本更重细节修饰、词汇变化与复杂度高。）

### 5.3 实验设置

> The learning rate was set to **2 × 10⁻⁵** ... **AdamW** optimizer ... batch size **16** ... trained for **5 epochs** ... **early stopping** based on validation performance. (A100)
> （lr=2e-5、AdamW、batch=16、5 轮、早停，A100 —— 与你项目 YAML 里的基线超参一致。）

**改写集构造方式（关键，可直接照抄）：**

> Rewritten texts were generated using **ChatGPT with paraphrasing prompts** to simulate realistic post-editing scenarios. The rewriting prompts instructed the model to **preserve the original semantic content while altering lexical choice, sentence structure, and syntactic organization**.
> （改写集 = 用 ChatGPT + 改写 prompt 生成，指令要求"保留语义、改变用词/句式/句法结构"。

### 5.4 结果（原文 Table 2 / 正文）

**HAGTC 数据集（教育场景）**：

| 模型 | 直接生成 acc / F1 | 改写 acc / F1 |
|---|---|---|
| RoBERTa | 87.71 / 92.42 | 83.22 / 87.33 |
| DistilBERT | 87.74 / 92.61 | 80.15 / 85.24 |
| Electra | 89.15 / 93.13 | 79.28 / 83.69 |
| DetectGPT | 81.63 / 93.34 | 66.83 / 80.47 |
| **RoBERTa-CNN（本文）** | **91.46 ± 0.32 / 94.66** | **87.64 / 90.21** |

**ChatGPT 撰写摘要数据集（学术场景）**：

| 模型 | 直接生成 acc / F1 | 改写 acc / F1 |
|---|---|---|
| RoBERTa | 95.16 / 95.22 | 87.11 / 70.13 |
| DistilBERT | 95.25 / 94.82 | 85.26 / 58.26 |
| Electra | 96.17 / 96.11 | 85.72 / 69.58 |
| DetectGPT | 67.72 / 67.34 | 77.47 / 48.35 |
| **RoBERTa-CNN（本文）** | **96.43 / 96.37** | **87.53 / 70.84** |

**关键观察**：所有基线的 F1 在改写集上大幅崩塌（如 RoBERTa 摘要集 F1 从 95.22 掉到 70.13），而 RoBERTa-CNN 的 acc 始终稳在 87%+。

**消融实验（原文 Fig 7）**：

> The combination of **statistical features + readability features + special marks achieves 92.11% accuracy and 94.03% F1** ... the fusion of the three features can provide more comprehensive text information.
> （统计 + 可读性 + 特殊标记三类特征融合达 92.11% / 94.03%，显著优于任意两两组合 —— 证明特征融合本身是增益来源。）

### 5.5 错误分析（★ 对论文场景最直白的一段）

> Misclassified AI-generated texts frequently contain **domain-specific terminology, technical expressions, and structurally complex sentences that closely resemble formal academic writing**.
> （被漏判的 AI 文本常含领域术语、技术表达、复杂句式，极像正式学术写作。）

> Certain human-written texts are occasionally predicted as AI-generated. These instances commonly display **highly standardized formatting, low emotional variability, and reduced stylistic irregularities** ... In particular, **human-written academic abstracts and technical reports** often emphasize clarity, consistency, and structural regularity, which can overlap with statistical patterns commonly observed in AI-generated texts.
> （被误判为 AI 的人类文本则高度规范化、情绪波动小、风格不规则性低…… 特别是**人类撰写的学术摘要与技术报告**，天然追求清晰、一致、结构规整，恰好与 AI 生成的统计模式重叠。）

> The detection task is fundamentally influenced by **stylistic regularization effects** rather than purely authorship-dependent features.
> （检测任务本质上受「风格规范化效应」主导，而非纯粹的作者相关特征。）

### 5.6 对本项目论文检测的借鉴（最易照抄）

- 在现有 RoBERTa 分类器上**加一条「表层/文体特征」支路做特征级融合**（`[h_cls; h_cnn; f]`），是提升改写鲁棒性的最直接方案。
- **改写集构造法可直接复用**：ChatGPT + 改写 prompt（保语义、改用词/句式）。
- **错误分析提示**：论文/摘要天然高度规范化，判别信号本身就弱，检测难度是内生的、不是实现缺陷。

---

## 六、归纳

1. **主线正确**：两篇综述（Crothers、Fraser）+ 汇编三重确认「微调 RoBERTa 分类器」是当前 SOTA 与商用主流；继续在 `hfl/chinese-roberta-wwm-ext` 上做微调无偏差。

2. **真正短板在「改写/润色/人机混合」端，而非直接生成**：论文 AIGC 的典型场景（AI 生成后人工改写、人写好让 AI 润色、或人机混合）落在 Fraser §5.5 与 Chen 共同点名的「最难检测」区间 —— GPT-polished 甚至让 GPTZero/ZeroGPT/OpenAI 检测器差于随机。这是论文检测区别于通用检测的核心难点。

3. **按优先级可落地的三条借鉴**：
   - **（高）Chen 特征融合**：语义 + CNN 多尺度 + 表层/文体特征在特征层融合，显著提升改写鲁棒性（HAGTC 改写集 acc 87.64%）。
   - **（高）Fraser 集成 + 低假阳校准**：统计阈值法校准到极低假阳，与通用微调分类器组合；论文场景误伤真论文代价高。
   - **（中）改写/paraphrase/mixcase 样本纳入训练**：Fraser 明确「训练中未见 mixcase 则全部方法失效」，RADAR 见 mixcase 后约 88%；Chen 的改写集构造法可直接照抄。

4. **应警惕的坑**：
   - 非母语者高假阳（Fraser §5.2 中文作者 TOEFL 假阳近 60%）；中文论文检测尤其要注意公平性与阈值校准。
   - 长度过短（<120 词）可检测性骤降；论文检测按段落/摘要为单位需注意长度门槛。

5. **可放弃**：Katib 的传统 ML + 元启发路线（数据非学术、无改写验证）；Bammey/Guillaro 两篇图像方法（与本方向无关）。

---

## 七、下一步（可选）

- [ ] 基于结论 3 产出「改写鲁棒 + 特征融合」改造方案（含改动文件清单、改写集构造方式、超参）
- [ ] 在 `model-system-overview.html` 标记论文场景「高人工影响端」风险与对应策略（低假阳校准 + mixcase 训练数据）