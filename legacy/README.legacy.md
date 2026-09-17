# AIGC 多模态检测平台

> 面向教育、出版、传媒场景的 AI 生成内容检测平台，覆盖文本/图像/音频三模态 + 图像篡改检测，支持论文专项检测与一键降 AIGC。

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Vue 3 前端 (15 页)                  │
│  Element Plus + TypeScript + Vite + Pinia + ECharts  │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│               FastAPI 后端 (8 个路由模块)              │
│  auth · detection · upload · report · admin          │
│  identifier · robustness · assistant                 │
└────┬──────────┬──────────┬──────────┬───────────────┘
     │          │          │          │
     ▼          ▼          ▼          ▼
┌──────────┐ ┌────────┐ ┌──────┐ ┌──────────────────┐
│ 检测引擎  │ │ LLM 服务│ │ 存储层 │ │    基础设施       │
│ 文本4路   │ │DeepSeek│ │MySQL │ │ Redis + Celery   │
│ 图像4路   │ │ MiMo   │ │      │ │                  │
│ 音频2路   │ │        │ │      │ │                  │
│ 篡改3路   │ │        │ │      │ │                  │
└──────────┘ └────────┘ └──────┘ └──────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3.5 + TypeScript + Vite 6 + Element Plus 2.9 + Pinia + ECharts |
| 后端 | Python 3.11 + FastAPI 0.115 + Uvicorn (全异步) |
| 数据库 | MySQL (aiomysql) + SQLAlchemy async ORM |
| 文本模型 | hfl/chinese-roberta-wwm-ext (HIT) |
| 图像模型 | openai/clip-vit-large-patch14 + 自研高频噪声 CNN |
| 篡改检测 | Mask R-CNN (ResNet-50+FPN) + FFT频域 + 噪声不一致 |
| 音频模型 | wav2vec2-base + RawNet2 |
| LLM | DeepSeek (OpenAI 兼容) / MiMo (Anthropic 兼容) |

### 后端路由

| 模块 | 端点前缀 | 功能 |
|------|---------|------|
| `auth` | `/api/v1/auth` | 注册、登录、Token 刷新 |
| `detection` | `/api/v1/detect` | 文本/图像/音频/篡改检测 |
| `upload` | `/api/v1/detect` | 文档上传、论文检测 |
| `report` | `/api/v1/report` | 检测报告生成 |
| `admin` | `/api/v1/admin` | 用户管理、额度管理、支付确认 |
| `identifier` | `/api/v1/identify` | 内容标识检测 |
| `robustness` | `/api/v1/robustness` | 降 AIGC |
| `assistant` | `/api/v1/assistant` | 文档转 PDF + TTS |

### 前端页面

| 路由 | 功能 |
|------|------|
| `/login` | 登录注册 |
| `/dashboard` | 仪表盘 + 快速入口 |
| `/detect/text` | 文本 AI 检测 |
| `/detect/image` | 图像 AI 检测 (四路投票) |
| `/detect/tampering` | 图像篡改检测 |
| `/detect/audio` | 音频检测 |
| `/detect/thesis` | 论文 AIGC 检测 |
| `/detect/reduce` | 降 AIGC |
| `/assistant` | AI 助手 |
| `/history` | 检测历史 |
| `/admin` | 管理后台 |

---

## 检测管线

### 文本检测 — 四路融合

```
输入文本
  │
  ├─→ [防御预处理] 同形字标准化 + 零宽字符剥离
  │
  ├─→ [分支1] 统计特征 (权重 15%)
  │     11 项中文特征: Slop词密度 / 过渡词密度 / 成语密度 /
  │     句长CV / Burstiness / N-gram熵 / Zipf偏差 / Hapax比率 /
  │     Yule's K / 标点熵 / 二元重复率
  │
  ├─→ [分支2] Chinese-RoBERTa (权重 30%)
  │     hfl/chinese-roberta-wwm-ext
  │     长文本: 450字分块 (stride 200) → 方差惩罚聚合
  │
  ├─→ [分支3] MiMo API (权重 30%)
  │     Anthropic Messages API → 置信度分析
  │
  ├─→ [分支4] DeepSeek API (权重 25%)
  │     OpenAI 兼容 API (logprobs=True)
  │
  └─→ [融合] 加权平均
        短文本: 统计权重↑ / 长文本: RoBERTa权重↑
        RoBERTa 不可用时: 统计 40% + MiMo 35% + DeepSeek 25%
```

