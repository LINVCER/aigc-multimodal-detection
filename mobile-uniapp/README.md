# mobile-uniapp · 论文 AIGC 检测（uni-app 版）

Vue 3 + Vite + Pinia + uni-app（`@dcloudio/vite-plugin-uni`），一份代码编译到 **H5 + 微信小程序**（其它端可扩）。

与 `mobile-app/`（React Native + Expo）功能对齐、**并存**——两套技术栈可各自演进，业务对齐由 `api/detect.js` 的接口契约保证。

## 运行

```bash
cd mobile-uniapp
npm install

# H5（推荐先跑通 H5，浏览器直接看）
npm run dev:h5             # 默认 http://localhost:5175

# 微信小程序
npm run dev:mp-weixin      # 产物在 dist/dev/mp-weixin/，用微信开发者工具打开
```

微信开发者工具首次打开 `dist/dev/mp-weixin/`，AppID 使用 `manifest.json` 里的 `wx5dede2e8d33e3f15`（原骨架保留），或改为你自己的 AppID。

## Mock 模式

未配 `VITE_API_BASE` 环境变量时自动走内置 mock 数据（`api/detect.js`），可离线开发全部 UI。

接后端时：

```bash
# H5 走 vite proxy（manifest.json 里 h5.devServer.proxy 已配 /api → http://localhost:8080）
# 小程序需在微信后台配置合法域名 或 开发调试关闭校验

# 生产打包指定 API base
VITE_API_BASE=https://api.example.com npm run build:h5
```

## 目录

```
mobile-uniapp/
├── manifest.json         应用配置（H5 + mp-weixin 多端能力）
├── pages.json            页面路由 + tabBar
├── main.js               入口（Pinia）
├── App.vue               根组件（登录守卫）
├── vite.config.js
├── pages/
│   ├── login/login.vue           登录
│   ├── index/index.vue           检测记录（tabBar）
│   ├── upload/upload.vue         上传（tabBar）
│   ├── profile/profile.vue       我的（tabBar）
│   └── task/detail.vue           报告详情（句子级高亮 + 降 AIGC）
├── api/detect.js         检测/上传/降 AIGC/列表接口（mock 可切）
├── store/auth.js         Pinia 登录态
└── utils/request.js      uni.request 封装（跨端）
```

## 已实现（MVP）

- 登录 + token 持久化（`uni.setStorageSync`）+ App onLaunch 路由守卫
- 论文上传（PDF/Word/TXT ≤ 20MB）
  - 微信小程序：`uni.chooseMessageFile`
  - H5：`<input type="file">` fallback
- 学位类型选择 → 教育部红线提示（本科 20% / 硕士 15% / 博士 10%）
- 任务列表（下拉刷新，AI 率红黄绿）
- 报告详情：文档级判定卡 + 溯源分布条 + **句子级三档高亮** + 高危段落一键降 AIGC

## 与 mobile-app（RN）的对比

| 维度 | mobile-app (RN) | mobile-uniapp |
|---|---|---|
| 目标端 | iOS / Android 原生 | H5 + 微信小程序 |
| 语言 | TypeScript | JavaScript |
| UI 框架 | React + Tamagui/RN 原生 | Vue 3 + uni-app 组件 |
| 上架 | App Store / Google Play | 微信小程序审核 / Web CDN |
| 覆盖学生场景 | ~50%（愿意装 app 的） | ~90%（微信即用） |

## 待接入（后端就绪后）

- 学校 SSO / OIDC 登录
- 报告 PDF 预览下载（H5 走浏览器；小程序需下载到本地打开）
- 微信消息订阅（检测完成通知）
- 额度余额展示（等收费功能启用）

## 未做（对齐课题级 TEAM_ROLES 负向清单）

- ❌ 支付 / 收费
- ❌ 分享 / 社交
- ❌ 生物识别登录
- ❌ 深度定制主题 / 白标
