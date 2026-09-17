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

1. 先导入若依自带的 `sys_*` 初始化脚本（RuoYi-Vue-Plus/script/sql/）
2. 再导入本仓库业务表：`doc/sql/init.sql` 中 **除 sys_org / sys_user 之外的所有表**（paper / detect_task / detect_paragraph_result / detect_sentence_result / humanize_task / report / credit_* / payment_order / model_version）
   - `sys_org` → 用若依的 `sys_dept`（组织树语义一致）
   - `sys_user` → 用若依自带（字段更全），`student_no` 加为扩展字段：
     ```sql
     ALTER TABLE sys_user ADD COLUMN student_no VARCHAR(32) NULL COMMENT '学号';
     ALTER TABLE sys_user ADD COLUMN degree_type VARCHAR(20) NULL COMMENT '学位类型';
     ```
3. `audit_log` → 用若依自带 `sys_oper_log`（`@Log` 注解自动写入），本表删除

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
