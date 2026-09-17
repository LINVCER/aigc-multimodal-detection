# DATASETS · 训练与评测数据集清单

> 面向企业级论文 AIGC 检测平台。分**立即拉 / 补充覆盖 / 自建**三档，附下载命令、许可标注、用途分工。
> 关联文档：[MODEL_UPGRADE_PLAN.md](MODEL_UPGRADE_PLAN.md) §2 数据方案 · [MODEL_RESEARCH_TEXT.md](MODEL_RESEARCH_TEXT.md) §6 中文数据源

---

## 0. 用法总览

- **数据一律 DVC track**，不入 git。约定放到 `training/data/{name}/`，`dvc add` 后 push 到 MinIO/OSS
- **训练用 vs 评测用严格分开**：立即拉里 1/2/3/4 用于训练，第 5 项（C-ReD）**只做测试集不入训练**（防污染）
- **许可红线**：产品训练数据只允许 **Apache / MIT / CC-BY** 系；研究许可集只在内部 evals 用，不进商用 checkpoint
- **人写语料防污染红线**：所有 human 端样本必须来自 2020 年以前发表内容，或人工核验；2023 年后的中文互联网语料已被 AI 大量污染，直接用会标签噪声

---

## 1. 一档 · 立即拉（Phase 1 训练必备）

| # | 数据集 | 规模 | 语言/域 | 用途 | 许可 |
|---|---|---|---|---|---|
| 1 | **HC3-Chinese** | 24.3K 对 | 中文，金融/医疗/百科/开放问答/reddit-eli5 | 主分类 baseline | CC-BY-SA 4.0 |
| 2 | **CHEAT** | 35K | **中文学术论文摘要**，ChatGPT 生成 vs 真人 | **教育路径主推** | 研究用（商用需申请） |
| 3 | **M4** | 122K 含中文子集 | 多域，8 家 LLM | **溯源头训练** | Apache 2.0 |
| 4 | **MAGE** | 400K | 多域，27 家 LLM | 溯源跨代泛化 | 研究用 |
| 5 | **C-ReD**（2026） | — | 中文真实 prompt | **evals 主基准（非训练）** | 见 paper |

### 1.1 一键拉取脚本

已有 `training/scripts/download_datasets.py` 支持 HC3 + M4，另外扩展：

```bash
# 起环境
bash training/setup_env.sh
cd training

# HC3-Chinese（约 24K 条，跑一次几分钟）
python scripts/download_datasets.py --only hc3

# M4（限中文子集流式抓 10 万条）
python scripts/download_datasets.py --only m4

# CHEAT（需邮件申请后手动放盘）
# 1. 邮件申请: https://github.com/botianzhe/CHEAT
# 2. 拿到 tar 后:
mkdir -p data/cheat && tar -xzf ~/downloads/CHEAT.tar.gz -C data/cheat

# MAGE（需邮件申请）
# https://github.com/yafuly/MAGE

# C-ReD（跟论文发布节奏，2026 后期公开）
# arxiv 2604.11796
```

### 1.2 DVC 登记

```bash
cd training
dvc add data/hc3-chinese data/m4 data/cheat data/mage
dvc push                                          # 推到 MinIO / OSS
git add data/*.dvc .gitignore && git commit -m "data(dvc): register base training sets"
```

**首版训练组合**（Phase 1 里程碑）：`HC3-Chinese + CHEAT + M4 中文子集 = 约 15 万条`，跑 mDeBERTa-v3-base 4 epoch 单 A100 40GB 6-10 小时即可拿第一份数字。

---

## 2. 二档 · 补充覆盖（Phase 2 增量）

| # | 数据集 | 补什么 | 拉取 |
|---|---|---|---|
| 6 | **MAGA-Bench**（2026） | 人机混写检测集 | arxiv 2601.04633 |
| 7 | **HC3-Plus** | 改写后仍要判 AI | `Hello-SimpleAI/HC3-Plus`（HF） |
| 8 | **DetectRL / DetectRL-X** | 真实世界综合基准 | arxiv 2410.23746 / 2605.15518 |
| 9 | **MULTITuDE** | 74K 新闻多语言（含中文），11 家 LLM | `MulTALIN/MULTITuDE`（HF） |
| 10 | **HACo-Det** | 句子级人机共写细粒度 | arxiv 2506.02959 |
| 11 | **CCL2024 CTG-AI / NLPCC 2024 AIGC** | 中文最新竞赛集 | cips-cl.org / tcci.ccf.org.cn |
| 12 | **CSL 中文学术摘要** | 降 AIGC pairs 的 human 端；防污染语料 | `neuclir/csl`（HF） |

**分工**：6/10 → 句子级检测评测 · 7/8/9 → 主分类泛化补充 · 11 → 最新中文 LLM 覆盖 · 12 → 降 AIGC 训练 human 端

---

