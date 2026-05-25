# AIGC--多模态检测

> 面向教育、出版、传媒场景的 AI 生成内容检测平台，覆盖文本/图像/音频三模态，支持论文专项检测与一键降 AIGC。

---

## 目录

- [系统架构](#系统架构)
- [检测管线](#检测管线)
- [关键 Prompt 与 Vibe 思路](#关键-prompt-与-vibe-思路)
- [AI 调用逻辑](#ai-调用逻辑)
- [部署步骤](#部署步骤)
- [项目结构](#项目结构)

---

## 系构架

### 整体分层

```
┌─────────────────────────────────────────────────────────┐
│                      客户端层                             │
│  Vue3 Web 前端 (14页)  │  微信小程序  │  Chrome 扩展      │
└────────────┬────────────┴──────┬──────┴────────┬─────────┘
             │                   │               │
             ▼                   ▼               ▼
┌─────────────────────────────────────────────────────────┐
│                  FastAPI 后端 (8 个路由模块)               │
│  auth · detection · upload · report · admin              │
│  identifier · robustness · assistant                     │
└────────┬──────────┬──────────┬──────────┬───────────────┘
         │          │          │          │
         ▼          ▼          ▼          ▼
┌────────────┐ ┌─────────┐ ┌───────┐ ┌──────────────────┐
│  检测引擎   │ │ LLM 服务 │ │ 存储层 │ │    基础设施        │
│            │ │          │ │       │ │                  │
│ 文本3路融合 │ │ DeepSeek │ │ MySQL │ │ Redis + Celery   │
│ 图像3路融合 │ │ MiMo-VL  │ │ MinIO │ │ Alembic 迁移     │
│ 音频3路融合 │ │          │ │       │ │                  │
└────────────┘ └─────────┘ └───────┘ └──────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3.5 + TypeScript + Vite 6 + Element Plus 2.9 + Pinia + ECharts |
| 后端 | Python 3.11 + FastAPI 0.115 + Uvicorn (全异步) |
| 数据库 | MySQL (aiomysql) + SQLAlchemy async ORM + Alembic |
| 缓存/队列 | Redis + Celery |
| 文件存储 | MinIO |
| 认证 | JWT (HS256, access + refresh token) |
| 文本模型 | hfl/chinese-roberta-wwm-ext (HIT) |
| 图像模型 | openai/clip-vit-large-patch14 + 自研高频噪声 CNN |
| 音频模型 | wav2vec2-xls-r-300m + RawNet2 |
| LLM | DeepSeek (OpenAI 兼容) / MiMo-VL (Anthropic 兼容) |
| 小程序 | uni-app 3.x |
| 浏览器插件 | Chrome Extension Manifest V3 |

### 后端路由模块

| 模块 | 端点前缀 | 功能 |
|------|---------|------|
| `auth` | `/api/v1/auth` | 注册、登录、Token 刷新 |
| `detection` | `/api/v1/detect` | 单条文本/图像/音频检测 |
| `upload` | `/api/v1/detect` | 文档上传、论文检测、批量检测 |
| `report` | `/api/v1/report` | 检测报告生成与导出 |
| `admin` | `/api/v1/admin` | 用户管理、配额管理 |
| `identifier` | `/api/v1/identify` | 内容标识检测 (C2PA/元数据) |
| `robustness` | `/api/v1/robustness` | 对抗鲁棒性测试 + 降 AIGC |
| `assistant` | `/api/v1/assistant` | 文档转 PDF + TTS 语音合成 |

### 前端页面 (14 页)

| 路由 | 页面 | 功能 |
|------|------|------|
| `/login` | 登录 | JWT 认证 |
| `/dashboard` | 仪表盘 | 快速入口 + 历史概览 |
| `/detect/text` | 文本检测 | 单条文本 AI 检测 |
| `/detect/image` | 图像检测 | 图片伪造检测 |
| `/detect/audio` | 音频检测 | 合成语音检测 |
| `/detect/thesis` | 论文检测 | 学术论文 AIGC 专项检测 |
| `/detect/reduce` | 降 AIGC | 多轮迭代降 AI 率 |
| `/detect/batch` | 批量检测 | 最多 100 文件并发 |
| `/assistant` | AI 助手 | 文档转 PDF + TTS |
| `/history` | 检测历史 | 历史记录查询 |
| `/standards` | 合规标准 | GB 45438—2025 对标 |
| `/report/:id` | 报告详情 | 三色标注 + 取证分析 |
| `/admin` | 管理后台 | 角色门控管理面板 |

---

## 检测管线

### 文本检测 — 三路融合

```
输入文本
  │
  ├─→ [防御预处理] 同形字标准化 + 零宽字符剥离 + 改写检测
  │
  ├─→ [分支1] 统计特征 (权重 0.2)
  │     12 项中文特征: Slop词密度 / 过渡词密度 / 成语密度 /
  │     句长CV / Burstiness / N-gram熵 / Zipf偏差 / Hapax比率 /
  │     Yule's K / 标点熵 / 二元重复率
  │     → 加权 Sigmoid 评分
  │
  ├─→ [分支2] Chinese-RoBERTa (权重 0.5)
  │     hfl/chinese-roberta-wwm-ext (冻结编码器)
  │     → [CLS] → MLP (hidden→256→1) → 温度缩放 + Platt 校准
  │     长文本: 450字分块 (stride 200) → 方差惩罚聚合
  │
  ├─→ [分支3] LLM Logprob (权重 0.3)
  │     DeepSeek API (logprobs=True, top_logprobs=20)
  │     → 零样本 YES/NO 概率比 → DetectGPT 概率曲率分析
  │
  └─→ [融合] 对数空间加权平均
        短文本: 统计权重↑ / 长文本: RoBERTa权重↑
        分支失效时动态重分配权重
        → 最终 AI 置信度 + 风险等级
```

**阈值配置:**
- AI 判定: 0.25 (RoBERTa) / 0.3 (LLM logprob)
- 风险等级: low (<0.3) / medium (0.3-0.7) / high (>0.7)

### 图像检测 — 三路融合

```
输入图像
  │
  ├─→ [分支1] 高频噪声 CNN (权重 0.45)
  │     双分支: RGB + SRM残差滤波 → CNN
  │            FFT 对数振幅 → FFT 分支
  │     SRM 核: 3 个固定高通滤波器提取噪声残差
  │     灵感: CNNDetection / DIRE / F3Net
  │
  ├─→ [分支2] CLIP-ViT (权重 0.35)
  │     openai/clip-vit-large-patch14 (冻结视觉编码器)
  │     → CLS token → Linear probing head
  │     BICUBIC 插值缩放至 224×224
  │     灵感: UniversalFakeDetect (CVPR 2023)
  │
  ├─→ [分支3] MiMo-VL (权重 0.20)
  │     Xiaomi MiMo-VL (Anthropic Messages API)
  │     → Base64 编码图像 + 结构化分析 Prompt
  │     → JSON 解析 {confidence, reasoning}
  │
  └─→ [融合] 灵敏度感知加权融合
        灵敏度参数 (0.0-1.0) 调节决策阈值 (0.30-0.50)
        分支严重分歧时自适应权重提升
```

### 音频检测 — 三路融合

```
输入音频 (→ 重采样至 16kHz)
  │
  ├─→ [分支1] Wav2Vec2 XLS-R (权重 0.50)
  │     wav2vec2-xls-r-300m (冻结, 315M 参数)
  │     → 帧级特征 → 均值池化 [1024]
  │     → 3层分类器 (1024→256→64→1)
  │     5秒分块处理
  │
  ├─→ [分支2] Resemble AI API (权重 0.35)
  │     云端深度伪造检测 API
  │
  ├─→ [分支3] RawNet2 (权重 0.15)
  │     端到端原始波形处理
  │     SincNet + GRU + 注意力池化
  │     4秒分块 @ 16kHz
  │
  └─→ [融合] 加权融合
        API 不可用时动态重分配 (Wav2Vec2 0.75 + RawNet2 0.25)
```

### 论文检测 — 多阶段管线

```
上传文档 (.txt / .docx / .pdf)
  │
  ├─→ [1] 文档解析 (magic-byte 校验)
  ├─→ [2] 段落分割 + 章节识别 (正则匹配标题)
  ├─→ [3] 学科自适应阈值 (thesis_optimizer)
  ├─→ [4] 并行逐段检测 (5 并发, asyncio.Semaphore)
  │       └─→ 每段: 统计特征 + RoBERTa + LLM logprob
  ├─→ [5] 跨章节风格一致性分析 (thesis_detector)
  ├─→ [6] 取证分析: 引用验证 + 数据具体性评分 (thesis_forensics)
  └─→ [7] 加权 AI 率计算 + 通过/不通过判定
          → 知网风格三色标注报告 (红:高危 / 橙:中危 / 绿:安全)
```

---

## 关键 Prompt 与 Vibe 思路

### Vibe 思路: 分级渐进式 Prompt 设计

本项目的 LLM Prompt 设计遵循 **"检测置信度驱动的分级改写"** 思路 — 根据 AI 检测结果的严重程度，动态选择不同强度的改写指令，实现精准打击而非一刀切。

核心理念:
1. **检测先行**: 先用本地模型 + LLM logprob 精确测量 AI 置信度
2. **分级响应**: 高置信度 → 大幅改写; 低置信度 → 微调打磨
3. **迭代收敛**: 改写 → 重新检测 → 反馈 → 再改写，最多 5 轮
4. **领域适配**: 学术论文保持严谨性，日常文本追求口语化

### 文本人性化改写 Prompt

**System Prompt:**
```
你是文本人性化改写助手。你的任务是将AI生成的文本改写为人类写作风格。
要求：删除AI标志词、加入口语和个人表达、拆分长句、句式多样化。
保持原意不变。直接输出改写文本，不加任何说明。
```

**User Prompt (分级):**

| 置信度区间 | 策略 | Prompt 核心指令 |
|-----------|------|----------------|
| > 0.70 | 大幅改写 | "高度疑似AI生成。请**大幅改写**：删除所有AI标志词、加入个人观点和情感、拆分长句、使用口语化表达" |
| 0.55 - 0.70 | 中度改写 | "中度疑似。请**进一步改写**，增加句式变化，加入更多个人化表达" |
| < 0.55 | 微调 | "接近人类。请**微调文本**，使其更自然，减少任何残留的AI痕迹" |

### 论文降 AIGC Prompt

**System Prompt:**
```
你是学术论文写作优化助手。将AI生成的学术文本改写为人类写作风格。
要求：1)保持学术严谨性 2)删除AI标志词 3)加入具体数据和文献引用格式
4)句式多样化 5)加入适度的个人观点表达 6)段落结构有起伏。直接输出改写文本。
```

### LLM Logprob 检测 Prompt

```
请判断以下文本是否为 AI 生成。只回答 YES 或 NO。

