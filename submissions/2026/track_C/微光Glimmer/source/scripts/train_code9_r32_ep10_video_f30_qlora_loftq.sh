#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="${PY:-./.venv/bin/python}"
MODEL_DIR="${MODEL_DIR:-/home/huzi/Downloads/gemma-4-E4B-it}"
DATA_ROOT="${DATA_ROOT:-data/raw/ASD-DS}"
PROMPT_LANG="${PROMPT_LANG:-zh}"

RUN_NAME="${RUN_NAME:-gemma4-asd-lora-r32-code9-zh-examples-video-f30-ep10-qlora-loftq-v1}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/${RUN_NAME}}"
CACHE_DIR="${CACHE_DIR:-outputs/asd_ds_processor_cache_code9_examples_video_f30}"
REPORT_DIR="${REPORT_DIR:-outputs/${RUN_NAME}-reports}"

CUDA_DEVICES="${CUDA_DEVICES:-2,3}"
FRAME_FPS="${FRAME_FPS:-1.0}"
MAX_FRAMES="${MAX_FRAMES:-30}"
MAX_AUDIO_SECONDS="${MAX_AUDIO_SECONDS:-30}"
IMAGE_WIDTH="${IMAGE_WIDTH:-512}"

CACHE_WORKERS="${CACHE_WORKERS:-8}"
TRAIN_EPOCHS="${TRAIN_EPOCHS:-10}"
LEARNING_RATE="${LEARNING_RATE:-5e-5}"
GRAD_ACCUM_STEPS="${GRAD_ACCUM_STEPS:-8}"
EVAL_STEPS="${EVAL_STEPS:-84}"
SAVE_STEPS="${SAVE_STEPS:-84}"
SAVE_TOTAL_LIMIT="${SAVE_TOTAL_LIMIT:-10}"
PREDICTION_MAX_NEW_TOKENS="${PREDICTION_MAX_NEW_TOKENS:-16}"
BEST_METRIC="${BEST_METRIC:-macro_f1}"

WANDB="${WANDB:-1}"
WANDB_PROJECT="${WANDB_PROJECT:-gemma4-asd-ft}"
WANDB_ENTITY="${WANDB_ENTITY:-chenghuzi}"
ENV_FILE="${ENV_FILE:-.env}"

BARK_URL="${BARK_URL:-}"
BARK_GROUP="${BARK_GROUP:-hz_res_ft}"
LOG_PATH="${LOG_PATH:-}"
STAGE="init"

mkdir -p "$REPORT_DIR"

urlencode() {
  "$PY" - "$1" <<'PY'
import sys
from urllib.parse import quote

print(quote(sys.argv[1], safe=""))
PY
}

notify() {
  local title="$1"
  local body="$2"
  if [[ -z "$BARK_URL" ]]; then
    return 0
  fi
  local encoded_title
  local encoded_body
  encoded_title="$(urlencode "$title")"
  encoded_body="$(urlencode "$body")"
  curl -fsS --get "${BARK_URL}/${encoded_title}/${encoded_body}" \
    --data-urlencode "group=${BARK_GROUP}" \
    --data-urlencode "isArchive=1" >/dev/null || true
}

