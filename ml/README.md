# ml/ · 新一代模型迭代目录

C 端产品线的模型训练 / 评估 / 版本管理在这里做，**与 `legacy/algorithms/` 完全分开**。
老实验（`legacy/algorithms/train_text_detector.py` 及其产出 `models/*.pth`）作为历史参考保留，
新代码不引、新数据不共用；产品线一切从零重训。

**2026-09-21 起主方向收敛为论文 AIGC 文本检测**，音频 / 图像目录归档不再推进。

设计文档：[`docs/design/202609-text-detector-training-pipeline.md`](../docs/design/202609-text-detector-training-pipeline.md)
文献依据：[`docs/research/AIGC文本论文检测-文献精读笔记.md`](../docs/research/AIGC文本论文检测-文献精读笔记.md)

---

## 状态

| 模块 | 路径 | 状态 |
|---|---|---|
| 统一 schema | `ml/datasets/text/schema.py` | ✅ |
| 数据集构建（HC3 / CSL / M4 / CHEAT / 自建 → 清洗 / PII / 去重 / 按原文分 split） | `ml/datasets/text/build_dataset.py` | ✅ |
| 改写 / 润色 / 混写增强（LLM 或规则引擎，断点续跑，按 doc_id 合并） | `ml/datasets/text/paraphrase_augment.py` | ✅ |
| 六套评测集切分 | `ml/datasets/text/build_evalsets.py` | ✅ |
| 表层特征 f（30 维，训练 / 推理共用） | `ml/common/surface_features.py` | ✅ |
| 融合模型 `[h_cls ; h_cnn ; f]` + 溯源头 | `ml/common/fusion_model.py` | ✅ |
| checkpoint 契约（训练 / 评估 / 推理三侧） | `ml/common/checkpoint.py` | ✅ |
| 训练（Focal · R-Drop · EMA · FGM · 分层 LR · bf16 · 早停 · MLflow） | `ml/training/text/train.py` | ✅ 待首跑 |
| 校准（温度 + Platt）+ 低假阳阈值 + 指标 | `ml/training/text/calibration.py` | ✅ |
| 离线评估（6 套分报 + 验收线） | `ml/evaluation/text/eval.py` | ✅ |
| 配置 | `ml/configs/text/v0.1.0-baseline.yaml` · `v0.2.0-fusion-mdeberta.yaml` · `v0.3.0-fusion-deberta-large.yaml` | ✅ |
| 推理侧适配（新老 checkpoint 双兼容） | `deploy/inference-python/detectors/text.py` | ✅ |

## 目录结构

```
ml/
├── README.md / VERSIONS.md
├── common/                          ← 训练与推理共用（推理镜像会 COPY 这一目录）
│   ├── surface_features.py          表层 / 文体特征 30 维 + z-score scaler
│   ├── fusion_model.py              FusionAIGCDetector（fusion / cls_only）
│   └── checkpoint.py                best.pth 读写契约
├── configs/text/                    一个版本一个 yaml
├── datasets/text/
│   ├── schema.py                    JSONL 行结构 / 场景 / 来源家族 / 增强类型
│   ├── build_dataset.py             公开集 → train/val/test/short/held_out
│   ├── paraphrase_augment.py        paraphrase × 3 档 / polished / mixcase
│   ├── build_evalsets.py            eval_in_domain / cross_generator / adversarial / polished / mixed / short_text
│   └── data/                        （.gitignore）产出的 jsonl
├── training/text/
│   ├── data.py                      采样 / Dataset / collate
│   ├── model.py                     re-export ml.common.fusion_model
│   ├── losses.py                    Focal / LabelSmoothing / R-Drop KL / SupCon
│   ├── tricks.py                    EMA / FGM / 分层 LR / seed
│   ├── calibration.py               温度 + Platt + ECE / AUROC / TPR@FPR / 阈值搜索
│   └── train.py                     训练入口
├── evaluation/text/eval.py
└── checkpoints/                     （.gitignore）
```

## 一条命令跑通

```bash
bash training/setup_env.sh                      # conda + torch + requirements
bash training/scripts/train_baseline.sh smoke   # 200 条冒烟（需先有 data/train.jsonl；无数据时先跑 data）
bash training/scripts/train_baseline.sh all     # data → augment(rule) → evalsets → train fusion → eval
```

真正出高精度模型需要 LLM 改写增强：配好 `PARAPHRASE_BASE_URL / PARAPHRASE_API_KEY / PARAPHRASE_MODEL`
后跑 `train_baseline.sh augment llm`，再 `train fusion`。详见设计文档 §10。

## 版本命名

`v{major}.{minor}.{patch}-{codename}`：major = 结构大改（换 backbone / 加分支）；minor = 数据集增删或采样口径变；patch = 只调超参 / 校准。

## 产出 → 上线

1. `ml/checkpoints/text/{version}/best.pth` + `metrics.json` + `eval-report.json`
2. 六套评测全过验收线 → 登记 `VERSIONS.md`
3. `deploy/inference-python/.env` 里 `TEXT_CHECKPOINT_PATH` 指向新 best.pth，重启服务（新 checkpoint 自带 backbone / 阈值 / 表层特征 scaler，无需再配 `TEXT_BASE_MODEL_PATH`）
4. 灰度走 `detect_scenario_threshold` / `model_version`

## 老模型是否复用

不复用权重。`models/text/aigc_detector_v3_thesis.pth` 仅作推理链路兜底；推理侧对它保留向后兼容加载（cls_only + `TEXT_BASE_MODEL_PATH`）。
