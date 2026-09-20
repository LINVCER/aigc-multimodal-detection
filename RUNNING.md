# 论文 AIGC 检测平台 · 本地运行指南

项目三端独立架构，各自独立启动，互不耦合。

```
前端（web / mobile-uniapp） ──HTTP──▶ Java 后端（RuoYi-Vue-Plus） ──HTTP──▶ Python 推理
     :5173 / :5175                        :8080                            :18000
```

---

## 一、环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| JDK | 21 | 若依 Vue-Plus 5.x 要求 |
| Maven | 3.9+ | |
| MySQL | 8.x | 数据库 `ry-vue`，用户 `root`，密码留空 |
| Redis | 7 | 端口 `16379`，密码 `123456` |
| Node.js | 18+ | 前端构建 |
| Python | 3.10+ | 推理服务（可选，不跑推理可不启） |

---

## 二、后端启动

### 2.1 克隆若依基座（一次性）

```bash
git clone https://gitee.com/dromara/RuoYi-Vue-Plus.git -b 5.X D:/AAA/RuoYi-Vue-Plus
```

### 2.2 挂载业务模块

**Windows PowerShell（管理员模式）：**

```powershell
cd D:\AAA\image_nious\backend-java

New-Item -ItemType SymbolicLink -Path D:\AAA\RuoYi-Vue-Plus\ruoyi-modules\ruoyi-detect    -Target D:\AAA\image_nious\backend-java\business-modules\ruoyi-detect
New-Item -ItemType SymbolicLink -Path D:\AAA\RuoYi-Vue-Plus\ruoyi-modules\ruoyi-inference -Target D:\AAA\image_nious\backend-java\business-modules\ruoyi-inference
```

### 2.3 Patch 基座 Maven 配置

编辑 `D:\AAA\RuoYi-Vue-Plus\ruoyi-modules\pom.xml`，在 `<modules>` 中追加：

```xml
<module>ruoyi-detect</module>
<module>ruoyi-inference</module>
```

编辑 `D:\AAA\RuoYi-Vue-Plus\ruoyi-admin\pom.xml`，追加依赖：

```xml
<dependency>
  <groupId>org.dromara</groupId>
  <artifactId>ruoyi-detect</artifactId>
  <version>${revision}</version>
</dependency>
```

### 2.4 初始化数据库

确保 MySQL 运行中，先执行若依基座的全套 SQL：

```bash
# 执行若依官方建表脚本
mysql -uroot -p < D:\AAA\RuoYi-Vue-Plus\script\sql\ry_vue_5.X.sql
```

再执行项目增量迁移脚本：

```bash
mysql -uroot -p ry-vue < D:\AAA\image_nious\docs\releases\v0.1.0\sql\V0.1.0.001__init_ops_backend_schema.sql
mysql -uroot -p ry-vue < D:\AAA\image_nious\docs\releases\v0.1.0\sql\V0.1.0.002__init_detect_task_schema.sql
mysql -uroot -p ry-vue < D:\AAA\image_nious\docs\releases\v0.1.0\sql\R__seed_scenario_threshold.sql
mysql -uroot -p ry-vue < D:\AAA\image_nious\docs\releases\v0.2.0\sql\V0.2.0.001__init_user_profile.sql
mysql -uroot -p ry-vue < D:\AAA\image_nious\docs\releases\v0.2.0\sql\V0.2.0.002__add_detect_task_audio.sql
mysql -uroot -p ry-vue < D:\AAA\image_nious\docs\releases\v0.2.0\sql\R__seed_user_profile_demo.sql
mysql -uroot -p ry-vue < D:\AAA\image_nious\docs\releases\v0.2.0\sql\R__seed_detect_task_demo.sql
```

### 2.5 启动

```bash
cd D:\AAA\RuoYi-Vue-Plus
mvn -pl ruoyi-admin -am spring-boot:run "-Dspring-boot.run.jvmArguments=-Dspring.main.allow-bean-definition-overriding=true" -DskipTests
```

> `-Dspring.main.allow-bean-definition-overriding=true` 解决 bean 冲突（rateLimiterAspect）。

启动成功后访问：
- 后端端口：`http://localhost:8080`
- 健康检查：`GET http://localhost:8080/api/v1/detect/health`

---

## 三、Python 推理服务（可选）

```bash
cd D:\AAA\image_nious\deploy\inference-python

# 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置模型路径（首次）
copy .env.example .env

# 启动（端口 18000）
uvicorn main:app --host 0.0.0.0 --port 18000 --env-file .env
```

