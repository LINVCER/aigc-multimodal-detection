# deploy · 全栈 Docker 部署

单机一键起论文 AIGC 检测平台全栈：**用户端 Web + 管理端 Web + Java 后端（若依基座 + 业务模块）+ Python 推理 stub + MySQL + Redis + MinIO + Nginx 网关**。

> Phase 0 目标：全栈能起、UI 能点、检测走通 stub 返回假数据。真实模型（DeBERTa / Qwen LoRA / 白盒双检）在后续阶段替换 `inference` 服务即可。

## 前置

- Docker 24+ 与 Docker Compose v2
- 至少 8 GB 内存空闲（首次 build 会占更多），60 GB 磁盘
- 首次 build 需要联网 clone 若依基座与 plus-ui（默认 Gitee，国内快）

## 启动

```bash
cd deploy
cp .env.example .env
# ⚠️ 生产环境务必改 MYSQL_ROOT_PASSWORD / REDIS_PASSWORD / MINIO_SECRET_KEY / JWT_SECRET

docker compose up -d --build     # 首次构建 20-40 分钟（下载依赖 + Maven build）
docker compose logs -f backend   # 等到看见 "Started RuoYiAdminApplication"
```

首次全栈起来后：

| 入口 | 地址 | 说明 |
|---|---|---|
| 用户端 | http://localhost/ | Vue 3 现有前端 |
| 管理端 | http://localhost/admin/ | plus-ui（若依默认账号 `admin` / `admin123`） |
| Java API | http://localhost/api/actuator/health | 通过 Nginx |
| Python 推理 | http://localhost:8000/health | 直连 |
| MinIO 控制台 | http://localhost:9001 | 见 `.env` 里 KEY/SECRET |
| MLflow（可选） | http://localhost:5000 | `docker compose --profile mlops up -d` 单独起 |

## 目录

```
deploy/
├── docker-compose.yml         # 主编排（8 服务 + mlops profile）
├── .env.example
├── backend-java/Dockerfile    # 多阶段：clone 若依 → 挂业务模块 → mvn package
├── frontend/Dockerfile        # 用户端：Vite build → Nginx serve
├── admin-web/Dockerfile       # 管理端：clone plus-ui → npm build → Nginx serve
├── inference-python/          # FastAPI stub（哈希取模 mock 打分）
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── nginx/                     # 统一入口反代
│   ├── nginx.conf
│   └── conf.d/gateway.conf
└── README.md（本文档）
```

## 常用命令

```bash
docker compose ps                       # 服务状态
docker compose logs -f <service>        # 跟日志
docker compose restart backend          # 只重启后端
docker compose up -d --build backend    # 只重建后端
docker compose down                     # 停全部（数据保留）
docker compose down -v                  # 停全部并清数据（谨慎）
docker compose --profile mlops up -d    # 加起 MLflow
```

## 依赖关系与启动顺序

Compose 已用 `depends_on: condition: service_healthy` 编排：

```
mysql / redis / minio  → 全 healthy 后
  inference (Python stub) → healthy 后
    backend (Java) → healthy 后
      frontend + admin → gateway (Nginx)
```

Java 后端首次启动会自动跑若依内置 schema + 我们的业务表（`docs/sql/init.sql` 已挂载）。

## 关键设计

- **Java 后端镜像里 clone 若依基座**：仓库不包含若依源码；Dockerfile builder 阶段用 Gitee clone `RuoYi-Vue-Plus 5.X`，把 `backend-java/business-modules/` 拷入 `ruoyi-modules/`，sed 挂载 pom + 对齐 revision → `mvn package`
- **管理端同理**：镜像里 clone `plus-ui`，vite 构建时把 API base 写成 `/admin-api`，Nginx 反代到 backend
- **Nginx 统一入口**：单端口 80 分发全部路径，避免 CORS，方便 HTTPS 证书统一
- **Python 推理是 stub**：接口与 gRPC proto 语义对齐，方便后续换 Triton/vLLM 时前后端零改动
- **数据卷 named volumes**：`mysql_data / redis_data / minio_data`，`docker compose down` 不丢

## 生产化改造清单（本方案未覆盖）

- [ ] HTTPS：在 Nginx 前加 Traefik / Caddy，或 Nginx 里配 Let's Encrypt
- [ ] 分离数据层：MySQL/Redis/MinIO 走托管服务或独立机器
- [ ] Java 堆参数：按机器内存调整 `JAVA_TOOL_OPTIONS`
- [ ] 秘钥管理：`.env` 换 Vault / KMS
- [ ] 日志采集：Loki / ELK
- [ ] 监控：Prometheus + Grafana（Micrometer 已在 backend 暴露 `/actuator/prometheus`）
- [ ] 备份：MySQL xtrabackup + MinIO 对象跨区域

## 故障排查

- **backend 起不来**：`docker compose logs backend` 看日志；若是 Maven build 失败常见于 Gitee 拉不到某依赖，可以进 builder 层排查或换 `RUOYI_GIT_URL` 到 GitHub
- **管理端登录失败**：确认 backend 已启动且 Nginx 的 `/admin-api/` 反代通；`curl http://localhost/admin-api/actuator/health`
- **MinIO bucket 没建好**：`docker compose logs minio-init` 看输出；重跑 `docker compose up -d minio-init`
- **端口占用**：改 `.env` 里 MYSQL_PORT/REDIS_PORT，或改 `docker-compose.yml` 里对应 host 端口
