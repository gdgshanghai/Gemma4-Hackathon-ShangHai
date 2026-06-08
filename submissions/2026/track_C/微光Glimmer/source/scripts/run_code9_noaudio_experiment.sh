#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="${PY:-./.venv/bin/python}"
MODEL_DIR="${MODEL_DIR:-/home/huzi/Downloads/gemma-4-E4B-it}"
DATA_ROOT="${DATA_ROOT:-data/raw/ASD-DS}"
PROMPT_LANG="${PROMPT_LANG:-zh}"
LORA_R="${LORA_R:-32}"
LORA_ALPHA="${LORA_ALPHA:-64}"
LORA_DROPOUT="${LORA_DROPOUT:-0.05}"

RUN_NAME="${RUN_NAME:-gemma4-asd-lora-r${LORA_R}-code9-${PROMPT_LANG}-examples-noaudio-v1}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/${RUN_NAME}}"
CACHE_DIR="${CACHE_DIR:-outputs/asd_ds_processor_cache_code9_examples_noaudio}"
MERGED_DIR="${MERGED_DIR:-outputs/${RUN_NAME}-merged}"
LITERT_FP_DIR="${LITERT_FP_DIR:-outputs/${RUN_NAME}-litert-fp-noaudio}"
LITERT_W4_DIR="${LITERT_W4_DIR:-outputs/${RUN_NAME}-litert-w4-noaudio}"
HF_EVAL_DIR="${HF_EVAL_DIR:-${MERGED_DIR}/generated_metrics_noaudio}"
FP_EVAL_DIR="${FP_EVAL_DIR:-${LITERT_FP_DIR}/generated_metrics_noaudio}"
W4_EVAL_DIR="${W4_EVAL_DIR:-${LITERT_W4_DIR}/generated_metrics_noaudio}"
REPORT_DIR="${REPORT_DIR:-outputs/${RUN_NAME}-reports}"

CACHE_WORKERS="${CACHE_WORKERS:-8}"
TRAIN_PHYSICAL_CUDA_DEVICES="${TRAIN_PHYSICAL_CUDA_DEVICES:-2,3}"
TRAIN_CUDA_DEVICES="${TRAIN_CUDA_DEVICES:-0,1}"
EXPORT_PHYSICAL_CUDA_DEVICES="${EXPORT_PHYSICAL_CUDA_DEVICES:-2,3}"
EXPORT_CUDA_DEVICES="${EXPORT_CUDA_DEVICES:-0,1}"
HF_EVAL_PHYSICAL_CUDA_DEVICES="${HF_EVAL_PHYSICAL_CUDA_DEVICES:-2,3}"
HF_EVAL_CUDA_DEVICES="${HF_EVAL_CUDA_DEVICES:-0,1}"
LITERT_PHYSICAL_CUDA_DEVICES="${LITERT_PHYSICAL_CUDA_DEVICES:-2,3}"

FRAME_FPS="${FRAME_FPS:-1.0}"
MAX_FRAMES="${MAX_FRAMES:-16}"
MAX_AUDIO_SECONDS="${MAX_AUDIO_SECONDS:-30}"
IMAGE_WIDTH="${IMAGE_WIDTH:-512}"

TRAIN_EPOCHS="${TRAIN_EPOCHS:-3}"
LEARNING_RATE="${LEARNING_RATE:-5e-5}"
GRAD_ACCUM_STEPS="${GRAD_ACCUM_STEPS:-8}"
EVAL_STEPS="${EVAL_STEPS:-84}"
SAVE_STEPS="${SAVE_STEPS:-84}"
SAVE_TOTAL_LIMIT="${SAVE_TOTAL_LIMIT:-3}"
PREDICTION_MAX_NEW_TOKENS="${PREDICTION_MAX_NEW_TOKENS:-16}"

