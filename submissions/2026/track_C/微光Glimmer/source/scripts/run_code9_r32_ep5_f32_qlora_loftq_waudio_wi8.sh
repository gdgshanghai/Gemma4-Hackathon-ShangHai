#!/usr/bin/env bash
set -euo pipefail

export RUN_NAME="${RUN_NAME:-gemma4-asd-lora-r32-code9-zh-examples-waudio-f32-ep5-qlora-loftq-v1}"
export CACHE_DIR="${CACHE_DIR:-outputs/asd_ds_processor_cache_code9_examples_audio_f32}"
export TRAIN_EPOCHS="${TRAIN_EPOCHS:-5}"
export MAX_FRAMES="${MAX_FRAMES:-32}"
export LITERT_CACHE_LENGTH="${LITERT_CACHE_LENGTH:-8192}"
export S3_URI="${S3_URI:-s3://huzi-nydata/asd-gemma4-code9-qlora-loftq-ep5-f32-wi8-waudio.litertlm}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/run_code9_r32_ep10_qlora_loftq_waudio_wi8.sh"