### 图像检测 — 四路投票

```
输入图像
  │
  ├─→ [分支1] 高频噪声 CNN (权重 1.0)
  │     双分支: RGB + SRM残差滤波 → CNN
  │     灵感: CNNDetection / F3Net
  │
  ├─→ [分支2] CLIP-ViT (权重 1.0)
  │     openai/clip-vit-large-patch14
  │     → CLS token → Linear probing head
  │
  ├─→ [分支3] MiMo API — 质感分析 (权重 1.1)
  │     专业数字图像取证分析 Prompt
  │     6 维度: 细节结构/文字符号/光影反射/纹理/透视/语义
  │
  ├─→ [分支4] MiMo API — 细节分析 (权重 1.1)
  │     相同的专业取证分析 Prompt (并发独立调用)
  │
  └─→ [融合] 四方投票 + 加权融合
        ≥ 3 票 AI → "AI生成"
        ≥ 3 票真实 → "真实图像"
        否则 → 融合概率与决策阈值比较
        分支分歧过大时自适应降权
```

**MiMo 图像分析 Prompt (两轮共用):**

```
你是一位专业的数字图像取证分析师，擅长通过视觉线索判断图片是否由人工智能生成。
请你仅根据图像内容，进行一次客观、细致的分析，而不是凭感觉猜测。

请按以下步骤观察并思考：
1. 细节与解剖结构：检查手部、手指、耳朵、牙齿等细节，是否有扭曲、多余指节
2. 文字与符号：逐字检查是否清晰可辨，有无乱码、虚假字形
3. 光影与反射：确认光源方向是否一致，阴影与高光是否吻合
4. 纹理与重复元素：观察是否有不自然的平滑区域、涂抹感、重复纹理贴片
5. 透视与空间逻辑：检查物体比例、透视是否正确
6. 语义合理性：判断场景中物体组合是否符合现实常识

只返回JSON：{"confidence": 0.0-1.0, "reasoning": "20字内关键证据摘要"}
```

### 音频检测 — 双路融合

```
输入音频 (→ 重采样至 16kHz)
  │
  ├─→ [分支1] Wav2Vec2-base (权重 50%)
  │     wav2vec2-base (768 维)
  │     → 均值池化 → 3层分类器
  │     本地训练: 99.6% 验证准确率
  │
  ├─→ [分支2] RawNet2 (权重 50%)
  │     端到端原始波形处理
  │     SincNet + GRU + 注意力池化
  │
  └─→ [融合] 加权融合
        决策阈值: 0.55
        Wav2Vec2 不可用时: RawNet2 100%
```

### 篡改检测 — 三路融合

```
输入图像
  │
  ├─→ [分支1] Mask R-CNN (ResNet-50+FPN)
  │     2 尺度 [1.0, 0.75] + TTA 水平翻转
  │     双阈值: score>0.7→mask 0.7, 0.4-0.7→mask 0.5
  │
  ├─→ [分支2] FFT 频域异常
  │     灰度图 → FFT → 对数振幅 → 归一化 → score_map
  │
  ├─→ [分支3] 噪声不一致
  │     灰度图 → 高斯模糊差分 → 归一化 → score_map
  │
  └─→ [融合] 核心-边缘分离
        DL mask 腐蚀 3×3 → 核心 (直接保留)
        DL mask 膨胀 5×5 → 边缘
        噪声为主确认者: edge & (noise | freq)
        support_ratio > 0.35 → 确认
        形状过滤 (面积≥80, 宽高比 0.1-8.0)
        → is_forged = np.any(fused_mask)
```