EVAL_SPLIT="${EVAL_SPLIT:-test}"
EVAL_MAX_SAMPLES="${EVAL_MAX_SAMPLES:-}"
LITERT_WORKERS="${LITERT_WORKERS:-1}"
LITERT_BACKEND="${LITERT_BACKEND:-gpu}"
LITERT_VISION_BACKEND="${LITERT_VISION_BACKEND:-gpu}"
LITERT_AUDIO_BACKEND="${LITERT_AUDIO_BACKEND:-cpu}"
LITERT_MAX_OUTPUT_TOKENS="${LITERT_MAX_OUTPUT_TOKENS:-9}"

WANDB="${WANDB:-1}"
WANDB_PROJECT="${WANDB_PROJECT:-gemma4-asd-ft}"
WANDB_ENTITY="${WANDB_ENTITY:-chenghuzi}"
ENV_FILE="${ENV_FILE:-.env}"

SKIP_CACHE="${SKIP_CACHE:-0}"
SKIP_TRAIN="${SKIP_TRAIN:-0}"
SKIP_FP_EXPORT="${SKIP_FP_EXPORT:-0}"
SKIP_HF_EVAL="${SKIP_HF_EVAL:-0}"
SKIP_FP_EVAL="${SKIP_FP_EVAL:-0}"
SKIP_W4_EXPORT="${SKIP_W4_EXPORT:-0}"
SKIP_W4_EVAL="${SKIP_W4_EVAL:-0}"

run() {
  echo
  printf '+'
  printf ' %q' "$@"
  echo
  "$@"
}

maybe_max_samples_args=()
if [[ -n "$EVAL_MAX_SAMPLES" ]]; then
  maybe_max_samples_args=(--max-samples "$EVAL_MAX_SAMPLES")
fi

wandb_args=(--wandb --env-file "$ENV_FILE" --wandb-project "$WANDB_PROJECT" --wandb-entity "$WANDB_ENTITY")
if [[ "$WANDB" == "0" ]]; then
  wandb_args=(--no-wandb)
fi

mkdir -p "$REPORT_DIR"

if [[ "$SKIP_CACHE" == "1" ]]; then
  echo "Skipping cache build because SKIP_CACHE=1"
else
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
fi

if [[ "$SKIP_TRAIN" == "1" ]]; then
  echo "Skipping training because SKIP_TRAIN=1"
else
  run env CUDA_VISIBLE_DEVICES="$TRAIN_PHYSICAL_CUDA_DEVICES" "$PY" run_train.py train \
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
    --lora-r "$LORA_R" \
    --lora-alpha "$LORA_ALPHA" \
    --lora-dropout "$LORA_DROPOUT" \
    --target-modules language \
    --max-memory-per-gpu 22GiB \
    --prediction-max-new-tokens "$PREDICTION_MAX_NEW_TOKENS" \
    --generated-metrics \
    --bf16 \
    --gradient-checkpointing
fi

if [[ "$SKIP_FP_EXPORT" == "1" ]]; then
  echo "Skipping FP LiteRT export because SKIP_FP_EXPORT=1"
else
  run env CUDA_VISIBLE_DEVICES="$EXPORT_PHYSICAL_CUDA_DEVICES" "$PY" run_train.py export \
    --cuda-devices "$EXPORT_CUDA_DEVICES" \
    --model-dir "$MODEL_DIR" \
    --adapter-dir "$OUTPUT_DIR" \
    --merged-model-dir "$MERGED_DIR" \
    --litert-out-dir "$LITERT_FP_DIR" \
    --no-audio \
    --quantization-recipe none \
    --vision-encoder-quantization-recipe none \
    --inspect \
    --no-smoke-test
fi

if [[ "$SKIP_HF_EVAL" == "1" ]]; then
  echo "Skipping merged HF eval because SKIP_HF_EVAL=1"
