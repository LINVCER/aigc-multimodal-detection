# 数据集构建方案（文本态 · v1）

> 2026-10 · 与 `docs/reports/dataset-summary/` 论文汇总报告配套。
> 已按仓库真实状态核对（文本态为主、6 场景、9 溯源家族、统一 JSONL schema、本机零数据、v0.2.0-fusion 从未首跑）。
> 不改 `schema.py`、不改训练入口，只补数据 + 新增三个脚本。

## 1. 目标

8 周交付可跑通 `v0.2.0-fusion-mdeberta` 的训练集 + 评测集，验收线直接沿用 `ml/evaluation/text/eval.py` 现有阈值（§4）。

## 2. 四层数据结构（全部落 `schema.py` 字段）

| 层 | 内容 | 规模 | 来源 / 做法 |
|---|---|---|---|
| L0 人类锚点 | 真实论文正文段 | 30K 段（≈3K 篇） | `ingest_thesis.py` 已有；年份 ≤2022-01 截断；按 6 场景分层 本科40/硕士30/博士10/职业10/自媒体5/其他5 |
| L1 公开底座 | HC3-Chinese / CSL / M4-zh | 现成约 60K | **已内置 `build_dataset.py`**（HF `neuclir/csl` 等直接拉）；CHEAT 只进 test |
| L2 自建生成 | 论文域 AI 文本 | 100K | 以 L0 + CSL 标题/首段为种子，6~8 家国产 LLM 生成；qwen/deepseek 各留 held-out |
| L3 增强 | 改写 / 润色 / 混写 / 对抗 | 50K | `paraphrase_augment.py` 已有三模式；20% 样本递归 1~3 轮改写 |

- **溯源**：9 家族 = `human` + 8 生成器（gpt/claude/qwen/deepseek/glm/kimi/ernie/other）。human 来自 L0/L1，8 生成器来自 L2，保证每类 ≥3K。
- 增强值用全名：`paraphrase_weak/mid/strong`、`polished`、`mixcase`。

## 3. 构建流程（对应现有脚本）

1. **人类语料**：`ingest_thesis.py`，manifest 带 scenario/year；PII 走 `clean_text` 打码。
2. **公开集**：`build_dataset.py --sources hc3,csl,m4`（CSL 已内置，无需单独下载脚本）；CHEAT 走 `--sources cheat`。
3. **生成**（新脚本 `generate_thesis_domain.py`）：读种子 → 角色化 prompt（「你是该方向硕士生，写一段 300~600 字引言…」，禁抄种子原文、控长度）→ 多模型并发 → 写 JSONL（origin=custom、source=家族、doc_id 继承种子）。
4. **增强**：`paraphrase_augment --mode paraphrase|polish|mixcase` 跑 L1+L2。
   - 注意：现成 `mixcase` 是**随机 30~60% 句替换**（非 1:1）；要句级 1:1 需改脚本，否则沿用 30~60%。
5. **质控**（新脚本 `qc_dataset.py`）：MinHash 去重（阈 0.8）→ 长度 120~1600 字过滤 → Sentence-BERT 与种子相似度 0.4~0.85（太低偏题、太高抄袭）→ PPL 离群剔除 → 每家族抽检报告。
6. **切分**：`build_dataset --held-out-sources qwen,deepseek`，按 doc_id 哈希 8:1:1（`_split_of`，同原文及改写派生必同 split）；再跑 `build_evalsets` + `build_appeal_evalset` + `ingest_thesis` 产评测集（§4）。

## 4. 评测集与验收线（以 `eval.py` ACCEPTANCE 为准，共 8 套）

| 评测集 | 产出脚本 | 验收阈值 |
|---|---|---|
| eval_in_domain | build_evalsets | AUROC ≥ 0.98 · ECE ≤ 0.05 · source_top1 ≥ 0.70 |
| eval_cross_generator | build_evalsets（需 held-out） | F1 ≥ 0.85 |
| eval_adversarial | build_evalsets | F1 ≥ 0.70 |
| eval_polished | build_evalsets | F1 ≥ 0.60 |
| eval_mixed | build_evalsets | F1 ≥ 0.60 |
| eval_short_text | build_evalsets | AUROC ≥ 0.85 |
| eval_appeal | **build_appeal_evalset**（单独脚本） | FPR ≤ 0.10 · 只评不训 |
| eval_real_thesis | **ingest_thesis** | FPR ≤ 0.05 |

> 更正点：`build_evalsets` 产 **6 套**，eval_appeal 与 eval_real_thesis 各由单独脚本产，合计 8 套（原「7 套、第七套 eval_appeal」有误）。

## 5. 配比

- 训练集 label 0:1 = 1:1（人类 L0+L1 约 90K，AI 从 L2+L3 下采样到同量）。
- 6 场景按红线反比加权：博士/硕士（阈值最严）多给样本。
- 跨生成器评测只用 held-out 的 qwen/deepseek，训练集一条不见。
- 申诉回流维持「只评不训」（建议 v1 阶段，等溯源头跑通再议）。

## 6. 要新写的代码（3 个，复用现有断点续跑框架）

1. `generate_thesis_domain.py`：种子 → 角色化 prompt → 多模型并发 → JSONL。
2. `qc_dataset.py`：去重 / 相似度 / PPL / 抽检报告。
3. `download_datasets.py`：批量预拉 + 缓存（CSL 已在 build_dataset，此脚本主做 CHEAT 原始档与缓存，非必须但便于复现）。

DVC → MinIO 的数据版本配置一并落地，否则 100K+ 数据不入 git 无法追溯。

## 7. 里程碑

| 周 | 内容 |
|---|---|
| W1–2 | L0 真实论文入库（≥3K 篇）+ L1 公开集；产第一版 eval_real_thesis |
| W3–5 | `generate_thesis_domain.py` 跑 L2 100K，边生成边过 `qc_dataset.py`，每家族抽检 300 条 |
| W6 | L3 增强 50K（递归对抗 + 混写） |
| W7 | `build_dataset` 切分 + 8 套评测集；`v0.2.0-fusion-mdeberta` 首跑，`eval.py` 出 PASS/FAIL |
| W8 | 按失败项回补数据，DVC 打 tag |

## 8. 待拍板

| 决策 | 要点 | 建议 |
|---|---|---|
| 一 · 生成预算 | 100K×500 字≈5000 万 token，国产 API 约 ¥300~800，含对抗翻倍，控在 ¥2000 内 | 确认走哪几家 API |
| 二 · 真实论文来源 | 3K 篇从哪来，是 FPR 指标根基 | 无它「真论文 FPR ≤0.05」无法验，优先解决 |
| 三 · gpt/claude 溯源 | 两家国内调用有障碍 | v1 先降级或标 N/A，溯源头跑通再补 |
| 四 · 申诉回流 | 只评不训 vs 到量后进训 | v1 维持只评不训 |