### 论文检测 — 异步管线

```
上传文档 (.txt / .docx / .pdf)
  │
  ├─→ [1] 文档解析 (LibreOffice / python-docx / PyPDF2)
  ├─→ [2] 段落分割 + 章节识别
  ├─→ [3] 后台异步处理 (asyncio.create_task)
  ├─→ [4] 逐段检测 (统计 + RoBERTa + LLM)
  ├─→ [5] 跨章节风格一致性分析
  ├─→ [6] 取证分析: 引用验证 + 数据具体性
  └─→ [7] 知网风格三色标注报告
          红(≥70%) / 橙(40-70%) / 绿(<40%)
```

---

## 部署

### 环境要求

| 依赖 | 版本 |
|------|------|
| Python | >= 3.11 |
| Node.js | >= 18 |
| MySQL | >= 8.0 |
| 内存 | >= 4GB (无 GPU 时) |

### 快速启动

```bash
# 1. 克隆
git clone <repo-url>
cd image_nious

# 2. 后端
cd backend
pip install -r requirements.txt
# 配置 .env (数据库、API Key)
uvicorn app.main:app --host 0.0.0.0 --port 8001

# 3. 前端
cd frontend
npm install
npm run dev
```

### 环境变量 (.env)

```bash
# 数据库
DATABASE_URL=mysql+aiomysql://root:password@localhost:3306/image_nious

# DeepSeek (文本检测 + 降AIGC)
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEG_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# MiMo (图像视觉分析 + 文本检测)
MIMO_API_KEY=tp-xxx
MIMO_API_BASE=https://token-plan-cn.xiaomimimo.com/anthropic
MIMO_MODEL=mimo-v2.5

# JWT
JWT_SECRET_KEY=your-secret-key
```

### 模型文件

| 模型 | 大小 | 路径 |
|------|------|------|
| chinese-roberta-wwm-ext | ~400MB | 自动下载 (HuggingFace) |
| clip-vit-large-patch14 | ~1.7GB | 自动下载 (HuggingFace) |
| wav2vec2-base | ~380MB | `models/audio/wav2vec2-base` |
| Mask R-CNN | ~504MB | `models/tampering/best_model.pth` |

### 服务器部署 (4GB RAM 优化)

```bash
# ViT (1.7GB) 检测后自动卸载释放内存
# Wav2Vec2 (380MB) 检测后自动卸载
# Nginx 反向代理
server {
    listen 80;
    server_name your-domain.com;
    client_max_body_size 50M;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

---

## 用户系统

- 注册/登录 (JWT 认证)
- 额度系统: 充值 10 元 = 10 额度
  - 文本检测: 1 额度
  - 图像检测: 1 额度
  - 音频检测: 1 额度
  - 篡改检测: 2 额度
  - 论文检测: 2 额度
  - AI 助手: 免费
- 管理员: 用户管理、额度充值、月卡发放、黑名单、支付确认

---

## 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 配置 + 阈值参数
│   │   ├── api/v1/                 # 8 个路由模块
│   │   ├── detectors/              # 检测引擎
│   │   │   ├── text/               # RoBERTa + LLM + 统计特征 + DeepSeek
│   │   │   ├── image/              # CNN + CLIP-ViT + MiMo (两轮)
│   │   │   ├── audio/              # Wav2Vec2 + RawNet2
│   │   │   ├── tampering/          # Mask R-CNN + FFT + 噪声
│   │   │   └── defense/            # 同形字标准化
│   │   ├── services/               # 业务服务层
│   │   ├── models/                 # SQLAlchemy ORM
│   │   └── schemas/                # Pydantic 数据模型
│   └── train_audio_detector.py     # 音频模型训练脚本
├── frontend/
│   ├── src/
│   │   ├── views/                  # 15 个页面
│   │   ├── stores/                 # Pinia 状态管理
│   │   ├── composables/            # 组合式函数
│   │   └── utils/                  # 工具函数
│   └── package.json
└── README.md
```

## 许可证

本项目仅供学术研究与内部使用。
