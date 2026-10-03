# RuoYi-Vue-Plus 集成指南

> 后端基座采用 **RuoYi-Vue-Plus 5.x**（Spring Boot 3 + Java 17/21 + MyBatis-Plus + Sa-Token + Redisson）。
> 本目录只保留**业务模块**（`business-modules/`），若依基座代码不入本仓库，通过以下步骤挂载。

## 1. 获取基座

```bash
# Gitee（国内推荐）
git clone https://gitee.com/dromara/RuoYi-Vue-Plus.git -b 5.X
# 或 GitHub
git clone https://github.com/dromara/RuoYi-Vue-Plus.git -b 5.X
```

前端管理端（自带 Vue3 + Element Plus）：

```bash
git clone https://gitee.com/JavaLionLi/plus-ui.git
```

## 2. 挂载业务模块

1. 把 `business-modules/ruoyi-detect` 和 `business-modules/ruoyi-inference` 拷贝（或软链）到 `RuoYi-Vue-Plus/ruoyi-modules/` 下
2. 在 `ruoyi-modules/pom.xml` 的 `<modules>` 中追加：

```xml
<module>ruoyi-detect</module>
<module>ruoyi-inference</module>
```

3. 在 `ruoyi-admin/pom.xml` 添加依赖：

```xml
<dependency>
    <groupId>org.dromara</groupId>
    <artifactId>ruoyi-detect</artifactId>
    <version>${revision}</version>
</dependency>
```

4. 两个模块 pom 里的 `<parent><version>5.2.3</version></parent>` 改成你 clone 到的实际版本（`revision` 属性值）

## 3. 数据库

C 端定位（个人用户，非校园 SaaS），跟 `docs/design/OPERATIONS_REQUIREMENTS.md §5` 对齐：

1. 先导入若依自带的 `sys_*` 全套初始化脚本（RuoYi-Vue-Plus/script/sql/）
2. 再导入本仓库业务表 —— 用 `scripts/patch-schema.sql` 一键跑：
   - 保留：`paper / detect_task / detect_paragraph_result / detect_sentence_result / humanize_task / report`
   - 新增（Wave 3 运营后台配套）：`user_feedback / detect_scenario_threshold / model_version / user_abnormal_flag`
   - 场景阈值初始数据（本科 20 / 硕士 15 / 博士 10 / 职业报告 15 / 自媒体 30 / 其他 25）随建表插入
3. `sys_user` 直接用若依自带（不再加 `student_no / degree_type`，C 端产品不需要）
4. `sys_org / sys_dept` 只做后台角色隔离用，不承载教师/院系语义
5. `audit_log` → 若依自带 `sys_oper_log`（`@Log` 注解自动写入），业务侧删除

> ⚠️ 老版 `docs/sql/init.sql` 里的 `sys_org / sys_user / STUDENT|TEACHER` 那批 B2B 字段在 C 端定位下已弃用，仅作历史参考，不要执行。

## 4. 配置

### 4.1 `platform.*` 平台业务配置 —— **无需手工改基座文件**

默认值统一放在 **`business-modules/ruoyi-detect/src/main/resources/platform-defaults.yml`**，
由 `PlatformDefaultsEnvironmentPostProcessor` 在 Environment 准备阶段以 `addLast` 追加
（优先级最低，任何 `application.yml` / profile / 环境变量都能覆盖）。

覆盖的键：

```yaml
platform:
  inference:
    host: ${INFERENCE_HOST:localhost}
    port: ${INFERENCE_PORT:8000}
    deadline-seconds: ${INFERENCE_DEADLINE_SECONDS:15}   # HttpInferenceClient 单次请求超时
  storage:
    local-root: ${STORAGE_LOCAL_ROOT:./storage}          # LocalFileSystemStorageService
  assistant:
    base-url: ${ASSISTANT_BASE_URL:http://localhost:8000}
    rate-per-minute: ${ASSISTANT_RATE_PER_MINUTE:8}
    rate-per-day: ${ASSISTANT_RATE_PER_DAY:100}
    stream-timeout-seconds: ${ASSISTANT_STREAM_TIMEOUT_SECONDS:120}
```

> ⚠️ 键名必须与代码里 `@Value("${platform.*}")` 的读取路径一致。
> 历史上这里踩过坑：`platform.storage.local-path` 曾经被写进配置文件，而
> `LocalFileSystemStorageService` 读的是 `platform.storage.local-root` —— 死键，静默失效。

**加载方式（两种后端形态都覆盖）**：`PlatformDefaultsEnvironmentPostProcessor` 由
`ruoyi-detect/src/main/resources/META-INF/spring.factories` 注册（`spring.factories` 而非
`AutoConfiguration.imports` —— 前者在 Environment 准备阶段就执行，后者太晚）。

