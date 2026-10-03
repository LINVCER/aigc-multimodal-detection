# CHANGELOG

顶层滚动变更日志。每版一段摘要 + 指向 `v{X.Y.Z}/release-notes.md` 详情。

格式约定：`[Added / Changed / Fixed / Deprecated / Removed / Security / Breaking]`

---

## [v0.3.0] · 2026-10-03 · 论文检测助手骨架 🚧（线路已铺通，暂不对用户开放）

按调研路线 B 落地「论文检测助手」端到端：Python `assistant/`（LLM / 7 工具 / BM25 知识库 / Redis 会话 / SSE）→ Java `/api/v1/assistant/*` 限流 + 审计 + SseEmitter 透传 → uniapp 流式对话页 + FAB + 报告页入口 → web 抽屉。零新部署单元。

- **Added**（Python）：`assistant/` 11 个模块 + 6 篇知识库（32 块）· `TextAIGCDetector.surface_profile()` 表层特征 z-score
- **Added**（Java）：`AssistantController / IAssistantService / AssistantServiceImpl / AssistantChatDTO / AssistantLog / AssistantLogMapper` · `ErrorCode` 7xxx 段 · `GET /detect/scenario-thresholds` · `assistant_log` 表（V0.3.0.001）
- **Added**（端上）：uniapp `httpStream`（chunked / fetch 流 / 整包退化）· `pages/assistant/chat` · `AssistantFab` 挂 4 tab · detail「问助手」「为什么这段像 AI？」· web `AssistantDrawer`
- **Changed**：compose 给 inference 注入 `ASSISTANT_*`、给 backend 注入 `PLATFORM_ASSISTANT_BASE_URL`；`.env.example` 加 ASSISTANT 段
- **Known Issues**：本机未编译 Java、未真机；`sec-check` 代理 / 会话历史页 / 边界测试集 归 W2-W3；助手须等新 checkpoint 上线后再开放
- 详情 → [`v0.3.0/release-notes.md`](v0.3.0/release-notes.md)

---

## [v0.2.0] · 2026-09-19 · Phase B 落库 ✅ · mobile-uniapp Wave 2/3/4 联发

后端：InMemoryRepository 逐 batch 换 MyBatis-Plus，数据落 MySQL；Repository `@Primary` 顶 InMemory，Service/Controller/前端零改动。
端上：mobile-uniapp 走完 completion-plan 3 Wave，v0.5.0 生产就绪。

- **Added**（后端）：`user_profile` / `detect_task+paragraph+sentence` / `detect_scenario_threshold` 4 表 · Caffeine 5min 缓存 · JacksonTypeHandler JSON 列 · 图像模态接入（`ImageSegmentResult` + `image_segments_json` + `detectImage()` + `submitImage()`；Python 端点后补）
- **Added**（端上）：task 生命周期长按菜单 · 报告 PDF 双端下载 · 反馈历史 mine 页 · statistics 30 天 dailyTrend · 微信一键登录 · 分享 3 页 · 订阅消息封装 · 联系客服 · 深色模式骨架 · 网络断连兜底 · 键盘避让 · 版本号动态读取
- **Changed**：Detect Service 阈值走 `IScenarioThresholdService` 替代 `ScenarioConstants` · request.js fail 语义化分类 · 3 处 InMemory 实现 git rm
- **Fixed**：MOCK_MODE 短路 · uploadFile 不拼 baseURL · proxy 端口错 · 双重 toast · timeout 笼统
- **Batch 进度**：B1 ✅ · B2 ✅ · B3 ✅ · B4 ✅（Phase B 收官）· mobile-uniapp Wave 2 ✅ · Wave 3 ✅ · Wave 4 ✅
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
