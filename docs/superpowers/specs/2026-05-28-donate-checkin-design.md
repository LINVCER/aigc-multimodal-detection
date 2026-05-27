# 打赏配额 + 每日签到 + PDF转Word 设计文档

## 概述

为 AIGC 多模态检测平台添加三项功能：
1. **打赏配额** — 用户点击"打赏支持"后直接获得10配额（荣誉制）
2. **每日签到** — 用户每天签到获得递增配额，连续签到奖励更多
3. **PDF 转 Word** — AI 助手模块新增 PDF→Word 转换，与现有 Word→PDF 合并为"文档互转"

## 数据模型

### User 表新增字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `last_checkin_date` | `Date \| None` | `None` | 上次签到日期 |
| `checkin_streak` | `Integer` | `0` | 当前连续签到天数 |

### UserResponse Schema 新增返回

- `last_checkin_date: date | None`
- `checkin_streak: int`

## 后端 API

### 1. `POST /auth/checkin` — 每日签到

**请求：** 无参数（依赖 `get_current_user`）

**逻辑：**
1. 检查 `last_checkin_date` 是否等于今天
   - 若是，返回 HTTP 409 "今日已签到"
2. 检查是否连续签到：
   - 若 `last_checkin_date == yesterday`：`streak += 1`
   - 否则：`streak = 1`（断签重置）
3. 计算奖励：
   - `base = 10`
   - `bonus = min(streak - 1, 6) * 2`（第1天无额外，之后每天+2，第7天封顶+12）
   - `reward = base + bonus`
4. 更新 User：
   - `quota_remaining += reward`
   - `last_checkin_date = today`
   - `checkin_streak = streak`
5. 返回：
```json
{
  "reward": 14,
  "streak": 3,
  "quota_remaining": 144
}
```

### 2. `POST /auth/donate` — 打赏领取

**请求：** 无参数（依赖 `get_current_user`）

**逻辑：**
1. `quota_remaining += 10`
2. 返回：
```json
{
  "reward": 10,
  "quota_remaining": 134
}
```

**注意：** 无次数限制（荣誉制）。

## 前端 UI

### 仪表盘签到卡片

**位置：** 欢迎区域下方、检测入口卡片上方

**显示内容：**
- 标题："每日签到"
- 当前连续签到天数
- 最近7天签到日历（圆点标记已签到的日期）
- 签到按钮："签到 +X"（X为今日应得配额，已签到则显示"已签到"并禁用）

**样式：** 白色卡片，圆角16px，与现有卡片风格一致

### 打赏对话框增强

**现有：** 静态二维码图片 + "感谢您的支持！"

**增强：**
- 二维码下方添加"我已打赏，领取配额"按钮
- 点击后调用 `POST /auth/donate`
- 成功后显示 "+10 配额" 提示，更新顶部配额显示

## 签到奖励规则

| 连续天数 | 基础 | 额外 | 总计 |
|----------|------|------|------|
| 第1天 | 10 | 0 | 10 |
| 第2天 | 10 | 2 | 12 |
| 第3天 | 10 | 4 | 14 |
| 第4天 | 10 | 6 | 16 |
| 第5天 | 10 | 8 | 18 |
| 第6天 | 10 | 10 | 20 |
| 第7天+ | 10 | 12 | 22（封顶） |

断签重置为第1天（10配额）。

## 文件改动

### 后端
- `backend/app/models/user.py` — 添加 `last_checkin_date` 和 `checkin_streak` 字段
- `backend/app/schemas/user.py` — UserResponse 添加新字段
- `backend/app/api/v1/auth.py` — 添加 `/checkin` 和 `/donate` 端点
- `backend/alembic/versions/` — 数据库迁移脚本

### 前端
- `frontend/src/stores/auth.ts` — 添加 `checkin()` 和 `donate()` 方法
- `frontend/src/views/Dashboard.vue` — 添加签到卡片 + 增强打赏对话框

---

## PDF 转 Word 功能

### UI 改造

**Tab 1 "文档转 PDF" → 改为 "文档互转"：**
- 上传区域接受 `.pdf`、`.docx`、`.txt` 文件
- 自动识别文件类型，显示转换方向：
  - `.pdf` → 生成 `.docx`（"转换为 Word"）
  - `.docx` / `.txt` → 生成 `.pdf`（"转换为 PDF"，现有逻辑不变）
- 按钮文字根据文件类型动态变化

### 后端 API

**改造 `POST /assistant/convert-to-pdf` → `POST /assistant/convert-document`：**

- 端点改名，保留原有 `.docx` → PDF 和 `.txt` → PDF 逻辑
- 新增 `.pdf` → `.docx` 逻辑：
  - 使用 LibreOffice：`soffice --headless --convert-to docx --outdir /tmp input.pdf`
  - 返回 `.docx` 文件作为下载附件
- 根据文件扩展名自动选择转换方向
- 返回的 Content-Disposition 文件名自动改为对应扩展名

### 文件改动

- `frontend/src/views/AIAssistant.vue` — Tab 改名、上传 accept 扩展、按钮文字动态化
- `backend/app/api/v1/assistant.py` — 端点改名、新增 PDF→Word 转换逻辑
