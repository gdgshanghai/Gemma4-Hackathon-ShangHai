#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="${PY:-./.venv/bin/python}"
MODEL_DIR="${MODEL_DIR:-/home/huzi/Downloads/gemma-4-E4B-it}"
DATA_ROOT="${DATA_ROOT:-data/raw/ASD-DS}"
PROMPT_LANG="${PROMPT_LANG:-zh}"

RUN_NAME="${RUN_NAME:-gemma4-asd-lora-r32-code9-zh-examples-waudio-ep10-qlora-loftq-v1}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/${RUN_NAME}}"
CACHE_DIR="${CACHE_DIR:-outputs/asd_ds_processor_cache_code9_examples_audio}"
REPORT_DIR="${REPORT_DIR:-outputs/${RUN_NAME}-reports}"

CUDA_DEVICES="${CUDA_DEVICES:-2,3}"
FRAME_FPS="${FRAME_FPS:-1.0}"
MAX_FRAMES="${MAX_FRAMES:-16}"
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

OFFICIAL_LITERTLM_FILE="${OFFICIAL_LITERTLM_FILE:-outputs/gemma4-official-litert/gemma-4-E4B-it.litertlm}"
LITERT_BACKEND="${LITERT_BACKEND:-gpu}"
LITERT_VISION_BACKEND="${LITERT_VISION_BACKEND:-gpu}"
LITERT_AUDIO_BACKEND="${LITERT_AUDIO_BACKEND:-cpu}"
LITERT_WORKERS="${LITERT_WORKERS:-2}"
LITERT_MAX_OUTPUT_TOKENS="${LITERT_MAX_OUTPUT_TOKENS:-9}"
LITERT_CACHE_LENGTH="${LITERT_CACHE_LENGTH:-4096}"

S3_URI="${S3_URI:-s3://huzi-nydata/asd-gemma4-code9-qlora-loftq-ep10-wi8-waudio.litertlm}"

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
  notify "ep10-waudio-wi8-failed" "阶段=${STAGE}，退出码=${code}。run=${RUN_NAME}。日志=${LOG_PATH:-未设置}。"
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

metric_value() {
  local metrics_path="$1"
  local key="$2"
  "$PY" - "$metrics_path" "$key" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
key = sys.argv[2]
if key == "micro_f1":
    value = data["micro"]["f1"]
elif key == "macro_f1":
    value = data["macro"]["f1"]
else:
    value = data[key]
print(value)
PY
}

