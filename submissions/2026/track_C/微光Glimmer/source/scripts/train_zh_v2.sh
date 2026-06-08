#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_NAME="${RUN_NAME:-gemma4-asd-lora-r32-code9-zh-v1}"
CACHE_DIR="${CACHE_DIR:-outputs/asd_ds_processor_cache_code9}"
CACHE_WORKERS="${CACHE_WORKERS:-12}"
SKIP_CACHE="${SKIP_CACHE:-0}"
TRAIN_PHYSICAL_CUDA_DEVICES="${TRAIN_PHYSICAL_CUDA_DEVICES:-2,3}"
TRAIN_CUDA_DEVICES="${TRAIN_CUDA_DEVICES:-0,1}"

if [[ "$SKIP_CACHE" == "1" ]]; then
  echo "Skipping cache build because SKIP_CACHE=1"
else
  ./.venv/bin/python run_train.py build-cache \
    --model-dir /home/huzi/Downloads/gemma-4-E4B-it \
    --data-root data/raw/ASD-DS \
    --cache-dir "$CACHE_DIR" \
    --prompt-lang zh \
    --workers "$CACHE_WORKERS" \
    --frame-fps 1.0 \
    --max-frames 16 \
    --max-audio-seconds 30 \
    --image-width 512 \
    --cache-kind supervised \
    --cache-kind prompt
fi

CUDA_VISIBLE_DEVICES="$TRAIN_PHYSICAL_CUDA_DEVICES" \
PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}" \
./.venv/bin/python run_train.py train \
  --cuda-devices "$TRAIN_CUDA_DEVICES" \
  --model-dir /home/huzi/Downloads/gemma-4-E4B-it \
  --data-root data/raw/ASD-DS \
  --output-dir "outputs/$RUN_NAME" \
  --cache-dir "$CACHE_DIR" \
  --cache-mode require \
  --prompt-lang zh \
  --run-name "$RUN_NAME" \
  --wandb \
  --env-file .env \
  --wandb-project gemma4-asd-ft \
  --wandb-entity chenghuzi \
  --num-train-epochs 10 \
  --learning-rate 5e-5 \
  --warmup-ratio 0.03 \
  --weight-decay 0.0 \
  --per-device-train-batch-size 1 \
  --per-device-eval-batch-size 1 \
  --gradient-accumulation-steps 8 \
  --logging-steps 5 \
  --eval-steps 84 \
  --save-steps 84 \
  --save-total-limit 3 \
  --remix-train-validation \
  --remix-validation-ratio 0.10 \
  --remix-seed 42 \
  --frame-fps 1.0 \
  --max-frames 16 \
  --max-audio-seconds 30 \
  --image-width 512 \
  --lora-r 32 \
  --lora-alpha 64 \
  --lora-dropout 0.05 \
  --target-modules language \
  --max-memory-per-gpu 22GiB \
  --prediction-max-new-tokens 16 \
  --generated-metrics \
  --bf16 \
  --gradient-checkpointing
