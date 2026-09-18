# ADMIN_REQUIREMENTS · 管理端需求文档

> 面向 `plus-ui`（若依配套 Vue3 管理端）挂载业务后的**教务/教师/院系管理员**使用场景。
> 目的：先对齐范围，再实施 —— 避免实施后发现漏能力或过度设计。
> 关联：[ENTERPRISE_ARCHITECTURE.md](ENTERPRISE_ARCHITECTURE.md) · [API_CONTRACT.md](API_CONTRACT.md) · [TEAM_ROLES.md](TEAM_ROLES.md) · [COMPETITIVE_FEATURE_GAP.md](COMPETITIVE_FEATURE_GAP.md) §6.2
> 报告日期：2026-09-18

---

## 0. 约束与决策前提

- **端选型固定**：`plus-ui`（RuoYi-Vue-Plus 官方配套），不重开一套。挂载已在 `deploy/admin-web/Dockerfile` 就绪，未真跑过。
- **认证走 Sa-Token**（若依基座内置），**不复用**用户端的 JWT。管理员账号在 `sys_user` 表，用户端账号在同表另标记 `role`。
- **对齐 TEAM_ROLES §4 负向清单**：不做支付/发票、不做 SSO CAS 对接、不做 LMS 集成、不做多语言、不做私有化一键部署 —— 均为课题阶段延后项。
- **API 命名**：管理端调用 `/admin/**`，与用户端 `/api/v1/**` 隔离；后端 controller 加 `@RequestMapping("/admin/...")` 前缀。
- **数据权限**：教师只看本院系任务；院系管理员看本院系；教务超管看全部。走若依 `@DataScope`。

---

## 1. 角色

| Code | 中文名 | 数据可见范围 | 主要操作 |
|---|---|---|---|
| `ADMIN` | 平台超管 | 全部 | 全部菜单，含系统配置、模型版本切换 |
| `STAFF_UNIV` | 教务超管（校级） | 全校任务 | 阈值配置、大盘统计、批量导出、模型版本审核 |
| `STAFF_COLLEGE` | 院系管理员 | 本院系任务 | 大盘（限本院）、批量导出（本院）、教师账号增删 |
| `TEACHER` | 教师 | 所指导学生的任务 | 查看学生任务详情、人工判定 override、批注、批量下载报告 |
| `STUDENT` | 学生 | **不进管理端**（走用户端 web/mobile） | — |

**基础表**：所有角色都落在 `sys_user`（若依自带），`role` 字段区分；`org_id` = `sys_dept.id`（院系）。学生 role 不在管理端菜单里出现。

---

## 2. 页面地图（左侧菜单）

按若依菜单树组织，✅ = 若依自带用即可；🆕 = 我们新增；✏ = 若依自带但需业务定制。

```
📊 首页                        ✏  改造为教务大盘（4 KPI + 30 天趋势 + Top10 高风险学生）
├─ 检测管理                    🆕
│  ├─ 论文检测记录              🆕  全平台/本院系任务列表 + 复用用户端 detail 页只读版
│  ├─ 教师人工判定 override    🆕  已 DONE 的任务允许教师手动改结论（附理由 + 日志）
│  ├─ 批量导出                  🆕  按班级/院系/时间段勾选 → 压缩包 PDF + Excel 汇总
│  └─ 模型版本                  🆕  当前生产版本 + 校准参数 + 手动切换（超管专用）
├─ 学生管理                    🆕
│  ├─ 学生名单                  🆕  按院系/班级筛选，可导入 Excel 批量建号
│  └─ 教师-学生关系             🆕  指定教师所指导的学生（决定教师能看到谁的任务）
├─ 阈值配置                    🆕
│  └─ 学位红线                  🆕  BACHELOR/MASTER/PHD 默认 20/15/10%，按学校/院系覆盖
├─ 报告模板                    🆕  PDF 报告字段与顺序自定义（保留院系抬头、校方章）
├─ 系统管理                    ✅
│  ├─ 用户管理                  ✅  若依 sys_user
│  ├─ 角色管理                  ✅  加入本文档 §1 5 个角色
│  ├─ 菜单管理                  ✅
│  ├─ 部门管理（=院系）         ✅  改标签为"院系"
│  ├─ 岗位管理                  ✅
│  ├─ 字典管理                  ✅
│  ├─ 参数设置                  ✅
│  └─ 通知公告                  ✅
├─ 系统监控                    ✅
│  ├─ 在线用户 / 日志 / 缓存 / Actuator ✅  若依全套
│  └─ 推理服务健康              🆕  单独一屏显示 Python 推理服务 /health、模型版本、GPU（如有）
└─ 系统工具                    ✅
   ├─ 表单 / 代码 / 系统 ✅  若依 CRUD 生成器（用它生成 §2 里的 🆕 页面骨架）
```

