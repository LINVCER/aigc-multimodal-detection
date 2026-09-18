# OPERATIONS_REQUIREMENTS · 运营后台需求文档

> **产品定位纠正**：不是面向学校机构的教务 SaaS，是**面向个人用户（主打学生自查）的 C 端工具**。
> 本文档定义**运营后台**（给项目团队 / 产品 / 开发者用），不是"教务管理系统"。
> 关联：[ENTERPRISE_ARCHITECTURE.md](ENTERPRISE_ARCHITECTURE.md) · [API_CONTRACT.md](API_CONTRACT.md) · [TEAM_ROLES.md](TEAM_ROLES.md) · 替换废弃的 `ADMIN_REQUIREMENTS.md`
> 报告日期：2026-09-18

---

## 0. 定位与前提

- **C 端产品目标用户**：个人学生（毕业论文 / 作业 / 报告自查）为主，兼容一般写作者
- **需要登录**：手机号 / 微信 / 邮箱（三选一即可），未登录不能提交检测
- **有运营后台**：给项目团队用，不是给学校用
- **场景预设**（替代原"学位红线"）：`学术论文（本科/硕士/博士细分）· 职业报告 · 自媒体 · 其他`
- **端选型固定**：`plus-ui`（若依配套 Vue3 管理端）继续用，但重构菜单树
- **认证**：运营后台走 Sa-Token（若依内置）；C 端用户走 JWT（用户端 Web / Mobile）

---

## 1. 角色重定义

只有 **2 个角色**（大幅简化）：

| Code | 中文名 | 落在哪 | 说明 |
|---|---|---|---|
| `USER` | 普通用户 | C 端 Web / mobile-uniapp | 手机号 / 微信 / 邮箱登录，进 C 端；**不进后台** |
| `OPS_ADMIN` | 运营 / 开发管理员 | plus-ui 后台 | 内部账号，若依 `sys_user` 建，看运营数据 |

**取消**：`STAFF_UNIV / STAFF_COLLEGE / TEACHER` 全废（教务视角）。
**保留**：若依原生 `admin` 超管账号做兜底。

---

## 2. 运营后台页面地图

给 `OPS_ADMIN` 一个人（或小团队）用的后台，专注 4 件事：**看用户 · 看任务 · 看反馈 · 管模型**。

```
📊 首页                        🆕 运营大盘（DAU / 检测量 / 平均 AI 率 / 场景分布 / 30 天趋势）
├─ 用户管理                    🆕
│  ├─ 用户列表                  🆕 手机号/邮箱/微信 openid + 注册时间 + 累计检测数 + 状态
│  ├─ 异常账号                  🆕 短时高频 / 大文件疑似滥用 / 被投诉 → 一键封禁
│  └─ 账号详情                  🆕 单用户所有检测任务时间线（点开进任务详情）
├─ 检测任务运营视图            🆕
│  ├─ 全平台任务列表            🆕 无 org 过滤，跨用户查询；按场景/AI率/状态筛选
│  ├─ 失败/超时任务             🆕 需人工介入的：模型异常、Tika 抽不出文本等
│  └─ 高频用户分析              🆕 单用户 1h 内检测 > 10 次的自动告警
├─ 用户反馈                    🆕 （用户从 C 端提交反馈 → 后台看 → 标记已处理）
│  ├─ 反馈列表                  🆕 分类：Bug / 建议 / 结果申诉（"检测不准"）
│  └─ 结果申诉详情              🆕 用户主张 AI 率有误 → 关联对应任务，运营核对
├─ 模型运营                    🆕
│  ├─ 模型版本                  🆕 当前生产 / Staging，一键切换（同 §2.3）
│  ├─ 灰度实验                  🆕（P2）10% / 50% 流量切新模型，看 A/B 数据
│  └─ 场景预设阈值              🆕 全平台默认 + 每场景红线可调（本科 20% / 硕士 15% / 博士 10% / 职业报告 15% / 自媒体 30% ...）
├─ 系统管理                    ✅  若依自带
│  ├─ 用户管理（=运营账号）      ✅ 后台账号增删（不是 C 端用户）
│  ├─ 角色 / 菜单 / 字典        ✅
│  └─ 通知公告                  ✅ （可选：在 C 端弹通知）
└─ 系统监控                    ✅
   ├─ 在线用户 / 日志 / Actuator ✅
   └─ 推理服务健康              🆕 Python 推理 /health + P95 延迟 + 错误率
```

