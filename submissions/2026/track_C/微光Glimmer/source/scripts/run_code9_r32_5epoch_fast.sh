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
RUN_NAME="${RUN_NAME:-gemma4-asd-lora-r${LORA_R}-code9-${PROMPT_LANG}-examples-noaudio-ep5-v1}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/${RUN_NAME}}"
CACHE_DIR="${CACHE_DIR:-outputs/asd_ds_processor_cache_code9_examples_noaudio}"
REPORT_DIR="${REPORT_DIR:-outputs/${RUN_NAME}-reports}"
BEST_METRIC="${BEST_METRIC:-macro_f1}"

TRAIN_PHYSICAL_CUDA_DEVICES="${TRAIN_PHYSICAL_CUDA_DEVICES:-2,3}"
TRAIN_CUDA_DEVICES="${TRAIN_CUDA_DEVICES:-0,1}"
MERGE_PHYSICAL_CUDA_DEVICES="${MERGE_PHYSICAL_CUDA_DEVICES:-2,3}"
MERGE_CUDA_DEVICES="${MERGE_CUDA_DEVICES:-0,1}"
HF_EVAL_PHYSICAL_CUDA_DEVICES="${HF_EVAL_PHYSICAL_CUDA_DEVICES:-2,3}"
HF_EVAL_CUDA_DEVICES="${HF_EVAL_CUDA_DEVICES:-0,1}"
LITERT_PHYSICAL_CUDA_DEVICES="${LITERT_PHYSICAL_CUDA_DEVICES:-2,3}"
EXPORT_PHYSICAL_CUDA_DEVICES="${EXPORT_PHYSICAL_CUDA_DEVICES:-2,3}"
EXPORT_CUDA_DEVICES="${EXPORT_CUDA_DEVICES:-0,1}"

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

SKIP_CACHE="${SKIP_CACHE:-1}"
CACHE_WORKERS="${CACHE_WORKERS:-8}"

BASELINE_R32_HF_METRICS="${BASELINE_R32_HF_METRICS:-outputs/gemma4-asd-lora-r32-code9-zh-examples-noaudio-v1-merged/generated_metrics_noaudio/test_hf_step_000000_epoch_none_metrics.json}"
RUN_LITERT_SMOKE="${RUN_LITERT_SMOKE:-auto}"
LITERT_MAX_SAMPLES="${LITERT_MAX_SAMPLES:-50}"
LITERT_FP_DIR="${LITERT_FP_DIR:-outputs/${RUN_NAME}-best-litert-fp-noaudio}"
LITERT_FP_EVAL_DIR="${LITERT_FP_EVAL_DIR:-${LITERT_FP_DIR}/generated_metrics_noaudio}"
LITERT_BACKEND="${LITERT_BACKEND:-gpu}"
LITERT_VISION_BACKEND="${LITERT_VISION_BACKEND:-gpu}"
LITERT_AUDIO_BACKEND="${LITERT_AUDIO_BACKEND:-cpu}"
LITERT_MAX_OUTPUT_TOKENS="${LITERT_MAX_OUTPUT_TOKENS:-9}"

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
  notify "r32 5epoch 实验失败" "阶段=${STAGE}，退出码=${code}。run=${RUN_NAME}。日志=${LOG_PATH:-未设置}。"
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
    value = data.get("micro", {}).get("f1")
elif key == "macro_f1":
    value = data.get("macro", {}).get("f1")
else:
    value = data.get(key)
print("" if value is None else value)
PY
}

wandb_args=(--wandb --env-file "$ENV_FILE" --wandb-project "$WANDB_PROJECT" --wandb-entity "$WANDB_ENTITY")
if [[ "$WANDB" == "0" ]]; then
  wandb_args=(--no-wandb)
fi

mkdir -p "$REPORT_DIR"

notify "r32 5epoch 实验开始" "开始 r32/no-audio/code9/中文 prompt/5 epoch。GPU=${TRAIN_PHYSICAL_CUDA_DEVICES}，run=${RUN_NAME}。本轮只先跑 train + best checkpoint merged HF full test；LiteRT 只有 HF 明显优于 r32/3epoch baseline 才跑小样本。日志=${LOG_PATH:-未设置}。"

