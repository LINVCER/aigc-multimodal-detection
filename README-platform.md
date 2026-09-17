# paper-aigc-detect · 企业级论文 AIGC 检测平台

面向中国高校的论文 AIGC 检测 + 降 AIGC 一体化平台。政策背景：教育部 2026 年起全面实施学位论文 AIGC 检测（本科 ≤20% / 硕士 ≤15% / 博士 ≤10%）。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端基座 | **RuoYi-Vue-Plus 5.x**（Spring Boot 3 + Java 21 + MyBatis-Plus + Sa-Token） |
| 业务模块 | `backend-java/business-modules/`（ruoyi-detect / ruoyi-inference） |
| 推理服务 | Python：Triton（分类/溯源）+ vLLM（Qwen LoRA 降 AIGC）+ FastAPI（白盒双检） |
| 训练 | Python + PyTorch + Transformers + PEFT；MLflow + DVC |
| Web 管理端 | plus-ui（RuoYi-Vue-Plus 配套 Vue3 + Element Plus） |
| 移动端 | React Native + Expo（`mobile-app/`） |
| 数据层 | MySQL 8 + Redis 7 + MinIO |

## 目录结构

```
paper-aigc-detect/
├── backend-java/
│   ├── RUOYI_INTEGRATION.md      # 若依基座挂载指南（必读）
│   └── business-modules/
│       ├── ruoyi-detect/         # 检测任务编排业务模块
│       └── ruoyi-inference/      # gRPC 推理网关（proto + 客户端）
├── training/
│   ├── setup_env.sh              # 云 GPU 环境一键搭建
│   ├── requirements.txt
│   ├── docker-compose.mlops.yml  # MLflow
│   └── scripts/
│       ├── download_datasets.py  # HC3-Chinese / M4 / CHEAT
│       └── train_baseline.sh     # RoBERTa vs mDeBERTa A/B
├── mobile-app/                   # React Native + Expo（见其 README）
├── doc/sql/init.sql              # 业务表 DDL
└── docker-compose.yml            # 开发数据层（MySQL/Redis/MinIO）
```

## 快速开始

```bash
# 1. 起数据层
docker compose up -d

# 2. 后端：按 backend-java/RUOYI_INTEGRATION.md 挂载若依基座后
cd RuoYi-Vue-Plus && mvn spring-boot:run -pl ruoyi-admin

# 3. 训练环境（云 GPU 实例）
bash training/setup_env.sh
docker compose -f training/docker-compose.mlops.yml up -d
python training/scripts/download_datasets.py
bash training/scripts/train_baseline.sh both   # 第一个假设检验

# 4. 移动端
cd mobile-app && npm install && npx expo start
```

## 设计文档

规划与调研文档在 `D:\tmp\aigc-multimodal-detection\`（后续迁入本仓库 doc/）：

- `ENTERPRISE_ARCHITECTURE.md` — 系统架构总方案
- `MODEL_UPGRADE_PLAN.md` — 模型选型与实施计划（决策入口）
- `MODEL_RESEARCH_TEXT.md` — 文本检测调研（v1+v2）
- `MODEL_RESEARCH_IMAGE_TAMPERING.md` — 论文插图检测调研
- `BASELINE.md` — 上游参考项目基线分析
