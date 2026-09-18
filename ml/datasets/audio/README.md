# ml/datasets/audio/

**音频文件不入 git**（体积 + 版权）。本目录只放：
- 数据集准备 / 清洗脚本
- 索引 jsonl（可选入 git · 视规模）
- 数据来源说明

## JSONL 格式

```json
{"audio_path": "raw/human/xxx.wav", "label": 0, "source": "real_human",   "duration_sec": 12.3}
{"audio_path": "raw/tts/gpt4o/yyy.mp3", "label": 1, "source": "tts",       "duration_sec": 8.5}
{"audio_path": "raw/cloned/zzz.wav",    "label": 1, "source": "cloned_voice", "duration_sec": 20.1}
```

| 字段 | 说明 |
|---|---|
| `audio_path` | 相对 `ml/datasets/audio/` 的路径 · 支持 wav / mp3 / m4a / flac / ogg |
| `label` | 0 = 真人语音, 1 = AI 生成 |
| `source` | 细分：real_human / tts / cloned_voice / mixed（tts + 后期人声）|
| `duration_sec` | 时长（秒）· 供分时长桶评估 |

## 划分（v0.1.0-baseline）

| split | 文件 | 目标数 | source 等比 |
|---|---|---|---|
| train | `train.jsonl` | ~20k 片段（每片段 3s） | 是 |
| val   | `val.jsonl`   | ~2k | 是 |
| test  | `test.jsonl`  | ~2k | 是 |

三个 split **必须来自不同发言人**（一个人的多段音频不能既在 train 又在 test）以避免 speaker leakage。

## 数据来源清单（v0.1.0 采集计划 · 待启动）

- **real_human**：AISHELL-3 / MAGICDATA / 公开访谈 / 视频剪辑分离音轨
- **tts**：OpenAI TTS · ElevenLabs · Azure TTS · MiniMax · CosyVoice · 各产 6 类 prompt × 500 段
- **cloned_voice**：Coqui XTTS · Real-Time-Voice-Cloning（学术用途） × 200 段
- **mixed**：TTS 生成后叠加背景噪声/混响，验证鲁棒性

采集脚本待写：`collect_v0_1_0.py`

## 敏感数据

- 名人声音 / 商用样本 / 未授权访谈 → 不采集
- 采集脚本必须记录来源许可证类型（CC / MIT / 学术用途 only）
