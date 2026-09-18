# ml/ · 新一代模型迭代目录

C 端产品线的模型训练 / 评估 / 版本管理在这里做，**与 `legacy/algorithms/` 完全分开**。

老实验（`legacy/algorithms/train_text_detector.py` 及其产出 `models/*.pth`）作为历史参考保留，
新代码不引、新数据不共用；产品线一切从零重训。

---

## 分模态

| 模态 | 目录 | 状态 |
|---|---|---|
| 文本 | `ml/training/text/` | 🟡 骨架就位，训练计划待启动 |
| 音频 | `ml/training/audio/` | 🟡 骨架就位（含推理层 stub 兜底），训练计划待启动 |
| 图像 | `ml/training/image/` | ⚪ 未启动（Wave 5 议） |

## 目录结构

```
ml/
├── README.md                    ← 本文
├── VERSIONS.md                  ← 每次训完在此登记（日期/数据/指标/部署时间）
├── configs/                     ← 训练超参 yaml（一个版本一个文件，可复现）
│   └── text/
│       └── v0.1.0-baseline.yaml
├── training/                    ← 训练代码（跟 legacy/ 严格分离）
│   └── text/
│       ├── model.py             ← 模型结构
│       ├── data.py              ← 数据加载 / 采样
│       ├── calibration.py       ← 温度 + Platt 拟合
│       └── train.py             ← 训练入口
├── evaluation/                  ← 评估脚本（离线批测 + ECE + 场景细分）
│   └── text/
│       └── eval.py
├── datasets/                    ← 数据集准备与清洗脚本（数据本身不入 git）
│   └── text/
│       └── README.md
└── checkpoints/                 ← 训练输出（.gitignore 忽略；线下管理）
    └── text/
        └── v0.1.0-baseline/
            ├── best.pth
            ├── metrics.json
            └── config.snapshot.yaml
```

## 版本命名规范

`v{major}.{minor}.{patch}-{codename}`

- `major`：模型结构大改（换 backbone / 加多分支）→ +1
- `minor`：训练数据集有增删或采样口径变了 → +1
- `patch`：只调超参 / 校准 / 修数据 leak → +1
- `codename`：便于口语引用（baseline / thesis-boost / cnki-align 等）

例：
- `v0.1.0-baseline`：首次能跑起来的最小模型
- `v0.2.0-scenario-mix`：加入 6 场景混合训练
- `v1.0.0-production`：首个正式对外可用版本

## 产出 → 上线流程

1. 训练完 → `ml/checkpoints/text/{version}/best.pth`
2. 评估通过 → 登记 `VERSIONS.md`
3. 拷贝到部署路径（生产走对象存储 / 本地跑走 `TEXT_CHECKPOINT_PATH`）
4. 更新 `deploy/inference-python/.env` 里的 checkpoint 路径 + 重启服务
5. 灰度参数走 `detect_scenario_threshold` / `model_version` 表控制

## 与推理层的对接

```
ml/checkpoints/text/{ver}/best.pth
       │
       ▼   （TEXT_CHECKPOINT_PATH 指向此文件）
deploy/inference-python/detectors/text.py · TextAIGCDetector.load()
       │
       ▼
FastAPI /api/v1/detect/paragraph
       │
       ▼
backend-java · IInferenceClient
```

推理层不感知模型来自 ml/ 还是 legacy/，只认 `TEXT_CHECKPOINT_PATH` env。切模型 =
换路径 + 重启，无需改代码。

## 老模型是否复用？

**不复用**。老 `models/text/aigc_detector_v3_thesis.pth` 仅在 `deploy/inference-python`
上作为「打通链路的临时兜底」使用，本目录训练代码从零开始，不加载老权重初始化，不复用
老训练集划分。
