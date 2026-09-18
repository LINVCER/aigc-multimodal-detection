# mobile-app 全链完善开发计划

**发起日期**：2026-09-18
**当前版本**：v0.1.0 骨架（736 行 · 8 文件）
**目标版本**：v0.3.0 与 mobile-uniapp 功能等价 + 原生特性加成
**并存关系**：跟 `mobile-uniapp/`（H5 + 微信小程序）**功能对齐**，走同一后端契约；两栈可各自演进

---

## 1. 现状快照

### 技术栈

| 层 | 技术 | 版本 | 状态 |
|---|---|---|---|
| Runtime | Expo SDK | 51 | ✅ |
| Native | React Native | 0.74.5 | ✅ |
| 路由 | expo-router (file-based) | 3.5 | ✅ |
| 状态 | Zustand | 4.5 | ✅ |
| 数据 | TanStack Query | 5.59 | ✅ |
| HTTP | axios + expo-secure-store | 1.7 / 13 | ✅ |
| 选文件 | expo-document-picker | 12 | ✅ |
| UI 库 | 无（原生 StyleSheet） | — | 🟡 待引入 |
| 图标 | Emoji 字符 | — | 🟡 待换 SVG |
| 图表 | 无 | — | 🟡 报告页需要 |
| 推送 | 无 | — | ⏳ 待接 |
| 离线 | 无 | — | ⏳ 待接 |

### 页面清单

```
app/
├── _layout.tsx        41 行 · AuthGate + QueryClientProvider
├── login.tsx          65 行 · 简单表单
├── (tabs)/
│   ├── _layout.tsx    34 行 · 3 tabs（emoji 图标）
│   ├── index.tsx      76 行 · 检测记录 FlatList
│   ├── upload.tsx    125 行 · 3 学位 chip + dashed 文件框
│   └── profile.tsx    44 行 · 灰白菜单
└── task/[id].tsx     161 行 · 总览卡 + 溯源 bar + 段落卡
```

代码总量 **736 行**，跟 mobile-uniapp（≈ 3000+ 行，含 Tokens/组件/精修页面）差距 4 倍以上。

---

## 2. 差距矩阵（对齐 uniapp v0.1.0 baseline + 后端契约）

### 2.1 与 mobile-uniapp 功能差距

| 维度 | mobile-uniapp | mobile-app | 差距 |
|---|---|---|---|
| **场景配置（W3.b）** | 6 场景 SCENARIO_MAP 带 tint/wash | 老 3 学位 BACHELOR/MASTER/PHD | 🔴 P0 |
| **反馈模块（W3.d）** | FeedbackSheet + Profile/详情双入口 | 无 | 🔴 P0 |
| **userId 透传** | store.userId + upload 传参 | 未做 | 🔴 P0 |
| **Design Tokens** | uni.scss 12 组 tokens + 15 mixin | 全硬编码色/尺寸 | 🟠 P1 |
| **主列表** | Hero + KPI + Segmented + 独立卡 + Skeleton | 简单 FlatList | 🟠 P1 |
| **报告页** | SVG 环 + 段落速览 + 语义 pill + CSS 小旗 | 蓝色总览 + bar + 段落卡 | 🟠 P1 |
| **上传页** | 场景 2 列瓦片 + 磨砂 + 粘贴模式 | 3 chip + dashed 框 | 🟠 P1 |
| **我的页** | Large Title + 头像 + Inset Grouped | 灰白菜单 | 🟡 P2 |
| **登录页** | 待重构 | 简单表单 | 🟡 P2 |

### 2.2 与后端契约差距（api/detect.ts）

