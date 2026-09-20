# backend-java · Java 后端

独立可启动。跟前端（web / mobile-uniapp）、Python 推理端（deploy/inference-python）**互不耦合**，各自本地进程各自跑。

## 依赖

- JDK 21（若依 Vue-Plus 5.x 要求）
- Maven 3.9+
- MySQL 8.x（本地 / 局域网，端口自定）
- Redis 7（若依 Sa-Token 依赖）

## 目录

```
backend-java/
├── README.md                  ← 本文
├── RUOYI_INTEGRATION.md       ← 若依基座详细集成指南（可选阅读）
├── business-modules/          ← 只保留业务模块，不含若依基座代码
│   ├── ruoyi-detect/          ← 检测任务编排 · Auth mock · 反馈 · 运营后台
│   └── ruoyi-inference/       ← gRPC proto + 客户端骨架（Python 端接入前保留）
└── scripts/
    └── patch-schema.sql       ← 当前累计的全量 schema 快照（本地一键；增量走 docs/releases/*/sql/）
```

## 启动步骤（手动 · 三端独立不共脚本）

### 1. 准备若依基座（一次性）

任选国内 / GitHub 源 clone 到本机任意目录（**不入本仓库**）：

```bash
git clone https://gitee.com/dromara/RuoYi-Vue-Plus.git -b 5.X ~/workspace/RuoYi-Vue-Plus
```

### 2. 挂载业务模块

拷贝或软链两个业务模块到基座的 `ruoyi-modules/`：

```bash
# Linux/macOS/WSL 软链
ln -s $(pwd)/business-modules/ruoyi-detect    ~/workspace/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-detect
ln -s $(pwd)/business-modules/ruoyi-inference ~/workspace/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-inference

# Windows PowerShell（需管理员或开发者模式）
New-Item -ItemType SymbolicLink -Path ~/workspace/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-detect    -Target (Resolve-Path ./business-modules/ruoyi-detect)
New-Item -ItemType SymbolicLink -Path ~/workspace/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-inference -Target (Resolve-Path ./business-modules/ruoyi-inference)
```

### 3. Patch 基座 pom

`~/workspace/RuoYi-Vue-Plus/ruoyi-modules/pom.xml` 的 `<modules>` 追加：

```xml
<module>ruoyi-detect</module>
<module>ruoyi-inference</module>
```

`~/workspace/RuoYi-Vue-Plus/ruoyi-admin/pom.xml` 追加依赖：

```xml
<dependency>
  <groupId>org.dromara</groupId>
  <artifactId>ruoyi-detect</artifactId>
  <version>${revision}</version>
</dependency>
```

> **无需改 DromaraApplication.java**：`business-modules/ruoyi-detect` 通过 Spring Boot 3 AutoConfiguration SPI（`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` → `DetectAutoConfiguration`）自动扫描 `com.paperaigc.detect.*`。

### 4. 初始化数据库

先跑若依 `sys_*` 全套（`RuoYi-Vue-Plus/script/sql/ry_vue_5.X.sql`）；再跑本项目 baseline：

```bash
# 增量迁移（规范化路径，推荐）
mysql -uroot -p ry-vue < ../docs/releases/v0.1.0/sql/V0.1.0.001__init_ops_backend_schema.sql
mysql -uroot -p ry-vue < ../docs/releases/v0.1.0/sql/V0.1.0.002__init_detect_task_schema.sql
mysql -uroot -p ry-vue < ../docs/releases/v0.1.0/sql/R__seed_scenario_threshold.sql

# 或全量快照一键（首次搭本地时更快）
mysql -uroot -p ry-vue < scripts/patch-schema.sql
```

### 5. 启动

```bash
cd ~/workspace/RuoYi-Vue-Plus
mvn -pl ruoyi-admin -am spring-boot:run
# 默认端口 8080；配置在 ruoyi-admin/src/main/resources/application.yml
```

## 与其它端的通信

- **前端 → 后端**：HTTP。前端 dev server 走 vite proxy `/api → http://localhost:8080`
- **后端 → Python 推理**：HTTP。`application-dev.yml` 里 `platform.inference.host/port` 指到 Python 端（默认 `localhost:18000`）
- **Python 推理端启动完全独立**，见 `deploy/inference-python/README.md`

## 分层规范

Controller → Service (I+Impl) → Repository (I+Impl) 三层，数据用 DTO / VO / Entity 分离，异常走 `ErrorCode` enum + `BizException` + `GlobalExceptionHandler`。详见业务模块内 package 结构：

```
com.paperaigc.detect/
├── common/{constant,enums,exception,util}
├── config/DetectAutoConfiguration
├── controller/     ← 只做参数装配 + 调 Service + 返 R
├── domain/{entity,dto,vo}
├── repository/     ← 内存实现；Phase B 换 MyBatis-Plus 只换 impl 不改上层
└── service/        ← 业务规则、事务、跨依赖编排
```

## 联调排查

- 后端启动后：`GET http://localhost:8080/api/v1/detect/health` → 返回 Python 端 health（推理未启也返回，含错误信息）
- 登录：`POST /api/v1/auth/login` `{username: "admin", password: "admin"}` → `admin/admin` 派 OPS_ADMIN 可进 `/admin/*`；其它派 USER
- 上传：`POST /api/v1/detect/submit` multipart（file + scenario + userId）
