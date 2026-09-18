# paperaigc-inference

FastAPI 推理服务，对齐 `backend-java/.../proto/detection.proto` 的 HTTP 端点。

## 状态

| 模态 | 骨架 | 权重 | 状态 |
|---|---|---|---|
| 文本 | chinese-roberta-wwm-ext + 分类头 | `aigc_detector_v3_thesis.pth` | ✅ 真实推理（Wave 4 · Batch 1） |
| 图像 | CLIP-ViT + DINOv2 + CNN 三分支 | `cnn_detection.pth` + `*_linear_head.pth` | ⏳ stub |
| 音频 | wav2vec2 / xls-r-300m | `aigc_audio_classifier.pth` | ⏳ stub |
| 篡改 | Mask R-CNN | `best_model.pth` | ⏳ stub |
| 降 AIGC 改写 | — | — | ⏳ stub |
| 溯源 attribute | — | — | ⏳ stub |

## 本地运行（不走 docker）

```bash
cd deploy/inference-python

# 1) 建环境
python -m venv .venv
.\.venv\Scripts\activate       # Windows
# source .venv/bin/activate    # macOS / Linux

# 2) 装依赖（首次会下 torch，约 2GB）
pip install -r requirements.txt

# 3) 配模型路径（复制样例并按实际路径改）
copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
# 编辑 .env，把 TEXT_BASE_MODEL_PATH / TEXT_CHECKPOINT_PATH 指向本机权重

# 4) 起服务（默认监听 18000 端口，对齐 backend-java application-dev.yml）
uvicorn main:app --host 0.0.0.0 --port 18000 --env-file .env
```

## 校准公式（对齐训练脚本）

```
raw_logit  = model(text).logits[:, 1]                # AI 类原始 logit
ai_prob    = sigmoid(raw_logit)                      # 未校准
calibrated = sigmoid((raw_logit / T) * a + b)        # 温度 → Platt
```

`T / a / b` 由 checkpoint 里的 `temperature / platt_a / platt_b` 直接给出。

## Fallback 机制

- checkpoint 未配置或加载失败 → 自动 fallback 到 MD5 stub，服务不 down
- 单次推理异常 → 同段兜底 stub，日志记录 exception
- `GET /health` 返回 `text.backend = "real" | "stub"` + `load_error`，前端 / 运维可判定

## 常见踩坑

- **Windows 首次 load 慢**：transformers 会下 model card，第一次 ~30s；已配 `local_files_only` 时无网络请求
- **CPU OOM**：`max_length` 大 + 段落长 → 单次 forward 显存/内存高。建议 `TEXT_MAX_LENGTH=512`，段落再长时后端已经切好
- **CUDA 装错**：`torch>=2.2` 默认 CPU 版；GPU 走 `pip install torch --index-url https://download.pytorch.org/whl/cu121`
- **weights_only 报错**：torch>=2.4 `torch.load` 默认 weights_only=True 但我们 checkpoint 是完整 dict，代码里已显式 `weights_only=False`
