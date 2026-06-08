#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY="${PY:-./.venv/bin/python}"
MODEL_DIR="${MODEL_DIR:-/home/huzi/Downloads/gemma-4-E4B-it}"
DATA_ROOT="${DATA_ROOT:-data/raw/ASD-DS}"
PROMPT_LANG="${PROMPT_LANG:-zh}"

RUN_NAME="${RUN_NAME:-gemma4-asd-lora-r32-code9-zh-examples-waudio-f32-ep5-qlora-loftq-v1}"
BEST_STEP="${BEST_STEP:-420}"
ADAPTER_DIR="${ADAPTER_DIR:-outputs/${RUN_NAME}/checkpoint-${BEST_STEP}}"
MERGED_DIR="${MERGED_DIR:-outputs/${RUN_NAME}-best-step${BEST_STEP}-merged}"
LITERT_OUT_DIR="${LITERT_OUT_DIR:-outputs/${RUN_NAME}-best-step${BEST_STEP}-litert-wi4text-wi8vision-waudio}"
REPORT_DIR="${REPORT_DIR:-outputs/${RUN_NAME}-reports}"

CACHE_DIR="${CACHE_DIR:-outputs/asd_ds_processor_cache_code9_examples_audio_f32}"
OFFICIAL_LITERTLM_FILE="${OFFICIAL_LITERTLM_FILE:-outputs/gemma4-official-litert/gemma-4-E4B-it.litertlm}"

CUDA_DEVICES="${CUDA_DEVICES:-2,3}"
FRAME_FPS="${FRAME_FPS:-1.0}"
MAX_FRAMES="${MAX_FRAMES:-32}"
MAX_AUDIO_SECONDS="${MAX_AUDIO_SECONDS:-30}"
IMAGE_WIDTH="${IMAGE_WIDTH:-512}"
LITERT_CACHE_LENGTH="${LITERT_CACHE_LENGTH:-8192}"
LITERT_BACKEND="${LITERT_BACKEND:-gpu}"
LITERT_VISION_BACKEND="${LITERT_VISION_BACKEND:-gpu}"
LITERT_AUDIO_BACKEND="${LITERT_AUDIO_BACKEND:-cpu}"
LITERT_WORKERS="${LITERT_WORKERS:-2}"
LITERT_MAX_OUTPUT_TOKENS="${LITERT_MAX_OUTPUT_TOKENS:-9}"

TEXT_QUANTIZATION_RECIPE="${TEXT_QUANTIZATION_RECIPE:-dynamic_wi4_afp32}"
VISION_QUANTIZATION_RECIPE="${VISION_QUANTIZATION_RECIPE:-dynamic_wi8_afp32}"

HF_BASELINE_METRICS="${HF_BASELINE_METRICS:-${REPORT_DIR}/hf_audio_eval/test_hf_step_000000_epoch_none_metrics.json}"
WI8_BASELINE_METRICS="${WI8_BASELINE_METRICS:-outputs/${RUN_NAME}-best-step${BEST_STEP}-litert-wi8-waudio/generated_metrics_audio/test_litert_audio_zh_metrics.json}"
EVAL_DIR="${EVAL_DIR:-${LITERT_OUT_DIR}/generated_metrics_audio}"
MEDIA_CACHE_DIR="${MEDIA_CACHE_DIR:-${LITERT_OUT_DIR}/media_cache_audio}"
LITERT_RUNTIME_CACHE_DIR="${LITERT_RUNTIME_CACHE_DIR:-${LITERT_OUT_DIR}/litert_cache_audio}"

BARK_URL="${BARK_URL:-}"
BARK_GROUP="${BARK_GROUP:-hz_res_ft}"
LOG_PATH="${LOG_PATH:-}"
OVERWRITE="${OVERWRITE:-1}"
S3_URI="${S3_URI:-}"
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
  notify "textWI4-visionWI8-audio失败" "阶段=${STAGE}，退出码=${code}。run=${RUN_NAME}。日志=${LOG_PATH:-未设置}。输出=${LITERT_OUT_DIR}。"
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

