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

**InMemory 实现清理**：✅ 已删除
- `InMemoryFeedbackRepository.java` · `InMemoryAdminUserRepository.java` · `InMemoryDetectTaskRepository.java` 三份 git rm
- 3 处 Mybatis 类 + 2 处 Repository 接口的注释同步清理（去掉"顶掉 InMemory"字样，改为"@Primary 保留供 Phase C 引缓存层新实现"）
- `InMemoryAuthTokenRepository` 保留：Sa-Token mock 期专用不落 DB，Phase C Auth 走基座时整体删除

**Phase C 视野**：Sa-Token 接入 · @Cacheable / Redis 缓存 · IStorageService MinIO 实现 · 类名 rename（AdminUser → UserProfile）· 前端类型对齐后端 modality 分模态视图。

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

---

# 图像模态 · Java 后端接入（B5）

对照 `docs/design/202609-image-backend-integration-plan.md` 逐文件平移音频链路。
Python `/api/v1/detect/image` 端点未就绪前，`submit` 后 `runImageInference` 走 stub 兜底
（连不上 → STATUS_FAILED，不阻塞主流程）。Python 端补齐后 Java 侧无需再改。

### 新增文件

- `domain/entity/ImageSegmentResult.java` · `segmentIdx / x / y / w / h / aiProb / calibratedProb / sourceLabel`（整图=一个元素、bbox=null；未来接篡改/区域时同结构扩多元素）
- `docs/releases/v0.2.0/sql/V0.2.0.003__add_detect_task_image.sql` · 幂等 ALTER 加 `image_segments_json` JSON 列

### 改动文件

- `common/constant/DetectConstants.java` · `MODALITY_IMAGE` 去掉 Wave 5 注释 · 加 `FILE_SIZE_MAX_IMAGE (20MB)` / `ALLOWED_IMAGE_MIME` / `ALLOWED_IMAGE_EXT` · `guessModality()` 补 image 分支
- `service/IInferenceClient.java` · 加 `detectImage(byte[], String, boolean)` 契约
- `service/impl/HttpInferenceClient.java` · 实现 `detectImage`（POST `/api/v1/detect/image` · multipart + `return_regions`）· 抽通用 `buildFileMultipart(bytes, filename, flagName, flagValue, boundary)`，audio/image 共用
- `domain/entity/DetectTask.java` · 加 `imageSegments`（JacksonTypeHandler · `image_segments_json` JSON 列）
- `service/impl/DetectTaskServiceImpl.java` · `submit()` switch 加 image 分支 → `submitImage()`；新增 `runImageInference()` / `runImageInferenceBytes()`（共享 `fillImageResult()` 解析）；`retry()` 加 image 分支 + 清 `imageSegments`
- `domain/vo/DetectTaskDetailVO.java` · 加 `imageSegments` 字段 + `from()` 补 `.imageSegments(t.getImageSegments())`（列表 VO 不加，对齐 audio）
- `backend-java/scripts/patch-schema.sql` · `detect_task` 全量快照追加 `image_segments_json` 列

### 关键决策

- **结果形态用 `List<ImageSegmentResult>`（推荐方案 A）**：整图单结果时列表长度为 1 且 bbox 为 null；未来接篡改/区域定位不用改 schema，与 audio segments 结构对称，前端按 `modality` 分渲染路径
- **Python 契约 key = `regions` / `return_regions`**：语义比 `segments` 更贴合图像（区域 vs 时序片段）· 与音频 `segments` / `return_segments` 平行
- **无独立子表**：对齐 audio 走 JSON 单列，避免小数据量表膨胀
- **Python 端点未就绪不阻塞 Java 上线**：`detectImage` catch-all → STATUS_FAILED，主流程照跑
- **modelVersion 硬编码 `image-stub-v0`**：模型接入后由 Python 侧回填 `model_version` 字段，Java 侧再切读远端值

### 前置依赖

- ⏳ Python `/api/v1/detect/image` 端点（推理侧独立 PR，Java 侧无需再动）
- ⏳ 前端 `image.vue` 结果页面按 imageSegments 结构渲染（整图 vs 多区域视图）· 本轮不动

---

# mobile-uniapp · Wave 2/3/4 联发

Phase B 落库同期，mobile-uniapp 走完 completion-plan 里的 3 个 Wave，v0.5.0 端上生产就绪。

## Wave 2 · 契约补齐

- **task 生命周期**：`api/detect.js` +cancelTask/deleteTask；`pages/index/index.vue` 长按弹窗 → 撤销/删除
- **报告 PDF 下载**：`api/report.js` 新建 · H5 走 fetch blob + anchor · 小程序走 uni.downloadFile + uni.openDocument · 详情页 hero 加下载按钮
- **反馈历史**：`pages/feedback/mine.vue` 新建 · 待处理/已处理分组 · REPLIED 折叠展开回复 · profile 入口接真调
- **statistics**：`api/detect.js` +getStatistics（含 30 天 dailyTrend mock）· home.vue weekStats 优先后端 · fallback 本地聚合

## Wave 3 · 微信生态

- **一键登录**：`IAuthService.loginByWechat(code, nickname, avatarUrl)` + POST `/api/v1/auth/wechat/login`（mock 用 code hashCode 派生 openid）· login.vue 微信绿 CTA · `#ifdef MP-WEIXIN`
- **分享**：home/upload/detail 加 `onShareAppMessage` + `onShareTimeline`；详情页脱敏只带 taskId + AI 率
- **订阅消息**：`api/wechat.js` `requestAndSaveSubscribe(tmplIds)` 封装 · text/audio 上传提交后触发 · 其它端静默 resolve([])
- **客服**：profile 加 `<button open-type="contact">` · 详情页加 `<button open-type="share">分享给同学`

## Wave 4 · 生产化收官

| Batch | 主题 | 交付 |
|---|---|---|
| 4.1 | 深色模式 | `pages.json` 加 `"darkmode": true`（小程序端跟随系统主题）；`App.vue` `detectTheme()` 埋 `uni.getSystemInfoSync().theme` 写 storage；`uni.scss` 尾部加 dark tokens 骨架说明（真切换需重构 SCSS 变量为 CSS var，列 iOS HIG 对照色 · Wave 5 单独 batch） |
| 4.2 | 键盘避让 + 网络兜底 | `App.vue` `bindNetworkWatcher()` 监听 onNetworkStatusChange · 断/连都弹 toast；login/text/FeedbackSheet 4 处输入加 `cursor-spacing` + `adjust-position` |
| 4.3 | PWA 骨架 | `manifest.json` h5 段加占位注释 · 真 PWA 待引 vite-plugin-pwa 生成 webmanifest + SW（CacheFirst 静态 · NetworkFirst /api/*） |
| 4.4 | .env 版本号 | `.env.example` 打开 `VITE_APP_VERSION=0.3.0`；`profile.vue` `readAppVersion()` 三级兜底：env → `uni.getAccountInfoSync().miniProgram.version` → 常量 |

### 关键决策

- **4.1 只做骨架不做真切换**：SCSS 变量 → CSS var 涉及 15 mixin + 全部页面 tokens 引用（500-800 行），Wave 5 单独 batch
- **4.3 PWA 只留占位**：uni-app H5 转真 PWA 需要 vite-plugin-pwa 或第三方脚本注入，配置量足够单开一个 batch
- **4.4 版本号读取优先级 env > 小程序 SDK > 常量**：CI 注入最方便统一改，miniProgram.version 是小程序线上真实版本，常量做最终兜底
