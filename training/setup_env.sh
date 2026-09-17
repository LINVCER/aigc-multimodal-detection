#!/usr/bin/env bash
# 训练环境一键搭建（Linux 云 GPU 实例，Ubuntu 22.04 + CUDA 12.x）
# 用法: bash setup_env.sh [--cpu]
set -euo pipefail

PYTHON_VERSION="3.11"
ENV_NAME="paperaigc"
CUDA_INDEX="https://download.pytorch.org/whl/cu124"

echo "=== [1/6] 检查 conda ==="
if ! command -v conda &>/dev/null; then
  echo "未找到 conda，安装 Miniconda..."
  wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
  bash /tmp/miniconda.sh -b -p "$HOME/miniconda3"
  eval "$("$HOME/miniconda3/bin/conda" shell.bash hook)"
  conda init bash
else
  eval "$(conda shell.bash hook)"
fi

echo "=== [2/6] 创建环境 ${ENV_NAME} (Python ${PYTHON_VERSION}) ==="
if ! conda env list | grep -q "^${ENV_NAME} "; then
  conda create -y -n "${ENV_NAME}" "python=${PYTHON_VERSION}"
fi
conda activate "${ENV_NAME}"

echo "=== [3/6] 安装 PyTorch ==="
if [[ "${1:-}" == "--cpu" ]]; then
  pip install torch --index-url https://download.pytorch.org/whl/cpu
else
  pip install torch --index-url "${CUDA_INDEX}"
fi

echo "=== [4/6] 安装依赖 ==="
pip install -r "$(dirname "$0")/requirements.txt"

echo "=== [5/6] 初始化 DVC ==="
cd "$(dirname "$0")/.."
if [ ! -d .dvc ]; then
  dvc init --subdir 2>/dev/null || dvc init
  # 远端存储指向 MinIO（本地 compose）或生产 S3/OSS
  dvc remote add -d minio s3://paperaigc-dvc
  dvc remote modify minio endpointurl "${DVC_S3_ENDPOINT:-http://localhost:9000}"
  dvc remote modify minio access_key_id "${MINIO_ACCESS_KEY:-minioadmin}"
  dvc remote modify minio secret_access_key "${MINIO_SECRET_KEY:-minioadmin}"
  echo "DVC 初始化完成，remote 指向 MinIO"
fi

echo "=== [6/6] 验证 ==="
python - <<'PY'
import torch, transformers, mlflow, peft
print(f"torch        {torch.__version__}  cuda={torch.cuda.is_available()}")
print(f"transformers {transformers.__version__}")
print(f"mlflow       {mlflow.__version__}")
print(f"peft         {peft.__version__}")
if torch.cuda.is_available():
    print(f"GPU          {torch.cuda.get_device_name(0)}  "
          f"{torch.cuda.get_device_properties(0).total_memory/1e9:.0f} GB")
PY

echo ""
echo "环境就绪。下一步:"
echo "  1. 起 MLflow:        docker compose -f training/docker-compose.mlops.yml up -d"
echo "  2. 下载数据集:       python training/scripts/download_datasets.py"
echo "  3. 跑基线:           bash training/scripts/train_baseline.sh"
