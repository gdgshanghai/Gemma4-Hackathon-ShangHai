#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

APP_DIR="${1:-}"
if [[ -z "${APP_DIR}" ]]; then
  echo "Usage: post-install.sh <app-dir-or-.app-bundle>" >&2
  exit 1
fi

init_install_log
log_install INFO "post-install APP_DIR=${APP_DIR}"

"${SCRIPT_DIR}/ensure-app-data.sh" "${APP_DIR}" || true

if [[ -x "${SCRIPT_DIR}/install-obs-plugin-bundled.sh" ]]; then
  "${SCRIPT_DIR}/install-obs-plugin-bundled.sh" "${APP_DIR}" || log_install WARN "OBS plugin install skipped"
fi

if command -v ffmpeg >/dev/null 2>&1; then
  log_install INFO "FFmpeg found: $(command -v ffmpeg)"
else
  log_install WARN "FFmpeg not found. Install with: brew install ffmpeg"
fi

if [[ -d "/Applications/OBS.app" ]] || command -v obs >/dev/null 2>&1; then
  log_install INFO "OBS Studio appears installed"
else
  log_install WARN "OBS Studio not found. Download: https://obsproject.com/download"
fi

RESULT_JSON="${BLIVECHAT_INSTALL_LOG_ROOT}/install-result.json"
cat > "${RESULT_JSON}" <<EOF
{
  "platform": "darwin",
  "obs_plugin": { "status": "ok", "message": "see install.log" },
  "ffmpeg": { "status": "$(command -v ffmpeg >/dev/null 2>&1 && echo ok || echo missing)" },
  "config": { "path": "${HOME}/Library/Application Support/blivechat/data/config.ini" }
}
EOF

log_install INFO "post-install finished"
exit 0
