# 推理服务启动规范（SOP）

> 目标：在任何机器上，从零到「服务就绪」的可复现流程。
> 切换检测模型不在本文范围 —— 见 `MODEL_SWITCH.md`。接口契约见 `docs/api/inference-openapi.yaml`。

## 0. 端口与契约

| 项 | 值 |
|---|---|
| 监听地址 | `0.0.0.0:8000`（与 backend-java `application-dev.yml` 的 `platform.inference.port` 及前端一致） |
| 健康检查 | `GET /health` |
| 就绪判据 | `text.backend == "real"` 且 `text.load_error == null` |

## 1. 环境准备（首次，一次性）

**Python 版本**：3.11 / 3.12（本机实测 3.12.10）

```powershell
cd d:\AAA\image_nious\deploy\inference-python
py -3.12 -m venv .venv                 # 创建虚拟环境
.\.venv\Scripts\Activate.ps1           # PowerShell 激活（每开新终端都要做，或用下面的脚本直接调 python.exe 免激活）
```

**安装依赖**：优先用阿里云镜像加速

```powershell
pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
```

> 注意：`requirements.txt` 里 `torch>=2.2,<3.0` 默认装 **CPU 版**。若需 GPU 加速，装完后单独换装对应 CUDA 版本，例如：
> ```powershell
> pip install -i https://mirrors.aliyun.com/pypi/simple/ torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
> ```
> 验证：`.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"`
> 本机当前为 `2.6.0+cu124`、`cuda.is_available()=True`。

## 2. 配置 `.env`

```powershell
Copy-Item .env.example .env           # 首次复制，之后手动改
```

关键项（完整说明见 `.env.example` 注释）：

```ini
TEXT_CHECKPOINT_PATH=D:/AAA/image_nious/models/text/aigc_detector_v3_thesis.pth   # 必填，绝对路径
TEXT_BASE_MODEL_PATH=D:/AAA/image_nious/models/text/chinese-roberta-wwm-ext       # legacy checkpoint 必填；新模型可留空
TEXT_DEVICE=cuda:0                     # cpu / cuda:0
TEXT_MODEL_VERSION=aigc_v3_thesis      # 报给前端/后端的版本标签
```

## 3. 启动

### 3.1 本地（uvicorn，开发推荐）

```powershell
cd d:\AAA\image_nious\deploy\inference-python
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env
```

或直接用一键脚本：`.\start.ps1`（见 §6）

### 3.2 Docker（部署）

```powershell
# build context 必须是仓库根目录（Dockerfile 会拷贝 ml/common 契约代码）
docker build -f deploy/inference-python/Dockerfile -t paperaigc-inference .
docker run -p 8000:8000 -v d:/AAA/image_nious/models:/app/models \
  -e TEXT_CHECKPOINT_PATH=/app/models/text/aigc_detector_v3_thesis.pth paperaigc-inference
```

## 4. 验证就绪

```powershell
curl.exe http://127.0.0.1:8000/health
```

期望：

```json
{"status":"ok","text":{"backend":"real","load_error":null,
  "detail":{"loaded":true,"model_version":"aigc_v3_thesis","device":"cuda:0",...}}}
```

关键三条：`backend=real`（非 stub）、`load_error=null`、`model_version` 与预期一致。

端到端冒烟（真实段落）：

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/detect/paragraph -H "Content-Type: application/json" -d "{\"text\":\"≥120 字的中文论文片段\"}"
```

## 5. 停止 / 重启

- 前台运行：`Ctrl+C`
- 后台/端口占用：`Get-NetTCPConnection -LocalPort 8000 | Select OwningProcess` → `Stop-Process -Id <PID>`
- 重启 = 停止后按 §3 重新启动（改过 `.env` 必须重启才生效）

## 6. 一键启动脚本 `start.ps1`

```powershell
# 一键启动推理服务（首次需先完成 §1 环境准备与 §2 配置 .env）
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py))      { throw "未找到 .venv，请先执行 START.md §1" }
if (-not (Test-Path ".env"))   { throw "未找到 .env，请先 Copy-Item .env.example .env 并配置" }
& $py -m uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env
```

## 7. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `/health` 里 `backend=stub` | checkpoint / backbone 加载失败回退 | 看启动日志 `detectors.text loading checkpoint` 报错原因（路径、`TEXT_DEVICE=cuda:0` 但无 GPU、legacy 忘配基座） |
| `cuda:0 不可用` | 装的 CPU 版 torch 或驱动不匹配 | §1 换装对应 cu 版本，或把 `TEXT_DEVICE` 改 `cpu` |
| 端口被占用 | 已有一个实例在跑 | §5 停止旧进程 |
| 首次加载很慢 | backbone 冷启动（HF 下载/加载） | 等待；离线机用 `TEXT_BASE_MODEL_PATH` 指本地目录 |
| `missing=0 unexpected=N` 的 WARNING | 权重含 optimizer/scheduler 等非模型键 | 无害，忽略 |