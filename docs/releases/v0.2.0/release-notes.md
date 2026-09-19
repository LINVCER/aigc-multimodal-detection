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
| B2 | Admin User → 新建 user_profile 表 | ✅ 完成（commit b7e7061）|
| B3 | Detect 三表 · detect_task / paragraph / sentence + 音频列 | ✅ 完成（commit bf3f6c2）|
| B4 | Scenario Threshold → detect_scenario_threshold + Caffeine 5min 缓存 | ✅ 完成（本版）· Phase B 收官 |

## B4 · 本版改动

### 新增文件

- `domain/entity/ScenarioThreshold.java` · `@TableName("detect_scenario_threshold")` · PK 是 scenario 字符串
- `mapper/ScenarioThresholdMapper.java` · `BaseMapper<ScenarioThreshold>`
- `repository/IScenarioThresholdRepository.java` · `findByScenario / findAllEnabled / update`
- `repository/impl/MybatisScenarioThresholdRepository.java` · `@Primary` · 唯一实现（无 InMemory 对应）
- `service/IScenarioThresholdService.java` · `threshold / label / listAll / updateThreshold / invalidateCache`
- `service/impl/ScenarioThresholdServiceImpl.java` · Caffeine 5 分钟 TTL · maxSize 20 · @PostConstruct 预热

### 改动文件

- `service/impl/DetectTaskServiceImpl.java` · 注入 `IScenarioThresholdService` · `ScenarioConstants.threshold(sc)` → `scenarioThresholdService.threshold(sc)`（submitText + submitAudio 共 2 处）
- `controller/ReportController.java` · 注入 `IScenarioThresholdService` · `ScenarioConstants.label(scenario)` → `scenarioThresholdService.label(scenario)`
- `backend-java/business-modules/ruoyi-detect/pom.xml` · 加 `com.github.ben-manes.caffeine:caffeine:3.1.8`

### 关键决策

- **Caffeine 手工 Cache 实例**（不用 Spring `@Cacheable`）：避免 `@EnableCaching` 全局副作用，逻辑更直接
- **DB 空/miss 兜底 ScenarioConstants**：保证 seed 缺失或 DB 未就绪时 detect 不崩溃
- **无 InMemory 对应实现**：原本走硬编码常量，Repository 直接一份 MyBatis 实现即可；`ScenarioConstants` 保留作 fallback 常量类
- **PK 是 scenario 字符串**（不是自增 Long）：6 场景固定，PK 用业务码可读性 > 匿名 id

## Phase B 收官

| Batch | 表 | 关键 |
|---|---|---|
| B1 | user_feedback | 5 件套跑通模式 |
| B2 | user_profile（新建） | C 端用户跟 sys_user 分离 |
| B3 | detect_task + paragraph_result + sentence_result | JSON TypeHandler + 主子表事务 |
| B4 | detect_scenario_threshold | Caffeine 缓存 + 运营可改阈值 |

**InMemory 实现清理**：4 batch 全部 `@Primary` 顶掉后，`InMemoryFeedbackRepository / InMemoryAdminUserRepository / InMemoryDetectTaskRepository` 三份仍在，Spring 因 `@Primary` 优先注 Mybatis 版本，功能不受影响。规划下 batch 统一删除 InMemory + 打 v0.2.0 tag 收尾。

## B3 · 本版改动

### 新增文件

- `mapper/DetectTaskMapper.java` · `BaseMapper<DetectTask>` 主表
- `mapper/DetectParagraphResultMapper.java` · 段级子表
- `mapper/DetectSentenceResultMapper.java` · 句级子表
- `repository/impl/MybatisDetectTaskRepository.java` · `@Primary` · 三表事务
- `docs/releases/v0.2.0/sql/V0.2.0.002__add_detect_task_audio.sql` · 补 modality + audio_duration_sec + audio_segments_json 列 + idx_modality_time

### 改动文件

- `domain/entity/DetectTask.java` · `@TableName(autoResultMap=true)` + `@TableId(AUTO)` + `@TableField(typeHandler=JacksonTypeHandler.class)` 给 sourceLabels/audioSegments · paragraphs 加 `@TableField(exist=false)`
- `domain/entity/ParagraphResult.java` · `@TableName + @TableId + taskId 外键 + JacksonTypeHandler` 给 confidenceInterval/warnings · sentences 加 `exist=false`
- `domain/entity/SentenceResult.java` · `@TableName + @TableId + taskId/paragraphIdx 外键`
- `backend-java/scripts/patch-schema.sql` · detect_task 全量快照补音频列

### 关键决策

- **JSON 字段走 `JacksonTypeHandler`**（MyBatis-Plus 自带；跟项目 Jackson 生态一致）：
    · `detect_task.source_labels_json` ← `Map<String, Double>`
    · `detect_task.audio_segments_json` ← `List<AudioSegmentResult>`（不建独立表 · 数据量小 · 只在详情展示）
    · `detect_paragraph_result.confidence_interval` ← `Object`
    · `detect_paragraph_result.warnings_json` ← `List<String>`
- **段/句独立子表**（用户量大 · 需按 task_id 查询）· 事务边界靠 `@Transactional` 覆盖
- **save/update 段/句"删旧插新"**：策略简单，写放大不严重（每 task 段一般 <100）；生产按 idx 差量更新
- **findAll 只查主表**：段/句不加载，列表接口性能优先
- **findById 分两次拉**（主表 + 段全量 + 句全量），Service 层内存组装；生产量大改一次 JOIN + resultMap

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
