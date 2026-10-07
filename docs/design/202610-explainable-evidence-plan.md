# 可解释检测证据链方案（模型产出判断原因 → AI 助手翻译）

> 日期：2026-10
> 方向：**后面训练的模型检测出「具体判断 AIGC 率的原因」，作为结构化证据交给 AI 助手，由助手解释给用户**
> 状态：**L1 已实施（2026-10-07）**，L2 待训练 fusion，L3 未排期 · 调研结论与改进点见 §7

---

## 0. 核心架构：三段式证据链

```
检测模型（训练侧）
  │  输出：AI 率 + 结构化「判断原因」（证据）
  ▼
证据契约（JSON schema，两端对齐）
  ▼
AI 助手（推理侧）
  │  把证据翻译成人话 + 引用数值 + 申诉材料
  ▼
用户（看懂「为什么」）
```

**关键原则**：模型负责「产出原因」，助手负责「翻译原因」，两者通过**证据契约**解耦——模型不写文案，助手不编数字。

---

## 1. 模型侧要产出的「判断原因」（证据）

| 证据 | 说明 | 回答的问题 |
|---|---|---|
| **表层统计特征**（surface） | 30 维 z-score：句长节奏、套话连接词、用词丰富度、标点分布、n-gram 重复率 | 「这段**为什么**像 AI」——最直观、人可理解 |
| **溯源**（source） | 与哪家 LLM 的输出最像（gpt/qwen/deepseek/human…概率） | 「**像谁**」 |
| **句子级概率** | 逐句 AI 概率，定位哪几句拉高整段 | 「**哪句**最可疑」 |
| **校准概率 + 置信区间** | 整体判定 + 可靠性 | 「判定多确定」 |
| （进阶）**归因** | 特征重要性 / token 归因 | 「模型**凭什么**判」 |

---

## 2. 训练侧现状（已铺好大半）

| 组件 | 状态 |
|---|---|
| `ml/common/fusion_model.py` | ✅ 已实现：分类 + surface 支路 + source_head（multi-task） |
| `ml/common/surface_features.py` | ✅ 30 维统计特征，纯 numpy，不依赖模型 |
| `ml/common/checkpoint.py` | ✅ 契约含 `uses_surface` / `source_families` / `scaler` |
| 配置 `v0.2.0/v0.3.0-fusion` | ✅ `use_source_head: true`（9 类溯源 human + 8 家族） |
| 训练脚本 `train.py` | ✅ 已保存 scaler + source_families 进 checkpoint |

**缺口只有一个**：当前部署的是 `cls_only` 纯分类 checkpoint（`aigc_detector_v3_thesis.pth`），它**没有 surface 支路 + 没有 source head**，所以：

- `surface_profile()` 返回 `None` → 助手拿不到「句长/连接词/用词」证据；
- `source_probs` 为空 → 溯源「像哪家 LLM」也是空的。

**结论**：训练侧代码和配置都已就绪，**只差训出 fusion 模型并部署**，证据链就会自动打通（推理侧 `surface_profile` / `_forward` 的 source 分支早就在等）。

---

## 3. 助手侧消费（翻译，代码已就绪）

`explain_paragraph` / `detect_text` 工具拿到证据后：

- `SURFACE_EXPLAIN` 映射（`tools.py`，8 维）已把特征名 → 人话方向写死（"句长变化 z 低 → 句子很匀，机器文本的『平』"）；
- 提示词（`prompts.py` L19）已要求「引用具体数值翻译成人话」；
- 前端结构化分析卡（段卡/报告卡/即时检测卡）已落地渲染；
- 知识库已写「统计特征」科普。

**只要模型把 `surfaceEvidence` + `sourceProbs` 吐出来，翻译层零改动即生效。**

---

## 4. 证据契约（两端对齐的 JSON）

```json
{
  "calibratedProb": 0.87,
  "rawProb": 0.92,
  "verdict": "高风险（红）",
  "modelVersion": "v0.3.0-fusion-deberta-large",
  "surfaceEvidence": [
    { "name": "sent_len_cv",          "label": "句长变化",   "z": -1.6, "direction": "句子长短很匀，节奏偏『平』" },
    { "name": "discourse_marker_rate", "label": "套话连接词", "z":  2.1, "direction": "『首先/综上所述』模板词偏多" },
    { "name": "ttr",                  "label": "用词丰富度", "z": -0.9, "direction": "词汇重复偏高" }
  ],
  "sourceProbs": { "gpt": 0.42, "qwen": 0.31, "deepseek": 0.11, "human": 0.08 },
  "sourceLabel": "gpt",
  "sentences": [
    { "idx": 0, "aiProb": 0.93, "text": "…" },
    { "idx": 2, "aiProb": 0.81, "text": "…" }
  ]
}
```

> `ParagraphPrediction` 已含 calibrated_prob / source_probs / sentences；`surfaceEvidence` 不入库，由助手工具在解释时现算（见 §7.2），所以 Java 侧零改动。
>
> **实际字段名以代码为准**（上面示例是意图）：`surfaceEvidence[]` 每项为 `{feature, zscore, reading}`；新增 `evidenceBasis`（人话限定语）、`evidenceBasisKey`（`checkpoint | baseline | document`）、`surfaceFacts`（事实读数：`sentences / avgSentLen / sentLenMin / sentLenMax / sentLenCv / discourseMarkers / discourseMarkerList / ttr / repeatBigramRate`）。

