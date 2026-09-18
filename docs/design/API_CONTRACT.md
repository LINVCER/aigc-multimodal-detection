# API_CONTRACT · 前后端 API 契约

> 面向 3 个前端（Web 用户端 `frontend/` · Web 管理端 `plus-ui` · 移动端 `mobile-uniapp/` + `mobile-app/`）+ Java 后端 + Python 推理服务的统一接口契约。
> **改代码前先对齐本文档；本文档变更需 PR review。**
> 关联：[ENTERPRISE_ARCHITECTURE.md](ENTERPRISE_ARCHITECTURE.md) §2.4 · `backend-java/business-modules/ruoyi-inference/src/main/proto/detection.proto`

---

## 0. 现状（2026-09-18）—— 尚未对齐

| 面 | 现状 | 问题 |
|---|---|---|
| Java → Python 推理 | `DetectController` 硬编码 `localhost:18000` | 端口错（应 `:8000`），host 应为容器名/环境变量 |
| Mobile → Java | Mobile 端全调 `/api/v1/mobile/detect/*`；Java 只提供 `/detect/paragraph` | 路径完全不匹配，全部走 mock |
| Web `frontend/` → Java | `frontend/src/api/` 目录不存在 | 前端根本没有 API 层 |
| Admin `plus-ui` → Java | 未部署 | 我们的业务 API 一个都没接进管理端 |
| 若依基座 | 未落地 | Java 项目跑不起来（缺基座依赖） |

**目标**：本文档定完，5 个对接面在一次冲刺内全部打通。

---

## 1. 契约总原则

### 1.1 路径分组

| 前缀 | 面向 | 认证 | 举例 |
|---|---|---|---|
| `/api/v1/auth/**` | 全端 | 无 | 登录 / 刷新 token |
| `/api/v1/detect/**` | Web 用户端 + Mobile 端 | JWT | 提交检测、查任务、报告 |
| `/api/v1/humanize/**` | Web 用户端 + Mobile 端 | JWT | 降 AIGC |
| `/api/v1/report/**` | Web 用户端 + Mobile 端 | JWT | PDF/Excel 下载 |
| `/api/v1/user/**` | 全端 | JWT | 个人信息 |
| `/admin/**` | 管理端 plus-ui | 若依 Sa-Token | 若依自带 + 业务扩展 |
| `/actuator/**` | 运维/监控 | 内网限制 | Spring Actuator |
| 内部 gRPC（Java ↔ Python） | 服务间 | 内网 mTLS 或明文 | `paperaigc.inference.v1.DetectionService` |
| 内部 HTTP fallback（Java ↔ Python） | 服务间 | — | `/api/v1/detect/*` 由 `inference-python/main.py` 提供 |

**Mobile 端不用独立 `/api/v1/mobile/*` 前缀**——同一份接口即可（前端字段自行按需 pick），未来若需要精简响应体再加 `?slim=1` 参数。**mobile-app/mobile-uniapp 需要改路径**。

### 1.2 统一响应体（若依 R 结构）

```json
{
  "code": 200,
  "msg": "操作成功",
  "data": { /* 业务数据；无数据时可为 null 或省略 */ }
}
```

- `code`：200 成功；4xx 客户端错误；5xx 服务端错误；具体错误码见 §7
- `msg`：给用户看的中文消息
- `data`:  T 或 T[]，成功时才有

### 1.3 认证

- **登录**：`POST /api/v1/auth/login` 返回 `accessToken`
- **携带**：`Authorization: Bearer <token>`
- **过期**：401 响应，前端拦截 → 跳登录页
- **JWT 密钥**：Java 侧 `platform.jwt.secret`（RS256 生产 / HS256 骨架起步）

### 1.4 命名约定

- **REST 路径**：小写 kebab-case，资源名复数：`/detect/tasks/{id}`
- **JSON 字段**：camelCase（若依 Jackson 默认）
- **枚举**：全大写 `PENDING | RUNNING | DONE | FAILED`
- **时间**：ISO 8601 `2026-09-18T09:12:00+08:00`（Jackson `@JsonFormat`）
- **分页**：`{ pageNum, pageSize }` 请求；`{ total, rows }` 响应（若依风格）

---

## 2. 认证接口（`/api/v1/auth`）

### 2.1 登录

`POST /api/v1/auth/login`

请求：
```json
{ "username": "20220001", "password": "secret" }
```

响应：
```json
{
  "code": 200,
  "msg": "登录成功",
  "data": {
    "accessToken": "eyJhbGciOi...",
    "refreshToken": "eyJhbGciOi...",
    "expiresIn": 3600,
    "user": {
      "id": 1001,
      "username": "20220001",
      "realName": "张三",
      "role": "STUDENT",
      "orgId": 500,
      "orgName": "计算机学院"
    }
  }
}
```