latest_metrics() {
  local dir="$1"
  ls -t "$dir"/*_metrics.json | head -n 1
}

assert_new_or_empty_dir() {
  local path="$1"
  if [[ -d "$path" ]] && [[ -n "$(find "$path" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "Refusing to overwrite non-empty directory: $path" >&2
    echo "Set OUTPUT_DIR/RUN_NAME to a new path, or move the existing directory." >&2
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

notify "ep10-waudio-wi8-start" "开始流程：QLoRA+LoftQ，r32，audio，zh prompt，10 epoch，按 validation macro F1 选 best，save_total_limit=${SAVE_TOTAL_LIMIT}。run=${RUN_NAME}。"

STAGE="build-cache"
if [[ "${SKIP_CACHE:-0}" == "1" ]]; then
  echo "Skipping cache build because SKIP_CACHE=1"
else
  notify "ep10-waudio-cache-start" "开始 build audio cache，workers=${CACHE_WORKERS}，cache=${CACHE_DIR}。"
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
    --audio
  notify "ep10-waudio-cache-done" "audio cache build 完成：${CACHE_DIR}。"
fi

STAGE="train"
if [[ "${SKIP_TRAIN:-0}" == "1" ]]; then
  echo "Skipping training because SKIP_TRAIN=1"
else
  notify "ep10-waudio-train-start" "开始训练：10 epoch，audio on，GPU=${CUDA_DEVICES}，W&B=${WANDB}。"
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
    --audio \
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

STAGE="select-best"
BEST_INFO_JSON="${REPORT_DIR}/best_checkpoint.json"
run "$PY" - "$OUTPUT_DIR" "$BEST_METRIC" "$BEST_INFO_JSON" <<'PY'
import glob
import json
import re
import sys
from pathlib import Path

output_dir = Path(sys.argv[1])
metric_name = sys.argv[2]
best_info_path = Path(sys.argv[3])
metric_files = sorted(Path(item) for item in glob.glob(str(output_dir / "generated_metrics" / "validation_step_*_metrics.json")))
if not metric_files:
    raise SystemExit(f"No validation_step metrics found under {output_dir / 'generated_metrics'}")

def metric_value(data: dict, name: str) -> float:
    if name == "micro_f1":
        return float(data["micro"]["f1"])
    if name == "macro_f1":
        return float(data["macro"]["f1"])
    return float(data[name])

rows = []
for path in metric_files:
    data = json.loads(path.read_text(encoding="utf-8"))
    match = re.search(r"validation_step_(\d+)_", path.name)
    step = int(match.group(1)) if match else int(data["step"])
    checkpoint = output_dir / f"checkpoint-{step}"
    rows.append(
        {
            "step": step,
            "epoch": data.get("epoch"),
            "metric": metric_name,
            "metric_value": metric_value(data, metric_name),
            "parse_rate": data.get("parse_rate"),
            "micro_f1": data.get("micro", {}).get("f1"),
            "macro_f1": data.get("macro", {}).get("f1"),
            "exact_match": data.get("exact_match"),
            "hamming_accuracy": data.get("hamming_accuracy"),
            "metrics_path": str(path),
            "checkpoint": str(checkpoint),
            "checkpoint_exists": checkpoint.is_dir(),
        }
    )

best = max(rows, key=lambda row: (row["metric_value"], row["micro_f1"] or 0.0, row["step"]))
if not best["checkpoint_exists"]:
    raise SystemExit(f"Best checkpoint is missing: {best['checkpoint']}")

best_info = {"best": best, "candidates": rows}
best_info_path.write_text(json.dumps(best_info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(best_info["best"], ensure_ascii=False))
PY

BEST_STEP="$("$PY" - "$BEST_INFO_JSON" <<'PY'
import json, sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["best"]["step"])
PY
)"
BEST_CHECKPOINT="$("$PY" - "$BEST_INFO_JSON" <<'PY'
import json, sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["best"]["checkpoint"])
PY
)"
BEST_METRICS_PATH="$("$PY" - "$BEST_INFO_JSON" <<'PY'
import json, sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["best"]["metrics_path"])
PY
)"
BEST_VAL_MICRO="$(metric_value "$BEST_METRICS_PATH" micro_f1)"
BEST_VAL_MACRO="$(metric_value "$BEST_METRICS_PATH" macro_f1)"
BEST_VAL_EXACT="$(metric_value "$BEST_METRICS_PATH" exact_match)"
notify "ep10-waudio-best-selected" "best checkpoint：step=${BEST_STEP}，validation macro=${BEST_VAL_MACRO}，micro=${BEST_VAL_MICRO}，exact=${BEST_VAL_EXACT}。checkpoint=${BEST_CHECKPOINT}。"

MERGED_DIR="${MERGED_DIR:-outputs/${RUN_NAME}-best-step${BEST_STEP}-merged}"
HF_EVAL_DIR="${HF_EVAL_DIR:-${MERGED_DIR}/generated_metrics_audio}"
WI8_DIR="${WI8_DIR:-outputs/${RUN_NAME}-best-step${BEST_STEP}-litert-wi8-waudio}"
WI8_EVAL_DIR="${WI8_EVAL_DIR:-${WI8_DIR}/generated_metrics_audio}"

STAGE="merge-best"
notify "ep10-waudio-merge-start" "开始 merge best checkpoint step=${BEST_STEP}。输出=${MERGED_DIR}。"
run env CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" run_train.py merge \
  --cuda-devices "$CUDA_DEVICES" \
  --model-dir "$MODEL_DIR" \
  --adapter-dir "$BEST_CHECKPOINT" \
  --merged-model-dir "$MERGED_DIR" \
  --max-memory-per-gpu 22GiB \
  --bf16
notify "ep10-waudio-merge-done" "merge 完成：${MERGED_DIR}。"

STAGE="hf-direct-test"
notify "ep10-waudio-hf-test-start" "开始 merged HF audio test eval，samples=182。"
run env CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" run_train.py eval-hf \
  --cuda-devices "$CUDA_DEVICES" \
  --model-dir "$MERGED_DIR" \
  --processor-dir "$MODEL_DIR" \
  --data-root "$DATA_ROOT" \
  --output-dir "$HF_EVAL_DIR" \
  --cache-dir "$CACHE_DIR" \
  --cache-mode require \
  --split test \
  --prompt-lang "$PROMPT_LANG" \
  --frame-fps "$FRAME_FPS" \
  --max-frames "$MAX_FRAMES" \
  --max-audio-seconds "$MAX_AUDIO_SECONDS" \
  --image-width "$IMAGE_WIDTH" \
  --audio \
  --prediction-max-new-tokens "$PREDICTION_MAX_NEW_TOKENS" \
  --max-memory-per-gpu 22GiB \
  --bf16
HF_METRICS_PATH="$(latest_metrics "$HF_EVAL_DIR")"
HF_METRICS_REPORT_PATH="${REPORT_DIR}/hf_audio_test_metrics.json"
cp "$HF_METRICS_PATH" "$HF_METRICS_REPORT_PATH"
HF_METRICS_PATH="$HF_METRICS_REPORT_PATH"
HF_PARSE="$(metric_value "$HF_METRICS_PATH" parse_rate)"
HF_MICRO="$(metric_value "$HF_METRICS_PATH" micro_f1)"
HF_MACRO="$(metric_value "$HF_METRICS_PATH" macro_f1)"
HF_EXACT="$(metric_value "$HF_METRICS_PATH" exact_match)"
notify "ep10-waudio-hf-test-done" "HF audio test 完成：parse=${HF_PARSE}，micro=${HF_MICRO}，macro=${HF_MACRO}，exact=${HF_EXACT}。metrics=${HF_METRICS_PATH}。"

STAGE="export-wi8"
notify "ep10-waudio-wi8-export-start" "开始导出 WI8 audio LiteRT-LM，cache_length=${LITERT_CACHE_LENGTH}，graft source=${OFFICIAL_LITERTLM_FILE}。输出=${WI8_DIR}。"
run env CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" run_train.py export \
  --cuda-devices "$CUDA_DEVICES" \
  --model-dir "$MODEL_DIR" \
  --adapter-dir "$BEST_CHECKPOINT" \
  --merged-model-dir "$MERGED_DIR" \
  --litert-out-dir "$WI8_DIR" \
  --official-litertlm-file "$OFFICIAL_LITERTLM_FILE" \
  --max-memory-per-gpu 22GiB \
  --bf16 \
  --overwrite \
  --inspect \
  --no-smoke-test \
  --audio \
  --cache-length "$LITERT_CACHE_LENGTH" \
  --quantization-recipe dynamic_wi8_afp32 \
  --vision-encoder-quantization-recipe dynamic_wi8_afp32

STAGE="eval-wi8"
notify "ep10-waudio-wi8-eval-start" "开始 WI8 LiteRT-LM audio test eval，workers=${LITERT_WORKERS}。"
run env CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" -u eval_litert_lm.py \
  --litertlm-file "$WI8_DIR/model.litertlm" \
  --data-root "$DATA_ROOT" \
  --model-dir "$MODEL_DIR" \
  --split test \
  --prompt-lang "$PROMPT_LANG" \
  --output-dir "$WI8_EVAL_DIR" \
  --media-cache-dir "$WI8_DIR/media_cache_audio" \
  --frame-fps "$FRAME_FPS" \
  --max-frames "$MAX_FRAMES" \
  --max-audio-seconds "$MAX_AUDIO_SECONDS" \
  --image-width "$IMAGE_WIDTH" \
  --backend "$LITERT_BACKEND" \
  --vision-backend "$LITERT_VISION_BACKEND" \
  --audio-backend "$LITERT_AUDIO_BACKEND" \
  --audio \
  --temperature 0.0 \
  --top-p 1.0 \
  --top-k 1 \
  --max-output-tokens "$LITERT_MAX_OUTPUT_TOKENS" \
  --workers "$LITERT_WORKERS" \
  --reuse-media-cache
WI8_METRICS_PATH="$(latest_metrics "$WI8_EVAL_DIR")"
WI8_PARSE="$(metric_value "$WI8_METRICS_PATH" parse_rate)"
WI8_MICRO="$(metric_value "$WI8_METRICS_PATH" micro_f1)"
WI8_MACRO="$(metric_value "$WI8_METRICS_PATH" macro_f1)"
WI8_EXACT="$(metric_value "$WI8_METRICS_PATH" exact_match)"
notify "ep10-waudio-wi8-eval-done" "WI8 audio eval 完成：parse=${WI8_PARSE}，micro=${WI8_MICRO}，macro=${WI8_MACRO}，exact=${WI8_EXACT}。metrics=${WI8_METRICS_PATH}。"

STAGE="upload-wi8"
notify "ep10-waudio-wi8-upload-start" "开始上传 WI8 audio 到 S3：${S3_URI}。"
run aws s3 cp "$WI8_DIR/model.litertlm" "$S3_URI" --only-show-errors
S3_LS="$(aws s3 ls "$S3_URI")"
notify "ep10-waudio-wi8-upload-done" "WI8 audio 已上传：${S3_URI}。S3=${S3_LS}。"

STAGE="summary"
SUMMARY_JSON="${REPORT_DIR}/performance_summary.json"
SUMMARY_MD="${REPORT_DIR}/performance_summary.md"
run "$PY" - "$SUMMARY_JSON" "$SUMMARY_MD" "$RUN_NAME" "$BEST_INFO_JSON" "$HF_METRICS_PATH" "$WI8_METRICS_PATH" "$WI8_DIR/model.litertlm" "$S3_URI" "$TRAIN_EPOCHS" "$MAX_FRAMES" "$MAX_AUDIO_SECONDS" "$LITERT_CACHE_LENGTH" <<'PY'
import json
import os
import sys
from pathlib import Path

summary_json = Path(sys.argv[1])
summary_md = Path(sys.argv[2])
run_name = sys.argv[3]
best_info_path = Path(sys.argv[4])
hf_metrics_path = Path(sys.argv[5])
wi8_metrics_path = Path(sys.argv[6])
wi8_file = Path(sys.argv[7])
s3_uri = sys.argv[8]
train_epochs = int(float(sys.argv[9]))
max_frames = int(float(sys.argv[10]))
max_audio_seconds = float(sys.argv[11])
litert_cache_length = int(float(sys.argv[12]))

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def compact(path: Path) -> dict:
    data = load(path)
    return {
        "path": str(path),
        "samples": data.get("num_samples"),
        "parse_rate": data.get("parse_rate"),
        "micro_f1": data.get("micro", {}).get("f1"),
        "macro_f1": data.get("macro", {}).get("f1"),
        "exact_match": data.get("exact_match"),
        "hamming_accuracy": data.get("hamming_accuracy"),
        "runtime": data.get("runtime"),
    }

def gib(path: Path) -> float | None:
    if not path.is_file():
        return None
    return os.path.getsize(path) / (1024 ** 3)

best_info = load(best_info_path)
summary = {
    "run_name": run_name,
    "training": {
        "method": "QLoRA + LoftQ",
        "lora_r": 32,
        "epochs": train_epochs,
        "use_audio": True,
        "max_frames": max_frames,
        "max_audio_seconds": max_audio_seconds,
        "selection_metric": "validation_macro_f1",
        "best": best_info["best"],
    },
    "current": {
        "hf_direct_audio": compact(hf_metrics_path),
        "litert_wi8_audio": {
            **compact(wi8_metrics_path),
            "model_file": str(wi8_file),
            "model_size_gib": gib(wi8_file),
            "cache_length": litert_cache_length,
            "s3_uri": s3_uri,
        },
    },
}
summary_json.parent.mkdir(parents=True, exist_ok=True)
summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"

def size(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f} GiB"

rows = [
    ("HF direct audio", summary["current"]["hf_direct_audio"], None),
    ("LiteRT WI8 audio", summary["current"]["litert_wi8_audio"], summary["current"]["litert_wi8_audio"]["model_size_gib"]),
]
lines = [
    f"# {run_name}",
    "",
    f"Best checkpoint: step {best_info['best']['step']}, validation macro F1 {best_info['best']['macro_f1']:.4f}, validation micro F1 {best_info['best']['micro_f1']:.4f}.",
    "",
    "| Artifact | Size | Parse | Micro F1 | Macro F1 | Exact | Hamming |",
    "|---|---:|---:|---:|---:|---:|---:|",
]
for name, item, model_size in rows:
    lines.append(
        f"| {name} | {size(model_size)} | {fmt(item.get('parse_rate'))} | {fmt(item.get('micro_f1'))} | "
        f"{fmt(item.get('macro_f1'))} | {fmt(item.get('exact_match'))} | {fmt(item.get('hamming_accuracy'))} |"
    )
lines.extend(
    [
        "",
        "## S3",
        "",
        f"- WI8 audio: `{s3_uri}`",
        "",
        "## Artifacts",
        "",
        f"- Best info: `{best_info_path}`",
        f"- HF metrics: `{hf_metrics_path}`",
        f"- WI8 metrics: `{wi8_metrics_path}`",
    ]
)
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
print(summary_json)
PY

notify "ep10-waudio-wi8-done" "流程完成。best step=${BEST_STEP}，val macro=${BEST_VAL_MACRO}。HF audio: parse=${HF_PARSE}, micro=${HF_MICRO}, macro=${HF_MACRO}, exact=${HF_EXACT}。WI8 audio: parse=${WI8_PARSE}, micro=${WI8_MICRO}, macro=${WI8_MACRO}, exact=${WI8_EXACT}, S3=${S3_URI}。报告=${SUMMARY_MD}。"

echo
echo "DONE"
echo "run_name: $RUN_NAME"
echo "best_checkpoint: $BEST_CHECKPOINT"
echo "merged_dir: $MERGED_DIR"
echo "hf_metrics: $HF_METRICS_PATH"
echo "wi8_metrics: $WI8_METRICS_PATH"
echo "wi8_s3: $S3_URI"
echo "summary: $SUMMARY_MD"