for required in "$ADAPTER_DIR" "$MERGED_DIR" "$OFFICIAL_LITERTLM_FILE"; do
  if [[ ! -e "$required" ]]; then
    echo "Required path does not exist: $required" >&2
    exit 1
  fi
done

if [[ "$OVERWRITE" == "1" && -d "$LITERT_OUT_DIR" ]]; then
  rm -rf "$LITERT_OUT_DIR"
fi

notify "textWI4-visionWI8-audio开始" "开始混合 LiteRT-LM 导出：text=${TEXT_QUANTIZATION_RECIPE}，vision=${VISION_QUANTIZATION_RECIPE}，audio=official graft。checkpoint=${ADAPTER_DIR}，输出=${LITERT_OUT_DIR}。"

STAGE="export"
run env CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" run_train.py export \
  --cuda-devices "$CUDA_DEVICES" \
  --model-dir "$MODEL_DIR" \
  --adapter-dir "$ADAPTER_DIR" \
  --merged-model-dir "$MERGED_DIR" \
  --litert-out-dir "$LITERT_OUT_DIR" \
  --official-litertlm-file "$OFFICIAL_LITERTLM_FILE" \
  --max-memory-per-gpu 22GiB \
  --bf16 \
  --inspect \
  --no-smoke-test \
  --audio \
  --cache-length "$LITERT_CACHE_LENGTH" \
  --quantization-recipe "$TEXT_QUANTIZATION_RECIPE" \
  --vision-encoder-quantization-recipe "$VISION_QUANTIZATION_RECIPE"

MODEL_FILE="${LITERT_OUT_DIR}/model.litertlm"
if [[ ! -f "$MODEL_FILE" ]]; then
  echo "Expected model file missing: $MODEL_FILE" >&2
  exit 1
fi
MODEL_SIZE="$(du -h "$MODEL_FILE" | awk '{print $1}')"
notify "textWI4-visionWI8-audio导出完成" "导出完成：${MODEL_FILE}，大小=${MODEL_SIZE}。开始 test eval，samples=182，workers=${LITERT_WORKERS}。"

STAGE="eval"
run env CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" -u eval_litert_lm.py \
  --litertlm-file "$MODEL_FILE" \
  --data-root "$DATA_ROOT" \
  --model-dir "$MODEL_DIR" \
  --split test \
  --prompt-lang "$PROMPT_LANG" \
  --output-dir "$EVAL_DIR" \
  --media-cache-dir "$MEDIA_CACHE_DIR" \
  --frame-fps "$FRAME_FPS" \
  --max-frames "$MAX_FRAMES" \
  --max-audio-seconds "$MAX_AUDIO_SECONDS" \
  --image-width "$IMAGE_WIDTH" \
  --backend "$LITERT_BACKEND" \
  --vision-backend "$LITERT_VISION_BACKEND" \
  --audio-backend "$LITERT_AUDIO_BACKEND" \
  --audio \
  --cache-dir "$LITERT_RUNTIME_CACHE_DIR" \
  --temperature 0.0 \
  --top-p 1.0 \
  --top-k 1 \
  --max-output-tokens "$LITERT_MAX_OUTPUT_TOKENS" \
  --workers "$LITERT_WORKERS" \
  --reuse-media-cache

METRICS_PATH="$(latest_metrics "$EVAL_DIR")"
PARSE="$(metric_value "$METRICS_PATH" parse_rate)"
MICRO="$(metric_value "$METRICS_PATH" micro_f1)"
MACRO="$(metric_value "$METRICS_PATH" macro_f1)"
EXACT="$(metric_value "$METRICS_PATH" exact_match)"
HAMMING="$(metric_value "$METRICS_PATH" hamming_accuracy)"

STAGE="summary"
SUMMARY_JSON="${REPORT_DIR}/textwi4_visionwi8_audio_summary.json"
SUMMARY_MD="${REPORT_DIR}/textwi4_visionwi8_audio_summary.md"
run "$PY" - "$SUMMARY_JSON" "$SUMMARY_MD" "$RUN_NAME" "$MODEL_FILE" "$METRICS_PATH" "$HF_BASELINE_METRICS" "$WI8_BASELINE_METRICS" "$TEXT_QUANTIZATION_RECIPE" "$VISION_QUANTIZATION_RECIPE" "$LITERT_CACHE_LENGTH" <<'PY'
import json
import os
import sys
from pathlib import Path

