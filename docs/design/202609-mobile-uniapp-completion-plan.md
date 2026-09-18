# mobile-uniapp 全链完善开发计划

**发起日期**：2026-09-19
**当前版本**：v0.1.0（约 2890 行，7 页面 + 5 组件）
**目标版本**：v0.4.0 生产就绪
**并存关系**：跟 `mobile-app/`（React Native + Expo）**功能对齐**，走同一后端契约；两栈可各自演进

---

## 1. 现状快照

### 技术栈

| 层 | 技术 | 版本 | 状态 |
|---|---|---|---|
| Framework | uni-app | 3.0.0-4020420240722001 | ✅ |
| Vue | Vue 3 + `<script setup>` | 3.4.21 | ✅ |
| 编译器 | Vite | 5.2.8 | ✅ |
| 状态 | Pinia | 2.0.36 | ✅ |
| 样式 | Sass | 1.77 + uni.scss 全量 tokens | ✅ |
| 编译目标 | H5 · 微信小程序（其它端可扩） | — | ✅ |

### 页面 & 组件清单

```
mobile-uniapp/
├── pages/
│   ├── login/login.vue           105 行 · iOS 风骨架（Hero + Inset input + CTA）
│   ├── index/index.vue           496 行 · ✅ 已 tokens 化精修
│   ├── upload/upload.vue         520 行 · 🟡 场景瓦片已改；文件区/emoji 未走 tokens
│   ├── profile/profile.vue       162 行 · 🟡 结构 OK；样式硬编码，未走 tokens
│   └── task/detail.vue           863 行 · ✅ 已 tokens 化精修（SVG 环 · 段落速览 · CSS 小旗）
├── components/
│   ├── FeedbackSheet.vue         183 行 · ✅ W3.d 反馈半屏（tokens 化）
│   ├── EmptyState.vue             46 行 · 🟡 硬编码，未 tokens
│   ├── Skeleton.vue               39 行 · 🟡 简单版
│   ├── StatusChip.vue             41 行 · ✅ 简单可用
│   └── AiRateBadge.vue            31 行 · 🟡 未在页面用
├── api/
│   ├── detect.js                 159 行 · 覆盖 5/15 契约
│   └── feedback.js                22 行 · 覆盖 W3.d 提交
├── store/auth.js                  68 行 · ✅ userId/role 已就位
├── utils/{constants,diff,request}.js  ✅
└── uni.scss                     428 行 · ✅ Design Tokens 完整（12 组 tokens + 15 mixin）
```

代码总量 **2890 行**，v0.1.0 baseline 完成度约 **65%**。

---

## 2. 差距矩阵

### 2.1 页面精修完成度

| 页面 | 状态 | 剩余 |
|---|---|---|
| index/index.vue（主列表） | ✅ 完成 | — |
| task/detail.vue（报告） | ✅ 完成 | — |
| FeedbackSheet 组件 | ✅ 完成 | — |
| upload/upload.vue（上传） | 🟡 场景瓦片 OK · 其它未 tokens 化 | Task #59 |
| profile/profile.vue（我的） | 🟡 结构 OK · 硬编码样式 | Task #60 |
| login/login.vue（登录） | 🟡 iOS 风骨架 · 硬编码样式 | 新 Task |
| EmptyState / Skeleton 组件 | 🟡 未走 tokens | 顺手 |
| AiRateBadge | 🟡 未使用 | 删或用起 |

### 2.2 与后端契约差距（api/detect.js + feedback.js）

| 接口 | 契约 | mobile-uniapp | 差距 |
|---|---|---|---|
| `POST /auth/login` | 完整 LoginVO | ✅ 已接（userId 已存 store） | — |
| `POST /auth/logout` | 就绪 | 🟡 未真调后端 | P2 |
| `GET /auth/me` | 就绪 | 🟡 未接 | P2 |
| `POST /detect/submit` | scenario + userId | ✅ 已接 | — |
| `GET /detect/tasks` | 分页 { total, rows } | ✅ 已接 | — |
| `GET /detect/tasks/{id}` | 完整详情 | ✅ 已接 | — |
| `POST /detect/tasks/{id}/retry` | 就绪 | 🟡 详情页有按钮，但只调 retryTask 未处理详细 UI | P1 |
| `POST /detect/tasks/{id}/cancel` | 就绪 | 🔴 未接 | P1 |
| `DELETE /detect/tasks/{id}` | 就绪 | 🔴 未接（列表长按删除缺） | P1 |
| `GET /detect/statistics` | C 端 KPI | 🟡 主列表本周 KPI 走本地聚合，未走后端 | P2 |
| `POST /humanize` | 完整响应 | ✅ 已接 | — |
| `POST /detect/paragraph` | 粘贴模式 | ✅ 已接 | — |
| `GET /detect/health` | 推理健康 | 🔴 未接（我的-系统状态可展示） | P3 |
| `POST /feedback` | 提交 | ✅ 已接 | — |
| `GET /feedback/mine` | 历史 | 🔴 未接（我的-我的反馈子页缺） | P2 |
| `GET /report/tasks/{id}/pdf` | PDF | 🔴 未接（H5 可直下，小程序需 saveFile） | P1 |

