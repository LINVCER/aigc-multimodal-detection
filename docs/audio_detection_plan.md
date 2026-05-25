# AIGC 音频检测模块 — 技术调研与实施计划

## 一、GitHub 关键项目调研

### 1.1 核心开源模型

| 项目 | Stars | 方法 | 性能 | 预训练权重 | 中文适用性 |
|------|-------|------|------|-----------|-----------|
| [AASIST](https://github.com/clovaai/aasist) | 171 | 图谱+时间注意力 | ASVspoof 2021 EER 1.89% | ✅ 官方提供 | ⭐⭐ 英文训练，中文待验证 |
| [SSL_Anti-spoofing](https://github.com/TakHemlata/SSL_Anti-spoofing) | 103 | Wav2Vec 2.0 + 轻量分类头 | ASVspoof 2021 EER 2.15% | ✅ 提供 | ⭐⭐⭐ XLS-R 多语言前端 |
| [RawNet2](https://github.com/asvspoof-challenge) | 48 | 端到端原始波形 | ASVspoof 2019 EER 1.59% | ✅ 官方提供 | ⭐⭐ 英文训练 |
| [AASIST_SCALING](https://github.com/KORALLLL/AASIST_SCALING) | 新 | Wav2Vec 2.0 XLS-R + MHA | ASVspoof 5 EER 7.6% | ⚠️ 论文代码 | ⭐⭐⭐ 多语言前端最优 |
| [AI-Synth-Voice](https://github.com/entn-at/AI-Synthesized-Voice-Generalization) | 新 | AAAI 2025 泛化增强 | 跨模型泛化提升 | ⚠️ 需训练 | ⭐⭐ 泛化方法可迁移 |

### 1.2 水印方案（主动检测对比）

| 项目 | 方法 | 适用场景 |
|------|------|---------|
| [AudioSeal (Meta)](https://github.com/facebookresearch/audioseal) | 神经网络水印 | 生成端嵌入水印，检测端解码验证 |
| [Timbre (Interspeech 2025)](https://timbre-watermark.github.io/) | 音色水印 | 听觉不可察觉的水印 |

> **结论**：本项目采用被动检测方案（无水印依赖），因为检测对象是未知来源的音频。

### 1.3 基准评测工具

| 项目 | 说明 |
|------|------|
| [AUDDT](https://github.com/MuSAELab/AUDDT) | 音频深度伪造统一检测基准，覆盖 28 数据集 |
| [ASVspoof 2021 Baseline](https://github.com/asvspoof-challenge/ASVspoof2021) | 官方基线系统 (LFCC-GMM, RawNet2) |

---

## 二、技术路线选型

### 2.1 推荐架构：SSL_Anti-spoofing 方案

```
输入音频 (任意长度/格式)
   │
   ├─→ [预处理]
   │    ├─ ffmpeg 转 WAV 16kHz 单声道
   │    ├─ 静音检测 + 分段 (3-5s 窗口)
   │    └─ 重采样 16kHz
   │
   ├─→ [SSL 特征提取] 冻结 Wav2Vec 2.0 XLS-R (300M)
   │    ├─ 输出: [T, 1024] 帧级特征
   │    └─ 均值池化 → [1024-dim] 段级特征
   │
   ├─→ [轻量分类头] 可训练 (~1M 参数)
   │    ├─ Linear(1024→256)
   │    ├─ ReLU + Dropout(0.3)
   │    └─ Linear(256→1) → sigmoid
   │
   └─→ [分段聚合]
        多数投票/均值 → 最终判定
```

### 2.2 为什么选 SSL_Anti-spoofing 而非 AASIST

| 维度 | SSL_Anti-spoofing | AASIST |
|------|-------------------|--------|
| 中文支持 | XLS-R 多语言预训练 ✅ | 英文训练，中文 OOD |
| 模型复杂度 | 冻结编码器 + 轻量头 (~1M) | 图注意力网络 (大) |
| 预训练权重 | ✅ HuggingFace 直接下载 | ✅ 官方 checkpoint |
| 推理速度 | 快 (仅分类头计算) | 中等 |
| 数据需求 | 少样本即可微调 | 需要大规模数据 |

---

## 三、中文语音合成检测特殊性

### 3.1 主要中文 TTS 系统

| 系统 | 类型 | 语音特点 |
|------|------|---------|
| 讯飞语音 | 商业 TTS | 非常自然，广泛使用 |
| 百度语音 | 商业 TTS | 多种音色可选 |
| 阿里语音 (CosyVoice) | 开源 | 少样本克隆，高质量 |
| GPT-SoVITS | 开源 | 少样本声音克隆 |
| Fish-Speech | 开源 | 端到端 TTS |
| ChatTTS | 开源 | 对话风格，非常自然 |
| CosyVoice 2 | 开源 (2025) | 阿里最新，支持流式 |

### 3.2 中文特有的检测挑战

1. **声调语言**：四声 + 轻声，TTS 在声调过渡上可能不自然
2. **语气词**：中文语气词（啊、吧、呢、嘛）在合成语音中常异常
3. **停顿模式**：中文句读停顿与英文不同，合成语音停顿可能过于均匀
4. **基频 (F0) 跳变**：中文声调导致基频变化更丰富，合成语音的 F0 包络可能过度平滑

---

## 四、数据集资源

### 4.1 英文数据集（可获取）

| 数据集 | 规模 | 内容 | 下载 |
|------|------|------|------|
| ASVspoof 2019 LA | 12万+ | TTS + VC 欺骗 | 官网注册 |
| ASVspoof 2021 LA | 18万+ | 电话信道欺骗 | 官网注册 |
| ASVspoof 2021 DF | 60万+ | 深度伪造音频 | 官网注册 |
| WaveFake | 10万+ | 多声码器生成 | GitHub |
| In-the-Wild | 38小时 | 真实场景深度伪造 | GitHub |

### 4.2 中文数据集（需自建）

目前**没有公开的中文深度伪造语音检测数据集**。建议：

1. **自建 TTS 生成集**（~5000 条）
   - 真实语音：AISHELL-3 / CSMSC 中文语音数据集
   - 合成语音：用 ChatTTS + GPT-SoVITS + CosyVoice 对相同文本生成

2. **数据增强**
   - 添加背景噪声 (MUSAN)
   - 编解码压缩 (MP3, AAC)
   - 房间混响 (RIR)
   - 变速变调 (±10%)

---

## 五、预训练权重下载清单

| 模型 | 大小 | 来源 | 状态 |
|------|------|------|------|
| Wav2Vec 2.0 XLS-R 300M | ~1.2GB | `facebook/wav2vec2-xls-r-300m` | HF 下载 |
| SSL_Anti-spoofing 分类头 | ~5MB | 官方 checkpoint | GitHub/Google Drive |
| AASIST 完整模型 | ~340MB | 官方 release | GitHub |
| RawNet2 预训练 | ~80MB | ASVspoof 官方 | 官网 |

---

## 六、实施计划

### Phase 4a — 音频检测模块 (第 9-10 周)

| 周 | 任务 | 产出 |
|----|------|------|
| 第9周 | 下载 Wav2Vec 2.0 XLS-R + SSL 预训练权重 | 模型就绪 |
| | 实现 `wav2vec2_detector.py` | 音频检测器 |
| | 实现 `resemble_client.py` (已有骨架) | API 客户端 |
| | 构建中文测试集 (~200 条) | 自建测试数据 |
| 第10周 | 在 ASVspoof 2019 + 自建中文测试集上评估 | EER, AUC 报告 |
| | 微调分类头 (中文语音样本, ~500 对) | 中文优化 |
| | 实现基频分析可视化 | 解释报告用 |
| | 实现音频融合层 | Resemble + SSL 双路 |
| | 音频检测 API + Worker 集成 | 生产就绪 |

### 预计性能

| 场景 | 预期 EER | 预期 AUC |
|------|---------|---------|
| 英文 TTS (预训练直接推理) | 2-5% | 0.96+ |
| 中文 ChatTTS (零样本) | 8-15% | 0.85+ |
| 中文 CosyVoice (零样本) | 10-18% | 0.82+ |
| 中文微调后 (500 对) | 3-8% | 0.92+ |

---

## 七、与现有架构的集成

```
当前项目结构:
  detectors/audio/
    ├── resemble_client.py     ✅ 已有骨架
    ├── rawnet2_detector.py    ✅ 已有骨架
    ├── wav2vec2_detector.py   📝 新增 (SSL_Anti-spoofing)
    └── ensemble.py            ✅ 已有骨架，需更新三路融合

  services/
    └── audio_service.py       ✅ 已有，需更新

  workers/
    └── audio_worker.py        ✅ 已有，需更新
```

### 更新后的音频融合权重

```
Resemble AI API 可用时:
  SSL Wav2Vec2: 0.5 (主力)
  Resemble:     0.35
  RawNet2:      0.15

Resemble API 不可用时 (本地降级):
  SSL Wav2Vec2: 0.7
  RawNet2:      0.3
```

---

## 八、替代方案：如果无法下载预训练权重

1. **直接使用 Resemble AI API**：每月 1000 次免费，原型足够
2. **对接阿里云语音反欺骗 API**：国内可用，商业化
3. **Wav2Vec 2.0 零样本**：仅用预训练 SSL 特征 + 随机分类头，在少量样本上微调