if [[ "$SKIP_CACHE" == "1" ]]; then
  STAGE="cache-skip"
  echo "Skipping cache build because SKIP_CACHE=1"
  notify "r32 5epoch cache 跳过" "复用已有 no-audio processor cache: ${CACHE_DIR}。"
else
  STAGE="cache-build"
  notify "r32 5epoch cache 开始" "开始 build-cache，workers=${CACHE_WORKERS}，cache=${CACHE_DIR}。"
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
  notify "r32 5epoch cache 完成" "cache build 完成: ${CACHE_DIR}。"
fi

STAGE="train"
notify "r32 5epoch training 开始" "开始训练：rank=${LORA_R}, alpha=${LORA_ALPHA}, epochs=${TRAIN_EPOCHS}, eval/save every ${EVAL_STEPS} steps, save_total_limit=${SAVE_TOTAL_LIMIT}。"
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
BEST_VAL_MICRO="$("$PY" - "$BEST_INFO_JSON" <<'PY'
import json, sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["best"]["micro_f1"])
PY
)"
BEST_VAL_MACRO="$("$PY" - "$BEST_INFO_JSON" <<'PY'
import json, sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["best"]["macro_f1"])
PY
)"
BEST_VAL_EXACT="$("$PY" - "$BEST_INFO_JSON" <<'PY'
import json, sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["best"]["exact_match"])
PY
)"
notify "r32 5epoch best checkpoint" "按 ${BEST_METRIC} 选择 best checkpoint：step=${BEST_STEP}，validation micro=${BEST_VAL_MICRO}，macro=${BEST_VAL_MACRO}，exact=${BEST_VAL_EXACT}。checkpoint=${BEST_CHECKPOINT}。"

MERGED_DIR="${MERGED_DIR:-outputs/${RUN_NAME}-best-step${BEST_STEP}-merged}"
HF_EVAL_DIR="${HF_EVAL_DIR:-${MERGED_DIR}/generated_metrics_noaudio}"

STAGE="merge-best"
notify "r32 5epoch merge 开始" "开始 merge best checkpoint step=${BEST_STEP}。输出=${MERGED_DIR}。"
run env CUDA_VISIBLE_DEVICES="$MERGE_PHYSICAL_CUDA_DEVICES" "$PY" run_train.py merge \
  --cuda-devices "$MERGE_CUDA_DEVICES" \
  --model-dir "$MODEL_DIR" \
  --adapter-dir "$BEST_CHECKPOINT" \
  --merged-model-dir "$MERGED_DIR" \
  --max-memory-per-gpu 22GiB \
  --bf16
notify "r32 5epoch merge 完成" "best checkpoint step=${BEST_STEP} 已 merge 到 ${MERGED_DIR}。"

STAGE="merged-hf-test"
notify "r32 5epoch HF test 开始" "开始对 best merged HF 跑完整 test eval，samples=182。"
run env CUDA_VISIBLE_DEVICES="$HF_EVAL_PHYSICAL_CUDA_DEVICES" "$PY" run_train.py eval-hf \
  --cuda-devices "$HF_EVAL_CUDA_DEVICES" \
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
  --no-audio \
  --prediction-max-new-tokens "$PREDICTION_MAX_NEW_TOKENS" \
  --max-memory-per-gpu 22GiB \
  --bf16

HF_METRICS_PATH="$(ls -t "$HF_EVAL_DIR"/*_metrics.json | head -n 1)"
HF_PARSE="$(metric_value "$HF_METRICS_PATH" parse_rate)"
HF_MICRO="$(metric_value "$HF_METRICS_PATH" micro_f1)"
HF_MACRO="$(metric_value "$HF_METRICS_PATH" macro_f1)"
HF_EXACT="$(metric_value "$HF_METRICS_PATH" exact_match)"
notify "r32 5epoch HF test 完成" "best-step${BEST_STEP} merged HF test：parse=${HF_PARSE}，micro=${HF_MICRO}，macro=${HF_MACRO}，exact=${HF_EXACT}。metrics=${HF_METRICS_PATH}。"

STAGE="liteRT-decision"
RUN_LITERT_DECISION="$("$PY" - "$HF_METRICS_PATH" "$BASELINE_R32_HF_METRICS" "$RUN_LITERT_SMOKE" <<'PY'
import json
import sys
from pathlib import Path

hf_path = Path(sys.argv[1])
baseline_path = Path(sys.argv[2])
mode = sys.argv[3]
if mode in {"0", "false", "False", "no"}:
    print("0")
    raise SystemExit