### 2.2 刷新 token

`POST /api/v1/auth/refresh`
- 请求 `{ "refreshToken": "..." }`
- 响应同 §2.1

### 2.3 登出

`POST /api/v1/auth/logout` （需 token）
- 响应 `{ "code": 200, "msg": "已退出", "data": null }`

### 2.4 当前用户

`GET /api/v1/auth/me` （需 token）
- 响应同 §2.1 `data.user`

---

## 3. 检测接口（`/api/v1/detect`）

### 3.1 提交论文

`POST /api/v1/detect/submit` （multipart/form-data，需 token）

字段：
| name | type | 说明 |
|---|---|---|
| `file` | file | 论文文件（PDF / DOCX / DOC / TXT ≤ 20 MB）|
| `degreeType` | string | `BACHELOR` / `MASTER` / `PHD` |
| `title` | string | 论文标题（可选，缺省从文件名提取） |

响应：
```json
{
  "code": 200,
  "data": {
    "taskId": 12345,
    "paperTitle": "基于深度学习的中文文本情感分析研究",
    "status": "PENDING",
    "createdAt": "2026-09-18T14:20:00+08:00"
  }
}
```

### 3.2 任务列表

`GET /api/v1/detect/tasks?pageNum=1&pageSize=20&status=&keyword=`

响应：
```json
{
  "code": 200,
  "data": {
    "total": 128,
    "rows": [
      {
        "id": 12345,
        "paperTitle": "基于深度学习的中文文本情感分析研究",
        "status": "DONE",
        "aiRate": 26.4,
        "degreeType": "MASTER",
        "threshold": 15,
        "createdAt": "2026-09-16T14:20:00+08:00",
        "finishedAt": "2026-09-16T14:20:32+08:00"
      }
    ]
  }
}
```

### 3.3 任务详情（含段落 + 句子级 + 溯源）

`GET /api/v1/detect/tasks/{id}`

响应：
```json
{
  "code": 200,
  "data": {
    "id": 12345,
    "paperTitle": "基于深度学习的中文文本情感分析研究",
    "status": "DONE",
    "aiRate": 26.4,
    "degreeType": "MASTER",
    "threshold": 15,
    "modelVersion": "mdeberta-v3-base@2027Q1",
    "createdAt": "2026-09-16T14:20:00+08:00",
    "finishedAt": "2026-09-16T14:20:32+08:00",
    "sourceLabels": {
      "qwen": 0.42, "gpt": 0.31, "human": 0.27
    },
    "paragraphs": [
      {
        "paragraphIdx": 0,
        "text": "随着...",
        "aiProb": 0.91,
        "calibratedProb": 0.88,
        "confidenceInterval": { "lower": 0.80, "upper": 0.94 },
        "sourceLabel": "qwen",
        "warnings": [],
        "sentences": [
          { "sentenceIdx": 0, "text": "...", "aiProb": 0.93 }
        ]
      }
    ]
  }
}
```

**PENDING/RUNNING 状态时** `paragraphs` / `sourceLabels` / `aiRate` 均为 `null`，前端应轮询直到 `status === "DONE"` 或 `"FAILED"`。

### 3.4 重试失败任务

`POST /api/v1/detect/tasks/{id}/retry`
- 响应：任务详情（同 §3.3，`status` 重置为 `PENDING`）

### 3.5 取消进行中任务

`POST /api/v1/detect/tasks/{id}/cancel`
- 响应 `{ "code": 200, "msg": "已取消", "data": null }`

### 3.6 删除任务（软删）

`DELETE /api/v1/detect/tasks/{id}`
- 响应 `{ "code": 200, "msg": "已删除", "data": null }`

---

## 4. 降 AIGC 接口（`/api/v1/humanize`）

### 4.1 段落改写

`POST /api/v1/humanize`

请求：
```json
{
  "taskId": 12345,
  "paragraphIdx": 0,
  "style": "academic"
}
```

响应：
```json
{
  "code": 200,
  "data": {
    "humanizeTaskId": 8801,
    "originalText": "随着...",
    "rewrittenText": "人工智能近年来发展得很快...",
    "qualityScore": 0.87,
    "modelVersion": "qwen2.5-7b-lora-humanize@v1"
  }
}
```

### 4.2 直接文本改写（不走任务）

`POST /api/v1/humanize/direct`

请求：
```json
{ "text": "...", "style": "academic" }
```

响应同 §4.1 `data`（无 `humanizeTaskId`）。

---

## 5. 报告接口（`/api/v1/report`）

### 5.1 生成/查询报告

`GET /api/v1/report/tasks/{taskId}`