**明确砍掉**（比原 ADMIN 文档更精简）：
- 教务大盘 → 改为运营大盘
- 教师 override / 教师-学生关系 → 完全删除
- 学生名单 Excel 导入 → 用户自己注册
- 阈值三级覆盖（校/院/班）→ 改为按场景预设配置（平台全局）
- 批量导出（教师端场景）→ 删除；C 端个人下载单份 PDF 已够
- 报告电子签校方章 → 删除（个人场景无学校背书需求）
- 私有化部署 → 删除（C 端 SaaS 单点部署即可）

---

## 3. 关键页面详细字段

### 3.1 运营大盘（首页）

```
顶部 KPI 卡（5 个）：
  今日新增用户 · 今日检测数 · 累计用户 · 累计检测数 · 平均 AI 率

中部：
  30 天趋势（新增用户 + 检测量 + 平均 AI 率）三线折线
  场景分布饼图：学术论文本科/硕士/博士 · 职业报告 · 自媒体 · 其他

底部：
  Top 10 高活跃用户（最近 7 天）· Top 10 待处理反馈
```

**接口**：`GET /admin/dashboard`（后端聚合）

### 3.2 用户列表

字段：
- 用户 ID · 登录方式（🔵 手机 / 🟢 微信 / 🟡 邮箱）· 手机号/邮箱/openid（脱敏）· 累计检测数 · 最近登录 · 注册时间 · 状态（正常 / 已封禁 / 未激活）

操作：
- 查看详情 · 封禁 / 解封 · 重置密码（如是邮箱登录）· 加白名单（免限流）

筛选：注册时间段 · 登录方式 · 累计检测数区间 · 状态

### 3.3 异常账号识别

规则（后台 CronJob 每 5 分钟跑一次）：
- 1h 内提交 > 20 次 → 疑似脚本刷额度 → 自动标注 `SUSPICIOUS`
- 同 IP 24h 内注册 > 5 个账号 → 疑似黑号 → 手动确认
- 单次上传 > 15MB × 5 次 → 疑似消耗资源 → 限流

页面：SUSPICIOUS 用户列表 + 一键封禁 + 查看关联任务

### 3.4 全平台任务列表

字段：
- 任务 ID · 用户（脱敏账号）· 论文标题 · 场景（学术-硕士 / 职业 / 自媒体 …）· AI 率 · 状态 · 提交时间

差异 vs C 端"我的任务"：**看得到任意用户任务**，供运营复核 / 结果申诉时定位。

**明确不做**：教师 override —— 运营不能改用户报告结论，只能查看。

### 3.5 用户反馈

C 端有个"反馈"按钮（`我的`页面 or 报告详情页），弹表单：
- 分类（radio）：使用 Bug · 建议 · 结果申诉（"我觉得检测不准"）
- 关联任务 ID（可选，如果分类=结果申诉则必填）
- 描述（textarea）
- 联系方式（可选，回复用）

**表结构**：见 §5 `user_feedback`

后台列表：分类筛选 · 状态（待处理 / 处理中 / 已回复 / 已忽略）· 时间倒序

**结果申诉详情**：显示反馈内容 + 关联任务的完整报告 + "标注申诉合理"按钮（不改用户报告，但记入模型改进 backlog）

### 3.6 模型版本切换

字段：
- 版本号 · 训练日期 · Backbone · 校准参数 · val_f1 · 状态（Production / Staging / Archived）· 上线时间 · 部署人

