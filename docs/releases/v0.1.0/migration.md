# v0.1.0 · 升级手册

**三端独立启动，各自可控**。不提供一键脚本，各端进程互不阻塞：只跑前端也能开发（走 mock 数据）、只跑后端也能测接口、只跑推理也能验证模型。

## 前置

- MySQL 8.x + Redis 7（后端要用）
- Java 21 + Maven 3.9+（后端要用）
- Node 20 + npm/pnpm（前端要用）
- Python 3.10+（推理端要用）

各端只装自己那份即可。

---

## 端 1 · Java 后端 → 详见 [`backend-java/README.md`](../../../backend-java/README.md)

关键步骤（首次搭本地）：

```bash
# 1) clone 若依基座到任意本机目录（不入本仓库）
git clone https://gitee.com/dromara/RuoYi-Vue-Plus.git -b 5.X ~/workspace/RuoYi-Vue-Plus

# 2) 软链业务模块到基座 ruoyi-modules/
ln -s $(pwd)/backend-java/business-modules/ruoyi-detect    ~/workspace/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-detect
ln -s $(pwd)/backend-java/business-modules/ruoyi-inference ~/workspace/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-inference

# 3) 改基座 pom（ruoyi-modules/pom.xml 加 <module>；ruoyi-admin/pom.xml 加依赖）
#    详见 backend-java/README.md

# 4) 数据库初始化
mysql -uroot -p ry-vue < docs/releases/v0.1.0/sql/V0.1.0.001__init_ops_backend_schema.sql
mysql -uroot -p ry-vue < docs/releases/v0.1.0/sql/V0.1.0.002__init_detect_task_schema.sql
mysql -uroot -p ry-vue < docs/releases/v0.1.0/sql/R__seed_scenario_threshold.sql

# 5) 启动
cd ~/workspace/RuoYi-Vue-Plus
mvn -pl ruoyi-admin -am spring-boot:run
# 默认端口 18080
```

---

## 端 2 · Python 推理 → 详见 [`deploy/inference-python/README.md`](../../../deploy/inference-python/README.md)

**完全独立进程，跟 Java 后端解耦**。

```bash
cd deploy/inference-python

python -m venv .venv
.\.venv\Scripts\activate           # Windows
# source .venv/bin/activate         # macOS / Linux

pip install -r requirements.txt

cp .env.example .env
# 编辑 .env：
#   - TEXT_BASE_MODEL_PATH    基座 RoBERTa（HF repo 或本地路径）
#   - TEXT_CHECKPOINT_PATH    权重路径（legacy 兜底 or ml/checkpoints/{ver}/best.pth）

uvicorn main:app --host 0.0.0.0 --port 18000 --env-file .env
```

**Python 端未启也不阻断后端启动**：后端 IInferenceClient 调用超时会返回 `DETECT_INFERENCE_ERROR`，前端有兜底展示。

---

## 端 3 · 前端 → 详见 [`web/README.md`](../../../web/README.md) 与 [`mobile-uniapp/README.md`](../../../mobile-uniapp/README.md)

### Web（C 端 + 运营后台）

```bash
cd web
npm install
npm run dev       # 端口 5173，vite proxy /api → http://localhost:18080
```

访问：
- C 端 `http://localhost:5173/#/`
- 运营后台 `http://localhost:5173/#/admin`（登录 admin/admin 派 OPS_ADMIN）

### Mobile-uniapp（H5 + 微信小程序）

```bash
cd mobile-uniapp
npm install

npm run dev:h5           # H5，默认端口 5175
npm run dev:mp-weixin    # 产物在 unpackage/dist/dev/mp-weixin/，用微信开发者工具打开
```

**前端未连后端也能跑**：`VITE_API_BASE` 空时自动走 mock 数据。

---

## 联调排查（三端各自可探测）

| 端 | 探测方式 |
|---|---|
| Java 后端 | `curl http://localhost:18080/api/v1/detect/health` → 返 Python 端 health |
| Python 推理 | `curl http://localhost:18000/health` → `text.backend = "real" \| "stub"` + `load_error` |
| Web 前端 | 浏览器 devtools Network 看是否 200 |
| Mobile H5 | 同上，端口 5175 |

任何一端出问题，只需重启该端；其它端不受影响。

## 回滚

本版为 baseline，不提供 undo SQL。清理：`DROP DATABASE ry-vue` 重来。
