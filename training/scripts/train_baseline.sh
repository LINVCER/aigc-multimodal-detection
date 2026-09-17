#!/usr/bin/env bash
# 基线训练：先跑 RoBERTa 基线，再跑 mDeBERTa-v3 A/B 对比
# 前置: setup_env.sh 已执行、MLflow 已起、download_datasets.py 已跑
# 用法: bash train_baseline.sh [roberta|mdeberta|both]
set -euo pipefail

cd "$(dirname "$0")/.."
export MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://localhost:5000}"

TARGET="${1:-both}"
DATA_TRAIN="data/hc3-chinese/train.jsonl"

if [ ! -f "$DATA_TRAIN" ]; then
  echo "缺训练数据，先跑: python scripts/download_datasets.py --only hc3"
  exit 1
fi

# train_text_detector.py 从 LINVCER 仓库借来改造（加 MLflow logging + jsonl 支持）
# 放置于 training/train_text_detector.py

run_train() {
  local backbone="$1"
  local exp_name="$2"
  echo "=== 训练 ${exp_name} (${backbone}) ==="
  python train_text_detector.py \
    --model_path "${backbone}" \
    --train_data "${DATA_TRAIN}" \
    --epochs 4 \
    --batch_size 8 \
    --grad_accum_steps 4 \
    --lr 1e-5 \
    --max_length 512 \
    --unfreeze_layers 12 \
    --save_path "models/text/${exp_name}.pth" \
    --mlflow_experiment "text_detector_baseline" \
    --mlflow_run_name "${exp_name}"
}

case "$TARGET" in
  roberta)
    run_train "hfl/chinese-roberta-wwm-ext" "roberta_base_hc3"
    ;;
  mdeberta)
    run_train "microsoft/mdeberta-v3-base" "mdeberta_base_hc3"
    ;;
  both)
    run_train "hfl/chinese-roberta-wwm-ext" "roberta_base_hc3"
    run_train "microsoft/mdeberta-v3-base" "mdeberta_base_hc3"
    echo ""
    echo "两组实验完成，打开 ${MLFLOW_TRACKING_URI} 对比 val_acc / val_f1 / ECE"
    echo "预期: mdeberta 比 roberta 高 3-8 pp（MODEL_UPGRADE_PLAN.md 的第一个假设检验）"
    ;;
  *)
    echo "用法: bash train_baseline.sh [roberta|mdeberta|both]"
    exit 1
    ;;
esac
