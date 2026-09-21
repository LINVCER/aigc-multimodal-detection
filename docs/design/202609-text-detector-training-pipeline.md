# 论文 AIGC 文本检测 · 训练链路设计（v0.2.0-fusion）

> 状态：**链路已实装，待首跑**（2026-09-21）
> 范围：`ml/`（数据构建 → 模型 → 训练 → 校准 → 评估）+ `deploy/inference-python/detectors/text.py` 推理适配
> 依据：`docs/research/AIGC文本论文检测-文献精读笔记.md`（5 篇文献）· `docs/design/MODEL_RESEARCH_TEXT.md` · `docs/design/DATASETS.md` · `docs/design/MODEL_UPGRADE_PLAN.md`
> 前身：`legacy/algorithms/train_text_detector.py`（9 项训练技巧保留；结构 / 数据 / 评估重做）

---

## 0. 一页纸结论

| 决策项 | 选择 | 依据 |
|---|---|---|
| 主线范式 | 有监督微调分类器 | Crothers 2023 §4.2 / 汇编第 3 条：RoBERTa 微调 = SOTA 且商用主流 |
| Backbone | `microsoft/mdeberta-v3-base`（主）· `chinese-roberta-wwm-ext`（对照）· `deberta-v3-large`（上限） | MODEL_RESEARCH_TEXT §2：预期 +3-8pp；DeBERTa-Sentinel 98.2% |
| 模型结构 | **`[h_cls ; h_cnn ; f]` 特征级融合** + 9 类溯源头 | **Chen 2026**：改写集 acc 87.6% vs RoBERTa 83.2%；表层规律在改写下稳定 |
| 数据关键动作 | **paraphrase×3 档 / polished / mixcase 必须入训** | **Fraser 2025 §5.5**：未见 mixcase → 全线差于随机；见过 → RADAR 88% |
| 校准 | 温度 + Platt + **低假阳阈值（FPR ≤ 1% / 5%）随 checkpoint 落盘** | Fraser §6：论文场景误伤真论文代价高 |
| 长度门槛 | 训练 / 判定 ≥ 120 字；50-119 字单独评测 | Fraser §5.3：~120 词达完整潜力 |
| 训练技巧 | Focal · R-Drop · EMA · FGM · 分层 LR · 梯度累积 · bf16 · 早停 | legacy 验证过的 9 项保留 |
| 评估 | 六套评测集分套报 AUROC / F1 / TPR@FPR=1% / ECE / Brier | MODEL_UPGRADE_PLAN §2.4 |
| 放弃 | Katib 传统 ML + 元启发；水印；LLM-as-classifier | 文献笔记 §六 5 / 调研 §1.2 |

---

## 1. 文献结论 → 设计映射

| 文献发现 | 落到哪 |
|---|---|
| Chen：`h = [h_cls ; h_cnn ; f]`，三类表层特征（结构 / 词汇 / 多样性）+ 发音代理（节奏 / 重复） | `ml/common/fusion_model.py` `FusionAIGCDetector` · `ml/common/surface_features.py` 30 维 f |
| Chen：改写集 = ChatGPT + 「保语义、改用词 / 句式 / 句法」prompt | `ml/datasets/text/paraphrase_augment.py` `PROMPTS["paraphrase_mid"]` 逐字对应；`strong` 档对应 DIPPER 目标 |
| Chen：lr 2e-5 · AdamW · batch 16 · 5 epoch · 早停 | `ml/configs/text/*.yaml` train 段 |
| Chen 错误分析：学术摘要天然规范化 → 判别信号内生弱 | 溯源头 + 场景均衡采样 + `academic_*` 场景低假阳阈值（运行时按场景选阈值） |
| Fraser §5.5：GPT-polished 最难；mixcase 不入训全线失效 | `paraphrase_augment --mode polish / mixcase`，标签 AI=1，配比 `augment_mix.polished=0.10` |
| Fraser §5.3：≥120 词；短文本可拼接 | `schema.MIN_CHARS=120`；`short.jsonl` 单独评测；backend 段落切分保证长度 |
| Fraser §5.1：nucleus 采样数据训练泛化最好 | 自建数据生成时 `temperature≈0.8, top_p≈0.95`（`paraphrase_augment` 默认 temperature 0.8） |
| Fraser §5.2：非母语 / 表达单一者高假阳 | 低假阳阈值 `fpr_1pct`；评估分场景报 FPR |
| Fraser §6：多个差异化校准指标 + 通用 LM 分类器集成 | 本轮先做单模型 + 校准；白盒零样本双检留 Phase 2（MODEL_UPGRADE_PLAN M3） |
| Crothers §4.3.1：跨域只需数百专家标注样本 | `build_dataset --sources custom` 支持小规模自建学术集直接并入 |
| DetectRL-X：Qwen 生成最难检测 | 自建数据 Qwen 占比 20%（DATASETS.md §3.1）；同时作为 cross-generator 未见组之一验证泛化 |