if mode in {"1", "true", "True", "yes"}:
    print("1")
    raise SystemExit
if not baseline_path.is_file():
    print("0")
    raise SystemExit
current = json.loads(hf_path.read_text(encoding="utf-8"))
baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
current_micro = float(current["micro"]["f1"])
current_macro = float(current["macro"]["f1"])
baseline_micro = float(baseline["micro"]["f1"])
baseline_macro = float(baseline["macro"]["f1"])
print("1" if current_micro > baseline_micro and current_macro > baseline_macro else "0")
PY
)"

if [[ "$RUN_LITERT_DECISION" == "1" ]]; then
  STAGE="litert-fp-export-small"
  notify "r32 5epoch LiteRT 小样本开始" "HF best 超过 baseline，开始 FP LiteRT export + ${LITERT_MAX_SAMPLES} 样本 smoke eval。"
  run env CUDA_VISIBLE_DEVICES="$EXPORT_PHYSICAL_CUDA_DEVICES" "$PY" run_train.py export \
    --cuda-devices "$EXPORT_CUDA_DEVICES" \
    --model-dir "$MODEL_DIR" \
    --adapter-dir "$BEST_CHECKPOINT" \
    --merged-model-dir "$MERGED_DIR" \
    --litert-out-dir "$LITERT_FP_DIR" \
    --no-audio \
    --quantization-recipe none \
    --vision-encoder-quantization-recipe none \
    --inspect \
    --no-smoke-test

  STAGE="litert-fp-eval-small"
  run env CUDA_VISIBLE_DEVICES="$LITERT_PHYSICAL_CUDA_DEVICES" "$PY" eval_litert_lm.py \
    --litertlm-file "$LITERT_FP_DIR/model.litertlm" \
    --data-root "$DATA_ROOT" \
    --model-dir "$MODEL_DIR" \
    --split test \
    --prompt-lang "$PROMPT_LANG" \
    --output-dir "$LITERT_FP_EVAL_DIR" \
    --media-cache-dir "$LITERT_FP_DIR/media_cache_noaudio" \
    --frame-fps "$FRAME_FPS" \
    --max-frames "$MAX_FRAMES" \
    --max-audio-seconds "$MAX_AUDIO_SECONDS" \
    --image-width "$IMAGE_WIDTH" \
    --max-samples "$LITERT_MAX_SAMPLES" \
    --backend "$LITERT_BACKEND" \
    --vision-backend "$LITERT_VISION_BACKEND" \
    --audio-backend "$LITERT_AUDIO_BACKEND" \
    --no-audio \
    --cache-dir "$LITERT_FP_DIR/litert_cache_noaudio" \
    --temperature 0.0 \
    --top-p 1.0 \
    --top-k 1 \
    --max-output-tokens "$LITERT_MAX_OUTPUT_TOKENS" \
    --workers 1
  LITERT_METRICS_PATH="$(ls -t "$LITERT_FP_EVAL_DIR"/*_metrics.json | head -n 1)"
  LITERT_PARSE="$(metric_value "$LITERT_METRICS_PATH" parse_rate)"
  LITERT_MICRO="$(metric_value "$LITERT_METRICS_PATH" micro_f1)"
  LITERT_MACRO="$(metric_value "$LITERT_METRICS_PATH" macro_f1)"
  notify "r32 5epoch LiteRT 小样本完成" "FP LiteRT ${LITERT_MAX_SAMPLES} samples：parse=${LITERT_PARSE}，micro=${LITERT_MICRO}，macro=${LITERT_MACRO}。metrics=${LITERT_METRICS_PATH}。"
else
  notify "r32 5epoch LiteRT 已跳过" "best merged HF 没有同时超过 r32/3epoch baseline，所以跳过 LiteRT export/eval，避免继续浪费时间。当前 HF micro=${HF_MICRO}，macro=${HF_MACRO}。"
fi

STAGE="summary"
SUMMARY_JSON="${REPORT_DIR}/performance_summary.json"
SUMMARY_MD="${REPORT_DIR}/performance_summary.md"
run "$PY" - "$OUTPUT_DIR" "$BEST_INFO_JSON" "$HF_METRICS_PATH" "$BASELINE_R32_HF_METRICS" "$SUMMARY_JSON" "$SUMMARY_MD" <<'PY'
import glob
import json
import sys
from pathlib import Path