不启动推理服务，后端 health 接口会返回错误信息但不影响启动。

---

## 四、前端启动

### 4.1 Web 前端（PC 浏览器）

```bash
cd D:\AAA\image_nious\web
npm install
npm run dev
```

访问：`http://localhost:5173`

代理配置见 `web/vite.config.ts`：`/api` → `http://127.0.0.1:8080`

### 4.2 移动端（H5）

```bash
cd D:\AAA\image_nious\mobile-uniapp
npm install
npm run dev:h5
```

访问：`http://localhost:5175`

### 4.3 移动端（微信小程序）

```bash
cd D:\AAA\image_nious\mobile-uniapp
npm run dev:mp-weixin
```

产物在 `dist/dev/mp-weixin/`，用微信开发者工具打开。

---

## 五、联调验证

### 5.1 后端启动验证

```bash
# 健康检查
curl http://localhost:8080/api/v1/detect/health

# 登录（管理员 admin/admin123）
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 查询任务列表
curl http://localhost:8080/api/v1/detect/tasks?pageNum=1&pageSize=10 \
  -H "Authorization: Bearer <token>"
```

### 5.2 账号

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | 管理员（可访问运营后台） |
| testuser | test123 | 普通用户 |

种子数据中还包含更多测试用户，详见 `docs/releases/v0.2.0/sql/R__seed_user_profile_demo.sql`。

### 5.3 管理端入口

Web 前端登录管理员账号后访问 `/admin/*` 路径：
- 运营仪表盘：`http://localhost:5173/#/admin/dashboard`
- 用户管理：`http://localhost:5173/#/admin/users`
- 任务管理：`http://localhost:5173/#/admin/tasks`
- 反馈管理：`http://localhost:5173/#/admin/feedback`

---

## 六、常见问题

### 6.1 Vite 代理报 ECONNREFUSED

确保后端 Java 进程已启动在 `8080` 端口。如果后端用了不同端口，修改 `web/.env` 或设置环境变量：

```bash
# Windows PowerShell
$env:VITE_API_TARGET="http://127.0.0.1:你的端口"
npm run dev
```

### 6.2 登录接口 404

检查是否配置了 Sa-Token 白名单。`backend-java/business-modules/ruoyi-detect` 的 AuthController 类头需要 `@SaIgnore` 注解。

### 6.3 Maven 构建失败（parent POM 版本冲突）

检查 `business-modules/ruoyi-detect/pom.xml` 和 `ruoyi-inference/pom.xml` 中 `<parent><version>` 必须为 `${revision}` 而非具体版本号。

### 6.4 Bean 冲突 (rateLimiterAspect)

启动参数中必须包含 `-Dspring.main.allow-bean-definition-overriding=true`。

### 6.5 健康检查返回 500

通常是 Python 推理服务未启动。如果不需要推理，可以忽略此错误——任务提交等功能会 fallback 报错。

### 6.6 npm 报 ENOENT

当前工作目录不对。确保 `cd` 到了 `package.json` 所在目录：

```bash
cd D:\AAA\image_nious\web          # Web 前端
cd D:\AAA\image_nious\mobile-uniapp # 移动端
```

### 6.7 端口被占用

```powershell
# 查找占用端口的进程
netstat -ano | findstr :8080

# 终止进程
Stop-Process -Id <PID> -Force
```

### 6.8 数据库连接失败

确认 `D:\AAA\RuoYi-Vue-Plus\ruoyi-admin\src\main\resources\application-dev.yml` 中：
- `spring.datasource.dynamic.datasource.master.url` 指向 `jdbc:mysql://localhost:3306/ry-vue`
- `username` / `password` 与本机 MySQL 一致
- `spring.data.redis.host/port/password` 与本机 Redis 一致

---

## 七、项目结构速览

```
D:\AAA\image_nious\
├── web/                    Vue 3 + Vite + TS · PC 端（:5173）
├── mobile-uniapp/          uni-app · H5 + 微信小程序（:5175）
├── mobile-app/             React Native + Expo · iOS/Android 原生
├── backend-java/           业务模块（ruoyi-detect / ruoyi-inference）
│   └── scripts/patch-schema.sql   全量 schema 快照
├── deploy/inference-python/       FastAPI 推理服务（:18000）
├── ml/                     新一代模型训练（与 legacy 分离）
├── legacy/                 老实验代码（只做参考）
├── docs/
│   ├── design/             架构设计 / API 契约 / 需求文档
│   └── releases/           版本文档 + Flyway SQL 迁移
└── deploy/                 生产部署文件（Docker / Nginx）
```