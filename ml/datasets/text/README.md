# ml/datasets/text/

**数据本身不入 git**（体积 + 隐私 + 许可）。本目录只放脚本与说明；产物在 `data/`（.gitignore）。

## JSONL schema（`schema.py`）

```json
{"text": "...", "label": 1, "scenario": "academic_master", "source": "gpt",
 "augment": "paraphrase_strong", "origin": "hc3", "doc_id": "hc3-open_qa-000123-a", "split": "train"}
```

| 字段 | 说明 |
|---|---|
| `text` | 段落文本，`120 ≤ len ≤ 1600` 字（Fraser §5.3 长度门槛；上限对齐 backend 切分） |
| `label` | 0 = 人类，1 = AI（**改写 / 润色 / 混写后的文本仍为 1**） |
| `scenario` | 6 场景之一，对齐 C 端 `detect_scenario_threshold` |
| `source` | 生成器家族：human / gpt / claude / qwen / deepseek / glm / kimi / ernie / other（溯源头类别） |
| `augment` | none / paraphrase_weak / paraphrase_mid / paraphrase_strong / polished / mixcase |
| `origin` | 原始数据集：hc3 / csl / m4 / cheat / custom |
| `doc_id` | 同一原文及其全部派生共享；**split 按 doc_id 哈希划分**，杜绝改写样本跨 split 泄漏 |
| `split` | train / val / test / short / held_out / eval_* |

## 构建流程

```bash
# 1. 公开集 → train/val/test（qwen / deepseek 留作未见生成器）
python -m ml.datasets.text.build_dataset --sources hc3,csl,m4 --out ml/datasets/text/data --held-out-sources qwen,deepseek
# 2. 增强（LLM 引擎；无 API 时 --engine rule 只产 weak 档）
python -m ml.datasets.text.paraphrase_augment --mode paraphrase --in data/train.jsonl --out data/augment/paraphrase_train.jsonl --n 6000
python -m ml.datasets.text.paraphrase_augment --mode polish     --in data/train.jsonl --out data/augment/polish_train.jsonl     --n 4000
python -m ml.datasets.text.paraphrase_augment --mode mixcase    --in data/train.jsonl --out data/augment/mixcase_train.jsonl    --n 2000
#    test 也各产一份，供 adversarial / polished / mixed 评测集
python -m ml.datasets.text.paraphrase_augment --merge ml/datasets/text/data
# 3. 六套评测集
python -m ml.datasets.text.build_evalsets --data ml/datasets/text/data
```

## 数据源与许可（对齐 `docs/design/DATASETS.md` §5）

| 源 | 内容 | 许可 | 用途 |
|---|---|---|---|
| HC3-Chinese | 问答 human / ChatGPT 对 | CC-BY-SA | 训练 |
| CSL | 中文学术摘要（human） | Apache 2.0 | 训练 human 端 + 润色 / 混写原文 |
| M4 中文子集 | 多生成器 | Apache 2.0 | 训练 + 溯源 |
| CHEAT | ChatGPT 学术摘要（含 polish / fusion 子集） | 研究用 | **默认只进 test**（`--cheat-into-train` 需商业授权） |
| 自建 `raw/custom/*.jsonl` | 6 场景 × 多家 LLM | 自建 | 训练（真场景标签只能来自这里） |

人写语料红线：2020 年前或人工核验；PII（手机 / 邮箱 / 身份证 / 学号）在 `build_dataset.clean_text` 里统一打码。

## 场景标签的诚实说明

公开集只有粗 domain，`build_dataset.map_scenario` 做的是**弱映射**（HC3 医学问答 → academic_bachelor 之类）。
`scenario_mix` 均衡采样在这批数据上只能防"某一 domain 淹没"，真正的 6 场景分布要靠自建数据补齐；
`build_dataset` 会对不足 500 条的场景打 warning。

## 表层特征基线（`build_surface_baseline.py`）