| 接口 | 契约状态 | mobile-app 状态 |
|---|---|---|
| `POST /auth/login` | 返 `{ accessToken, user: { id, username, realName, role, orgName } }` | 只取 accessToken，扔 user.id 🔴 |
| `POST /auth/logout` | 就绪 | 未接 🟡 |
| `GET /auth/me` | 就绪 | 未接 🟡 |
| `POST /detect/submit` | 参数 `scenario + userId` | 传老 `degreeType`，缺 userId 🔴 |
| `GET /detect/tasks` | 分页 `{ total, rows }` + 过滤参数 | 只用 pageNum/pageSize 🟡 |
| `GET /detect/tasks/{id}` | 完整 DetectTaskDetailVO | TypeScript type 缺 4 个字段 🟡 |
| `POST /detect/tasks/{id}/retry` | 就绪 | 未接 🟠 |
| `POST /detect/tasks/{id}/cancel` | 就绪 | 未接 🟠 |
| `DELETE /detect/tasks/{id}` | 就绪 | 未接 🟠 |
| `GET /detect/statistics` | C 端 Dashboard KPI | 未接 🟠 |
| `POST /humanize` | 完整响应 `{ humanizeTaskId, originalText, rewrittenText, qualityScore, modelVersion }` | 只取 rewrittenText 🟡 |
| `POST /detect/paragraph` | 直接段检测（粘贴模式） | 未接 🟠 |
| `GET /detect/health` | 推理服务健康 | 未接 🟡 |
| `POST /feedback` + `GET /feedback/mine` | W3.d 反馈 | 未接 🔴 |
| `GET /report/tasks/{id}/pdf` | PDF 报告下载 | 未接 🟠 |

### 2.3 缺失的原生特性（RN 独有价值）

| 特性 | 价值 | 优先级 |
|---|---|---|
| 推送通知（expo-notifications） | 检测完成/失败推送，减少轮询 | 🟠 P1 |
| 深度链接（app.json scheme=paperaigc 已配） | 分享报告链接跳详情 | 🟡 P2 |
| 离线缓存（TanStack Query persist） | 断网仍看历史报告 | 🟡 P2 |
| 生物识别登录（expo-local-authentication） | Face ID / 指纹二次校验敏感操作 | 🟡 P2 |
| 分享原生 API（expo-sharing） | 报告 PDF 分享给同学/导师 | 🟠 P1 |
| Haptic 反馈（expo-haptics） | iOS 风精致化的一部分 | 🟢 P3 |
| 深色模式（useColorScheme） | 系统跟随，iOS/Android 都简单 | 🟠 P1 |

---

## 3. 目标 & 非目标

### 目标

- ✅ 功能对齐 mobile-uniapp v0.1.0 baseline
- ✅ 后端契约 100% 覆盖（15 个接口）
- ✅ Design Tokens 系统落地（RN StyleSheet 版）
- ✅ 引入 RN 独有价值特性（推送 / 分享 / 深色 / Haptic）
- ✅ 用户诊断 Phase A hotfix 对齐（userId 透传等）

### 非目标（本轮不做）

- ❌ 引入重量级 UI 库（Tamagui / NativeBase / Gluestack）— 保持轻量
- ❌ 状态管理换 Redux Toolkit — Zustand 够用
- ❌ 图表引 Victory / D3 — 用 react-native-svg 手绘（跟 uniapp SVG 环对齐）
- ❌ i18n — mobile-uniapp 也未做，等真国际化再统一上
- ❌ 单元测试 Jest + RN Testing Library — 本轮先手工验证

---

## 4. 分 Wave / Batch 开发计划

### Wave 1 · 功能对齐（约 30 文件，2-3 周）

#### Batch 1.1 · Design Tokens + 基础组件（P0 前置）

- `src/theme/tokens.ts` — 对齐 uni.scss 12 组 tokens（品牌色 / 语义色 / 字号 / 间距 / 圆角 / 阴影 / 动效 / z-index / 组件尺寸）
- `src/theme/index.ts` — 导出统一 theme + useTheme hook
- `src/theme/dark.ts` — 深色变体（可选 · P1 顺手做）
- `src/components/`（新增 8 个原子组件，全部走 Tokens）
  - `Text.tsx` · 6 层字号 + 语义色
  - `Card.tsx` · 3 种（默认 / flush / hero）
  - `Chip.tsx` · 状态胶囊
  - `Button.tsx` · primary / tinted / text / destructive 4 变体
  - `Skeleton.tsx` · shimmer
  - `EmptyState.tsx` · icon + title + desc + action
  - `Row.tsx` · Inset Grouped 单行
  - `Divider.tsx` · hairline
- **约 12 文件**

#### Batch 1.2 · 契约对齐 + 场景迁移（P0）