summary_json = Path(sys.argv[1])
summary_md = Path(sys.argv[2])
run_name = sys.argv[3]
model_file = Path(sys.argv[4])
mixed_metrics_path = Path(sys.argv[5])
hf_metrics_path = Path(sys.argv[6])
wi8_metrics_path = Path(sys.argv[7])
text_recipe = sys.argv[8]
vision_recipe = sys.argv[9]
cache_length = int(sys.argv[10])

def load_if_exists(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def compact(path: Path) -> dict | None:
    data = load_if_exists(path)
    if data is None:
        return None
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

summary = {
    "run_name": run_name,
    "export": {
        "text_quantization_recipe": text_recipe,
        "vision_encoder_quantization_recipe": vision_recipe,
        "audio_source": "official Gemma 4 E4B LiteRT-LM graft",
        "cache_length": cache_length,
        "model_file": str(model_file),
        "model_size_gib": gib(model_file),
    },
    "metrics": {
        "hf_direct_audio_baseline": compact(hf_metrics_path),
        "litert_wi8_audio_baseline": compact(wi8_metrics_path),
        "litert_textwi4_visionwi8_audio": compact(mixed_metrics_path),
    },
}
summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def fmt(value):
    return "n/a" if value is None else f"{float(value):.4f}"

def size(value):
    return "n/a" if value is None else f"{float(value):.2f} GiB"

rows = [
    ("HF direct audio", summary["metrics"]["hf_direct_audio_baseline"], None),
    ("LiteRT WI8 audio", summary["metrics"]["litert_wi8_audio_baseline"], None),
    (
        "LiteRT text WI4 + vision WI8 + audio graft",
        summary["metrics"]["litert_textwi4_visionwi8_audio"],
        summary["export"]["model_size_gib"],
    ),
]
lines = [
    f"# {run_name}: Text WI4 + Vision WI8 + Audio",
    "",
    f"- Text quantization: `{text_recipe}`",
    f"- Vision quantization: `{vision_recipe}`",
    "- Audio: official Gemma 4 E4B LiteRT-LM sections grafted into the package",
    f"- Cache length: `{cache_length}`",
    f"- Model file: `{model_file}`",
    "",
    "| Artifact | Size | Parse | Micro F1 | Macro F1 | Exact | Hamming |",
    "|---|---:|---:|---:|---:|---:|---:|",
]
for name, item, model_size in rows:
    if item is None:
        continue
    lines.append(
        f"| {name} | {size(model_size)} | {fmt(item.get('parse_rate'))} | "
        f"{fmt(item.get('micro_f1'))} | {fmt(item.get('macro_f1'))} | "
        f"{fmt(item.get('exact_match'))} | {fmt(item.get('hamming_accuracy'))} |"
    )
lines.extend(
    [
        "",
        "## Metrics Files",
        "",
        f"- Mixed LiteRT: `{mixed_metrics_path}`",
        f"- HF baseline: `{hf_metrics_path}`",
        f"- WI8 baseline: `{wi8_metrics_path}`",
    ]
)
summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(summary_md)
print(summary_json)
PY

if [[ -n "$S3_URI" ]]; then
  STAGE="upload"
  notify "textWI4-visionWI8-audio上传开始" "开始上传到 S3：${S3_URI}。"
  run aws s3 cp "$MODEL_FILE" "$S3_URI" --only-show-errors
  S3_LS="$(aws s3 ls "$S3_URI")"
  notify "textWI4-visionWI8-audio上传完成" "上传完成：${S3_URI}。S3=${S3_LS}。"
fi

notify "textWI4-visionWI8-audio完成" "混合 LiteRT eval 完成。大小=${MODEL_SIZE}，parse=${PARSE}，micro F1=${MICRO}，macro F1=${MACRO}，exact=${EXACT}，hamming=${HAMMING}。报告=${SUMMARY_MD}。"

echo
echo "DONE"
echo "model: $MODEL_FILE"
echo "metrics: $METRICS_PATH"
echo "summary: $SUMMARY_MD"
