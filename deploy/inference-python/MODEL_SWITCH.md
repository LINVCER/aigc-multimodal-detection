# 模型切换规范操作（SOP）

> 论文 AIGC 检测主方向为**文本态**。切换检测模型 = 改 `.env` 的 `TEXT_CHECKPOINT_PATH` + 重启服务，代码与接口**零改动**。
> 版本登记以 `ml/VERSIONS.md` 为准；每切换一次，务必同步更新本文档与 VERSIONS.md 的「部署时间」。

## 0. 当前生效模型

| 项 | 值 |
|---|---|
| checkpoint | `models/text/aigc_detector_v3_thesis.pth`（**legacy 兜底，不算正式版本**） |
| 基座 | `models/text/chinese-roberta-wwm-ext`（legacy 必配） |
| 版本标签 | `aigc_v3_thesis` |
| 定位 | 老实验产物，仅供链路联调；`v0.2.0-fusion-mdeberta` 训完并从 `ml/VERSIONS.md` 评估通过后替换 |

## 1. 切换原则

- **只改 `.env`，不改代码**。`detectors/text.py` 通过 `load_detector_from_checkpoint` 自动识别两类 checkpoint：
  - **新**（`ml/training/text/train.py` 产出）：`hyperparams.arch` 自带 backbone / 阈值 / 表层特征 scaler / version → `TEXT_BASE_MODEL_PATH` 可留空
  - **老**（`legacy/algorithms` 产出，无 arch）：必须同时配 `TEXT_BASE_MODEL_PATH`
- checkpoint 路径用**绝对路径**，Windows 下用正斜杠：`D:/AAA/image_nious/...`

## 2. 标准切换步骤

1. **备份当前配置**
   ```powershell
   copy .env .env.bak-YYYYMMDD   # 回滚凭据
   ```
2. **确认新 checkpoint 存在**
   ```powershell
   Test-Path "D:/AAA/image_nious/models/text/<new>.pth"
   ```
3. **改 `.env`**
   ```ini
   TEXT_CHECKPOINT_PATH=D:/AAA/image_nious/models/text/<new>.pth   # 必改
   TEXT_BASE_MODEL_PATH=D:/AAA/image_nious/models/text/chinese-roberta-wwm-ext  # 新模型可留空；legacy 必填
   TEXT_MODEL_VERSION=<可读版本标签>    # 新模型会被 checkpoint 里的 version 覆盖，此项兜底
   ```
4. **重启服务**
   ```powershell
   uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env
   ```
5. **验证加载成功**
   ```powershell
   curl.exe http://127.0.0.1:8000/health
   # 期望：text.backend == "real"，text.load_error == null，
   #       text.detail.model_version / backbone 与预期一致
   ```
6. **跑一次真实段落**，确认不走 stub
   ```powershell
   curl.exe -X POST http://127.0.0.1:8000/api/v1/detect/paragraph -H "Content-Type: application/json" -d "{\"text\":\"人工智能正在改变论文写作的方式，值得警惕的是它可能被滥用。\"}"
   # 期望：返回里 model_version 不是 "stub-v0"，且 warning 符合 MIN_CHARS 规则
   ```
7. **更新登记**：`ml/VERSIONS.md` 该版本「部署时间」改为今日，并在本文档 §0 替换为新模型
8. **回滚**：异常时用步骤 1 的备份恢复 `.env` → 重启即可，无需改代码

## 3. 模型文件命名与保留约定

模型权重统一放 `models/text/`，纳入 `.gitignore` 不入库。命名规范 `aigc_detector_v{N}_{purpose}.pth`：

| purpose | 含义 | 是否可指向 `.env` |
|---|---|---|
| `thesis` | 生产/联调正式版 | ✅ |
| `v{N}` | 版本正式权重（如 `v2`） | ✅（历史版本，灰度回退用） |
| `backup` | 备份 | ❌ 不指向 |
| `test` | 临时实验 | ❌ 不指向 |
| （无后缀） | 早期无名产物 | ❌ 弃用，建议归档 |

- **当前目录待整理**：`aigc_detector.pth` / `_test` / `_v1_backup` / `_v2` 为历史残留；确认不再需要后移入 `models/_archive/`，仅保留 `aigc_detector_v3_thesis.pth` 作为当前生效。
- 正式版本必须先在 `ml/VERSIONS.md` 登记（含 val 指标、backbone、阈值），才允许切到生产 `.env`。

## 4. 常见坑

- **忘记配 `TEXT_BASE_MODEL_PATH`（legacy checkpoint）** → `load_detector_from_checkpoint` 抛「checkpoint.hyperparams 缺 backbone」→ 服务 fallback stub
- **路径用反斜杠 `\`** → 部分环境解析异常，统一正斜杠
- **改完 `.env` 不重启** → uvicorn 只在启动时读 `.env`，必须重启才生效
- **误看 stub 当真实** → 一切以 `/health` 的 `backend == "real"` 为准，不要只看接口有返回