- `src/api/types.ts` — 从 backend `docs/design/API_CONTRACT.md` 补齐类型（DetectTaskDetailVO、ParagraphResult 全字段、SentenceResult、FeedbackVO、LoginVO 等）
- `src/api/detect.ts` — 补齐所有 15 个接口 · submit 用 scenario + userId
- `src/api/feedback.ts` — 新增（对齐 web/mobile-uniapp）
- `src/api/auth.ts` — 拆出，返回完整 user
- `src/api/report.ts` — 新增 PDF 下载
- `src/utils/constants.ts` — 复用 SCENARIO_MAP 常量（含 tint/wash）
- `src/store/auth.ts` — 加 userId / role 字段（对齐 uniapp store）
- **约 7 文件**

#### Batch 1.3 · 主列表页重构（P1）

- `app/(tabs)/index.tsx` 全量重写
  - Large Title Hero
  - 本周 KPI 三宫格（本周检测 / 平均 AI 率 / 达标率）
  - RUNNING 提示条 + pulse dot
  - 搜索栏（SVG data URI 放大镜 → react-native-svg）
  - 状态 Segmented + count 徽章
  - 独立任务卡（场景 chip + 60rpx AI 率大字 + 达标/超红线 badge）
  - Skeleton 3 张卡骨架
  - 精修错误 / 空 / 无匹配三态
- 引入 `react-native-svg` 依赖
- **约 2 文件**

#### Batch 1.4 · 上传页重构（P1）

- `app/(tabs)/upload.tsx` 全量重写
  - 场景 2 列瓦片（用 SCENARIO_MAP.tint/wash）
  - iOS 磨砂文件区（Pressable + 语义色）
  - 粘贴模式 tab 切换（对齐 uniapp 支持直接文本检测）
  - 主 CTA 按钮走 Button 组件
- **约 1 文件**

#### Batch 1.5 · 报告页重构（P1）

- `app/task/[id].tsx` 全量重写
  - AI 率环形 SVG（react-native-svg circle stroke-dasharray）
  - Verdict pill 胶囊（语义 bg + fg）
  - 段落速览 chip grid
  - 段落分析卡（折叠 / 展开）
  - 溯源分布 bar + 语义色
  - 改进建议卡（severity dot + 语义色）
  - 结果申诉入口（跳 FeedbackSheet）
- 处理中 / 失败 / 加载失败三态精修
- **约 1 文件**

#### Batch 1.6 · 我的页 + 登录页重构（P2）

- `app/(tabs)/profile.tsx` — Large Title + 头像 hero + Inset Grouped + 意见反馈入口
- `app/login.tsx` — 品牌页化 + Sa-Token mock 对齐（admin/admin 派 OPS_ADMIN 提示但不展示后台入口，因为 RN 不做 admin）
- **约 2 文件**

#### Batch 1.7 · FeedbackSheet 组件 + 反馈接入（P0）

- `src/components/FeedbackSheet.tsx` — 底部半屏 Modal（RN Modal / react-native-portalize）
  - suggestion / bug / appeal 三分类
  - 2000 字校验 + 联系方式选填
  - 跟 uniapp FeedbackSheet 行为等价
- profile / task 详情两处入口挂载
- **约 3 文件（组件 + 2 处 hook 点）**

### Wave 2 · RN 独有价值（约 12 文件，1-2 周）

#### Batch 2.1 · 推送通知（P1）

- `src/notifications/` — expo-notifications 权限申请 + token 注册
- 后端加 `POST /api/v1/user/push-token` 接口（Phase B 时补，本 wave 前端先做本地测试）
- 检测完成时 Local Notification 兜底
- **约 4 文件**（含 pkg deps + 权限 config）

#### Batch 2.2 · 深色模式（P1）

- `src/theme/dark.ts` 完成
- `useTheme` hook 读 `useColorScheme()` 切换
- 所有组件走 theme 变量，无需改
- 状态栏跟随
- **约 1 文件 + 8 组件调整**

#### Batch 2.3 · 报告 PDF 下载 & 分享（P1）

- 引入 expo-file-system + expo-sharing
- `src/utils/pdf.ts` — 下载 blob + 保存到 cache + 唤起系统分享
- 报告页顶栏加"下载 PDF"按钮
- **约 3 文件**

#### Batch 2.4 · Haptic + 深度链接（P2 / P3）

- expo-haptics 精修：按钮按压 / 提交成功 / 失败震动
- 深度链接 `paperaigc://task/{id}` → 直跳报告详情（scheme 已配，只需接 handler）
- **约 2 文件**