output_dir = Path(sys.argv[1])
best_info_path = Path(sys.argv[2])
hf_metrics_path = Path(sys.argv[3])
baseline_path = Path(sys.argv[4])
summary_json_path = Path(sys.argv[5])
summary_md_path = Path(sys.argv[6])

best_info = json.loads(best_info_path.read_text(encoding="utf-8"))
hf_metrics = json.loads(hf_metrics_path.read_text(encoding="utf-8"))
baseline_metrics = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.is_file() else None

def compact_metrics(data: dict) -> dict:
    return {
        "samples": data.get("num_samples"),
        "parse": data.get("parse_rate"),
        "micro_f1": data.get("micro", {}).get("f1"),
        "macro_f1": data.get("macro", {}).get("f1"),
        "exact": data.get("exact_match"),
        "hamming": data.get("hamming_accuracy"),
    }

validation_rows = []
for path in sorted(glob.glob(str(output_dir / "generated_metrics" / "validation_step_*_metrics.json"))):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validation_rows.append({"path": path, **compact_metrics(data), "step": data.get("step"), "epoch": data.get("epoch")})

final_test_paths = sorted(glob.glob(str(output_dir / "generated_metrics" / "test_final*_metrics.json")))
final_test = None
if final_test_paths:
    final_test = {"path": final_test_paths[-1], **compact_metrics(json.loads(Path(final_test_paths[-1]).read_text(encoding="utf-8")))}

summary = {
    "best": best_info["best"],
    "validation": validation_rows,
    "train_final_test": final_test,
    "best_merged_hf_test": {"path": str(hf_metrics_path), **compact_metrics(hf_metrics)},
    "baseline_r32_3epoch_merged_hf": (
        {"path": str(baseline_path), **compact_metrics(baseline_metrics)}
        if baseline_metrics is not None
        else None
    ),
}
summary_json_path.parent.mkdir(parents=True, exist_ok=True)
summary_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

lines = ["# r32 Code9 No-Audio 5 Epoch Fast Experiment", ""]
lines.append(f"Best checkpoint: step {summary['best']['step']} by {summary['best']['metric']}={summary['best']['metric_value']:.4f}")
lines.append("")
lines.append("| eval | step | epoch | parse | micro_f1 | macro_f1 | exact |")
lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for row in validation_rows:
    lines.append(
        f"| validation | {row['step']} | {row['epoch']} | {row['parse']:.4f} | {row['micro_f1']:.4f} | {row['macro_f1']:.4f} | {row['exact']:.4f} |"
    )
if final_test is not None:
    lines.append(
        f"| train final test |  |  | {final_test['parse']:.4f} | {final_test['micro_f1']:.4f} | {final_test['macro_f1']:.4f} | {final_test['exact']:.4f} |"
    )
best_hf = summary["best_merged_hf_test"]
lines.append(
    f"| best merged HF test | {summary['best']['step']} |  | {best_hf['parse']:.4f} | {best_hf['micro_f1']:.4f} | {best_hf['macro_f1']:.4f} | {best_hf['exact']:.4f} |"
)
baseline = summary["baseline_r32_3epoch_merged_hf"]
if baseline is not None:
    lines.append(
        f"| r32 3epoch baseline HF |  |  | {baseline['parse']:.4f} | {baseline['micro_f1']:.4f} | {baseline['macro_f1']:.4f} | {baseline['exact']:.4f} |"
    )
lines.append("")
lines.append(f"Best checkpoint metrics: `{summary['best']['metrics_path']}`")
lines.append(f"Best merged HF metrics: `{hf_metrics_path}`")
summary_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
PY

notify "r32 5epoch 实验完成" "完成。best step=${BEST_STEP}，validation micro=${BEST_VAL_MICRO}，macro=${BEST_VAL_MACRO}；best merged HF test parse=${HF_PARSE}，micro=${HF_MICRO}，macro=${HF_MACRO}，exact=${HF_EXACT}。报告=${SUMMARY_MD}。"

echo
echo "DONE"
echo "output_dir: $OUTPUT_DIR"
echo "best_checkpoint: $BEST_CHECKPOINT"
echo "merged_dir: $MERGED_DIR"
echo "hf_metrics: $HF_METRICS_PATH"
echo "report: $SUMMARY_MD"