文本: {sample}

回答:
```

通过 `logprobs=True, top_logprobs=20` 提取 YES/NO token 概率，计算对数概率比进行 DetectGPT 风格分析。

### MiMo-VL 图像分析 Prompt

```
分析这张图片是否有AI生成的痕迹。仔细检查以下特征：
1. 纹理伪影和不自然的平滑区域
2. 光照和阴影的不一致
3. 手指、牙齿、头发等细节异常
4. 背景中的重复模式或扭曲
5. 频域特征异常
6. 文字/符号的不自然

只返回一个JSON对象，不要有其他内容：
{"confidence": <0.0-1.0>, "reasoning": "<50字以内>"}

confidence表示该图像是AI生成的概率（0.0=确定真实，1.0=确定AI生成）
```

---

## AI 调用逻辑

### 双 LLM 提供商架构

```
┌─────────────────────────────────────────────────────┐
│                   LLM 调用层                         │
│                                                     │
│  ┌──────────────┐          ┌──────────────────┐     │
│  │  DeepSeek    │          │  MiMo-VL         │     │
│  │  (OpenAI 兼容) │          │  (Anthropic 兼容) │     │
│  │              │          │                  │     │
│  │  模型:        │          │  模型:            │     │
│  │  deepseek-chat│          │  mimo-v2.5-pro   │     │
│  │              │          │                  │     │
│  │  用途:        │          │  用途:            │     │
│  │  · 文本改写   │          │  · 图像视觉分析   │     │
│  │  · 对抗改写   │          │  · 多模态理解     │     │
│  │  · 回译       │          │                  │     │
│  │  · Logprob检测│          │                  │     │
│  └──────────────┘          └──────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 调用链路

