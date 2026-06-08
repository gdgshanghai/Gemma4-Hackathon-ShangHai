#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="${PY:-./.venv/bin/python}"
MODEL_DIR="${MODEL_DIR:-/home/huzi/Downloads/gemma-4-E4B-it}"
DATA_ROOT="${DATA_ROOT:-data/raw/ASD-DS}"
PROMPT_LANG="${PROMPT_LANG:-zh}"

RUN_NAME="${RUN_NAME:-gemma4-asd-lora-r32-code9-zh-examples-noaudio-ep5-qlora-loftq-v1}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/${RUN_NAME}}"
CACHE_DIR="${CACHE_DIR:-outputs/asd_ds_processor_cache_code9_examples_noaudio}"
REPORT_DIR="${REPORT_DIR:-outputs/${RUN_NAME}-reports}"

TRAIN_PHYSICAL_CUDA_DEVICES="${TRAIN_PHYSICAL_CUDA_DEVICES:-2,3}"
TRAIN_CUDA_DEVICES="${TRAIN_CUDA_DEVICES:-0,1}"

FRAME_FPS="${FRAME_FPS:-1.0}"
MAX_FRAMES="${MAX_FRAMES:-16}"
MAX_AUDIO_SECONDS="${MAX_AUDIO_SECONDS:-30}"
IMAGE_WIDTH="${IMAGE_WIDTH:-512}"

TRAIN_EPOCHS="${TRAIN_EPOCHS:-5}"
LEARNING_RATE="${LEARNING_RATE:-5e-5}"
GRAD_ACCUM_STEPS="${GRAD_ACCUM_STEPS:-8}"
EVAL_STEPS="${EVAL_STEPS:-84}"
SAVE_STEPS="${SAVE_STEPS:-84}"
SAVE_TOTAL_LIMIT="${SAVE_TOTAL_LIMIT:-6}"
PREDICTION_MAX_NEW_TOKENS="${PREDICTION_MAX_NEW_TOKENS:-16}"

WANDB="${WANDB:-1}"
WANDB_PROJECT="${WANDB_PROJECT:-gemma4-asd-ft}"
WANDB_ENTITY="${WANDB_ENTITY:-chenghuzi}"
ENV_FILE="${ENV_FILE:-.env}"

BARK_URL="${BARK_URL:-}"
BARK_GROUP="${BARK_GROUP:-hz_res_ft}"
LOG_PATH="${LOG_PATH:-}"
STAGE="init"

notify() {
  local title="$1"
  local body="$2"
  if [[ -z "$BARK_URL" ]]; then
    return 0
  fi
  curl -fsS --get "${BARK_URL}/${title}" \
    --data-urlencode "body=${body}" \
    --data-urlencode "group=${BARK_GROUP}" \
    --data-urlencode "isArchive=1" >/dev/null || true
}

on_error() {
  local code=$?
  notify "QLoRA LoftQ 实验失败" "阶段=${STAGE}，退出码=${code}。run=${RUN_NAME}。日志=${LOG_PATH:-未设置}。"
  exit "$code"
}
trap on_error ERR

run() {
  echo
  printf '+'
  printf ' %q' "$@"
  echo
  "$@"
}

metric_summary() {
  local metrics_path="$1"
  "$PY" - "$metrics_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
print(
    f"{path.name}: "
    f"samples={data['num_samples']} "
    f"parse={data['parse_rate']:.4f} "
    f"micro_f1={data['micro']['f1']:.4f} "
    f"macro_f1={data['macro']['f1']:.4f} "
    f"exact={data['exact_match']:.4f} "
    f"hamming={data['hamming_accuracy']:.4f}"
)
PY
}

wandb_args=(--wandb --env-file "$ENV_FILE" --wandb-project "$WANDB_PROJECT" --wandb-entity "$WANDB_ENTITY")
if [[ "$WANDB" == "0" ]]; then
  wandb_args=(--no-wandb)
fi

mkdir -p "$REPORT_DIR"

notify "QLoRA LoftQ 实验开始" "开始 r32/no-audio/code9/中文 prompt/5 epoch，训练方式=4bit QLoRA + LoftQ(bits=4, iter=1)。GPU=${TRAIN_PHYSICAL_CUDA_DEVICES}，run=${RUN_NAME}。日志=${LOG_PATH:-未设置}。"

