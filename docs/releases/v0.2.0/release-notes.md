# v0.2.0 · Phase B · MyBatis-Plus 落库（滚动）

**发布状态**：🚧 滚动中（每 batch 独立发布，全部完成后打 tag）

## 概要

Phase A 定的 5 件套（Controller → Service → Repository → Entity / DTO / VO）跑起来后，
Phase B 把 InMemoryRepository 逐一替换为 MyBatis-Plus 实现，数据真正落 MySQL。
Repository 用 `@Primary` 顶掉 InMemory，Service / Controller 零改动。

## Batch 进度

| Batch | 主题 | 状态 |
|---|---|---|
| B1 | Feedback → user_feedback 表 | ✅ 完成（commit 7439204） |
| B2 | Admin User → 新建 user_profile 表 | ✅ 完成（本版）|
| B3 | Detect 三表 · detect_task / paragraph / sentence | ⏳ |
| B4 | Scenario Threshold → detect_scenario_threshold + Caffeine 5min 缓存 | ⏳ |

## B2 · 本版改动

### 新增文件

- `mapper/AdminUserMapper.java` · `BaseMapper<AdminUser>` 空接口
- `repository/impl/MybatisAdminUserRepository.java` · `@Primary` 顶掉 InMemory
- `docs/releases/v0.2.0/sql/V0.2.0.001__init_user_profile.sql` · 建表 + 3 索引
- `docs/releases/v0.2.0/sql/R__seed_user_profile_demo.sql` · 6 条 demo seed（幂等）

### 改动文件

- `domain/entity/AdminUser.java` · 加 `@TableName("user_profile") + @TableId(AUTO)`
- `backend-java/scripts/patch-schema.sql` · 追加 user_profile 全量快照

### 决策

- **独立 user_profile 表**（不扩若依 sys_user）：
  sys_user 是后台运营账号；user_profile 是 C 端手机/微信/邮箱注册用户，语义分离
- **类名 AdminUser 保留**：Phase A 早期误命名，重命名为 UserProfile 需大改，Phase C 统一
- **seed 数据幂等**：`ON DUPLICATE KEY UPDATE` · 每次部署都跑保证 demo 一致

## 升级步骤

```bash
mysql -uroot -p ry-vue < docs/releases/v0.2.0/sql/V0.2.0.001__init_user_profile.sql
mysql -uroot -p ry-vue < docs/releases/v0.2.0/sql/R__seed_user_profile_demo.sql
```

后端重启后：
- `GET /admin/user/list` 走 MyBatis 从 user_profile 读
- ban/unban 也走 DB `UPDATE`

InMemory 实现（`InMemoryAdminUserRepository`）保留不动，Spring 因 `@Primary`
优先注入 Mybatis 版本；Phase B 全 4 batch 跑通后一次性删除 InMemory 3 份实现。

## Breaking

无。Service 层零改动，Controller 零改动，前端零改动。
