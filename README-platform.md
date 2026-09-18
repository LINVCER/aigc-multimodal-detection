# paper-aigc-detect · 论文 AIGC 检测平台

C 端为主的 AIGC 检测 + 降 AIGC 工具。6 场景红线（本科 20% / 硕士 15% / 博士 10% / 职业报告 15% / 自媒体 30% / 其他 25%）。

## 三端独立架构

**每端独立启动、独立部署、互不耦合**。没有一键脚本、没有 docker-compose 编排，各端在本地起各的进程。

```
┌──────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
│  前端（Front）       │  →   │  Java 后端（Backend）  │  →   │  Python 推理（Infer）  │
│  web/ + mobile-uniapp│  HTTP│  backend-java/         │  HTTP│  deploy/inference-python│
└──────────────────────┘      └────────────────────────┘      └────────────────────────┘
        独立端口                    独立端口                       独立端口
      web: 5173                  admin: 18080                    infer: 18000
      mobile: 5175
```

## 各端 README（各自独立启动步骤）

| 端 | 目录 | 启动文档 |
|---|---|---|
| Web 前端（C 端 + 运营后台） | `web/` | [`web/README.md`](web/README.md) |
| Mobile 前端（H5 + 微信小程序） | `mobile-uniapp/` | [`mobile-uniapp/README.md`](mobile-uniapp/README.md) |
| Java 后端 | `backend-java/` | [`backend-java/README.md`](backend-java/README.md) |
| Python 推理 | `deploy/inference-python/` | [`deploy/inference-python/README.md`](deploy/inference-python/README.md) |

## 通信

- **前端 → 后端**：HTTP。前端 dev server 走 vite proxy `/api → http://localhost:18080`。生产走 Nginx 反代。
- **后端 → Python 推理**：HTTP。后端 `application-*.yml` 里 `platform.inference.host/port` 指到 Python 端（默认 `localhost:18000`）。加载失败 / 超时 → 后端 fallback 报错，前端有兜底展示。
- **Python 端**：完全独立进程，任何一端挂掉不影响其它端启动。

## 目录结构

```
paper-aigc-detect/
├── README-platform.md            ← 本文
├── web/                          ← Vue 3 + Vite + TS · C 端 + /admin/*
├── mobile-uniapp/                ← Vue 3 + uni-app · H5 + 微信小程序
├── backend-java/                 ← 若依 Vue-Plus 5.x + 业务模块（分层规范化）
│   └── business-modules/ruoyi-detect/
├── deploy/inference-python/      ← FastAPI + 真实模型加载器（fallback stub）
├── ml/                           ← 新一代模型迭代（跟 legacy 严格分离）
├── legacy/                       ← 老实验代码 · 只做参考不动
├── docs/
│   ├── design/                   ← 需求 · 架构 · 需求评审
│   ├── database/                 ← ER 图 / 老 schema 归档
│   └── releases/                 ← 版本文档中心 + Flyway 风格 SQL 迁移
└── models/                       ← 训练好的老模型权重（.gitignore；本地兜底）
```

## 版本管理

- **发版规范** → [`docs/releases/README.md`](docs/releases/README.md)
- **变更日志** → [`docs/releases/CHANGELOG.md`](docs/releases/CHANGELOG.md)
- **模型版本** → [`ml/VERSIONS.md`](ml/VERSIONS.md)（跟发版可独立迭代）

## 设计文档

集中在 `docs/design/`：
- `OPERATIONS_REQUIREMENTS.md` — 运营后台需求
- `API_CONTRACT.md` — 前后端接口契约
- `COMPETITIVE_FEATURE_GAP.md` — 竞品对比
- `ENTERPRISE_ARCHITECTURE.md` — 总体架构
- `MODEL_UPGRADE_PLAN.md` — 模型选型
