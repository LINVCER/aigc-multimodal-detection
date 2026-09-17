#!/bin/bash
# ============================================================
# 云 GPU (A800-40GB) 全量训练一键脚本
# 
# 使用方法:
#   1. 租用 A800-40GB 实例 (AutoDL / 恒源云 / 矩池云)
#   2. 上传数据和代码 (见下方说明)
#   3. bash cloud_train.sh
# ============================================================

set -e

echo "=========================================="
echo "  AI 图像检测器 — 云端全量训练"
echo "  GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'Unknown')"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# ============================================================
# 1. 环境安装
# ============================================================

echo ""
echo "[1/5] 安装 Python 依赖..."

pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 -q
pip install transformers==4.47.1 Pillow numpy scipy scikit-learn tqdm -q

echo "  依赖安装完成"

# ============================================================
# 2. 路径配置 (根据实际上传位置修改)
# ============================================================

# 数据目录
DATA_ROOT="/root/autodl-tmp/image_data"
AI_DIR="${DATA_ROOT}/sd_v1_5/imagenet_ai_0424_sdv5/train/ai"
NATURE_DIR="${DATA_ROOT}/sd_v1_5/imagenet_ai_0424_sdv5/train/nature"
VAL_AI="${DATA_ROOT}/sd_v1_5/imagenet_ai_0424_sdv5/val/ai"
VAL_NATURE="${DATA_ROOT}/sd_v1_5/imagenet_ai_0424_sdv5/val/nature"

# 多生成器数据
EXTRA_AI="${DATA_ROOT}/imagenet_ai_0419_sdv4/ai ${DATA_ROOT}/imagenet_midjourney/ai"
EXTRA_NATURE="${DATA_ROOT}/imagenet_ai_0419_sdv4/nature ${DATA_ROOT}/imagenet_midjourney/nature"

# 代码目录
CODE_DIR="/root/autodl-tmp/image_nious/backend"

# 输出目录
OUTPUT_DIR="/root/autodl-tmp/models/image"

# CLIP 模型缓存 (如果已上传)
export TRANSFORMERS_CACHE="${DATA_ROOT}/huggingface_cache"

# ============================================================
# 3. 数据检查
# ============================================================

echo ""
echo "[2/5] 检查数据..."

check_dir() {
    if [ -d "$1" ]; then
        count=$(ls "$1" | wc -l)
        echo "  ✅ $1 : $count 文件"
    else
        echo "  ❌ $1 : 不存在!"
    fi
}

check_dir "$AI_DIR"
check_dir "$NATURE_DIR"
check_dir "$VAL_AI"
check_dir "$VAL_NATURE"

# ============================================================
# 4. 训练参数
# ============================================================

EPOCHS=12
BATCH_SIZE=128
MAX_SAMPLES=200000
LR=5e-4
PATIENCE=3
UNFREEZE_LAYERS=2

echo ""
echo "[3/5] 训练配置:"
echo "  Epochs: $EPOCHS"
echo "  Batch Size: $BATCH_SIZE"
echo "  Max Samples: $MAX_SAMPLES"
echo "  Learning Rate: $LR"
echo "  Early Stopping Patience: $PATIENCE"
echo "  ViT Unfreeze Layers: $UNFREEZE_LAYERS"
echo "  Output: $OUTPUT_DIR"

# ============================================================
# 5. 执行训练
# ============================================================

cd "$CODE_DIR"

echo ""
echo "[4/5] 开始 CNN 训练..."
echo "=========================================="

python train_image_sd.py \
    --ai_dir "$AI_DIR" \
    --nature_dir "$NATURE_DIR" \
    --val_ai "$VAL_AI" \
    --val_nature "$VAL_NATURE" \
    --extra_ai_dirs $EXTRA_AI \
    --extra_nature_dirs $EXTRA_NATURE \
    --epochs $EPOCHS \
    --batch_size $BATCH_SIZE \
    --max_samples $MAX_SAMPLES \
    --lr $LR \
    --patience $PATIENCE \
    --skip_vit \
    --seed 42

echo ""
echo "[5/5] 开始 ViT 训练..."
echo "=========================================="

python train_image_sd.py \
    --ai_dir "$AI_DIR" \
    --nature_dir "$NATURE_DIR" \
    --val_ai "$VAL_AI" \
    --val_nature "$VAL_NATURE" \
    --extra_ai_dirs $EXTRA_AI \
    --extra_nature_dirs $EXTRA_NATURE \
    --epochs $EPOCHS \
    --batch_size $BATCH_SIZE \
    --max_samples $MAX_SAMPLES \
    --lr $LR \
    --patience $PATIENCE \
    --unfreeze_layers $UNFREEZE_LAYERS \
    --skip_cnn \
    --seed 42

echo ""
echo "=========================================="
echo "  训练完成!"
echo "  CNN 模型: ${OUTPUT_DIR}/cnn_detection.pth"
echo "  ViT 模型: ${OUTPUT_DIR}/ufd_linear_head.pth"
echo "  配置文件: ${OUTPUT_DIR}/train_config.json"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 列出输出文件
echo ""
echo "输出文件:"
ls -lh "$OUTPUT_DIR"/*.pth "$OUTPUT_DIR"/*.json 2>/dev/null || echo "  未找到输出文件"