### 2.3 缺失的 uni-app 独有价值

| 特性 | 价值 | 优先级 |
|---|---|---|
| 微信一键登录（uni.login + wx.getPhoneNumber） | 小程序原生优势，秒登 | 🔴 P0 |
| onShareAppMessage / onShareTimeline | 分享报告/工具本身，拉新利器 | 🟠 P1 |
| 微信订阅消息（uni.requestSubscribeMessage） | 检测完成推送，无需轮询 | 🟠 P1 |
| 保存图片到相册（uni.saveImageToPhotosAlbum） | 报告截图分享 | 🟡 P2 |
| open-type="contact" | 微信客服入口，比反馈弹窗更即时 | 🟡 P2 |
| Skyline 渲染引擎 | 小程序原生级性能，动画更流畅 | 🟡 P2 |
| H5 PWA 化（Service Worker） | H5 端离线可用 + 桌面安装 | 🟡 P2 |
| 顶部自定义 navigationBar | pages.json 已 custom，但未实现导航栏组件 | 🟠 P1 |

### 2.4 通用 UX / 生产化缺口

| 缺口 | 影响 | 优先级 |
|---|---|---|
| 深色模式（uni.scss 无 dark tokens） | 系统跟随，iOS/Android 均支持 | 🟠 P1 |
| 键盘避让（iOS 输入被键盘遮挡） | 登录/反馈/粘贴模式易踩 | 🟠 P1 |
| 网络异常兜底页 | 断网时体验差 | 🟠 P1 |
| Skeleton 精修（现只 4 行灰条） | 主列表已用形状骨架，其它页缺 | 🟡 P2 |
| 长按操作菜单（列表长按删除/置顶） | 交互习惯对齐 iOS | 🟡 P2 |
| 搜索历史（上次搜过的关键字） | 主列表搜索复用 | 🟢 P3 |
| .env.example（VITE_API_BASE 说明） | 新人上手门槛 | 🟠 P1 |
| i18n | 国际化 | 🟢 P3（跟 web 统一后再上） |

---

## 3. 目标 & 非目标

### 目标

- ✅ 5 页面 + 5 组件全部走 uni.scss tokens（无硬编码色/尺寸）
- ✅ 后端契约 100% 覆盖（15 接口）
- ✅ 微信小程序独有能力接入（一键登录 · 分享 · 订阅消息）
- ✅ 深色模式 · 键盘避让 · 网络兜底
- ✅ H5 PWA 化 + .env.example 完善

### 非目标

- ❌ 引入重量级 UI 库（uni-ui / uview）— 保持轻量
- ❌ 状态管理改造 — Pinia 已够用
- ❌ 单元测试 Vitest — 本轮先手动验证
- ❌ Skyline 全面切换 — 待稳定后评估
- ❌ 管理后台视图 — RN/uni 都不做，走 web `#/admin`

---

## 4. 分 Wave / Batch 开发计划

### Wave 1 · 页面精修收尾（约 6 文件，1 周）

对齐 Task #59 #60 及登录 Tokens 化收尾。

#### Batch 1.1 · upload/upload.vue tokens 化（Task #59）

- 场景瓦片保留，文件区 emoji 换 SVG data URI
- 粘贴模式按钮/输入走 tokens/mixin
- 主 CTA 走 @include btn-primary
- Mode segmented（📄 文件 / ✍ 粘贴）emoji 换文字或 SVG

#### Batch 1.2 · profile/profile.vue tokens 化（Task #60）

- 用 @include large-title-bar / group-label / group-row / card-flush
- 加"我的反馈"子入口（新增子页 pages/feedback/mine.vue）
- 加"系统状态"子入口（跳推理健康页，P3）
- 版本号 v0.1.0 动态从 package.json 或 manifest 读

#### Batch 1.3 · login/login.vue tokens 化