响应：
```json
{
  "code": 200,
  "data": {
    "reportId": 4501,
    "pdfUrl": "/api/v1/report/download/4501.pdf",
    "excelUrl": "/api/v1/report/download/4501.xlsx",
    "signedPdfUrl": null,
    "generatedAt": "2026-09-18T14:21:00+08:00",
    "expireAt": "2029-09-18T14:21:00+08:00"
  }
}
```

### 5.2 下载

`GET /api/v1/report/download/{fileName}` — 返回二进制流（`Content-Disposition: attachment`），需 token。

---

## 6. 管理端接口（`/admin/**`，plus-ui 用）

**认证**：Sa-Token（若依基座自带），非 JWT。

### 6.1 若依自带（不重复列）
用户 / 组织 / 角色 / 菜单 / 字典 / 参数 / 日志 / 定时任务 —— 参考 RuoYi-Vue-Plus 文档。

### 6.2 业务扩展

| 接口 | 说明 |
|---|---|
| `GET /admin/detect/tasks` | 全院系任务列表（带数据权限过滤） |
| `GET /admin/detect/tasks/{id}` | 任意任务详情（无 org_id 限制） |
| `POST /admin/detect/tasks/{id}/override` | 教师人工判定（覆盖 AI 率） |
| `GET /admin/detect/statistics` | 大盘统计（本院系检测量 / 平均 AI 率 / 分布） |
| `GET /admin/model/versions` | 模型版本列表 |
| `POST /admin/model/versions/{id}/activate` | 灰度切换 Production |
| `GET /admin/threshold` / `PUT /admin/threshold` | 学位阈值配置 |

**这批接口由代码生成器批量生成 CRUD 骨架后再改造。**

---

## 7. 错误码

| code | 场景 | 前端行为 |
|---|---|---|
| 200 | 成功 | — |
| 400 | 参数错误 | Toast msg |
| 401 | 未登录或 token 过期 | 跳登录页 |
| 403 | 无权限 | Toast + 停在原页 |
| 404 | 资源不存在 | Toast + 返回列表 |
| 429 | 限流 | Toast "请求过于频繁" |
| 3000 | 论文格式不支持 | Toast |
| 3001 | 文件超大 | Toast |
| 3002 | 未能提取到文本 | Toast |
| 3003 | 任务不存在 | Toast + 返回列表 |
| 3004 | 任务进行中 | Toast + 展示进度 |
| 5000 | 推理服务不可用 | Toast "检测服务暂时不可用" |
| 5001 | 推理超时 | Toast "已自动退还额度" |

---

## 8. Java ↔ Python 推理服务契约（内部）

### 8.1 传输方式

**Phase 0（现在）**：HTTP JSON（Java `HttpClient` 调 FastAPI stub）
**Phase 1+**：切 gRPC（proto 已在 `backend-java/business-modules/ruoyi-inference/src/main/proto/detection.proto`）

### 8.2 HTTP 端点（对齐 `deploy/inference-python/main.py`）

| Java 调用点 | Python endpoint | proto RPC（切 gRPC 时） |
|---|---|---|
| 段落检测 | `POST http://{INFERENCE_HOST}:8000/api/v1/detect/paragraph` | `DetectParagraph` |
| 批量检测 | `POST /api/v1/detect/batch` | `DetectBatch` |
| 降 AIGC 生成 | `POST /api/v1/humanize` | `HumanizeStream`（流式） |
| 溯源 | `POST /api/v1/attribute` | `AttributeSource` |
| 健康 | `GET /health` | — |

### 8.3 端口与 host

- 端口固定 **8000**（`inference-python/Dockerfile` `EXPOSE 8000`；本地开发也 8000）
- Host 从环境变量取：
  ```yaml
  # 若依 application.yml
  platform:
    inference:
      host: ${INFERENCE_HOST:localhost}
      port: ${INFERENCE_PORT:8000}
  ```
- **DetectController 里必须改为从配置读取，不能硬编码**

### 8.4 Java 侧字段命名

Python 返回 snake_case（`ai_prob` / `calibrated_prob` / `source_probs`），Java 侧转 camelCase 再对外：
- Java Service 层用 Jackson `@JsonProperty` 或统一 `PropertyNamingStrategies.SNAKE_CASE` 处理 Python 响应
- 对前端接口一律 camelCase

---

## 9. 上传协议细节

### 9.1 请求

```http
POST /api/v1/detect/submit
Authorization: Bearer <token>
Content-Type: multipart/form-data; boundary=xxx

--xxx
Content-Disposition: form-data; name="file"; filename="thesis.pdf"
Content-Type: application/pdf

<binary>
--xxx
Content-Disposition: form-data; name="degreeType"

MASTER
--xxx--
```

### 9.2 客户端实现

