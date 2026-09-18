# 模型版本登记

> 每完成一次训练、通过评估后，在此登记一条记录。生产环境的模型切换以本文档为准。

## 登记模板（复制在最上方新增）

```markdown
## v{X.Y.Z}-{codename} · {modality}

| 字段 | 值 |
|---|---|
| 训练日期 | YYYY-MM-DD |
| 训练人 | @xxx |
| 数据集 | 名称 + 版本 + 样本数 + 划分（train/val/test） |
| Backbone | e.g. chinese-roberta-wwm-ext |
| 超参配置 | `ml/configs/text/vX.Y.Z-*.yaml` |
| val F1 | 0.xxxx |
| val AUROC | 0.xxxx |
| val ECE（校准） | 0.xxxx |
| 温度 T | 1.xxx |
| Platt (a, b) | (x.xxx, x.xxx) |
| checkpoint | `ml/checkpoints/{modality}/vX.Y.Z-*/best.pth` |
| 训练时长 | Nh Nm |
| 部署时间 | 未部署 / YYYY-MM-DD |
| 备注 | 与前一版差异、已知问题 |
```

---

## v0.1.0-baseline · text（📋 待启动）

| 字段 | 值 |
|---|---|
| 训练日期 | — |
| 训练人 | — |
| 数据集 | 待准备（对齐 C 端 6 场景：本科/硕士/博士/职业/自媒体/其他） |
| Backbone | chinese-roberta-wwm-ext（可选 deberta-v3-base 对比） |
| 超参配置 | `ml/configs/text/v0.1.0-baseline.yaml` |
| val F1 | — |
| val AUROC | — |
| val ECE | — |
| 温度 T | — |
| Platt (a, b) | — |
| checkpoint | 未产出 |
| 部署时间 | 未部署 |
| 备注 | 首个 baseline 目标：接管临时挂的老 `aigc_detector_v3_thesis.pth` |

---

## v0.1.0-baseline · audio（📋 待启动）

| 字段 | 值 |
|---|---|
| 训练日期 | — |
| 训练人 | — |
| 数据集 | 待准备（AISHELL-3 / OpenAI TTS / ElevenLabs / XTTS · 20k 片段 3s 窗口） |
| Backbone | facebook/wav2vec2-base（可选 xls-r-300m 对比） |
| 超参配置 | `ml/configs/audio/v0.1.0-baseline.yaml` |
| val F1 | — |
| val AUROC | — |
| val ECE | — |
| 温度 T | — |
| Platt (a, b) | — |
| checkpoint | 未产出 |
| 部署时间 | 未部署 |
| 备注 | 首个 baseline · 3s 窗口 + 1s stride 段级 AI 语音判定；Java + Python 骨架已就位（stub 兜底），训完直接替换 `AUDIO_CHECKPOINT_PATH` 即可 |

---

## legacy/aigc_detector_v3_thesis（⚠ 兜底不算正式版本）

| 字段 | 值 |
|---|---|
| 来源 | `legacy/algorithms/train_text_detector.py` 老实验产出 |
| checkpoint | `models/text/aigc_detector_v3_thesis.pth`（.gitignore） |
| 用途 | **仅供推理链路联调**，不列入产品线正式版本序列 |
| 何时下线 | v0.1.0-baseline 训完并评估通过后即替换 |
