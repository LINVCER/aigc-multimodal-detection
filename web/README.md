# web · 论文 AIGC 检测 Web 用户端

Vue 3 + Vite + TS + Pinia + Vue Router + Element Plus。面向学生 / 教师 / 教务的桌面浏览器体验。

与 `mobile-uniapp/`（RN / uni-app 移动端）**并存**，走同一份后端契约（`docs/design/API_CONTRACT.md`）。

## 运行

```bash
cd web
npm install
npm run dev            # http://localhost:5173
```

未启动 Java 后端时，可用 mock：
```bash
VITE_API_TARGET=http://localhost:8080 npm run dev   # dev server /api 反代到 Java
```

## 构建

```bash
npm run build           # 输出 dist/
npm run preview         # 本地预览产物
```

生产部署走 `deploy/frontend/Dockerfile`（多阶段：Vite build → Nginx serve + SPA fallback）。

## 目录

```
web/
├── index.html
├── vite.config.ts           dev 5173，/api 反代到 VITE_API_TARGET（默认 :8080）
├── tsconfig.json
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/index.ts      hash 路由 + 登录守卫
│   ├── api/
│   │   ├── client.ts        axios + 拦截器（若依 R 结构 + 401 跳登录）
│   │   ├── types.ts         DetectTask / TaskDetail / PageResp / UserInfo
│   │   ├── auth.ts          §2 认证
│   │   └── detect.ts        §3 检测 + §4 降 AIGC
│   ├── stores/auth.ts       Pinia + localStorage
│   └── views/
│       ├── Login.vue        大字号品牌卡片
│       ├── Dashboard.vue    任务列表（Element Table + 搜索 + 状态筛选 + 4s 轮询）
│       ├── Upload.vue       Element Upload 拖拽 + 学位红线提示
│       └── TaskDetail.vue   总览卡 + 溯源进度条 + 段落 + 句子级三色 + 一键降 AIGC + 复制
```

## 已实现（MVP）

- 登录（对齐 §2.1；token 持久化 localStorage；401 拦截自动跳登录）
- 任务列表（搜索 + 状态筛选 + 轮询 + 重试/删除操作）
- 论文上传（学位类型 → 教育部红线提示 + 拖拽上传 + 20MB 限制）
- 报告详情：文档级判定卡 + 溯源分布进度条 + **段落 + 句子级三档高亮** + 高危段落一键降 AIGC + 复制改写

## 契约一致性

所有 API 调用严格对齐 `docs/design/API_CONTRACT.md`：
- 路径：`/api/v1/auth/*` `/api/v1/detect/*` `/api/v1/humanize`
- 响应体：若依 R `{ code, msg, data }`；`data` 层由拦截器裸出
- 401 → 跳登录 · code≠200/0 → ElMessage 提示 · 5xx → 拦截器兜底 toast

## 与其它端的差异

| | web/ | mobile-uniapp/ | mobile-app/ |
|---|---|---|---|
| 目标端 | PC 浏览器 | 微信小程序 + H5 | iOS + Android 原生 |
| 组件库 | Element Plus | uni-app 原生 | React Native 组件 |
| 场景 | 教师批量 / 教务后台 | 学生日常主用 | 深度用户 / 离线场景 |