**明确砍掉**（若依自带但对课题无用）：定时任务（用不到）、支付宝/微信 SDK（不做支付）、云存储（用 MinIO 已够）—— 保留菜单入口但不上课时表。

---

## 3. 关键页面详细字段

### 3.1 教务大盘（首页）

```
顶部 4 KPI 卡（可点击下钻到明细列表）：
  今日检测量 · 本月检测量 · 平均 AI 率 · 达标率

中部：
  30 天检测量 + 平均 AI 率 双折线图（复用用户端 SVG 图）
  按学位类型堆叠柱状图（本科/硕士/博士，本月）

底部：
  Top 10 高风险学生：学号 · 姓名 · 论文题 · AI 率 · 超线幅度
  Top 5 高活跃教师：教师 · 本月审阅任务数 · 平均判定时长
```

**接口**：复用 `GET /api/v1/detect/statistics` + 新加 `GET /admin/detect/top-risk-students` + `GET /admin/detect/top-active-teachers`

### 3.2 检测记录列表（管理端）

字段列（相对用户端多 4 列）：
- `学生 · 学号 · 学院 · 班级` · 论文标题 · 学位 · 红线 · AI 率 · 状态 · 溯源分布 · 提交时间 · 教师 override · 操作

操作：
- 查看（进只读版详情，页面 URL 走 `/admin/task/:id`）
- 教师 override（弹窗输入判定 + 理由）
- 下载 PDF（复用 `/api/v1/report/tasks/{id}/pdf`）
- 删除（超管只）

筛选面板：
- 院系 · 班级（联动 dept 树）· 学位类型 · 状态 · 提交时间段 · AI 率范围（用 slider）· 是否达标 · 是否有教师 override

### 3.3 教师人工判定 override

一个抽屉/弹窗，字段：
- 系统判定：AI 率 X% · 达标/超线
- 教师判定（radio）：确认 AI 生成 · 疑似但可通过 · 判定人写 · 需二次检测
- 判定理由（textarea 必填 ≥ 20 字）
- 是否同步通知学生（switch，默认 on）

**审计**：所有 override 记录进 `detect_override_log` 表（新建：taskId / teacherId / verdict / reason / createdAt），管理端"审计日志"页可查。

### 3.4 批量导出

流程：
1. 从检测列表勾选任意条数 → 顶部"批量导出"按钮
2. 弹窗选择：导出格式（Excel 汇总 / PDF 单份 / 两者 ZIP 压缩包）+ 是否含教师 override 备注
3. 后端异步生成 ZIP → MinIO → 返回下载 URL 或通过站内信推送
4. 大批量（>100 篇）走后台任务队列，进度条实时刷新

**接口**：`POST /admin/detect/export` body `{ taskIds:[], format:'zip', includeOverride:true }` → `{ jobId }`；`GET /admin/detect/export/{jobId}` → `{ status, progress, downloadUrl }`

### 3.5 模型版本管理

字段：
- 版本号 · 训练日期 · Backbone · 训练集 · val_f1 · ECE · 校准参数 · 状态（Production / Staging / Archived）· 部署时间 · 部署操作人

操作：
- 上传新版本（超管，多字段填写 + `.pth`/`.onnx` 上传到 MinIO）
- Staging 切换 → Production（灰度提示：改动即时生效，需二次确认）
- 归档旧版本

**接口**：`GET /admin/model/versions` · `POST /admin/model/versions/{id}/activate`

