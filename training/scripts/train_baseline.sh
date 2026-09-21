#!/usr/bin/env bash
# 文本检测训练一键脚本：数据构建 → 增强 → 评测集 → 训练 → 评估
# 前置: setup_env.sh 已执行；LLM 改写需配 PARAPHRASE_BASE_URL / PARAPHRASE_API_KEY / PARAPHRASE_MODEL
# 用法:
#   bash training/scripts/train_baseline.sh data                 # 只拉数据 + 构建 train/val/test
#   bash training/scripts/train_baseline.sh augment [llm|rule]   # 改写 / 润色 / 混写增强并合并
#   bash training/scripts/train_baseline.sh evalsets             # 切 6 套评测集
#   bash training/scripts/train_baseline.sh train baseline|fusion|large
#   bash training/scripts/train_baseline.sh eval  baseline|fusion|large
#   bash training/scripts/train_baseline.sh smoke                # 冒烟：200 条 1 epoch 跑通链路
#   bash training/scripts/train_baseline.sh all                  # data → augment(rule) → evalsets → train fusion → eval
set -euo pipefail

cd "$(dirname "$0")/../.."          # 仓库根，以便 python -m ml.xxx
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
export MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://localhost:5000}"

DATA_DIR="ml/datasets/text/data"
declare -A CFG=(
  [baseline]="ml/configs/text/v0.1.0-baseline.yaml"
  [fusion]="ml/configs/text/v0.2.0-fusion-mdeberta.yaml"
  [large]="ml/configs/text/v0.3.0-fusion-deberta-large.yaml"
)
declare -A CKPT=(
  [baseline]="ml/checkpoints/text/v0.1.0-baseline/best.pth"
  [fusion]="ml/checkpoints/text/v0.2.0-fusion-mdeberta/best.pth"
  [large]="ml/checkpoints/text/v0.3.0-fusion-deberta-large/best.pth"
)

step_data() {
  echo "=== [data] 拉取公开集 → ${DATA_DIR} ==="
  # qwen / deepseek 留作 cross-generator 未见生成器；需要它们进训练时去掉 --held-out-sources
  python -m ml.datasets.text.build_dataset --sources hc3,csl,m4 --out "${DATA_DIR}" \
    --held-out-sources "${HELD_OUT_SOURCES:-qwen,deepseek}"
  if [ -d "ml/datasets/text/raw/cheat" ]; then
    python -m ml.datasets.text.build_dataset --sources cheat --out "${DATA_DIR}"
  fi
}

step_augment() {
  local engine="${1:-llm}"
  echo "=== [augment] engine=${engine} ==="
  mkdir -p "${DATA_DIR}/augment"
  python -m ml.datasets.text.paraphrase_augment --mode paraphrase --engine "${engine}" \
    --in "${DATA_DIR}/train.jsonl" --out "${DATA_DIR}/augment/paraphrase_train.jsonl" --n "${N_PARA:-6000}"
  python -m ml.datasets.text.paraphrase_augment --mode paraphrase --engine "${engine}" \
    --in "${DATA_DIR}/test.jsonl"  --out "${DATA_DIR}/augment/paraphrase_test.jsonl"  --n "${N_PARA_TEST:-800}"
  if [ "${engine}" = "llm" ]; then
    python -m ml.datasets.text.paraphrase_augment --mode polish  --in "${DATA_DIR}/train.jsonl" \
      --out "${DATA_DIR}/augment/polish_train.jsonl" --n "${N_POLISH:-4000}"
    python -m ml.datasets.text.paraphrase_augment --mode polish  --in "${DATA_DIR}/test.jsonl" \
      --out "${DATA_DIR}/augment/polish_test.jsonl"  --n "${N_POLISH_TEST:-600}"
    python -m ml.datasets.text.paraphrase_augment --mode mixcase --in "${DATA_DIR}/train.jsonl" \
      --out "${DATA_DIR}/augment/mixcase_train.jsonl" --n "${N_MIX:-2000}"
    python -m ml.datasets.text.paraphrase_augment --mode mixcase --in "${DATA_DIR}/test.jsonl" \
      --out "${DATA_DIR}/augment/mixcase_test.jsonl"  --n "${N_MIX_TEST:-400}"
  else
    echo "rule 引擎只能产 paraphrase_weak；polished / mixcase 需要 LLM（PARAPHRASE_* 环境变量）"
  fi
  python -m ml.datasets.text.paraphrase_augment --merge "${DATA_DIR}"
}

step_evalsets() {
  echo "=== [evalsets] ==="
  python -m ml.datasets.text.build_evalsets --data "${DATA_DIR}"
}

step_train() {
  local which="${1:-fusion}"
  echo "=== [train] ${which} → ${CFG[$which]} ==="
  python -m ml.training.text.train --config "${CFG[$which]}"
}

step_eval() {
  local which="${1:-fusion}"
  echo "=== [eval] ${which} ==="
  python -m ml.evaluation.text.eval --checkpoint "${CKPT[$which]}" --evalset-dir "${DATA_DIR}/evalsets"
}

step_smoke() {
  echo "=== [smoke] 200 条 × 1 epoch，验证整条链路 ==="
  python -m ml.training.text.train --config "${CFG[fusion]}" --max-train-samples 200 --epochs 1 --dry-run
}

case "${1:-}" in
  data)     step_data ;;
  augment)  step_augment "${2:-llm}" ;;
  evalsets) step_evalsets ;;
  train)    step_train "${2:-fusion}" ;;
  eval)     step_eval "${2:-fusion}" ;;
  smoke)    step_smoke ;;
  all)      step_data; step_augment rule; step_evalsets; step_train fusion; step_eval fusion ;;
  *)        sed -n '2,12p' "$0"; exit 1 ;;
esac