#### 1. 文本检测调用链

```
用户输入文本
  │
  ▼
本地预处理 (同形字标准化 / 零宽字符剥离)
  │
  ├──→ RoBERTa 本地推理 (无网络调用)
  │
  ├──→ 统计特征本地计算 (无网络调用)
  │
  └──→ DeepSeek API 调用
        │
        ├── [检测] logprobs=True → YES/NO 概率比
        │
        └── [改写] 分级 Prompt → 改写文本
              │
              ▼
        重新检测 → 判断是否达标
              │
              ├── 未达标 → 再次改写 (最多 5 轮)
              └── 达标 → 返回优化后文本
```

#### 2. 图像检测调用链

```
用户上传图像
  │
  ├──→ 高频噪声 CNN 本地推理
  ├──→ CLIP-ViT 本地推理
  │
  └──→ MiMo-VL API 调用
        │
        └── Base64 编码 → Anthropic Messages API
           → 解析 JSON {confidence, reasoning}
              │
              ▼
        三路加权融合 → 最终判定
```

#### 3. 降 AIGC 迭代循环

```
输入文本
  │
  ▼
┌──────────────────────────────────┐
│  第 N 轮迭代 (N ≤ 5)             │
│                                  │
│  ① 检测当前 AI 置信度             │
│     (RoBERTa + 统计 + LLM logprob)│
│                                  │
│  ② 置信度 < 0.30? ──→ 退出循环    │
│                                  │
│  ③ 根据置信度选择改写策略          │
│     高: 大幅改写 (DeepSeek API)   │
│     中: 中度改写 (DeepSeek API)   │
│     低: 本地微调 (同义替换/句式重构)│
│                                  │
│  ④ 本地优化辅助                   │
│     · AI Slop 词移除              │
│     · 句式拆分重组                 │
│     · 学术引用格式添加 (论文场景)   │
│                                  │
│  ⑤ 返回 ①                       │
└──────────────────────────────────┘
  │
  ▼
输出: 优化文本 + 前后对比报告 (.txt / .pdf / .docx)
```