---

## 5. 落地路线

| 阶段 | 动作 | 产出 | 周期 |
|---|---|---|---|
| **L1 过渡** ✅ | 三级基线：checkpoint scaler > 外置基线文件（`build_surface_baseline.py` 产出，`TEXT_SURFACE_BASELINE_PATH`）> **文档内基线**（对照同篇其它正文段）；另给不依赖基线的**事实读数** | cls_only / stub 都能「有据解释」，且不越权说「比人类更…」 | 已完成 |
| **L2 治本** ⭐ | **训出 fusion 模型**（v0.3.0-fusion，分类 + surface + source 三支路）并部署 | 真实 z-score（训练集 scaler）+ 真实溯源 | 数天~数周 |
| **L3 增强** | 句子级特征全量、归因（特征重要性/token 归因）、重写前后对比、溯源相似度检索 | 解释颗粒度到句、可验证、可申诉 | 长期 |

---

## 7. 调研结论与改进点（2026-10-07）

**可行性**：§2 的现状核对无误（`fusion_model.py` 三支路、`checkpoint.py` 含 `surface_scaler`、`train.py` 落盘 scaler、推理侧 `surface_profile` / source 分支就位）。方案成立，L2 只差算力与数据。

**原方案的三个问题及处理**

1. **「内置通用中文论文基线」没有数据来源**。仓库里没有任何人类正文语料（`ml/datasets/text/data/` 不存在，无 jsonl），手写一组 mean/std 等于编造。处理：基线改为**外置文件**，由 `ml/datasets/text/build_surface_baseline.py` 从真实语料拟合后挂载；在拿到语料之前，用**文档内基线**顶上（目标段对照同一篇文章其它正文段，≥ 4 段才算），这是零数据、且语义诚实的方案。
2. **z-score 的「比较对象」必须随证据一起下发**，否则助手会把「比你全文其它段更平」说成「比人类写的更平」。处理：工具返回 `evidenceBasis` 限定语，提示词规则 2 要求翻译时带上；三种基线三句话。
3. **没有基线时助手只能空谈**。处理：新增 `surfaceFacts` 事实读数（几句、平均几字、最长最短、命中的套话连接词及次数、用词重复度），不依赖任何基线，前端分析卡以一行小字展示，助手可直接引用数字。

**本次落地文件**

| 层 | 文件 | 改动 |
|---|---|---|
| 共享 | `ml/common/surface_features.py` | `surface_facts()` · `document_baseline_zscores()` · `load_surface_baseline()` |
| 训练侧 | `ml/datasets/text/build_surface_baseline.py` | 人类语料 → 30 维 mean/std JSON |
| 助手 | `assistant/tools.py` | `_surface_zscores` 三级基线 · `_attach_surface_evidence` · `explain_paragraph` 传同篇其它段作参考 |
| 助手 | `assistant/config.py` / `prompts.py` | `TEXT_SURFACE_BASELINE_PATH` · 规则 2 补基线限定与事实读数 |
| 前端 | web / uniapp `AssistantAnalysisCard.vue` | 表层特征标题带基线限定 · 底部事实读数行 |

**L2 前置清单**：① 人类 + AI 混合语料按 `schema.py` 落到 `ml/datasets/text/data/`（`build_dataset.py`）；② 单卡 A100 跑 `v0.3.0-fusion-deberta-large.yaml`（或先 v0.2.0 mdeberta 验证增益）；③ `MODEL_SWITCH.md` 切 checkpoint，`surface_profile` 自动走 checkpoint scaler，`evidenceBasis` 自动变「模型自带基线」；④ 用 `assistant/eval/golden.jsonl` 的 e01 / e06 回归解释质量。

**L3 建议**：先不做 token 归因（DeBERTa 上的梯度归因对学生不可读，也难验证）；优先做「重写前后对比」（已有 parentTaskId 对比接口，把表层特征差值也摆出来）和句级 facts。

## 6. 需要你拍板（已按「执行」处理）

- L1：已做，且不止内置基线，见 §7。
- L2：需要你安排训练算力与语料，代码与配置已就绪。
- L3：建议先做重写前后对比，归因缓做。

## 原 §6

1. **是否先做 L1 过渡**——让 cls_only 模型先吐方向性 surface 证据（几小时），在 fusion 模型训出来之前，用户就能看到「有解释的检测」？
2. **L2 的训练**——fusion 模型训练（v0.3.0）谁来跑、用什么数据（`ml/datasets/text` 已有多套评测集 + 申诉样本池）？这个周期最长，建议尽早排。
3. **归因（L3）**——「特征重要性/token 归因」要不要纳入训练侧 roadmap，还是先靠 surface + 溯源 + 句子级三件套就够？

---

**一句话**：你的方向是对的，而且**代码已经铺好了 80%**——训练侧的 fusion 三支路、推理侧的 surface_profile、助手的翻译层、前端的分析卡都在等「一个训出来的 fusion 模型」。L1 可以先过渡，但**真正的解是 L2 训出 fusion 模型**。