---

## 2. 数据集构建

### 2.1 统一 schema（`ml/datasets/text/schema.py`）

```json
{"text": "...", "label": 1, "scenario": "academic_master", "source": "gpt",
 "augment": "paraphrase_strong", "origin": "hc3", "doc_id": "hc3-open_qa-000123-a", "split": "train"}
```

- `label`：0 人类 / 1 AI，**改写 / 润色 / 混写后仍为 1**（DATASETS.md §3.3「改写了也是 AI」）
- `source`：9 类家族（human / gpt / claude / qwen / deepseek / glm / kimi / ernie / other），`normalize_source()` 归一，与推理 `/api/v1/attribute` 类别一致
- `augment`：none / paraphrase_weak / paraphrase_mid / paraphrase_strong / polished / mixcase
- `doc_id`：同一原文及全部派生共享；**split 按 doc_id 哈希**，改写样本不可能跨 split 泄漏

### 2.2 来源与流程（`build_dataset.py`）

```
HC3-Chinese ─┐
CSL 摘要     ├─ 收集 → clean_text（去 HTML/URL · PII 打码：手机/邮箱/身份证/学号）
M4 中文      │        → 句边界截断 ≤1600 字 → 精确去重（content_hash）→ 近似去重（前 160 字）
CHEAT(evals) │        → 长度分流：<50 丢 · 50-119 → short.jsonl · ≥120 → 主集
自建 custom ─┘        → held-out 生成器分流 → held_out.jsonl（cross-generator evals）
                      → 按 doc_id 哈希 80/10/10 → train / val / test.jsonl + stats.json
```

- 许可（DATASETS.md §5）：HC3 / CSL / M4 可商用进 train；**CHEAT 默认只进 test**（`--cheat-into-train` 需授权）
- `--held-out-sources qwen,deepseek`：这两家 AI 样本不进任何训练 split，专供「未见生成器」评测
- 场景映射是弱标注（`map_scenario`）：公开集只有粗 domain；真 6 场景分布靠 `raw/custom/` 自建数据补齐，不足 500 条的场景会 warning

### 2.3 增强（`paraphrase_augment.py`）

| 模式 | 原文 | 产物 | 依据 |
|---|---|---|---|
| `paraphrase` | label=1 AI 原文 | weak / mid / strong 三档改写，label=1 | Chen §5.3 · DATASETS §3.3 |
| `polish` | label=0 人写原文 | LLM 润色（保内容提清晰度），label=1，source=润色模型家族 | Fraser §5.5 GPT-polished |
| `mixcase` | label=0 人写原文 | 随机 30-60% 句子换 LLM 改写句，label=1，meta 记 AI 句索引 | Fraser mixcase · HACo-Det 句级混写 |

- 引擎：`llm`（OpenAI-compatible，Qwen / DeepSeek / GLM / GPT 皆可，`PARAPHRASE_BASE_URL / API_KEY / MODEL`）或 `rule`（离线同义替换 + 句序，仅 weak 档，用于无 API 跑通）
- 断点续跑（按 doc_id 跳过已产出）· 多线程 · 指数退避
- `--merge`：按原文 doc_id 所在 split 合并回 train / val / test，幂等
- 建议规模（v0.2.0）：train 侧 paraphrase 6000 原文 × 3 档 + polish 4000 + mixcase 2000；test 侧各 800 / 600 / 400 供评测集

### 2.4 六套评测集（`build_evalsets.py`）

| 集 | 构成 | 验收线（MODEL_UPGRADE_PLAN Phase 1） |
|---|---|---|
| in_domain | test 里 augment=none | AUROC ≥ 0.98 · ECE ≤ 0.05 |
| cross_generator | held_out AI + 等量 human | F1 ≥ 0.85 |
| adversarial | test paraphrase_mid/strong + human | F1 ≥ 0.70 |
| polished | test polished + human | F1 ≥ 0.60（Fraser 差于随机区间，先求过线） |
| mixed | test mixcase + polished + human | F1 ≥ 0.60 |
| short_text | 50-119 字 | AUROC ≥ 0.85 |