STAGE="train"
run env CUDA_VISIBLE_DEVICES="$TRAIN_PHYSICAL_CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" -u run_train.py train \
  --cuda-devices "$TRAIN_CUDA_DEVICES" \
  --model-dir "$MODEL_DIR" \
  --data-root "$DATA_ROOT" \
  --output-dir "$OUTPUT_DIR" \
  --cache-dir "$CACHE_DIR" \
  --cache-mode require \
  --prompt-lang "$PROMPT_LANG" \
  --run-name "$RUN_NAME" \
  "${wandb_args[@]}" \
  --num-train-epochs "$TRAIN_EPOCHS" \
  --learning-rate "$LEARNING_RATE" \
  --warmup-ratio 0.03 \
  --weight-decay 0.0 \
  --per-device-train-batch-size 1 \
  --per-device-eval-batch-size 1 \
  --gradient-accumulation-steps "$GRAD_ACCUM_STEPS" \
  --logging-steps 5 \
  --eval-steps "$EVAL_STEPS" \
  --save-steps "$SAVE_STEPS" \
  --save-total-limit "$SAVE_TOTAL_LIMIT" \
  --remix-train-validation \
  --remix-validation-ratio 0.10 \
  --remix-seed 42 \
  --frame-fps "$FRAME_FPS" \
  --max-frames "$MAX_FRAMES" \
  --max-audio-seconds "$MAX_AUDIO_SECONDS" \
  --image-width "$IMAGE_WIDTH" \
  --no-audio \
  --lora-r 32 \
  --lora-alpha 64 \
  --lora-dropout 0.05 \
  --target-modules language \
  --max-memory-per-gpu 22GiB \
  --prediction-max-new-tokens "$PREDICTION_MAX_NEW_TOKENS" \
  --generated-metrics \
  --bf16 \
  --gradient-checkpointing \
  --qlora-4bit \
  --loftq \
  --loftq-bits 4 \
  --loftq-iter 1

STAGE="summarize"
SUMMARY_MD="${REPORT_DIR}/performance_summary.md"
SUMMARY_JSON="${REPORT_DIR}/performance_summary.json"
run "$PY" - "$OUTPUT_DIR" "$SUMMARY_MD" "$SUMMARY_JSON" <<'PY'
import glob
import json
import sys
from pathlib import Path

output_dir = Path(sys.argv[1])
summary_md = Path(sys.argv[2])
summary_json = Path(sys.argv[3])
metric_paths = sorted(Path(p) for p in glob.glob(str(output_dir / "generated_metrics" / "*final*_metrics.json")))
if not metric_paths:
    raise SystemExit(f"No final metrics found under {output_dir / 'generated_metrics'}")

rows = []
for path in metric_paths:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows.append(
        {
            "file": str(path),
            "split": data["split"],
            "samples": data["num_samples"],
            "parse_rate": data["parse_rate"],
            "micro_f1": data["micro"]["f1"],
            "macro_f1": data["macro"]["f1"],
            "exact_match": data["exact_match"],
            "hamming_accuracy": data["hamming_accuracy"],
        }
    )

summary = {
    "run_name": output_dir.name,
    "training": "4bit QLoRA + LoftQ",
    "lora_r": 32,
    "epochs": 5,
    "metrics": rows,
}
summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

lines = [
    f"# {output_dir.name}",
    "",
    "Training: 4bit QLoRA + LoftQ, r=32, no-audio, zh prompt, 5 epochs.",
    "",
    "| Split | Samples | Parse | Micro F1 | Macro F1 | Exact | Hamming |",
    "|---|---:|---:|---:|---:|---:|---:|",
]
for row in rows:
    lines.append(
        f"| {row['split']} | {row['samples']} | {row['parse_rate']:.4f} | "
        f"{row['micro_f1']:.4f} | {row['macro_f1']:.4f} | "
        f"{row['exact_match']:.4f} | {row['hamming_accuracy']:.4f} |"
    )
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
print(summary_json)
PY

echo "== Final metrics =="
for metrics in "$OUTPUT_DIR"/generated_metrics/*final*_metrics.json; do
  metric_summary "$metrics"
done

body="$("$PY" - "$SUMMARY_JSON" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
parts = []
for row in data["metrics"]:
    parts.append(
        f"{row['split']}: parse={row['parse_rate']:.4f}, "
        f"microF1={row['micro_f1']:.4f}, macroF1={row['macro_f1']:.4f}, "
        f"exact={row['exact_match']:.4f}"
    )
print("；".join(parts))
PY
)"
notify "QLoRA LoftQ 实验完成" "run=${RUN_NAME}。${body}。summary=${SUMMARY_MD}。"
