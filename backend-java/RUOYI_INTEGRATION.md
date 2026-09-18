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

`ruoyi-admin/src/main/resources/application-dev.yml` 追加：

```yaml
platform:
  inference:
    host: ${INFERENCE_HOST:localhost}
    port: ${INFERENCE_PORT:9090}
    deadline-seconds: 10

resilience4j:
  circuitbreaker:
    instances:
      inference:
        sliding-window-size: 20
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10s
```

文件存储用若依自带 OSS 模块（`ruoyi-common-oss`），在管理后台「系统管理 → 文件配置」里配 MinIO 即可，**不需要自己写 MinIO client**。

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