操作：
- 上传新版本（.pth 上 MinIO + 填元信息）
- 灰度：`0% / 10% / 50% / 100%` 四档流量切换（Redis key `model.rollout.pct`）
- 一键回滚（切回上一 Production 版本）

**灰度实现**：请求进 Java 后端时按 `userId % 100 < rolloutPct` 决定用 Staging 还是 Production 模型，Python 侧带 `model_version` 参数。

### 3.7 场景预设阈值

页面：一张表格，每场景一行 AI 率红线（默认值 + 是否启用）

```
场景                默认 AI 率红线   是否启用
学术论文-本科        20%              ✅
学术论文-硕士        15%              ✅
学术论文-博士        10%              ✅
职业报告             15%              ✅
自媒体               30%              ✅
其他                 25%              ✅
```

**保存到**：`detect_threshold` 表（改后即时生效，用户端拉最新配置）

### 3.8 推理服务健康监控

同原文档 §3.8：Python `/health` 状态灯 + P95 延迟 + 错误率 + 手动冒烟按钮。

---

## 4. C 端改造项（配合定位调整）

原有代码需要改的地方（**这些是下一步实施的清单，不是本文档实施**）：

| 改动 | 位置 | 详情 |
|---|---|---|
| "学位类型" → "使用场景" | `web/src/views/Upload.vue` · `mobile-uniapp/pages/upload/upload.vue` | DEGREES 数组换成 SCENARIOS：`学术-本科/硕士/博士 · 职业报告 · 自媒体 · 其他` |
| 提交字段 `degreeType` → `scenario` | 前端 API 调用 + `DetectController.submit` 参数 | 后端 THRESHOLD Map 改为 SCENARIO_THRESHOLD |
| 报告 Hero "红线 N%" 措辞 | `TaskDetail.vue` 两端 | 保留"红线"字样但改成"该场景建议 ≤ N%" |
| 增加登录方式 | `Login.vue` 两端 | 加"微信"/"手机号"入口，走后端 `/auth/sms/send` `/auth/wechat/callback` |
| C 端加"反馈"入口 | `Profile.vue` 两端 + `TaskDetail.vue`（结果申诉入口） | 弹窗表单 → `POST /api/v1/feedback` |
| 移除"学校/学位"叙述 | README / 页面副标题 / 隐私提示 | 主标题从"教育部 2026 新规"改为"AI 检测 · 一键降 AIGC"更普适 |

---

## 5. 数据库补表（重写）

**保留**（用得上）：
- 若依自带 `sys_*` 全套
- `paper / detect_task / detect_paragraph_result / detect_sentence_result / humanize_task / report`（用户端主线）

**新增**（配合运营后台）：

```sql
-- 用户反馈（C 端提交，后台查看）
CREATE TABLE user_feedback (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  category VARCHAR(16) NOT NULL COMMENT 'bug / suggestion / appeal',
  task_id BIGINT NULL COMMENT '结果申诉时关联的检测任务 ID',
  content TEXT NOT NULL,
  contact VARCHAR(128) NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/PROCESSING/REPLIED/IGNORED',
  handled_by BIGINT NULL COMMENT '处理的运营账号 ID',
  handled_reply TEXT NULL,
  handled_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user (user_id),
  INDEX idx_status_time (status, created_at),
  INDEX idx_task (task_id)
);

-- 场景预设阈值（原学位红线改造）
CREATE TABLE detect_scenario_threshold (
  scenario VARCHAR(32) PRIMARY KEY COMMENT 'academic_bachelor / academic_master / academic_phd / job_report / self_media / other',
  label VARCHAR(64) NOT NULL COMMENT '展示名',
  threshold DECIMAL(5,2) NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 模型版本（同原文档，保留）
CREATE TABLE model_version (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  version_code VARCHAR(64) NOT NULL UNIQUE,
  backbone VARCHAR(64),
  train_dataset VARCHAR(255),
  val_f1 DECIMAL(6,4),
  ece DECIMAL(6,4),
  calibration_params JSON,
  status VARCHAR(16) NOT NULL DEFAULT 'STAGING',
  rollout_pct INT NOT NULL DEFAULT 0 COMMENT '灰度百分比 0-100',
  storage_url VARCHAR(512),
  created_by BIGINT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deployed_at DATETIME NULL
);

-- 异常账号标记（供 CronJob 写入 + 运营查看）
CREATE TABLE user_abnormal_flag (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  flag_type VARCHAR(32) NOT NULL COMMENT 'high_freq / bulk_ip / large_file / manual',
  detail TEXT NULL COMMENT 'JSON 明细',
  handled TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user (user_id),
  INDEX idx_handled_time (handled, created_at)
);
```

