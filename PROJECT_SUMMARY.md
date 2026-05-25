# AIGC--多模态检测 — 项目总结

> 更新时间: 2026-05-21

## 一、成功部分

### 图像检测
| 指标 | 数值 |
|------|------|
| CNN 准确率 | **96.1%** |
| ViT 准确率 | **94.9%** |
| 融合准确率 | **97.1%** |
| 训练数据 | GenImage SD1.5 (165K AI + 153K Nature) |
| API 单张测试 | SD1.5 生成图 → **100% AI** / ImageNet 真实图 → **0.01%** |

### 统计特征提取
- 12 项中文特征完整实现 (n-gram 熵 / 成语密度 / 标点间距 / Burstiness / Zipf 偏差 / Slop 词 / 过渡词 / Hapax / Yule's K 等)
- 中文 Slop 词表覆盖 GPT / Claude / 文心风格
- Sigmoid 归一化加权融合

### 检测管线
- **文本**: RoBERTa (97.1% Val) + 统计特征 + DeepSeek logprob 三路融合
- **图像**: 高频噪声 CNN + CLIP-ViT 双分支融合
- **仲裁**: 贝叶斯冲突消解 + 温度/Platt 校准
- **防御**: 同形字标准化 + 改写检测 + 对抗鲁棒性测试

### API 端点 (20+)
| 模块 | 端点 |
|------|------|
| 文本检测 | POST /detect/text |
| 图像检测 | POST /detect/image |
| 音频检测 | POST /detect/audio |
| 论文检测 | POST /detect/thesis |
| 文档上传 | POST /detect/document |
| 批量检测 | POST /detect/batch, POST /detect/batch-images |
| 标识检测 | POST /identify/image, POST /identify/text |
| 鲁棒性测试 | POST /robustness/test, POST /robustness/reduce |
| 多轮改写 | POST /robustness/iterative-paraphrase |
| 认证 | POST /auth/register, /auth/login |

### 前端 (7 页面)
- 仪表盘 (快速入口 + 历史记录)
- 文本检测 (输入 + 结果展示)
- 图像检测 (拖拽上传 + 环形仪表盘 + 智能提示)
- 论文检测 (知网标准报告: 目录识别 + 三色标注 + 疑似原因 + 通过建议)
- 降AI测试 (5 种简单方法 + 多轮迭代对抗改写)
- 音频检测
- 检测历史

### 基础设施
- MySQL 数据库 (4 表: users / tasks / detection_results / explanation_reports)
- Redis 缓存 + Celery 任务队列
- `start.py` 一键启动/关闭脚本 (支持 --port / --config / --kill)
- localStorage 结果缓存 (跨页面保留)

### 数据集
| 数据集 | 规模 | 用途 |
|--------|------|------|
| HC3-Chinese | 38K (已清洗到 29K) | 文本检测训练 |
| CUDRT Chinese | 25K (20K train + 5.6K val) | 基准测试 |
| GenImage SD1.5 | 318K (165K AI + 153K Nature) | 图像检测训练 |
| train2017 | 15K 真实图像 | 图像检测训练 |

---

## 二、失败部分

### 文本检测模型失效
- **现象**: AI 率常驻 50% 左右，无法区分 AI/人类
- **典型案例**: 老舍《林海》检测为 AI (>50%)
- **根因**: HC3 训练数据单一（仅百科/问答体），模型从未见过文学作品
- **过拟合**: 学到的是"百科体=人类"，而非真正的 AIGC 判别特征

### 短文本误判
- 短文本(<30 字)原设为 50% AI 率，不合理
- 已部分修复（短段落排除 + 字数加权），但仍需优化

### 服务进程管理
- uvicorn 背景启动反复崩溃（端口占用 / 僵尸进程）
- 需用 Python subprocess 方式启动

### HC3 数据质量问题
- 22% 样本含多余空格
- 9.4% AI 样本为"拒绝/免责"模式
- 人类样本为百科体，非真实口语/文学

### 其他
- 音频检测仅有代码骨架，RawNet2 使用随机权重
- C-ReD 数据集(2026.04)尚未公开发布
- DeepSeek API 偶发不可达（系统代理干扰）

---

## 三、当前基础

```
检测器:
  文本: RoBERTa (HC3 97.1% Val) + 统计特征 + DeepSeek API
  图像: CNN (96.1%) + ViT (94.9%) — GenImage SD1.5 训练
  音频: 仅代码骨架

API:    20+ 端点
前端:   Vue3 7 页面
数据库: MySQL 4 表
缓存:   Redis + localStorage
数据集: HC3-Chinese (29K) + CUDRT (25K) + GenImage SD1.5 (318K)
```

---

## 四、核心缺陷 & 修复优先级

| 优先级 | 问题 | 修复方案 |
|--------|------|---------|
| 🔴 P0 | **文本模型失效** | 构建学术+文学+新闻+口语多样化数据集，重新训练 |
| 🔴 P0 | 过拟合到百科体 | 增加文学作品、学生作文、新闻稿等人类样本 |
| 🟡 P1 | 服务不稳定 | 用 `start.py` 统一管理进程 |
| 🟡 P1 | 音频检测缺失 | 下载 RawNet2 预训练权重 |
| 🟢 P2 | 前端部分功能未完善 | 音频页面、历史页面增强 |

---

## 五、文本检测重训方案

```
新训练集构建:
  1. CUDRT Chinese (20K, 百科/医疗/金融/法律/心理) — 已下载 ✅
  2. HC3-Chinese cleaned (29K) — 已清洗 ✅
  3. 学术论文 (AI + 人类, 各 500) — DeepSeek 生成
  4. 文学作品 (鲁迅/老舍/朱自清 200+) — 公开领域
  5. 学生作文 (人类 + AI, 各 500) — DeepSeek 生成
  6. 新闻稿 (人类 + AI, 各 500) — DeepSeek 生成

  目标: ~35K 样本, 覆盖 6 种文体
  训练: 3 epochs, batch 16, RoBERTa 微调
  预期: F1 > 85%, 老舍散文 < 30% AIGC
```

---

## 六、论文/开源项目参考

| 项目 | 用途 |
|------|------|
| AIGC_text_detector (ICLR 2024) | MPU 短文本检测 |
| lmscan | 12 项统计特征 |
| UniversalFakeDetect (CVPR 2023) | CLIP-ViT 图像检测 |
| D³ (CVPR 2024) | 双分支融合 |
| Adversarial Paraphrasing (NeurIPS 2025) | 对抗改写 |
| GradEscape (USENIX 2025) | 梯度逃逸 |
| AuthorMist (2025) | RL 逃逸检测器 |
| SilverSpeak (ACL 2025) | 同形字符攻击 |
| CUDRT | 中文检测基准 |
| HC3-Chinese | 人类-ChatGPT 对比语料 |