else
  run env CUDA_VISIBLE_DEVICES="$HF_EVAL_PHYSICAL_CUDA_DEVICES" "$PY" run_train.py eval-hf \
    --cuda-devices "$HF_EVAL_CUDA_DEVICES" \
    --model-dir "$MERGED_DIR" \
    --processor-dir "$MODEL_DIR" \
    --data-root "$DATA_ROOT" \
    --output-dir "$HF_EVAL_DIR" \
    --cache-dir "$CACHE_DIR" \
    --cache-mode require \
    --split "$EVAL_SPLIT" \
    --prompt-lang "$PROMPT_LANG" \
    "${maybe_max_samples_args[@]}" \
    --frame-fps "$FRAME_FPS" \
    --max-frames "$MAX_FRAMES" \
    --max-audio-seconds "$MAX_AUDIO_SECONDS" \
    --image-width "$IMAGE_WIDTH" \
    --no-audio \
    --prediction-max-new-tokens "$PREDICTION_MAX_NEW_TOKENS" \
    --max-memory-per-gpu 22GiB \
    --bf16
fi

if [[ "$SKIP_FP_EVAL" == "1" ]]; then
  echo "Skipping FP LiteRT eval because SKIP_FP_EVAL=1"
else
  run env CUDA_VISIBLE_DEVICES="$LITERT_PHYSICAL_CUDA_DEVICES" "$PY" eval_litert_lm.py \
    --litertlm-file "$LITERT_FP_DIR/model.litertlm" \
    --data-root "$DATA_ROOT" \
    --model-dir "$MODEL_DIR" \
    --split "$EVAL_SPLIT" \
    --prompt-lang "$PROMPT_LANG" \
    --output-dir "$FP_EVAL_DIR" \
    --media-cache-dir "$LITERT_FP_DIR/media_cache_noaudio" \
    --frame-fps "$FRAME_FPS" \
    --max-frames "$MAX_FRAMES" \
    --max-audio-seconds "$MAX_AUDIO_SECONDS" \
    --image-width "$IMAGE_WIDTH" \
    "${maybe_max_samples_args[@]}" \
    --backend "$LITERT_BACKEND" \
    --vision-backend "$LITERT_VISION_BACKEND" \
    --audio-backend "$LITERT_AUDIO_BACKEND" \
    --no-audio \
    --cache-dir "$LITERT_FP_DIR/litert_cache_noaudio" \
    --temperature 0.0 \
    --top-p 1.0 \
    --top-k 1 \
    --max-output-tokens "$LITERT_MAX_OUTPUT_TOKENS" \
    --workers "$LITERT_WORKERS"
fi

if [[ "$SKIP_W4_EXPORT" == "1" ]]; then
  echo "Skipping W4 LiteRT export because SKIP_W4_EXPORT=1"
else
  run env CUDA_VISIBLE_DEVICES="$EXPORT_PHYSICAL_CUDA_DEVICES" "$PY" run_train.py export \
    --cuda-devices "$EXPORT_CUDA_DEVICES" \
    --model-dir "$MODEL_DIR" \
    --adapter-dir "$OUTPUT_DIR" \
    --merged-model-dir "$MERGED_DIR" \
    --litert-out-dir "$LITERT_W4_DIR" \
    --no-audio \
    --quantization-recipe dynamic_wi4_afp32 \
    --vision-encoder-quantization-recipe dynamic_wi8_afp32 \
    --inspect \
    --no-smoke-test
fi

if [[ "$SKIP_W4_EVAL" == "1" ]]; then
  echo "Skipping W4 LiteRT eval because SKIP_W4_EVAL=1"
