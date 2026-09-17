# paper-aigc-mobile · 论文 AIGC 检测移动端

React Native + Expo（SDK 51）+ TypeScript + Expo Router + Zustand + TanStack Query。

## 运行

```bash
npm install
npx expo start          # 扫码用 Expo Go 预览
npm run typecheck       # TS 检查
```

## Mock 模式

默认 `EXPO_PUBLIC_API_BASE` 为空 → 走内置 mock 数据（`src/api/detect.ts`），可离线开发全部 UI。

接后端时在 `.env` 配置：

```
EXPO_PUBLIC_API_BASE=https://api.example.com
```

## 页面结构（Expo Router file-based）

```
app/
├── _layout.tsx        根布局：QueryClient + 登录态守卫
├── login.tsx          登录
├── (tabs)/
│   ├── index.tsx      检测记录列表（红黄绿 AI 率）
│   ├── upload.tsx     论文上传（学位类型 → 红线提示 → 文件选择）
│   └── profile.tsx    我的
└── task/[id].tsx      检测报告详情：总览卡 + 溯源分布 + 句子级高亮 + 降 AIGC 改写
```

## 已实现（MVP 骨架）

- 登录 + token 持久化（expo-secure-store）+ 路由守卫
- 论文上传（PDF/Word/TXT ≤20MB，学位类型选择带教育部红线提示）
- 任务列表（状态、AI 率红黄绿）
- 报告详情：文档级判定 / 溯源分布条 / **句子级三档高亮** / 高危段落一键降 AIGC

## 待接入（后端就绪后）

- SSO（学校统一身份认证）
- 报告 PDF 预览下载（expo-file-system + sharing）
- 推送（检测完成通知，Expo Push）
- 额度余额展示
- UI 库升级（当前为原生组件 + StyleSheet，可平滑迁 Tamagui）