#### 4. 容错与降级策略

```
API 调用失败
  │
  ├── DeepSeek 不可用
  │     → 文本检测降级为 RoBERTa + 统计特征双路融合
  │     → 降 AIGC 降级为纯本地方法 (同义替换 + 句式重构)
  │
  ├── MiMo-VL 不可用
  │     → 图像检测降级为 CNN + ViT 双路融合
  │
  └── Resemble AI 不可用
        → 音频检测降级为 Wav2Vec2 + RawNet2 双路融合
        → 权重动态重分配
```

---

## 部署步骤

### 环境要求

| 依赖 | 版本要求 |
|------|---------|
| Python | >= 3.11 |
| Node.js | >= 18 |
| MySQL | >= 8.0 |
| Redis | >= 6.0 |
| GPU (可选) | CUDA 11.8+ (加速模型推理) |

### 方式一: 一键启动 (推荐开发环境)

```bash
# 1. 克隆项目
git clone <repo-url>
cd image_nious

# 2. 安装后端依赖
cd backend
pip install -r requirements.txt
cd ..

# 3. 安装前端依赖
cd frontend
npm install
cd ..

# 4. 确保 MySQL 和 Redis 已启动
# MySQL: 创建数据库 image_nious
# Redis: 默认 localhost:6379

# 5. 一键启动 (自动配置 .env、启动后端+前端)
python start.py

# 自定义端口
python start.py --port 9000

# 交互式配置后启动
python start.py --config

# 仅启动后端 (不启动前端)
python start.py --no-frontend

# 关闭所有服务
python start.py --kill
```

启动成功后:
- 前端: http://localhost:5173
- 后端 API: http://localhost:8001
- API 文档: http://localhost:8001/api/docs

