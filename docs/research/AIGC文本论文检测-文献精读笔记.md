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

- [x] 基于结论 3 产出「改写鲁棒 + 特征融合」改造方案 → `docs/design/202609-text-detector-training-pipeline.md`（2026-09-21 已落地为 `ml/` 训练链路）
- [ ] 在 `model-system-overview.html` 标记论文场景「高人工影响端」风险与对应策略（低假阳校准 + mixcase 训练数据）

---

## 八、2026 年新增文献补充（2026-09-21 检索）

> 检索范围：arXiv 2025-09 → 2026-09，聚焦「改写 / 润色 / 混写」「细粒度定位」「特征与表示」「假阳与公平性」「零样本」五个与论文检测直接相关的方向。
> 与 `MODEL_RESEARCH_TEXT.md` v2 增补（C-ReD / MAGA-Bench / DeBERTa-Sentinel / DetectRL-X / HACo-Det / 2509.17830 / GPTZero / DAMAGE …）不重复，只收新出现或此前未深读的。
> 每篇末尾「→」给出对本项目训练链路的具体影响。

### 8.1 改写 / 润色 / 混写（论文检测最难区间）

**ARB: A Matched Authorship-Rewriting Benchmark**（arXiv 2607.29539，2026-07，CC-BY-4.0）

- 同一原文四个匹配变体：人写原文 / LLM 直接生成 / **人写被 LLM 改写** / LLM 文本被同模型改写；1,800 源文本 × 4 生成器（Llama-3.2-3B / Qwen2.5-7B / Mistral-7B / Gemma-2-9B）
- @1% FPR：直接生成 recall 91-94%；**人写被 LLM 改写后 recall 掉到 15-31%（−60~78 点）**；LLM 文本被改写只掉 10-13 点；BERT / RoBERTa 防御式检测器全程 <3%
- → 我们的 `polished` 样本正是「人写被 LLM 改写」这一最惨格。印证 polished 必须单独成评测集且入训；数据可商用，可直接作英文外部 evalset 对照。

**OpAI-Bench: Operation-Guided Progressive Human-to-AI Text Transformation**（arXiv 2606.06481，2026-06）

- 从人写文档出发，按 5 种 AI 编辑操作 × 预设 AI 覆盖比例，逐步生成 9 个修订版本并记录 provenance；评测 8 文档级 + 7 句级 + 2 token 级检测器
- 核心发现：可检测性**非单调** —— 中间混写版本常比「全人写」和「重度 AI 编辑」两端都难检测；操作类型、领域、修订历史都影响
- → 评测集不能只有一档 mixcase，要按 AI 覆盖比例分档（我们 `paraphrase_augment --mode mixcase` 已在 meta 记 `ai_sentence_idx`，建 evalset 时按比例分桶即可）。

**Pangram 4 Technical Report**（arXiv 2607.27183，2026-07）

- 工业 SOTA 报告：AUROC 0.9916、FPR 0.0041%、FNR 0.34%；主打混写与细粒度 span 定位、对 humanizer 攻击的鲁棒；方法未公开
- → 对标数字。它证明「极低 FPR + 混写 + span」三者可同时达到，是我们 Phase 2 的产品目标线。

**Almost AI, Almost Human: The Challenge of Detecting AI-Polished Writing**（arXiv 2502.15666，2025-02）

- 轻度润色的人写文本 FPR 极高，现有检测器无法区分「人写 + AI 微调」与「全 AI」
- → 与 Fraser §5.5 同一结论；polished 评测集验收线（F1 ≥ 0.60）设得保守是有依据的。

### 8.2 细粒度 / 句子级 / token 级定位

**Detecting LLM-Generated Tokens in Human–LLM Coauthored Text**（arXiv 2607.21458，2026-07）

- token 级检测分数 + 相邻平滑 + **Lepski 型自适应带宽**按局部 authorship 结构选窗；**不需要 token 级标注**
- → Phase 2 句子级方案多了一条免标注路径：用 fusion 模型逐句 / 逐窗打分后做自适应平滑，比 2509.17830 的 CRF 少一套标注成本。

**Segmenting Human–LLM Co-authored Text via Change Point Detection**（arXiv 2605.03723，2026-05）

- 把 authorship 分段建模为时间序列变点检测，给出加权 / 广义两种算法与 minimax 最优性证明，开源
- → 与上一篇互补：先有句级分数序列，再做变点检测得到边界。两者都可直接消费我们推理侧 `return_sentences=true` 的句级校准概率。