- Hero + Inset input + CTA 走 tokens
- 加微信一键登录按钮（小程序端；H5 端隐藏）
- 加错误提示区（当前只 toast）

#### Batch 1.4 · EmptyState / Skeleton 精修

- EmptyState 走 tokens + 加 illustration 位（可留空）
- Skeleton 支持多种形状（rows/card/chip）

**Wave 1 输出**：v0.2.0 · 5 页面 + 5 组件 100% tokens 化

---

### Wave 2 · 契约补齐 + 缺失功能（约 8 文件，1-2 周）

#### Batch 2.1 · Task 生命周期完善（P1）

- `api/detect.js` 补 cancelTask · deleteTask
- 主列表长按弹 ActionSheet：置顶 / 删除 / 分享
- 详情页顶部加"取消检测"按钮（RUNNING 状态可见）
- 详情页失败态 retry 按钮细化：显示上次错误 + 剩余重试次数

#### Batch 2.2 · 报告 PDF 下载（P1）

- `api/report.js` 新增 downloadReportPdf
- H5 端走 anchor download
- 小程序端走 uni.downloadFile + uni.saveFile + uni.openDocument（PDF 预览）
- 详情页顶部加"下载 PDF"按钮

#### Batch 2.3 · 我的反馈历史子页（P2）

- 新增 `pages/feedback/mine.vue`
- 列表 + 状态 chip（PENDING/PROCESSING/REPLIED/IGNORED）
- 点击某条查看运营回复内容
- pages.json 加路由

#### Batch 2.4 · Dashboard 走后端 statistics（P2）

- 主列表本周 KPI 从后端 `/detect/statistics` 拉取
- fallback：无网 or 无 DONE 数据时兜底本地聚合

**Wave 2 输出**：v0.3.0 · 后端契约 100% + task 生命周期完整

---

### Wave 3 · 微信小程序独有价值（约 6 文件，1 周）

#### Batch 3.1 · 微信一键登录（P0）

- 登录页加"微信登录"按钮
- `api/auth.js` 补 loginByWechat（wx.login → code → 后端换 openid → 换 accessToken）
- 后端 `/api/v1/auth/wechat/login` 接口占位（W3.c 时补 Sa-Token 集成）
- 首次登录弹 wx.getUserProfile 获取昵称/头像（P1）

#### Batch 3.2 · 分享（P1）

- 各页 onShareAppMessage：
  - 首页/上传 → 分享工具本身
  - 报告详情 → 分享单份报告（脱敏）
- onShareTimeline（朋友圈）：首页/上传

#### Batch 3.3 · 订阅消息（P1）

- 上传成功时 uni.requestSubscribeMessage 拉起授权
- 后端 `/api/v1/user/wechat-subscribe` 记录 template_id + openid
- 检测完成时后端调 wx 服务端 API 推送

#### Batch 3.4 · 保存图片 + 客服（P2）

- 报告详情"保存截图"按钮（Canvas 生成海报 → uni.saveImageToPhotosAlbum）
- 我的-联系客服 open-type="contact"

**Wave 3 输出**：v0.4.0 · 微信生态完整闭环

---

### Wave 4 · 生产化（约 6 文件，1 周）

#### Batch 4.1 · 深色模式（P1）

- `uni.scss` 补深色 tokens（$bg-primary-dark 等）
- App.vue 监听系统主题（uni.getSystemInfoSync().theme）
- pages.json globalStyle 加 darkMode
- 各页面样式加 dark 变体（走 tokens 后基本零改动）

#### Batch 4.2 · 键盘避让 + 网络兜底（P1）

- input/textarea 用 cursor-spacing + adjust-position
- 全局 network offline 兜底页（uni.onNetworkStatusChange）
- request.js 拦截 fail 分类：offline / timeout / 5xx

#### Batch 4.3 · H5 PWA 化（P2）

- manifest.webmanifest 生成
- Service Worker 缓存静态资源 + API GET 结果
- 桌面安装引导

#### Batch 4.4 · 环境配置样例（P1）

- 新增 `mobile-uniapp/.env.example`
- README 加环境变量说明表

**Wave 4 输出**：v0.5.0 · 生产就绪

---

## 5. 里程碑

| 版本 | 交付 | 预估 | 状态 |
|---|---|---|---|
| **v0.2.0** | Wave 1 · 5 页面 + 5 组件 tokens 化 | 1 周 | ⏳ |
| **v0.3.0** | Wave 2 · 后端契约 100% + task 生命周期 | +1-2 周 | ⏳ |
| **v0.4.0** | Wave 3 · 微信小程序独有价值 | +1 周 | ⏳ |
| **v0.5.0** | Wave 4 · 生产化 | +1 周 | ⏳ |