on_error() {
  local code=$?
  notify "video-f30-ep10-failed" "阶段=${STAGE}，退出码=${code}。run=${RUN_NAME}。日志=${LOG_PATH:-未设置}。"
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

assert_new_or_empty_dir() {
  local path="$1"
  if [[ -d "$path" ]] && [[ -n "$(find "$path" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "Refusing to overwrite non-empty directory: $path" >&2
    echo "Set RUN_NAME/OUTPUT_DIR to a new path, or move the existing directory." >&2
    exit 1
  fi
}

wandb_args=(--wandb --env-file "$ENV_FILE" --wandb-project "$WANDB_PROJECT" --wandb-entity "$WANDB_ENTITY")
if [[ "$WANDB" == "0" ]]; then
  wandb_args=(--no-wandb)
fi

if [[ "${SKIP_TRAIN:-0}" != "1" ]]; then
  assert_new_or_empty_dir "$OUTPUT_DIR"
fi

notify "video-f30-ep10-start" "开始 video-only 训练：max_frames=${MAX_FRAMES}，audio=off，QLoRA+LoftQ，r32，${TRAIN_EPOCHS} epoch，run=${RUN_NAME}。"

STAGE="build-cache"
if [[ "${SKIP_CACHE:-0}" == "1" ]]; then
  echo "Skipping cache build because SKIP_CACHE=1"
else
  notify "video-f30-cache-start" "开始 build video-only cache：workers=${CACHE_WORKERS}，cache=${CACHE_DIR}。"
  run "$PY" run_train.py build-cache \
    --model-dir "$MODEL_DIR" \
    --data-root "$DATA_ROOT" \
    --cache-dir "$CACHE_DIR" \
    --prompt-lang "$PROMPT_LANG" \
    --workers "$CACHE_WORKERS" \
    --frame-fps "$FRAME_FPS" \
    --max-frames "$MAX_FRAMES" \
    --max-audio-seconds "$MAX_AUDIO_SECONDS" \
    --image-width "$IMAGE_WIDTH" \
    --cache-kind supervised \
    --cache-kind prompt \
    --no-audio
  notify "video-f30-cache-done" "video-only cache build 完成：${CACHE_DIR}。"
fi

STAGE="train"
if [[ "${SKIP_TRAIN:-0}" == "1" ]]; then
  echo "Skipping training because SKIP_TRAIN=1"
else
  notify "video-f30-train-start" "开始训练：GPU=${CUDA_DEVICES}，epoch=${TRAIN_EPOCHS}，W&B=${WANDB}。"
  run env CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" -u run_train.py train \
    --cuda-devices "$CUDA_DEVICES" \
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
fi

STAGE="summary"
SUMMARY_JSON="${REPORT_DIR}/performance_summary.json"
SUMMARY_MD="${REPORT_DIR}/performance_summary.md"
run "$PY" - "$OUTPUT_DIR" "$REPORT_DIR" "$SUMMARY_JSON" "$SUMMARY_MD" "$RUN_NAME" "$BEST_METRIC" "$TRAIN_EPOCHS" "$MAX_FRAMES" <<'PY'
import glob
import json
import re
import sys
from pathlib import Path

output_dir = Path(sys.argv[1])
report_dir = Path(sys.argv[2])
summary_json = Path(sys.argv[3])
summary_md = Path(sys.argv[4])
run_name = sys.argv[5]
best_metric = sys.argv[6]
train_epochs = float(sys.argv[7])
max_frames = int(float(sys.argv[8]))

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def metric_value(data: dict, name: str) -> float:
    if name == "micro_f1":
        return float(data["micro"]["f1"])
    if name == "macro_f1":
        return float(data["macro"]["f1"])
    return float(data[name])

def compact(path: Path | None) -> dict | None:
    if path is None:
        return None
    data = load(path)
    return {
        "path": str(path),
        "split": data.get("split"),
        "step": data.get("step"),
        "epoch": data.get("epoch"),
        "samples": data.get("num_samples"),
        "parse_rate": data.get("parse_rate"),
        "micro_f1": data.get("micro", {}).get("f1"),
        "macro_f1": data.get("macro", {}).get("f1"),
        "exact_match": data.get("exact_match"),
        "hamming_accuracy": data.get("hamming_accuracy"),
    }

def latest(pattern: str) -> Path | None:
    paths = sorted(Path(item) for item in glob.glob(str(output_dir / "generated_metrics" / pattern)))
    return paths[-1] if paths else None

validation_paths = sorted(
    Path(item)
    for item in glob.glob(str(output_dir / "generated_metrics" / "validation_step_*_metrics.json"))
)
if not validation_paths:
    raise SystemExit(f"No validation_step metrics found under {output_dir / 'generated_metrics'}")

candidates = []
for path in validation_paths:
    data = load(path)
    match = re.search(r"validation_step_(\d+)_", path.name)
    step = int(match.group(1)) if match else int(data["step"])
    candidates.append(
        {
            "step": step,
            "epoch": data.get("epoch"),
            "metric": best_metric,
            "metric_value": metric_value(data, best_metric),
            "parse_rate": data.get("parse_rate"),
            "micro_f1": data.get("micro", {}).get("f1"),
            "macro_f1": data.get("macro", {}).get("f1"),
            "exact_match": data.get("exact_match"),
            "hamming_accuracy": data.get("hamming_accuracy"),
            "metrics_path": str(path),
            "checkpoint": str(output_dir / f"checkpoint-{step}"),
            "checkpoint_exists": (output_dir / f"checkpoint-{step}").is_dir(),
        }
    )

best = max(candidates, key=lambda row: (row["metric_value"], row["micro_f1"] or 0.0, row["step"]))
validation_final_path = latest("validation_final_*_metrics.json")
test_final_path = latest("test_final_*_metrics.json")

summary = {
    "run_name": run_name,
    "training": {
        "method": "QLoRA + LoftQ",
        "lora_r": 32,
        "epochs": train_epochs,
        "prompt_lang": "zh",
        "use_audio": False,
        "frame_fps": 1.0,
        "max_frames": max_frames,
        "selection_metric": best_metric,
    },
    "best_validation": best,
    "validation_final": compact(validation_final_path),
    "test_final": compact(test_final_path),
    "validation_candidates": candidates,
}

summary_json.parent.mkdir(parents=True, exist_ok=True)
summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def fmt(value):
    return "n/a" if value is None else f"{float(value):.4f}"

rows = [
    ("Best validation", best),
    ("Final validation", summary["validation_final"]),
    ("Final test", summary["test_final"]),
]
lines = [
    f"# {run_name}",
    "",
    f"Video-only run: max_frames={max_frames}, audio=off, epochs={train_epochs:g}.",
    "",
    "| Metric row | Step | Epoch | Parse | Micro F1 | Macro F1 | Exact | Hamming |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
]
for label, row in rows:
    if row is None:
        lines.append(f"| {label} | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
    else:
        lines.append(
            f"| {label} | {row.get('step', 'n/a')} | {fmt(row.get('epoch'))} | "
            f"{fmt(row.get('parse_rate'))} | {fmt(row.get('micro_f1'))} | "
            f"{fmt(row.get('macro_f1'))} | {fmt(row.get('exact_match'))} | "
            f"{fmt(row.get('hamming_accuracy'))} |"
        )

lines.extend(
    [
        "",
        "## Artifacts",
        "",
        f"- Output dir: `{output_dir}`",
        f"- Summary JSON: `{summary_json}`",
        f"- Best validation metrics: `{best['metrics_path']}`",
    ]
)
if test_final_path is not None:
    lines.append(f"- Final test metrics: `{test_final_path}`")

summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md.read_text(encoding="utf-8"))
PY

notify "video-f30-ep10-done" "video-only f30 ep10 完成。报告=${SUMMARY_MD}。$(tr '\n' ' ' < "$SUMMARY_MD" | cut -c1-1200)"

echo
echo "DONE"
echo "run_name: $RUN_NAME"
echo "output_dir: $OUTPUT_DIR"
echo "summary: $SUMMARY_MD"