### 方式二: 手动启动

```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入数据库、Redis、API Key 等配置

# 2. 启动后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# 3. 启动前端 (新终端)
cd frontend
npx vite --port 5173 --host
```

### 方式三: Docker 部署

```bash
cd backend
docker build -t aigc-detection-api .
docker run -p 8001:8001 --env-file .env aigc-detection-api
```

### 环境变量说明 (.env)

```bash
# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_NAME=image_nious
DB_USER=root
DB_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# LLM API (DeepSeek)
LLM_API_KEY=sk-xxx
LLM_API_BASE=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# MiMo-VL (可选, 用于图像视觉分析)
MIMO_API_KEY=tp-xxx
MIMO_API_BASE=https://token-plan-cn.xiaomimimo.com/anthropic
MIMO_MODEL=mimo-v2.5-pro

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=480

# 模型路径 (HuggingFace model ID, 首次使用自动下载)
TEXT_MODEL_PATH=hfl/chinese-roberta-wwm-ext
IMAGE_VIT_MODEL_PATH=openai/clip-vit-large-patch14

# CORS
CORS_ORIGINS=http://localhost:5173,chrome-extension://*
```

### 模型首次加载

首次启动时，以下模型会自动从 HuggingFace 下载并缓存:

| 模型 | 大小 | 用途 |
|------|------|------|
| `hfl/chinese-roberta-wwm-ext` | ~400MB | 中文文本检测 |
| `openai/clip-vit-large-patch14` | ~1.7GB | 图像检测 |
| `wav2vec2-xls-r-300m` | ~1.2GB | 音频检测 |

可通过 `HF_HOME` 环境变量指定缓存目录:
```bash
export HF_HOME=/path/to/cache
```

### 创建管理员账户

```bash
cd backend
python scripts/create_admin.py
```

---

## 项目结构

```
.
├── start.py                          # 一键启动脚本
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                      # 数据库迁移
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口
│   │   ├── config.py                 # 配置 + 30+ 阈值参数
│   │   ├── api/v1/                   # 8 个路由模块
│   │   ├── detectors/                # 检测引擎
│   │   │   ├── text/                 # RoBERTa + LLM logprob + 统计特征
│   │   │   ├── image/                # CNN + CLIP-ViT + MiMo-VL
│   │   │   ├── audio/                # Wav2Vec2 + RawNet2 + Resemble
│   │   │   ├── defense/              # 同形字标准化 + 改写检测
│   │   │   └── metadata/             # 元数据标识检测
│   │   ├── services/                 # 业务服务层
│   │   │   ├── thesis_detector.py    # 论文风格一致性
│   │   │   ├── thesis_forensics.py   # 论文取证分析
│   │   │   ├── thesis_optimizer.py   # 学科自适应优化
│   │   │   ├── arbitration.py        # 贝叶斯冲突消解
│   │   │   └── calibration.py        # 温度/Platt 校准
│   │   ├── models/                   # SQLAlchemy ORM
│   │   ├── schemas/                  # Pydantic 数据模型
│   │   └── utils/                    # 文档解析 / N-gram 工具
│   ├── scripts/create_admin.py       # 管理员创建脚本
│   ├── train_text_detector.py        # 文本模型训练
│   ├── train_image_detector.py       # 图像模型训练
│   └── train_audio_detector.py       # 音频模型训练
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/views/                    # 14 个页面组件
├── miniapp/                          # 微信小程序 (uni-app)
├── extension/                        # Chrome 扩展 (MV3)
├── data/                             # 训练数据集
└── models/                           # 模型权重 (git ignored)
```

### 对标标准

本平台严格对标以下国家标准:

| 标准 | 内容 |
|------|------|
| GB 45438—2025 | 人工智能 生成内容标识方法 |
| TC260-003 | 生成式人工智能服务安全基本要求 |
| TC260-PG-20233A | 生成式人工智能服务内容标识要求 |
| 深度合成管理规定 | 互联网信息服务深度合成管理规定 (2023) |

---

## 许可证

本项目仅供学术研究与内部使用。
