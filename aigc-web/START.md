# Web 端配置与启动规范（SOP）

> 目标：web 端（Vue 3 + Element Plus + Vite）的端口、命令、环境变量、代理规则集中说明。
> 配置的唯一权威来源是 `web/vite.config.ts`，本目录不复制配置，只提供一键脚本与说明。

## 1. 端口与实例

| 实例 | 端口 | 启动命令 | 一键脚本 | 范围 |
|---|---|---|---|---|
| C 端 | **5173** | `npm run dev` | `aigc-web\start.ps1` | 全站（含 /admin 也能进） |
| 管理端 | **5174** | `npm run dev:admin`（`vite --mode admin`） | `aigc-web\start-admin.ps1` | 只开 `/admin/*`，其余路径被守卫弹回后台 |

端口写在 `web/vite.config.ts` 的 `port: isAdmin ? 5174 : 5173`，改端口只改这一处。

## 2. 依赖服务

| 服务 | 端口 | 说明 |
|---|---|---|
| Java 后端 | 8080 | IDEA 跑 `RuoYi-Vue-Plus` 基座（DromaraApplication）；生产部署以 `backend-java` 源目录为准 |
| 推理服务 | 8000 | `deploy\inference-python\start.ps1`，见其 START.md |
| MySQL | 3306 | root 空密码（dev profile 默认值） |
| Redis | 16379 | WSL，密码 123456 |

## 3. 环境变量（web/.env）

```ini
VITE_API_TARGET=http://localhost:8080   # vite proxy 转发目标，对齐后端 server.port
```

生产构建时另有 `VITE_API_BASE`（axios baseURL，走 Nginx 分发时留空即可）。

## 4. 代理规则（web/vite.config.ts）

| 前缀 | 目标 | 说明 |
|---|---|---|
| `/api` | `VITE_API_TARGET` | C 端接口（后端 `@RequestMapping("/api/v1/...")`） |
| `/admin` | `VITE_API_TARGET` | 后台接口（后端 `@RequestMapping("/admin/...")` 无 /api 前缀）；`bypass` 放行浏览器导航，SPA 路由 `/admin/*` 走 history fallback |

生产由 Nginx 分发，`try_files $uri $uri/ /index.html;` 兜底 history 路由。

## 5. 首次准备

```powershell
cd d:\AAA\image_nious\web
npm install -i https://mirrors.aliyun.com/npm/ --no-audit --no-fund   # 可用国内镜像
```

## 6. 验证

- C 端：http://localhost:5173 落地页可开
- 管理端：http://localhost:5174 自动跳 /admin/dashboard；需要 OPS_ADMIN / ADMIN 角色账号
- typecheck：`npm run typecheck`（vue-tsc --noEmit）

## 7. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 管理端 5174 打不开/转圈 | 后端 8080 未启动，登录接口不通 | 先起 Java 后端 |
| 登录后弹回登录页 | 账号角色非 OPS_ADMIN/ADMIN | 管理端实例会明确提示；提权见 `auth_user.role` |
| 后台数据接口 500/404 | dev 代理只认 `/api` 与 `/admin` 前缀 | 核对 vite.config.ts 的 proxy 规则 |
| 改了 .env 不生效 | vite 需重启 | 停掉 dev server 重新执行一键脚本 |
