# v0.1.0 · 若依基座 application-*.yml 配置补丁

业务模块 `ruoyi-detect` 通过 SPI 自动装配，但基座 `application-dev.yml` 的这几处配置需要
**手动 patch**（若依基座代码不入本仓库，我们无法自动覆盖）。

按需选一段合并到 `RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application-dev.yml`。

---

## 1. 平台推理服务连接（必需）

后端调 Python 推理的 host/port。默认值代码里已给 `localhost:18000`，配置显式声明更利于运维：

```yaml
platform:
  inference:
    host: ${INFERENCE_HOST:localhost}
    port: ${INFERENCE_PORT:18000}
    # 超时（HttpInferenceClient 内 hardcoded 15s，如需覆盖走系统属性）
```

对齐 [`deploy/inference-python/README.md`](../../../deploy/inference-python/README.md) 的默认监听端口。

---

## 2. Sa-Token 白名单兜底（推荐）

`AuthController` 已用类级 `@SaIgnore` 放行 `/api/v1/auth/**`，配置白名单是双重保险
（防止有人误删注解或 Sa-Token 版本升级注解语义变化）：

```yaml
sa-token:
  # 若依基座默认字段名可能是 excludes 或 exclude-urls，按实际版本对齐
  excludes:
    - /api/v1/auth/login
    - /api/v1/auth/logout
    - /api/v1/auth/me
    # 反馈 C 端提交 W3.c 登录接入前也放行；接入后收回
    - /api/v1/feedback
    # 上传检测 W3.c 前同上
    - /api/v1/detect/**
    # Python 端 health 探测
    - /api/v1/report/**
```

⚠ **W3.c 登录正式接入后**：把 `/api/v1/feedback`、`/api/v1/detect/**`、`/api/v1/report/**`
从 excludes 移除，改由 Sa-Token 正常校验 + Controller 上加 `@SaCheckPermission`。

---

## 3. 服务端口对齐（可选覆盖）

若基座 `server.port` 默认是 8080，改成 18080 与前端 vite proxy 对齐（如已改则忽略）：

```yaml
server:
  port: 18080
```

前端默认值：
- `web/vite.config.ts` → `apiTarget = 'http://localhost:18080'`（本版已改）
- `mobile-uniapp/manifest.json` → `h5.devServer.proxy["/api"].target = 'http://localhost:18080'`（本版已改）

---

## 4. 文件存储路径（可选覆盖）

`LocalFileSystemStorageService` 默认落到 `./storage/uploads/{yyyyMM}/{taskId}.{ext}`：

```yaml
platform:
  storage:
    local-root: ${STORAGE_ROOT:./storage}
```

生产切 MinIO 时新增 `MinioStorageService @Primary` 顶替此 bean 即可，配置项无需改。

---

## 5. MyBatis-Plus 表映射（Phase B）

Phase A 走内存态未接 DB。Phase B 启用 MyBatis 时补：

```yaml
mybatis-plus:
  mapper-locations: classpath*:mapper/**/*.xml
  type-aliases-package: com.paperaigc.detect.domain.entity
  configuration:
    map-underscore-to-camel-case: true
```
