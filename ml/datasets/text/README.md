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

## 评测集（`data/evalsets/`）

| 文件 | 构成 | 盯什么 |
|---|---|---|
| eval_in_domain | test 里 augment=none | 基础精度 · AUROC ≥ 0.98 |
| eval_cross_generator | held_out（未见生成器 AI）+ 等量 human | 跨生成器泛化 · F1 ≥ 0.85 |
| eval_adversarial | test 里 paraphrase_mid/strong + human | 改写鲁棒 · F1 ≥ 0.70 |
| eval_polished | test 里 polished + human | Fraser「差于随机」区间 · F1 ≥ 0.60 |
| eval_mixed | test 里 mixcase + polished + human | 人机混写 · F1 ≥ 0.60 |
| eval_short_text | 50–119 字 | 短文本下限 · AUROC ≥ 0.85 |