else
  run env CUDA_VISIBLE_DEVICES="$LITERT_PHYSICAL_CUDA_DEVICES" "$PY" eval_litert_lm.py \
    --litertlm-file "$LITERT_W4_DIR/model.litertlm" \
    --data-root "$DATA_ROOT" \
    --model-dir "$MODEL_DIR" \
    --split "$EVAL_SPLIT" \
    --prompt-lang "$PROMPT_LANG" \
    --output-dir "$W4_EVAL_DIR" \
    --media-cache-dir "$LITERT_W4_DIR/media_cache_noaudio" \
    --frame-fps "$FRAME_FPS" \
    --max-frames "$MAX_FRAMES" \
    --max-audio-seconds "$MAX_AUDIO_SECONDS" \
    --image-width "$IMAGE_WIDTH" \
    "${maybe_max_samples_args[@]}" \
    --backend "$LITERT_BACKEND" \
    --vision-backend "$LITERT_VISION_BACKEND" \
    --audio-backend "$LITERT_AUDIO_BACKEND" \
    --no-audio \
    --cache-dir "$LITERT_W4_DIR/litert_cache_noaudio" \
    --temperature 0.0 \
    --top-p 1.0 \
    --top-k 1 \
    --max-output-tokens "$LITERT_MAX_OUTPUT_TOKENS" \
    --workers "$LITERT_WORKERS"
fi

run "$PY" - "$REPORT_DIR" "$OUTPUT_DIR/generated_metrics" "$HF_EVAL_DIR" "$FP_EVAL_DIR" "$W4_EVAL_DIR" <<'PY'
import glob
import json
import sys
from pathlib import Path

report_dir = Path(sys.argv[1])
cases = [
    ("train_validation_final", Path(sys.argv[2]), "validation_final*_metrics.json"),
    ("train_test_final", Path(sys.argv[2]), "test_final*_metrics.json"),
    ("merged_hf", Path(sys.argv[3]), "*_metrics.json"),
    ("litert_fp_noaudio", Path(sys.argv[4]), "*_metrics.json"),
    ("litert_w4_noaudio", Path(sys.argv[5]), "*_metrics.json"),
]

def latest(path: Path, pattern: str) -> Path | None:
    matches = [Path(item) for item in glob.glob(str(path / pattern))]
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)

rows = []
for name, path, pattern in cases:
    metrics_path = latest(path, pattern)
    if metrics_path is None:
        rows.append({"name": name, "status": "missing", "path": str(path / pattern)})
        continue
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    rows.append(
        {
            "name": name,
            "status": "ok",
            "path": str(metrics_path),
            "num_samples": metrics.get("num_samples"),
            "parse_rate": metrics.get("parse_rate"),
            "micro_f1": metrics.get("micro", {}).get("f1"),
            "macro_f1": metrics.get("macro", {}).get("f1"),
            "exact_match": metrics.get("exact_match"),
            "hamming_accuracy": metrics.get("hamming_accuracy"),
            "per_label_f1": {
                key: value.get("f1")
                for key, value in metrics.get("per_label", {}).items()
            },
        }
    )

report_dir.mkdir(parents=True, exist_ok=True)
(report_dir / "performance_summary.json").write_text(
    json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

headers = ["model", "samples", "parse", "micro_f1", "macro_f1", "exact", "hamming", "metrics"]
lines = [
    "# Code9 No-Audio Experiment Performance",
    "",
    "| " + " | ".join(headers) + " |",
    "| " + " | ".join(["---"] * len(headers)) + " |",
]
for row in rows:
    if row["status"] != "ok":
        lines.append(f"| {row['name']} | missing | | | | | | `{row['path']}` |")
        continue
    lines.append(
        "| {name} | {num_samples} | {parse_rate:.4f} | {micro_f1:.4f} | "
        "{macro_f1:.4f} | {exact_match:.4f} | {hamming_accuracy:.4f} | `{path}` |".format(**row)
    )
(report_dir / "performance_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"\nWrote {report_dir / 'performance_summary.json'}")
print(f"Wrote {report_dir / 'performance_summary.md'}")
PY

echo
echo "DONE"
echo "output_dir: $OUTPUT_DIR"
echo "merged_dir: $MERGED_DIR"
echo "litert_fp: $LITERT_FP_DIR/model.litertlm"
echo "litert_w4: $LITERT_W4_DIR/model.litertlm"
echo "report: $REPORT_DIR/performance_summary.md"
