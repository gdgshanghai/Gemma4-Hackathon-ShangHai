#!/usr/bin/env bash
# Install OBS bridge plugin from bundled vendor (macOS .plugin bundle).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

APP_DIR="${1:-}"
if [[ -z "${APP_DIR}" ]]; then
  log_install ERROR "AppDir is required"
  exit 1
fi

VENDOR_PLUGIN="${APP_DIR}/vendor/obs-blivechat-bridge.plugin"
DEST_ROOT="${HOME}/Library/Application Support/obs-studio/plugins"

if [[ ! -d "${VENDOR_PLUGIN}" ]]; then
  log_install WARN "Bundled OBS plugin not found: ${VENDOR_PLUGIN}"
  exit 1
fi

mkdir -p "${DEST_ROOT}"
DEST="${DEST_ROOT}/obs-blivechat-bridge.plugin"
rm -rf "${DEST}"
cp -R "${VENDOR_PLUGIN}" "${DEST}"
log_install INFO "Bundled OBS plugin installed: ${DEST}"
exit 0
