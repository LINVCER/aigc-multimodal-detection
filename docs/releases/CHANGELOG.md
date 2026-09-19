# CHANGELOG

顶层滚动变更日志。每版一段摘要 + 指向 `v{X.Y.Z}/release-notes.md` 详情。

格式约定：`[Added / Changed / Fixed / Deprecated / Removed / Security / Breaking]`

---

## [v0.2.0] · 2026-09-19 · Phase B 落库（滚动）🚧

InMemoryRepository 逐 batch 换 MyBatis-Plus 实现，数据真正落 MySQL。
Repository 用 `@Primary` 顶掉 InMemory，Service/Controller/前端零改动。

- **Added**：`user_profile` 表 · `MybatisAdminUserRepository` · Wave 5 音频检测骨架 · 首页/上传三级页 · TabBar 磨砂精修
- **Changed**：AdminUser entity 加 MP 注解 · request.js fail 语义化分类 · home.vue 移除调试日志
- **Fixed**：MOCK_MODE 短路 · uploadFile 不拼 baseURL · proxy 端口错 · 双重 toast · timeout 笼统
- **Batch 进度**：B1 Feedback ✅ · B2 AdminUser ✅ · B3 Detect 三表 ⏳ · B4 Scenario Threshold ⏳
- 详情 → [`v0.2.0/release-notes.md`](v0.2.0/release-notes.md)

---

## [v0.1.0] · 2026-09-18 · Baseline 🚧

首个规范化版本，把 Wave 1-4 已完成内容归档为 baseline，正式启动版本管理。

- **Added**：C 端 6 场景检测配置 · 反馈模块（W3.d）· 运营后台 4 页（W3.e）· mobile-uniapp iOS 精致化重构 · 推理层文本模型加载器
- **Changed**：Java 后端 3 层规范化（Phase A · Controller → Service → Repository），DetectController 从 708 行瘦身到 130 行
- **Fixed**：Sa-Token 拦截 auth 端点、retry 卡 PENDING、submit userId 丢失、GlobalExceptionHandler 无 @Order 等 8 项（详见 Batch 3 hotfix）
- **Known Issues**：新一代模型训练计划待启动（当前推理挂 legacy checkpoint 兜底）；DB migration 首次跑
- 详情 → [`v0.1.0/release-notes.md`](v0.1.0/release-notes.md)

---

<!-- 后续版本追加在此。最新在上、越往下越旧。 -->