cls_only checkpoint 没有 `surface_scaler`，助手解释「为什么像 AI」拿不到 z-score。用人类正文拟合一份外置基线：

```bash
python -m ml.datasets.text.build_surface_baseline \
    --input ml/datasets/text/data/train.jsonl \
    --output deploy/inference-python/assets/surface_baseline_zh_thesis.json \
    --scenarios academic_bachelor academic_master academic_phd
```

推理服务设 `TEXT_SURFACE_BASELINE_PATH` 指向该文件即可生效；fusion checkpoint 上线后以其自带 scaler 为准，此文件自动退居次选。

## 真实论文基线（`ingest_thesis.py`）

公开集里没有一篇完整真论文，评测出的「学术假阳率」没有说服力。把真实学位论文解析成人类负样本，先给现有模型出一个基线数字：**规范学术写作被判 AI 的比例**。

**准备**：论文放 `ml/datasets/text/raw/thesis/`（pdf / docx / txt，不入 git），建议附 `manifest.csv`：

```csv
file,scenario,year,names
zhang_2021.pdf,academic_master,2021,张三;李四
wang_2019.docx,academic_phd,2019,
```

- `year` 必须 ≤ 2022（ChatGPT 之前才算纯人类样本，`--max-year` 之后的会被跳过）
- `names` 是要打码的作者 / 导师姓名；手机 / 邮箱 / 身份证 / 学号由 `clean_text` 统一打码；封面、声明、授权书、目录、参考文献、致谢整段丢弃
- 解析依赖：`pip install pymupdf python-docx`（没有 pymupdf 时退到 pypdf）

**跑基线**：

```bash
# 1. 解析 → eval_real_thesis.jsonl（全部 label=0，带 meta.section / file）
python -m ml.datasets.text.ingest_thesis --in ml/datasets/text/raw/thesis --manifest ml/datasets/text/raw/thesis/manifest.csv     --out ml/datasets/text/data/evalsets/eval_real_thesis.jsonl
# 2. 现有 legacy 模型跑一遍，看 fpr / by_section / per_doc / top_false_positives
python -m ml.evaluation.text.eval --checkpoint models/text/aigc_detector_v3_thesis.pth --base-model models/text/chinese-roberta-wwm-ext     --set real_thesis=ml/datasets/text/data/evalsets/eval_real_thesis.jsonl --threshold-key default_0_5 --out ml/datasets/text/data/evalsets/baseline-real-thesis.json
```

报告里看四个数：整体 `fpr`、`by_section`（摘要 / 引言 / 方法 / 结论哪一章最容易被冤枉）、`per_doc`（中位数、p90、超过 20% 的篇数、最差 10 篇）、`top_false_positives`（被判最像 AI 的 15 段原文，人工复看）。验收线 `fpr ≤ 0.05`，基线阶段只记数字不拦截。

同一批论文加 `--as-train` 可产出训练用人类样本到 `raw/custom/`，由 `build_dataset --sources custom` 按 doc_id 划分；评测用的那批要和训练用的分开，不能同一篇既训又评。

## 评测集（`data/evalsets/`）

| 文件 | 构成 | 盯什么 |
|---|---|---|
| eval_in_domain | test 里 augment=none | 基础精度 · AUROC ≥ 0.98 |
| eval_cross_generator | held_out（未见生成器 AI）+ 等量 human | 跨生成器泛化 · F1 ≥ 0.85 |
| eval_adversarial | test 里 paraphrase_mid/strong + human | 改写鲁棒 · F1 ≥ 0.70 |
| eval_polished | test 里 polished + human | Fraser「差于随机」区间 · F1 ≥ 0.60 |
| eval_mixed | test 里 mixcase + polished + human | 人机混写 · F1 ≥ 0.60 |
| eval_short_text | 50–119 字 | 短文本下限 · AUROC ≥ 0.85 |
| eval_real_thesis | 真实论文正文段（全 human） | 学术假阳 · FPR ≤ 0.05，按章节 / 按篇细分 |
