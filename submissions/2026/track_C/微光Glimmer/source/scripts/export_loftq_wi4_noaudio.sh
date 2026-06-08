#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="${PY:-./.venv/bin/python}"
MODEL_DIR="${MODEL_DIR:-/home/huzi/Downloads/gemma-4-E4B-it}"
ADAPTER_DIR="${ADAPTER_DIR:-outputs/gemma4-asd-lora-r32-code9-zh-examples-noaudio-ep5-qlora-loftq-v1}"
MERGED_MODEL_DIR="${MERGED_MODEL_DIR:-outputs/gemma4-asd-lora-r32-code9-zh-examples-noaudio-ep5-qlora-loftq-v1-merged}"
LITERT_OUT_DIR="${LITERT_OUT_DIR:-outputs/gemma4-asd-lora-r32-code9-zh-examples-noaudio-ep5-qlora-loftq-v1-litert-wi4-noaudio}"
REPORT_DIR="${REPORT_DIR:-outputs/gemma4-asd-lora-r32-code9-zh-examples-noaudio-ep5-qlora-loftq-v1-reports}"
LOG_PATH="${LOG_PATH:-${REPORT_DIR}/export_wi4.log}"

PHYSICAL_CUDA_DEVICES="${PHYSICAL_CUDA_DEVICES:-2,3}"
CUDA_DEVICES="${CUDA_DEVICES:-0,1}"
MAX_MEMORY_PER_GPU="${MAX_MEMORY_PER_GPU:-22GiB}"

mkdir -p "$REPORT_DIR"

if pgrep -af "run_train.py export|litert-torch export_hf" >/dev/null; then
  echo "Refusing to start: an export process already appears to be running." >&2
  pgrep -af "run_train.py export|litert-torch export_hf" >&2 || true
  exit 1
fi

echo "Cleaning incomplete output: $LITERT_OUT_DIR"
rm -rf "$LITERT_OUT_DIR"

echo "Starting true WI4 no-audio LiteRT-LM export in background."
echo "Log: $LOG_PATH"
echo "Output: $LITERT_OUT_DIR/model.litertlm"

nohup env CUDA_VISIBLE_DEVICES="$PHYSICAL_CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  "$PY" run_train.py export \
    --cuda-devices "$CUDA_DEVICES" \
    --model-dir "$MODEL_DIR" \
    --adapter-dir "$ADAPTER_DIR" \
    --merged-model-dir "$MERGED_MODEL_DIR" \
    --litert-out-dir "$LITERT_OUT_DIR" \
    --max-memory-per-gpu "$MAX_MEMORY_PER_GPU" \
    --bf16 \
    --overwrite \
    --inspect \
    --no-smoke-test \
    --no-audio \
    --quantization-recipe dynamic_wi4_afp32 \
    --vision-encoder-quantization-recipe dynamic_wi8_afp32 \
    > "$LOG_PATH" 2>&1 &

pid=$!
echo "PID: $pid"
echo
echo "Watch progress:"
echo "  tail -f \"$LOG_PATH\""
echo
echo "Check process:"
echo "  ps -p $pid -o pid,etime,%cpu,%mem,cmd"
echo
echo "After it finishes, verify recipe and size:"
echo "  cat \"$LITERT_OUT_DIR/export_manifest.json\""
echo "  ls -lh \"$LITERT_OUT_DIR/model.litertlm\""