### Wave 3 · 生产化（约 10 文件，1 周）

#### Batch 3.1 · 离线缓存

- TanStack Query persist（AsyncStorage backing）
- 报告详情断网仍可看
- **约 2 文件**

#### Batch 3.2 · 错误兜底 UI

- 网络异常 / 401 / 500 全局兜底页
- axios 拦截器补充 error 分类
- **约 3 文件**

#### Batch 3.3 · 生物识别（可选）

- expo-local-authentication
- 上传前/查看报告前二次校验（默认关闭，Profile 页可开启）
- **约 3 文件**

#### Batch 3.4 · Release 构建配置

- EAS Build 配置 `eas.json`（dev / preview / prod 三环境）
- app.json 版本号、图标、启动屏
- **约 2 文件**

---

## 5. 里程碑

| 版本 | 交付 | 预估时长 | 状态 |
|---|---|---|---|
| **v0.2.0** | Wave 1 完成 · 功能对齐 uniapp | 2-3 周 | ⏳ |
| **v0.3.0** | Wave 2 完成 · RN 独有特性 | +1-2 周 | ⏳ |
| **v0.4.0** | Wave 3 完成 · 生产就绪 | +1 周 | ⏳ |

## 6. 优先级

优先级参考（同 wave 内可并行）：

1. 🔴 **P0** Batch 1.1 Tokens+组件 · 1.2 契约+userId · 1.7 反馈 — 与 uniapp 功能对齐的核心
2. 🟠 **P1** Batch 1.3 主列表 · 1.4 上传 · 1.5 报告页 · 2.1 推送 · 2.2 深色 · 2.3 PDF - 视觉精修 + RN 差异化
3. 🟡 **P2** Batch 1.6 profile/login · 2.4 haptic/deeplink · 3.1 离线 · 3.2 兜底 · 3.3 生物 — 打磨

## 7. 风险 & 依赖

### 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| RN 0.74 + Expo 51 兼容性 | 依赖第三方库可能不兼容 | 优先 Expo 官方 SDK 内的库（expo-svg / expo-file-system / expo-sharing 都有）|
| iOS 上架审核 | 中国大陆需 App Store Connect + 备案 | 本轮先做 Android + iOS TestFlight，正式上架另立里程碑 |
| 微信登录 (mobile-uniapp 天然优势) | RN 需接 wechat SDK，复杂度高 | 本轮不做，OpenAPI 提供 phone/email 登录足够 |
| 后端 API 覆盖率 | 部分 admin 接口 RN 端用不到 | 只接 C 端 15 个接口，admin 走 web 即可 |

### 前置依赖

- ✅ 后端 Phase A 完成（已有）
- ⏳ 后端 Phase B 完成（Task #63 · 落库后 userId 才真正生效）
- ⏳ Python 推理层 gRPC 真接（当前 stub 也能跑通链路，不阻塞）
- ⏳ ml/ 新模型训练启动（不阻塞 mobile-app，模型换路径即可）

### 与其它端的边界

- **不做 admin 视图**：RN 端只做 C 端。运营后台走 web `#/admin`
- **不做支付**：本产品阶段无收费
- **不做校验第三方文件签名**：企业签名 / MDM 分发另议

---

## 8. 交付物清单

### 代码

- ~40 个新文件（Wave 1 · 30 · Wave 2 · 12 · Wave 3 · 10）
- ~10 个现有文件重写
- Design Tokens 系统 · 8 原子组件 · FeedbackSheet · 推送 · 深色 · PDF 分享 · 离线缓存

### 文档

- `docs/releases/v0.2.0/release-notes.md` — Wave 1 发版
- `docs/releases/v0.3.0/release-notes.md` — Wave 2 发版
- `docs/releases/v0.4.0/release-notes.md` — Wave 3 发版 + Release 构建指南
- `mobile-app/README.md` 每 wave 后更新状态表

### 分发

- Android APK · 通过 EAS Build 出内测包
- iOS · TestFlight 内测（需苹果开发者账号）
- Web 预览（`expo start --web`）作为快速联调补充，不作正式产物

---

## 9. 起点

**立即可开工**：Batch 1.1 (Tokens+组件) 是所有后续 Batch 的前置，无阻塞依赖。

推进指令示例：`继续 mobile-app Batch 1.1`