外部基准（C-ReD / MAGA-Bench）转成 schema 后 `--extra name=path` 直接挂入，`eval.py` 同口径出报告。

---

## 3. 模型结构（`ml/common/fusion_model.py`）

```
input_ids, mask ──► backbone ──► last_hidden [B, L, H]
                                   ├─ h_cls = hidden[:,0]                                 [B, H]      语义支路
                                   ├─ h_cnn = ‖_k maxpool(ReLU(Conv1d_k(hidden)))  k∈{2,3,5}  [B, 384]    局部 n-gram 结构
surface f (30 维, z-score) ──► MLP(30→64→64, GELU) ──────────────────────────────────  [B, 64]     表层 / 文体
fused = LayerNorm([h_cls ; h_cnn ; f])                                                 [B, H+448]
  ├─ classifier: Dropout → Linear(→256) → ReLU → Dropout → Linear(→2)                  主任务
  └─ source_head: Dropout → Linear(→128) → ReLU → Linear(→9)                          溯源（可选）
```

- `arch=cls_only` 退化为 legacy 同构（`[CLS]→MLP`），做 A/B 对照与老 checkpoint 兼容
- CNN 对 padding 位置 mask 为 -inf 再 max-pool，避免 pad 干扰
- 表层特征在**原文**上预计算；训练时的在线增强只扰动语义支路，f 保持原文统计 —— 刻意让模型学到「表层稳定、语义扰动」这一改写场景的真实分布
- `freeze_backbone_except_last(n)`：冻 embeddings + 底部层，DeBERTa 的 rel_embeddings 随顶层一起解冻
- 定义放 `ml/common` 是为了推理镜像 COPY 同一份，杜绝老代码那种"推理侧手抄结构"的漂移

### 3.1 表层特征 f（`ml/common/surface_features.py` · 30 维 · `sf-v1`）

| 组 | 特征 | Chen 对应 |
|---|---|---|
| 结构 (8) | 标点密度、逗号/句号/问叹号占比、人称代词比、话语标记率（首先/综上所述/值得注意的是…）、停用字比、特殊符号比 | Structural |
| 词汇 (8) | 句长均值/std/CV、log 句数、TTR、唯一字比、平均词长、长词比 | Lexical |
| 多样性 (8) | 字/词熵、Yule's K、重复 bi/tri-gram 率、hapax 比、数字比、拉丁字母比 | Language diversity |
| 节奏代理 (6) | 标点间隔均值/std/CV、子句长均值/std、相邻重复 token 率 | 发音相关代理（停顿 / 节奏 / 重复） |

- jieba 可选：缺失退化为字级统计，**维度不变**
- z-score 的 mean/std 在训练集拟合，随 checkpoint 落盘；推理侧校验 `SURFACE_FEATURE_VERSION`，不匹配直接报错而不是静默算错

---

## 4. 训练方法（`ml/training/text/train.py`）

| 技巧 | 参数 | 作用 |
|---|---|---|
| Focal Loss | γ=2, α=0.25 | 把梯度压到改写 / 润色这类难样本 |
| R-Drop | α=0.5 | 两次 dropout forward 的双向 KL，正则化 |
| EMA | 0.999 | 验证 / 保存用 shadow 权重 |
| FGM | ε=0.5，每 2 step | word embedding 梯度方向扰动，抗字面级攻击 |
| 溯源多任务 | w=0.3 | 共享表示学生成器指纹，顺带产出 `/attribute` 能力 |
| SupCon | w=0.1, τ=0.07 | 融合向量上同标签拉近 |
| 分层 LR | bottom 0.1× · mid 0.5× · top 1× · head 5× | 大 backbone 底层稳、新头快 |
| 解冻 | 最后 10 层（base）/ 14 层（large） | 显存与过拟合折中 |
| 精度 | bf16 autocast（不支持时 fp16 + GradScaler） | A100 提速 2× |
| 梯度累积 | 等效 batch 32 | large 用 8×4 |
| 调度 | cosine + 10% warmup | |
| 早停 | 监控 val AUROC，patience 2；large 每 2000 step 也评估 | |
| 场景均衡采样 | `scenario_mix` 6 场景配比 + 场景内 label 均衡 | 防 academic_master 淹没 |
| 增强配比 | `augment_mix`：weak 5% / mid 7% / strong 8% / polished 10% | Fraser：mixcase 必须入训 |
| 在线轻量增强 | 30% 概率：同义替换 / 句序 / 删字 | 沿用 legacy |

每次评估在 val 上拟合温度 + Platt，记录 ECE before/after，最优时落盘 best.pth + 阈值。