| 端 | 用法 |
|---|---|
| Web frontend | `FormData` + `axios.post(url, form, { headers: {'Content-Type': 'multipart/form-data'} })` |
| mobile-app (RN) | `FormData` + fetch 或 axios（RN 对 `FormData` 有原生支持） |
| mobile-uniapp (H5) | `<input type="file">` + `FormData`；已实现 |
| mobile-uniapp (微信) | `uni.uploadFile`（**不能用 uni.request**）；已实现 |

### 9.3 服务端限制

- Nginx `client_max_body_size 25M`（`deploy/nginx/nginx.conf` 已设）
- Spring Boot `spring.servlet.multipart.max-file-size=20MB` `max-request-size=25MB`（`platform-api-web/application.yml` 已设）

---

## 10. 各端对齐 Checklist

### 10.1 Java 后端（S1 owner）

- [ ] `DetectController` 端口从 18000 → **配置化**（默认 8000）
- [ ] host 从 `localhost` → 环境变量 `INFERENCE_HOST`
- [ ] 补齐 `/api/v1/detect/*` 全套接口（submit / tasks / tasks/{id} / retry / cancel / delete）
- [ ] 补齐 `/api/v1/humanize` + `/api/v1/humanize/direct`
- [ ] 补齐 `/api/v1/report/*`
- [ ] 补齐 `/api/v1/auth/*`（若依自带 sys/auth 需 wrap 一层适配）
- [ ] 若依基座落地能启动
- [ ] Swagger/Knife4j 打开，`/doc.html` 可查所有接口

### 10.2 Python 推理（S2/S3/S4 共同）

- [x] `/api/v1/detect/paragraph` `/batch` `/humanize` `/attribute` `/health` 已就绪（stub）
- [ ] 保持这些路径不变；未来替换 stub 为真实模型时不动 URL
- [ ] 字段用 snake_case（`ai_prob` 等）保持不变

### 10.3 Web 用户端 `frontend/`（S1 或 S4 owner）

- [ ] 建 `frontend/src/api/` 目录 + `axios` 实例 + 拦截器
- [ ] 按 §2-§5 定义所有接口调用
- [ ] 上传用 FormData
- [ ] 401 拦截 → 跳登录

### 10.4 管理端 `plus-ui`（S1 owner）

- [ ] 部署 plus-ui（`deploy/admin-web/Dockerfile` 已就绪）
- [ ] 用若依代码生成器生成 §6.2 业务表的 CRUD 页面
- [ ] 教师 override / 大盘统计 / 阈值配置手工写

### 10.5 mobile-uniapp（S5 owner）

- [ ] `api/detect.js` 路径全改：
  - `/api/v1/mobile/detect/tasks` → `/api/v1/detect/tasks`
  - `/api/v1/mobile/detect/tasks/{id}` → `/api/v1/detect/tasks/{id}`
  - `/api/v1/mobile/detect/upload` → `/api/v1/detect/submit`
  - `/api/v1/mobile/humanize` → `/api/v1/humanize`
- [ ] 响应体从直取 `data` 改为 `response.data.data`（若依 R 结构）
- [ ] 补 §3.2 分页参数支持
- [ ] 补 §3.4-3.6 重试/取消/删除

### 10.6 mobile-app（另一协作者 owner）

- [ ] 同 §10.5 路径改造
- [ ] `axios` 拦截器已有，只需改路径

---

## 11. 冲刺落地建议

**一次 3-4 天冲刺就能全部打通**：

| 天 | 谁 | 做什么 |
|---|---|---|
| D1 | S1 | 若依基座落地 + `DetectController` 端口/host 改配置 + `docker compose up` 验证 Java+Python 通 |
| D1 | S5 | mobile-uniapp / mobile-app 路径改造 + 响应结构适配 |
| D2 | S1 | 补 `/api/v1/detect/submit` + `/tasks` 系列（先返回假数据也行，接口先打通） |
| D2 | S4 | frontend 建 `api/` 目录 + 接入检测提交与列表 |
| D3 | S1 | 补 humanize + report 接口 |
| D3 | S1 | plus-ui 部署 + 用代码生成器出 CRUD |
| D4 | 全员 | 端到端联调：Web / mobile / 管理端各起一次，走完 上传 → 检测 → 结果 → 降 AIGC 全流程 |

**验收**：`docker compose up` 起全栈后，Web + mobile-uniapp 都能真实上传论文（走 Python stub），拿到 mock 检测结果并展示报告。

---

## 12. Sources

- 若依 R 结构：`org.dromara.common.core.domain.R`（RuoYi-Vue-Plus 5.x）
- gRPC proto：`backend-java/business-modules/ruoyi-inference/src/main/proto/detection.proto`
- Python stub：`deploy/inference-python/main.py`
- Java Controller：`backend-java/business-modules/ruoyi-detect/src/main/java/com/paperaigc/detect/controller/DetectController.java`