**Beyond the Final Actor: Modeling the Dual Roles of Creator and Editor**（arXiv 2604.04932，2026-04）

- 把细粒度检测拆成「谁创作 / 谁编辑」双角色，而非单一 authorship 标签
- → 与 OpAI-Bench 的 provenance 思路一致；我们 schema 里 `augment` + `source` 已经能表达「人写 / gpt 润色」这种双角色，未来扩三分类时不用改 schema。

### 8.3 特征与表示层

**FAID: Fine-Grained AI-Generated Text Detection Using Multi-Task Auxiliary and Multi-Level Contrastive Learning**（arXiv 2505.14271，2025-05）

- 三分类（human / LLM / **human-LLM 协作**）+ LLM 家族辅助头 + 多级对比学习；FAIDSet 多语多域多生成器；对 unseen 域 / 新 LLM 泛化好，且有无需重训的分布偏移适应
- → 直接印证本链路的「溯源辅助头 + SupCon」设计。建议 v0.2.x 把主任务从二分类扩为三分类（human / ai / collaborative），`augment ∈ {polished, mixcase}` 即 collaborative 标签，schema 不用动。

**Diversity Boosts AI-Generated Text Detection（DivEye）**（arXiv 2509.18880，TMLR 2026）

- 用 **surprisal 的波动**（词汇 / 结构不可预测性随文本的起伏，即「节奏不可预测性」）作可解释特征；单独用超零样本检测器最多 +33.2%，叠加已有检测器最多 +18.7%；对改写与对抗攻击鲁棒
- → 我们 30 维表层特征（`sf-v1`）里的句长 CV / 标点间隔 CV / 熵是同一思想的无 LM 版本；`sf-v2` 可加 6 维 surprisal 序列统计（均值 / 方差 / 峰度 / 自相关…），代价是推理时多一个小 LM 打分。

**Amplifying, Not Learning: Fine-Tuned AI Text Detectors Amplify a Pretrained Direction**（arXiv 2605.21653，2026-05，2026-08 修订）★

- 主张：微调检测器并没有学到新的「AI vs 人」边界，只是**放大预训练 LM 里已有的「可预测性」轴**
- 证据：检测器把 **99.5% 的正式人类作文判为 AI**，却放过 10.5% 的高温采样 AI 文本；分解后可迁移（跨生成器）的成分完全来自预训练继承，微调残差是生成器特定、不迁移的；**冻结表示 + 每类 25 条标签的探针在未见生成器上 AUROC 0.893，反超全微调的 0.831**
- 「no-go 定理」：能跨生成器迁移的那根轴，就是误伤正式人类文本的那根轴；训练目标、阈值、概念擦除、集成都无法在保留检测力的同时去掉这个伤害
- → 三点直接影响：（1）**学术论文假阳是结构性的**，不是校准问题，产品必须给置信区间 + 阈值 + 人工复核入口而不是单一分数；（2）fusion 加非 LM 支路（表层特征）是少数能引入「第二根轴」的手段，但作者认为特征选择本身也不够 —— 需要在 held-out 生成器上实测 fusion vs cls_only 的 AUROC 差才有结论；（3）**少解冻 + 强正则可能比全微调更泛化**，支持配置里 `unfreeze_layers` 取保守值，并建议加一组「backbone 全冻结 + 探针」对照实验。

### 8.4 假阳与公平性（中文论文场景同构）

**Style as a Confound: False Positives in AI Detection of Non-Native Academic Writing**（arXiv 2608.26710，EMNLP 2026）★

- 135,389 篇非母语学术稿件与其母语编辑版配对（2018-2025 专业润色服务）；13 个检测器 **FPR 从 0% 到 100%**；同一处编辑在不同检测器上把 AI 分数推向相反方向，变化幅度与编辑量正相关
- 结论：「专业编辑风格」是 authorship 之外的强混淆变量
- → 中文论文场景是同一个问题的镜像：规范化、低情绪波动的学术文体天然像 AI（Chen §5.5 错误分析也这么说）。落地：（1）评测集加「同一稿件编辑前 / 后」配对，专门看 FPR 漂移；（2）`academic_*` 场景用 `fpr_1pct` 阈值；（3）报告展示区间而非点值。

**AI Detectors Fail Diverse Student Populations: A Mathematical Framing of Structural Detection Limits**（arXiv 2603.20254，2026-03）

