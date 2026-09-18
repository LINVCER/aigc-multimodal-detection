# ml/datasets/text/

**数据本身不入 git**（体积 + 隐私）。本目录只放：
- 数据集准备 / 清洗脚本
- 数据集索引与来源说明
- 采样与划分策略

## JSONL 格式

```json
{"text": "...", "label": 1, "scenario": "academic_master", "source": "gpt"}
{"text": "...", "label": 0, "scenario": "self_media",      "source": "human"}
```

| 字段 | 说明 |
|---|---|
| `text` | 段落文本（100–800 字，与 backend TextProcessor 切分口径一致） |
| `label` | 0 = 人类, 1 = AI |
| `scenario` | 6 场景之一（对齐 C 端配置） |
| `source` | 细粒度来源；未知填 `unknown`；供未来溯源多任务用 |

## 划分（v0.1.0-baseline）

| split | 文件 | 目标数量 | 场景等比 |
|---|---|---|---|
| train | `train.jsonl` | ~50k | 是 |
| val   | `val.jsonl`   | ~5k  | 是 |
| test  | `test.jsonl`  | ~5k  | 是 |

三个 split **必须来自不同数据源**（同一 chatgpt 会话不能既在 train 又在 test），
以避免 data leakage。

## 数据来源清单（v0.1.0 采集计划 · 待启动）

- 人类：人民日报 / 学术论文摘要 / 公开博客
- AI：GPT-4o / Claude-3.5 / Qwen-2.5 / DeepSeek-V2 各产 6 场景各 5000 段
- 采集脚本待写：`collect_v0_1_0.py`

## 敏感数据

- 手机号 / 邮箱 / 身份证 / 学号 → 采集脚本必须 PII scrub 才能进 jsonl
- 商业机密文档 → 不采集