### 3.6 学生名单 / 教师-学生关系

**学生名单**：Excel 导入模板（学号 · 姓名 · 学院 · 班级 · 邮箱 · 学位类型 · 指导教师工号）→ 后端解析批量建号 + 邮件初始密码。

**教师-学生关系**：新表 `teacher_student (id, teacherId, studentId, createdAt)`；两栏穿梭框（左：本院系全部学生，右：该教师已指导），支持批量增删。

### 3.7 阈值配置

三层覆盖优先级（后覆盖前）：
1. 全平台默认 `20 / 15 / 10`
2. 校级覆盖（如"清华：15 / 12 / 8"）
3. 院系级覆盖（如"清华软院：12 / 10 / 6"）

页面：树形组织选择 + 表格输入本科/硕士/博士红线；空值代表继承上级。

**接口**：`GET /admin/threshold` · `PUT /admin/threshold/{orgId}` body `{ bachelor, master, phd }`

### 3.8 推理服务健康监控

一屏单页：
- Python 推理服务：`/health` 状态灯 · 最近一次响应时延 · 当前加载模型版本 · GPU 利用率（若可获取）
- Java-Python 调用统计：过去 1h 请求量 / P95 延迟 / 错误率
- 手动 "冒烟测试"按钮：调 `/detect/paragraph` 传示例文本，看返回是否正常

**接口**：复用 `GET /api/v1/detect/health` + 新加 `GET /admin/inference/metrics`

---

## 4. 权限矩阵（页面级）

| 页面 | ADMIN | STAFF_UNIV | STAFF_COLLEGE | TEACHER |
|---|:-:|:-:|:-:|:-:|
| 教务大盘 | 全校 | 全校 | 本院系 | 所指导学生聚合 |
| 检测记录列表 | 全校 | 全校 | 本院系 | 所指导学生 |
| 教师 override | ✅ | ✅ | ✅ | ✅ 仅所指导学生 |
| 批量导出 | ✅ | ✅ | 本院系 | ❌ |
| 模型版本 | ✅ | 只读 | ❌ | ❌ |
| 学生名单 | ✅ | ✅ | 本院系 | 只读所指导 |
| 教师-学生关系 | ✅ | ✅ | 本院系 | ❌ |
| 阈值配置 | ✅ | 全平台+校级 | 本院系 | ❌ |
| 报告模板 | ✅ | ✅ | ❌ | ❌ |
| 系统管理 / 监控 | ✅ | 只读日志 | ❌ | ❌ |

**技术手段**：Sa-Token 注解 `@SaCheckPermission` + `@DataScope`（若依自带）。

---

## 5. 数据库补表

除若依自带 `sys_*` 外，新增：

```sql
-- 教师-学生指导关系
CREATE TABLE teacher_student (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  teacher_id BIGINT NOT NULL COMMENT 'sys_user.user_id',
  student_id BIGINT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_teacher (teacher_id),
  INDEX idx_student (student_id),
  UNIQUE KEY uk_pair (teacher_id, student_id)
);

-- 教师人工判定日志
CREATE TABLE detect_override_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  teacher_id BIGINT NOT NULL,
  verdict VARCHAR(32) NOT NULL COMMENT 'ai/suspect_but_pass/human/recheck',
  reason TEXT,
  notify_student TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_task (task_id),
  INDEX idx_teacher_time (teacher_id, created_at)
);

-- 学位红线三级覆盖
CREATE TABLE detect_threshold (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  scope VARCHAR(16) NOT NULL COMMENT 'DEFAULT/UNIVERSITY/COLLEGE',
  org_id BIGINT NULL COMMENT 'sys_dept.dept_id; scope=DEFAULT 时为 null',
  degree_type VARCHAR(16) NOT NULL COMMENT 'BACHELOR/MASTER/PHD',
  threshold DECIMAL(5,2) NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_scope_org_degree (scope, org_id, degree_type)
);

-- 模型版本
CREATE TABLE model_version (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  version_code VARCHAR(64) NOT NULL UNIQUE,
  backbone VARCHAR(64),
  train_dataset VARCHAR(255),
  val_f1 DECIMAL(6,4),
  ece DECIMAL(6,4),
  calibration_params JSON,
  status VARCHAR(16) NOT NULL DEFAULT 'STAGING' COMMENT 'STAGING/PRODUCTION/ARCHIVED',
  storage_url VARCHAR(512),
  created_by BIGINT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deployed_at DATETIME NULL
);

-- 批量导出任务
CREATE TABLE export_job (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  creator_id BIGINT NOT NULL,
  task_ids JSON NOT NULL,
  format VARCHAR(16) NOT NULL COMMENT 'zip/xlsx/pdf',
  include_override TINYINT(1) NOT NULL DEFAULT 1,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  progress INT NOT NULL DEFAULT 0,
  download_url VARCHAR(512),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at DATETIME NULL,
  INDEX idx_creator_time (creator_id, created_at)
);
```