- 给出检测器在多样化学生群体上的结构性误差下界，结论「不适合作 authorship 的权威裁判」
- → 产品定位措辞：检测结果是「疑似标记 + 人工复核」，不是判定。

**Why AI-Generated Text Detection Fails: Evidence from Explainable AI Beyond Benchmark Accuracy**（arXiv 2603.23146，2026-03）

- SHAP 解释 30 个语言学特征，PAN CLEF 2025 / COLING 2025 两个基准；检测器依赖**数据集特有的风格线索**（格式、长度）而非稳定的机器 authorship 信号；域内 F1 0.9734 在分布偏移下显著退化；开源了带实例级解释的 Python 包
- → 我们 30 维表层特征训完必须做一次 SHAP / permutation importance，把只在 HC3 问答体上有效的特征（如某些标点比例）从 `sf-v2` 里剔除或降权；`eval.py` 分 origin 报告 F1 可以先暴露这类偏差。

### 8.5 零样本 / 白盒

**Luminol-AIDetect: Fast Zero-shot Detection based on Perplexity under Text Shuffling**（arXiv 2604.25860，2026-04）

- 测量文本随机打乱后困惑度的变化：AI 文本在打乱下表现出特征性的不稳定；8 领域 / 11 种对抗攻击 / **18 种语言（含中文）**；FPR 最多降 17×，且比 Fast-DetectGPT / Binoculars 便宜
- → Phase 2 白盒双检（MODEL_UPGRADE_PLAN M3）里，Luminol 有中文实证，优先级应高于无中文 paper 支撑的 Binoculars。

### 8.6 基准与评测平台（补充）

- **MGTEVAL**（arXiv 2604.25152，2026-04）：机器生成文本检测器的交互式系统评测平台 → 可作为我们六套评测之外的第三方复核。
- **Detecting AI-Generated Content in Academic Peer Reviews**（arXiv 2602.00319，2026-02）：2025 年约 20% ICLR 审稿、12% Nature Communications 审稿被判为 AI 生成 → 说明「学术文本 AI 化」已是基线现象，训练集的 human 端更要严守 2020 年前红线。
- **Efficient detection of AI-generated scientific abstracts with a lightweight transformer**（Sci Rep 2026, s41598-026-35203-3）：5,000 arXiv 摘要 + Gemini 2.0 Flash 生成对，域内 99.4% / 跨域 Macro-F1 0.948 → 单一生成器、单一域的高分不可信（对照 8.4 的 XAI 结论）。
- **Detector-Evasive LLM Paraphrasing via Constrained Policy Optimization**（arXiv 2606.00392，2026-06）：用约束策略优化训练规避检测的改写器 → 对抗评测集应加入这类「优化过的」改写样本，而不只是 prompt 改写。

### 8.7 对本项目训练链路的修正清单

| 优先级 | 动作 | 依据 | 状态 |
|---|---|---|---|
| 高 | polished / mixcase 入训 + 单独评测 | ARB · OpAI-Bench · Fraser | ✅ v0.2.0 已落地 |
| 高 | 评测集按 AI 覆盖比例分档（mixcase 非单调） | OpAI-Bench | 待做：`build_evalsets` 按 `meta.ai_sentence_idx` 比例分桶 |
| 高 | 评测集加「编辑前 / 后」配对看 FPR 漂移；`academic_*` 用 `fpr_1pct` | Style as a Confound | 待做：数据 + backend 场景阈值接线 |
| 高 | 产品报告给置信区间 + 阈值 + 人工复核，不给单一分数 | Amplifying no-go · 2603.20254 | 待做：前端 / 报告 |
| 中 | 主任务扩三分类 human / ai / collaborative | FAID | 待做：v0.2.x，schema 不动 |
| 中 | `sf-v2` 加 surprisal 波动 6 维 | DivEye | 待做：需小 LM 打分 |
| 中 | 训完做 SHAP，剔除数据集特有特征 | Why Detection Fails | 待做：`eval.py` 分 origin 已能暴露 |
| 中 | 加「backbone 全冻结 + 探针」对照，在 held-out 生成器上比 AUROC | Amplifying | 待做：一份 yaml（`unfreeze_layers: 0`） |
| 中 | Phase 2 句子级走「逐句打分 + 变点 / Lepski 平滑」免标注路径 | 2607.21458 · 2605.03723 | Phase 2 |
| 低 | 白盒双检用 Luminol 替代 Binoculars | Luminol（含中文） | Phase 2 |
| 低 | 对抗评测加策略优化改写器产物 | 2606.00392 | Phase 2 |