⚠️ 该 `spring.factories` 在 `standalone-app/src/main/resources/META-INF/` 下有**一份内容一致的副本**，
两处必须同步修改：`standalone-app/pom.xml` 的 build-helper 把 `ruoyi-detect` 的 `src/main/resources`
一并纳入本模块资源，而 Maven 资源拷贝是「后写覆盖前写」，两份同名文件内容不一致时会静默丢掉一份。
（build-helper 只排除 `META-INF/spring/**`，所以 `AutoConfiguration.imports` 在 standalone 里确实
被排除了，改由 `@SpringBootApplication` 组件扫描兜底 —— 这正是 standalone 需要的形态；
`META-INF/spring.factories` 不在排除范围内，因此两份同名文件会互相覆盖，必须保持一致。）

**为什么不用手改 `ruoyi-admin/src/main/resources/application-dev.yml`**：

1. `deploy/docker-compose.yml` 用 `SPRING_PROFILES_ACTIVE=prod` 启动，**dev profile 根本不加载**，
   写在里面的 `platform.inference.*` 在容器里从来不会生效；
2. `ruoyi-admin/src/main/resources` 属于若依基座，本仓库只保留业务模块，
   部署镜像里的基座是 clone 来的 —— 改本地基座副本不会被带进镜像；
3. `platform.assistant.*` / `platform.storage.*` 在若依态从未被声明过，
   原先只能靠 `@Value` 的行内兜底值，不可审查也无法在部署前发现写错。

### 4.2 文件存储

`LocalFileSystemStorageService` 是当前生效的实现（不装 MinIO 也能跑），
落盘路径 = `platform.storage.local-root` + `/uploads/{yyyyMM}/{taskId}.{ext}`。

容器里 `deploy/docker-compose.yml` 已固定 `PLATFORM_STORAGE_LOCAL_ROOT=/app/storage`
并挂载命名卷 `backend_storage` —— **不挂卷的话论文原件落在容器可写层，重建即丢**。

若改用若依自带 OSS 模块（`ruoyi-common-oss`），在管理后台「系统管理 → 文件配置」里配 MinIO 即可，
新增 `MinioStorageService @Primary` 顶替现有 bean，业务代码零改动。

### 4.3 熔断（可选，尚未接线）

`HttpInferenceClient` 目前是全阻塞实现，没有熔断 / 重试。若要启用，在基座引入 resilience4j 后加：

```yaml
resilience4j:
  circuitbreaker:
    instances:
      inference:
        sliding-window-size: 20
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10s
```

注意 `platform.inference.deadline-seconds` 此前是**死配置**（客户端硬编码 15s），
现已改为真正读取该键 —— 超时行为可从配置调整。

## 5. 权限与菜单

- 检测相关权限字符建议：`detect:task:submit` / `detect:task:query` / `detect:task:retry` / `humanize:task:submit`
- Controller 上用 Sa-Token 注解：`@SaCheckPermission("detect:task:submit")`
- 菜单 SQL 在业务开发时用若依代码生成器一并产出

## 6. 与手搭骨架的映射（历史参考）

| 手搭模块（已删除） | 若依替代 |
|---|---|
| platform-common `R` / `ErrorCode` / `BizException` | `org.dromara.common.core.domain.R` / `ServiceException` |
| platform-security JWT / SecurityConfig | Sa-Token（登录、权限、踢人下线全自带） |
| platform-user | `ruoyi-system` 的 sys_user / sys_dept / sys_role |
| platform-audit | `@Log` 注解 + sys_oper_log |
| platform-api-web 启动类 | `ruoyi-admin` |
| platform-detect | **→ business-modules/ruoyi-detect（保留）** |
| platform-inference | **→ business-modules/ruoyi-inference（保留）** |

## 7. 已知适配点

- `DetectionInferenceClient` 已改用 `org.dromara.common.core.exception.ServiceException`
- gRPC proto 在 `ruoyi-inference/src/main/proto/detection.proto`，`mvn compile` 自动生成 stub（需要网络拉 protoc）
- Java 21 虚拟线程：RuoYi-Vue-Plus 5.2+ 支持 `spring.threads.virtual.enabled=true`
- 若依的 `ruoyi-common-encrypt` 可直接用于论文文件字段加密（替代自写 AES 逻辑）
- 启动类 `DromaraApplication` 需改 `@SpringBootApplication(scanBasePackages = {"org.dromara", "com.paperaigc"})`，否则 `com.paperaigc` 业务包不被扫描
- 开发机用 WSL 跑 Redis（16379）时，启动类内置 `startRedisInWsl()` 自动拉起；可删 `DromaraServletInitializer` 按独立 jar 启动
- `application.yml` 已加开发阶段 API 白名单兜底：`/api/v1/auth/login`、`/api/v1/auth/logout`、`/api/v1/auth/me`、`/api/v1/feedback`、`/api/v1/detect/**`、`/api/v1/report/**`（W3.c 登录接入后收回，改 `@SaCheckPermission`）
- `application-dev.yml` 本地适配：`snail-job.enabled=false` 关闭分布式调度、exclude `RateLimiterAutoConfiguration`（与若依 `rateLimiterAspect` 冲突）、Redis `16379/123456`
