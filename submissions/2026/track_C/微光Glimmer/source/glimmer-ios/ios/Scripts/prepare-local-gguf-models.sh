#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${IOS_DIR}/../.." && pwd)"

SOURCE_DIR="${REPO_DIR}/outputs/gguf_experiments/gemma4-asd-code9-waudio-step420"
MODEL_DIR="${IOS_DIR}/Model"

install_model() {
  local name="$1"
  local source="${SOURCE_DIR}/${name}"
  local target="${MODEL_DIR}/${name}"

  if [[ ! -s "${source}" ]]; then
    echo "Missing GGUF source: ${source}" >&2
    exit 1
  fi

  mkdir -p "${MODEL_DIR}"
  rm -f "${target}"
  cp -p "${source}" "${target}"
  test -s "${target}"
  test ! -L "${target}"
  echo "Installed ${target}"
}

install_model "model-Q4_K_M.gguf"
install_model "mmproj-bf16.gguf"