## 6. 优先级

1. 🔴 **P0** Batch 1.1-1.3 页面收尾 · 3.1 微信登录 — 完整度硬指标
2. 🟠 **P1** Batch 2.1 task 生命周期 · 2.2 PDF · 3.2 分享 · 3.3 订阅消息 · 4.1 深色 · 4.2 键盘/网络 — 用户可感知的体验补齐
3. 🟡 **P2** Batch 1.4 组件 · 2.3 反馈历史 · 2.4 statistics · 3.4 保存图片/客服 · 4.3 PWA · 4.4 .env — 打磨
4. 🟢 **P3** Skyline · 搜索历史 · i18n — 视规模再上

---

## 7. 风险 & 依赖

### 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 微信小程序审核（本产品定位为学习工具，非"论文代写"避免违规词） | 上架被拒 | Wave 3 前把所有"降 AIGC 改写"文案改为"AI 率优化建议"；营销页避免"包过""绕过检测"字样 |
| uni-app Vite HMR 偶发失效 | 开发体验差 | 已知问题，重启 dev server 兜底；等 uni-app 官方修 |
| iOS 微信小程序键盘避让 bug | 输入体验差 | Batch 4.2 明确解决 |
| Skyline 兼容第三方组件 | 部分自定义组件失效 | 本轮不切 Skyline |

### 前置依赖

- ✅ 后端 Phase A 完成
- ⏳ 后端 Phase B（Task #63 · MyBatis 落库）— userId 才真正持久化
- ⏳ 后端 W3.c 微信登录接入 — 微信一键登录才能真通（Wave 3 前必需）
- ⏳ 后端订阅消息服务端推送 API — Wave 3 · Batch 3.3 依赖

### 与其它端边界

- **不做 admin 视图**：手机屏幕不适合大盘，走 web `#/admin`
- **PDF 生成**：走后端 `/report/tasks/{id}/pdf`，客户端只做下载/预览，不本地生成

---

## 8. 交付物清单

### 代码

- ~26 个改动文件（Wave 1 · 6 · Wave 2 · 8 · Wave 3 · 6 · Wave 4 · 6）
- Tokens 100% 覆盖 · 微信闭环 · 深色模式 · PWA

### 文档

- `docs/releases/v0.2.0` — Wave 1 发版（含 v0.1.0-baseline → v0.2.0 差异）
- `docs/releases/v0.3.0` — Wave 2 发版
- `docs/releases/v0.4.0` — Wave 3 发版
- `docs/releases/v0.5.0` — Wave 4 发版 + 生产上架清单
- `mobile-uniapp/README.md` 每 wave 后更新状态表 + 微信 AppID 配置说明
- `mobile-uniapp/.env.example` 新增（Wave 4）

### 分发

- H5 · 走后端 nginx 静态托管（跟 web 同域名，`/m` 路径前缀 or 独立子域名 `m.paperaigc.com`）
- 微信小程序 · 微信公众平台审核发布
- App 端（App+）· uni-app 打包 iOS/Android，走 App Store / 应用商店（本轮不做，Wave 5 议）

---

## 9. 起点

**立即可开工**：Wave 1 · Batch 1.1 (upload tokens 化) 无阻塞依赖，跟 mobile-app 计划并行。

推进指令示例：`继续 mobile-uniapp Batch 1.1`（对应 Task #59）

## 10. 两个前端子项目对比

| 维度 | mobile-uniapp | mobile-app | 备注 |
|---|---|---|---|
| 当前代码量 | 2890 行 | 736 行 | uniapp 领先 4 倍 |
| 目标完成度 | v0.1.0 (65%) → v0.5.0 (生产) | v0.1.0 (25%) → v0.4.0 (生产) | uniapp 起点高 |
| 微信生态 | 天然优势 · 一键登录 / 订阅消息 / 分享 | 需 wechat SDK 集成，重 | uniapp 主战场 |
| iOS/Android 原生 | uni-app App+ 打包（一份代码） | React Native 原生 | mobile-app 主战场 |
| 推送 | 微信订阅消息（小程序） · Web Push（H5） | expo-notifications（APN + FCM） | 各有优势 |
| 开发者门槛 | Vue 生态，跟 web 团队复用 | React 生态，独立技能栈 | uniapp 团队协作友好 |
| 建议 | 覆盖微信 + H5，占中国大陆用户绝大部分 | 覆盖海外 iOS/Android 用户 | 两栈并行，不合并 |