## 3. 三档 · 自建（Phase 1-2 关键投资）

### 3.1 论文域全生成器覆盖（约 100K）

**pipeline**：CSL / 教材段落 → 6-8 家中文 LLM 各生成 5-10K 条 → (AI 版, human 版) 平衡

```
生成器清单（3-5K 条/家，Qwen 系加倍到 20K，因为最难检测）:
  Qwen 2.5-Max / Qwen 3
  DeepSeek V3 / R1
  GLM-4.5
  Kimi K1.5
  文心 4.5
  Baichuan 3
  (国际) GPT-4o / Claude 4 / Gemini 2.0

场景 × 每家（各 500-1000 条）:
  论文摘要 · 引言 · 方法 · 讨论 · 结论

human 端不新生成，直接用:
  CSL 摘要
  2020 年前博客与论坛
  教材段落
```

**关键提醒**：**Qwen 系样本占比 20% 而非 1/8 均分**，依据是 DetectRL-X 实证「Qwen 是最难检测的生成器」。

**成本估算**：LLM API 调用总量约 100K prompts × 平均 500 tokens 输出 ≈ 5000 万 tokens，按 DeepSeek 定价约 200-500 元人民币，Qwen/GLM 定价相当。

### 3.2 降 AIGC 训练对（约 20-50K）

Warm start 借 HF 现成模型：

```bash
# 起个 vLLM 直接推
vllm serve arunsingh80475/qwen2.5-14b-humanizer-v3-lora \
  --served-model-name humanizer-warm --gpu-memory-utilization 0.9
```

自建配方：

```
CSL 摘要（human 原版）→ LLM 改写成 AI 风格 →
  (AI 版, human 原版) 有监督对
+ 双向 rejected data（防口语化漂移）:
  - 2K 条 "过于正式"的改写作为 rejected
  - 2K 条 "过于口语化"的改写作为 rejected
```

### 3.3 对抗改写（30K，Phase 2）

```
从主训练集抽 5-10% AI 样本 →
  用 GLM-4 / Qwen 2.5-7B 三档改写作 augment:
    - 弱: 同义词替换
    - 中: 句子级重组
    - 强: 提示 "改写以避开 AI 检测器"
标签保持 AI=1（这是关键：告诉检测器"改写了也是 AI"）
```

---

## 4. 图像 / 篡改（辅线，Phase 2+）

| # | 数据集 | 用途 |
|---|---|---|
| 13 | **GenImage**（2.7M） | 插图 AI 检测主训练 |
| 14 | **GenImage++** | test-only，含 Flux.1 / SD3 |
| 15 | **AI-GenBench** | 按新生成器时间轴增量 evals |
| 16 | **ForensicHub** | 篡改定位统一 benchmark + 合成工具 |
| 17 | **CASIA v2 / Coverage / Columbia** | 传统篡改集，baseline |
| 18 | 学术特化（PMC 抓 + 自建） | western blot / 显微图，对标 ImageTwin/Proofig |

---

## 5. 商用许可核对表

| 数据集 | 商用许可 | 处理 |
|---|---|---|
| HC3-Chinese | ✅ CC-BY-SA（需署名） | 直接用 |
| HC3-Plus | ✅ CC-BY-SA | 直接用 |
| M4 | ✅ Apache 2.0 | 直接用 |
| MULTITuDE | ✅ CC-BY | 直接用 |
| CSL | ✅ Apache 2.0 | 直接用 |
| CHEAT | ⚠️ 研究用 | evals 内部用，或邮件申请商业授权 |
| MAGE | ⚠️ 研究用 | 同上 |
| GenImage / GenImage++ | ⚠️ 研究用 | 图像模型 evals 用 |
| DetectRL / DetectRL-X | ⚠️ 研究用 | evals 用 |
| MAGA-Bench / HACo-Det / C-ReD | 待确认 | 论文/仓库 license 逐一确认 |
| 竞赛集 CCL / NLPCC | 视规则 | 赛后条款单独确认 |

**建议**：产品训练 checkpoint 只用 ✅ 的四家 + 自建 → 上线合规无风险；⚠️ 的用作内部 evals 与 spot 验证，不进模型权重。

---

## 6. 进度检查（对照 MODEL_UPGRADE_PLAN Phase 1 验收）

- [ ] HC3-Chinese 已入 DVC
- [ ] CHEAT 已入 DVC（需邮件申请）
- [ ] M4 中文子集已入 DVC
- [ ] CSL 已入 DVC
- [ ] 自建 100K 论文域样本已生成 + DVC
- [ ] 6 套 evals 测试集分离建成（in-domain / cross-generator / adversarial / short-text / mixed / image）
- [ ] 首版 mDeBERTa-v3-base 训练完成，MLflow 有可复现的 val_acc / val_f1 / ECE 记录
- [ ] Cross-generator 未见 3 家的 F1 达到 ≥ 0.85 门槛