**废弃**（原 ADMIN 文档提议但对个人产品无用）：
- ❌ `teacher_student`（无教师概念）
- ❌ `detect_override_log`（运营不改用户结论）
- ❌ `detect_threshold` 三级覆盖（改成 `detect_scenario_threshold` 单层配置）
- ❌ `export_job`（无批量导出场景）

---

## 6. 实施路径（Wave 3 分批 · 重排）

对齐 C 端定位，原 W3.a-W3.f 重排：

| 批 | 目标 | 时长估 | 备注 |
|---|---|---|---|
| **W3.a** | plus-ui 部署跑通 + ruoyi-detect 挂载 + 若依 sys_* 数据可用 | 1-2 天 | 首次挂载踩坑 |
| **W3.b** | C 端"学位类型 → 使用场景"改造（Web + mobile-uniapp + Java `SCENARIO_THRESHOLD`） | 半天 | 定位纠正必须先做 |
| **W3.c** | 登录扩展：手机号（SMS）+ 微信小程序 code2Session + 邮箱验证码 | 1-2 天 | 依赖三方 SDK 与短信服务，成本项 |
| **W3.d** | 用户反馈：C 端入口（Profile + TaskDetail 页反馈按钮）+ 后台反馈列表 | 1 天 | user_feedback 表 |
| **W3.e** | 运营后台首页大盘 + 全平台任务列表 + 用户列表 | 2 天 | 复用现有 `/statistics` + 加分页 |
| **W3.f** | 模型版本管理 + 场景阈值配置 + 灰度切换 | 1-2 天 | model_version / detect_scenario_threshold |
| **W3.g** | 异常账号识别 + 推理服务健康监控 | 1 天 | Cron + 现有 `/health` |

**并行**：Wave 2 剩余的 **PDF 报告封面美化** 可在 W3.b 一起做（场景改造后，PDF 抬头也要跟着改）。

---

## 7. 明确不做（本产品阶段负向清单）

- ❌ 学校/教务/教师/院系/班级/学生分组
- ❌ 教师端 override / 人工判定
- ❌ 批量上传 / 批量导出 ZIP（个人不需要）
- ❌ 报告电子签 / 校方章
- ❌ SSO CAS / OIDC 学校统一身份
- ❌ 私有化部署方案（C 端 SaaS 单点即可）
- ❌ 支付 / 发票 / 优惠码（用户已确认收费功能先不做）
- ❌ 多语言 UI
- ❌ LMS 集成
- ❌ 移动端运营后台 App（plus-ui 桌面足够）

---

## 8. 需要你 confirm 的 3 个决策点（简化版）

**Q1：三种登录方式全上还是先做一种？**
- 建议：**先做手机号 + 邮箱**（成本最低，微信小程序等 mobile-uniapp 走微信小程序端时再补 `wx.login`）

**Q2：C 端反馈按钮位置**
- 建议：**Profile 页 + 报告详情页各一个入口**（Profile 里是通用反馈，详情页是结果申诉快捷入口）

**Q3：模型灰度实现是否 Phase 1 就上？**
- 建议：**Phase 1 只上"上传新版 + 一键切生产"，灰度百分比 Phase 2 再做**（本科课题不需要那么复杂）

答复"按你建议"或指出调整，进入 W3.a plus-ui 部署实操。