---

## 5. 校准与阈值（`ml/training/text/calibration.py`）

```
calibrated = sigmoid( (raw_logit / T) * a + b )       raw_logit = logits[:, 1]（与推理侧口径一致）
```

- 温度：L-BFGS 最小化 NLL，T ∈ [0.05, 20]
- Platt：在 T 缩放后 logit 上再拟 (a, b)，带弱 L2
- 阈值（`find_thresholds`）：`fpr_1pct` / `fpr_5pct`（human 集假阳 ≤ 1% / 5%）· `youden` · `default_0_5`，全部写进 checkpoint `thresholds`
- 指标不依赖 sklearn：`auroc / tpr_at_fpr / ece / brier / binary_metrics` 自实现，推理镜像可瘦身

运行时策略（backend 侧后续接）：博士 / 硕士场景用 `fpr_1pct`，其它 `fpr_5pct`；报告同时给校准概率 + 所用阈值，避免"一个分数"式的黑盒。

---

## 6. Checkpoint 契约（`ml/common/checkpoint.py`）

```python
{
  "model_state_dict": ..., "temperature": T, "platt_a": a, "platt_b": b,
  "thresholds": {"default_0_5": .5, "fpr_1pct": ..., "fpr_5pct": ..., "youden": ...},
  "hyperparams": {"version", "codename", "backbone", "arch", "max_length", "classifier_hidden", "dropout",
                  "cnn_kernels", "cnn_filters", "surface_hidden", "surface_dim", "surface_feature_version",
                  "surface_scaler": {"version","names","mean","std"}, "num_sources", "source_families", ...},
  "metrics": {"val": {...}, "test": {...}, "thresholds": {...}},
  "val_acc", "val_f1", "ece"        # legacy 兼容键
}
```

- `load_detector_from_checkpoint()`：三侧共用；无 `hyperparams.arch` 视为 legacy，按 cls_only + 外部 backbone 加载，并把 `roberta.*` 键重映射到 `backbone.*`
- **新 checkpoint 自带 backbone 名**，推理 `.env` 只需 `TEXT_CHECKPOINT_PATH`；`TEXT_BASE_MODEL_PATH` 仅 legacy 用或本地覆盖

---

## 7. 推理侧改动（`deploy/inference-python/`）

- `detectors/text.py`：改用 `ml.common.checkpoint` 加载；fusion 模型推理时算表层特征 → scaler → 融合；`ParagraphPrediction` 新增 `thresholds` 与 `source_probs`；`health()` 暴露 arch / 阈值 / val 指标
- `Dockerfile`：build context 改为仓库根，`COPY ml/common` + `COPY detectors`（原 Dockerfile 漏 COPY detectors，顺手修）；`PYTHONPATH=/app`
- `requirements.txt`：+ sentencepiece（DeBERTa tokenizer）· numpy · jieba
- `main.py` 接口不变：`/api/v1/detect/paragraph` 响应结构未动，`/attribute` 可在下一步切到 `source_probs`

---

## 8. 配置（`ml/configs/text/`）

| 文件 | backbone | arch | 数据 | 用途 |
|---|---|---|---|---|
| `v0.1.0-baseline.yaml` | chinese-roberta-wwm-ext | cls_only | 无增强 | A/B 对照组，接管老兜底 |
| `v0.2.0-fusion-mdeberta.yaml` | mdeberta-v3-base | fusion + 溯源 | 增强 30% | **主推** |
| `v0.3.0-fusion-deberta-large.yaml` | deberta-v3-large | fusion + 溯源 | 增强 30%，200K | 上限；batch 8×4 + grad ckpt |

三份 yaml 字段完全一致，可直接 diff。

---

## 9. 验收

Phase 1 硬指标（MODEL_UPGRADE_PLAN §4）+ 本轮新增：

| 项 | 线 | 评测集 |
|---|---|---|
| In-domain AUROC | ≥ 0.98 | in_domain |
| ECE（校准后） | ≤ 0.05 | in_domain |
| Cross-generator F1（qwen / deepseek 未见） | ≥ 0.85 | cross_generator |
| Adversarial F1（mid / strong 改写） | ≥ 0.70 | adversarial |
| Polished F1 | ≥ 0.60 | polished |
| Mixed F1 | ≥ 0.60 | mixed |
| Short-text AUROC | ≥ 0.85 | short_text |
| 溯源 top-1 | ≥ 0.70 | in_domain（`source_top1_acc`） |
| A/B | v0.2.0 fusion 在 adversarial / polished 上 F1 ≥ v0.1.0 + 4pp | 两份 eval-report 对比 |

