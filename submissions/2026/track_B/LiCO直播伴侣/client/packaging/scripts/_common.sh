#!/usr/bin/env bash
# Shared helpers for macOS/Linux packaging scripts.
set -euo pipefail

BLIVECHAT_INSTALL_LOG_ROOT="${HOME}/Library/Application Support/blivechat"
BLIVECHAT_INSTALL_LOG_FILE="${BLIVECHAT_INSTALL_LOG_ROOT}/install.log"

init_install_log() {
  mkdir -p "${BLIVECHAT_INSTALL_LOG_ROOT}"
  cat > "${BLIVECHAT_INSTALL_LOG_FILE}" <<EOF
================================================================================
blivechat install log
Started: $(date '+%Y-%m-%d %H:%M:%S')
Host: $(hostname)
User: $(whoami)
Platform: $(uname -s) $(uname -m)
================================================================================
EOF
}

log_install() {
  local level="${1:-INFO}"
  shift || true
  local msg="$*"
  local line="[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] ${msg}"
  echo "${line}" >> "${BLIVECHAT_INSTALL_LOG_FILE}"
  case "${level}" in
    ERROR) echo "${line}" >&2 ;;
    WARN) echo "${line}" ;;
    *) echo "${line}" ;;
  esac
}

project_root_from() {
  local dir
  dir="$(cd "$1" && pwd)"
  for _ in $(seq 1 8); do
    if [[ -f "${dir}/main.py" ]] || [[ -f "${dir}/obs-plugintemplate/CMakePresets.json" ]]; then
      echo "${dir}"
      return 0
    fi
    local parent
    parent="$(dirname "${dir}")"
    if [[ "${parent}" == "${dir}" ]]; then
      break
    fi
    dir="${parent}"
  done
  echo "Cannot locate project root from $1" >&2
  return 1
}

find_bundled_plugins_dir() {
  local app_dir="$1"
  local candidates=(
    "${app_dir}/_internal/plugins"
    "${app_dir}/Contents/MacOS/_internal/plugins"
    "${app_dir}/Contents/Frameworks/plugins"
    "${app_dir}/plugins"
  )
  local c
  for c in "${candidates[@]}"; do
    if [[ -d "${c}" ]]; then
      echo "${c}"
      return 0
    fi
  done
  return 1
}

mac_app_bundle_dir() {
  local dist_dir="$1"
  if [[ -d "${dist_dir}/blivechat.app" ]]; then
    echo "${dist_dir}/blivechat.app"
    return 0
  fi
  return 1
}

mac_app_executable() {
  local bundle="$1"
  echo "${bundle}/Contents/MacOS/blivechat"
}
