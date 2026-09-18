# v0.1.0 · 升级手册

从零/无版本状态升级到 baseline。

## 前置

- MySQL 8.x（本地 / 内网）
- Java 21 + Maven（本地跑若依基座）
- Node 20 + pnpm（跑 web / plus-ui）
- Python 3.10+（跑 inference）

## 步骤

### 1. 拉基座 + 挂业务模块

```bash
cd backend-java
bash scripts/setup-ruoyi.sh   # Linux/macOS/WSL
# 或 Windows：
powershell -ExecutionPolicy Bypass -File scripts/setup-ruoyi.ps1
```

### 2. 数据库初始化

**先跑若依 sys_* 全套**（由 `scripts/setup-ruoyi.sh` 完成 `RuoYi-Vue-Plus/script/sql/` 里的初始化）

**再按顺序跑本版 SQL**：

```bash
mysql -uroot -p ry-vue < docs/releases/v0.1.0/sql/V0.1.0.001__init_ops_backend_schema.sql
mysql -uroot -p ry-vue < docs/releases/v0.1.0/sql/V0.1.0.002__init_detect_task_schema.sql
mysql -uroot -p ry-vue < docs/releases/v0.1.0/sql/R__seed_scenario_threshold.sql
```

或直接跑合并快照（等效但一次到位，仅首次搭本地时推荐）：

```bash
mysql -uroot -p ry-vue < backend-java/scripts/patch-schema.sql
```

### 3. 后端启动

```bash
cd backend-java/.workspace/RuoYi-Vue-Plus
mvn -pl ruoyi-admin -am spring-boot:run
# 端口 18080（对齐 web/.env）
```

### 4. 前端启动

```bash
# Web C 端 + 运营后台
cd web
npm install
npm run dev   # 端口 5173

# mobile-uniapp（H5 / 微信小程序）
cd mobile-uniapp
npm install
npm run dev:h5           # H5 · 端口 5175
npm run dev:mp-weixin    # 微信小程序 · HBuilderX 打开 unpackage/dist/dev/mp-weixin
```

### 5. Python 推理

```bash
cd deploy/inference-python
python -m venv .venv
.\.venv\Scripts\activate            # Windows
pip install -r requirements.txt

cp .env.example .env                # 编辑 .env，填 TEXT_BASE_MODEL_PATH / TEXT_CHECKPOINT_PATH
uvicorn main:app --host 0.0.0.0 --port 18000 --env-file .env
```

**注意**：`TEXT_CHECKPOINT_PATH` 当前如指向 `models/text/aigc_detector_v3_thesis.pth` 为 legacy 兜底；
新一代模型训完后指向 `ml/checkpoints/text/v0.1.0-baseline/best.pth` 即可，无需改代码。

## 验证

- 后端健康：`GET http://localhost:18080/api/v1/detect/health` → 返回 Python 侧 health 结果
- 推理健康：`GET http://localhost:18000/health` → `text.backend = "real"` 表示真实模型加载成功
- Web 登录：admin / admin → 进 `#/admin` 可见运营后台
- mobile 登录：任意账号密码

## 回滚

本版为 baseline，不提供 undo SQL；如需清理，`DROP DATABASE ry-vue` 重来。