`eval.py` 对每套自动打 PASS / FAIL。

---

## 10. 运行手册

```bash
# 0. 环境（云 GPU，A100 40GB）
bash training/setup_env.sh && docker compose -f training/docker-compose.mlops.yml up -d
export PARAPHRASE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export PARAPHRASE_API_KEY=...   PARAPHRASE_MODEL=qwen-plus

# 1. 数据
bash training/scripts/train_baseline.sh data            # HC3 + CSL + M4 → train/val/test（qwen/deepseek held-out）
bash training/scripts/train_baseline.sh augment llm     # paraphrase×3 / polish / mixcase → merge
bash training/scripts/train_baseline.sh evalsets        # 六套评测集

# 2. 冒烟（无 GPU 也能跑，验证链路）
bash training/scripts/train_baseline.sh smoke

# 3. 训练 + 评估
bash training/scripts/train_baseline.sh train baseline  # 对照组
bash training/scripts/train_baseline.sh train fusion    # 主推
bash training/scripts/train_baseline.sh eval  fusion    # → ml/checkpoints/text/v0.2.0-fusion-mdeberta/eval-report.json

# 4. 上线
#   deploy/inference-python/.env: TEXT_CHECKPOINT_PATH=./ml/checkpoints/text/v0.2.0-fusion-mdeberta/best.pth
#   docker build -f deploy/inference-python/Dockerfile -t paperaigc-inference . && 重启
#   登记 ml/VERSIONS.md
```

预估：v0.2.0 在 120K 样本 × 4 epoch，单 A100 40GB 约 5-7 小时；LLM 增强约 3 万次调用（DeepSeek / Qwen 定价 ≈ 200-400 元）。

---

## 11. 文件清单

| 路径 | 动作 |
|---|---|
| `ml/__init__.py` · `ml/common/__init__.py` · `ml/datasets/__init__.py` · `ml/datasets/text/__init__.py` · `ml/evaluation/__init__.py` · `ml/evaluation/text/__init__.py` | 新增（包结构） |
| `ml/common/surface_features.py` · `fusion_model.py` · `checkpoint.py` | 新增 |
| `ml/datasets/text/schema.py` · `build_dataset.py` · `paraphrase_augment.py` · `build_evalsets.py` | 新增 |
| `ml/datasets/text/README.md` | 重写 |
| `ml/training/text/data.py` · `model.py` · `calibration.py` · `train.py` | 骨架 → 实装 |
| `ml/training/text/losses.py` · `tricks.py` | 新增 |
| `ml/evaluation/text/eval.py` | 骨架 → 实装 |
| `ml/configs/text/v0.1.0-baseline.yaml` | 重写为可跑 |
| `ml/configs/text/v0.2.0-fusion-mdeberta.yaml` · `v0.3.0-fusion-deberta-large.yaml` | 新增 |
| `ml/README.md` · `ml/VERSIONS.md` | 更新 |
| `deploy/inference-python/detectors/text.py` · `Dockerfile` · `requirements.txt` | 适配 |
| `training/scripts/train_baseline.sh` · `training/requirements.txt` | 重写 / 加依赖 |

---

## 12. 风险与后续

| 风险 | 缓解 |
|---|---|
| 本机无 Python / GPU，代码未经运行验证 | 首跑先 `smoke`（200 条 dry-run）；任何报错优先看 `ml/common` 三个共用模块 |
| 公开集场景标签是弱映射，6 场景配比在 v0.2.0 上意义有限 | 自建 `raw/custom/` 学术集是 v0.2.x 最高优先级数据工作（DATASETS §3.1） |
| CHEAT / MAGE 研究许可 | 默认只进 evals；商用 checkpoint 只含 HC3 / CSL / M4 / 自建 |
| mDeBERTa sentencepiece tokenizer 与 BERT 不同 | `AutoTokenizer` 已兼容；推理 requirements 加 sentencepiece |
| DeBERTa `gradient_checkpointing` 与 R-Drop 双 forward 叠加显存 / 时间 | large 配置已开 ckpt，必要时把 `rdrop_alpha` 置 0 |
| 溯源头在公开集上类别极不均衡（gpt 一家独大） | `use_source_head` 可关；自建数据补齐 8 家后再开 |
| 白盒零样本 / 句子级 CRF 未在本轮 | Phase 2（MODEL_UPGRADE_PLAN M2 / M3），接口留在 `branch_scores` |