**执行**：并入 `docs/sql/init.sql`，`init-scripts` 挂载时自动跑。

---

## 6. 实施路径（Wave 3 分批）

| 批 | 目标 | 依赖 | 时长估 |
|---|---|---|---|
| **W3.a** | plus-ui 部署跑通 + 挂载 ruoyi-detect 业务模块 + 若依基座 sys_* 数据可用 | 现有 Dockerfile 就绪 | 1-2 天（首次挂载会踩若依配置坑） |
| **W3.b** | 用若依代码生成器出 §5 五张新表的 CRUD 骨架（学生名单/教师-学生/阈值/模型/导出） | W3.a | 半天（代码生成器很快） |
| **W3.c** | 检测记录列表 + 教师 override 弹窗 + 批量导出（这一批用得最勤） | W3.b + `detect_override_log` | 2-3 天 |
| **W3.d** | 教务大盘首页 + 推理服务健康 | 复用现有 stats 接口 | 1 天 |
| **W3.e** | 阈值配置三级覆盖 + 报告模板配置 | detect_threshold | 1-2 天 |
| **W3.f** | 学生名单 Excel 导入 + 教师-学生穿梭框 | teacher_student | 1 天 |

**并行**：把 Wave 2 剩余的 **PDF 报告封面美化 + 校方章** 塞进 W3.e（阈值/模板一起做）；**批量上传** 塞进用户端 mobile-uniapp 后续小改（教师批量在管理端 W3.c 做）。

---

## 7. 明确不做（负向清单）

- ❌ SSO CAS / OIDC 学校统一身份对接（自定义登录先撑用）
- ❌ 私有化一键部署 K8s Helm（用户课题环境用 docker-compose 够了）
- ❌ 教师批注在段落级：太重，教师用 override 判定 + reason 一段话即可
- ❌ 论文差异对比双份上传：Wave 3 之外
- ❌ 消息中心（若依自带走通知公告即可，不做站内信/邮件模板）
- ❌ 报表订阅 / 导出到第三方教务系统
- ❌ 移动端管理版（教师用桌面 plus-ui 即可，不做管理端 App）

---

## 8. 需要你 confirm 的 4 个决策点

在动手 W3.a 之前，请 review 以下：

**Q1：角色数量**
- 上面给了 5 个（ADMIN/STAFF_UNIV/STAFF_COLLEGE/TEACHER/STUDENT）—— 是否合适？还是精简到 3 个（ADMIN/TEACHER/STUDENT）？
- **建议 5 个**（教务超管和院系管理员对应的实际人是不同岗）

**Q2：教师 override 是否要通知学生**
- 上面设计成默认通知（学生用户端能看到"你的报告已被教师复核"）
- **建议：通知，但可关**（教师有时想内部沟通不想惊动学生）

**Q3：批量导出是走同步还是异步**
- 30 篇以内可以同步（不用异步任务表）；≥30 走异步
- **建议：全走异步**（学生数据量大时同步会 timeout；异步用 export_job 表跟踪）

**Q4：模型版本切换的粒度**
- 是"全校统一切换"还是"允许某院系单独切"（比如"软院用 v2、文院用 v1"）
- **建议：全校统一**（学术公平；分院系切换会引战）

**答复"按你建议"或"我调整"，然后进入 W3.a plus-ui 部署实操。**
