#!/usr/bin/env bash
# Initialize ~/Library/Application Support/blivechat data and config (macOS).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

APP_DIR="${1:-}"
CONFIG_EXAMPLE=""

init_install_log

DATA_ROOT="${HOME}/Library/Application Support/blivechat"
DATA_DIR="${DATA_ROOT}/data"
LOG_DIR="${DATA_ROOT}/log"
CONFIG_PATH="${DATA_DIR}/config.ini"

mkdir -p "${DATA_DIR}" "${DATA_DIR}/plugins" "${LOG_DIR}"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  if [[ -n "${APP_DIR}" ]]; then
    for c in \
      "${APP_DIR}/data/config.example.ini" \
      "${APP_DIR}/_internal/data/config.example.ini" \
      "${APP_DIR}/Contents/MacOS/_internal/data/config.example.ini" \
      "${APP_DIR}/Contents/Resources/data/config.example.ini"; do
      if [[ -f "${c}" ]]; then
        CONFIG_EXAMPLE="${c}"
        break
      fi
    done
  fi
  if [[ -n "${CONFIG_EXAMPLE}" ]]; then
    cp -f "${CONFIG_EXAMPLE}" "${CONFIG_PATH}"
    DB_PATH="${DATA_DIR}/database.db"
    DB_URL="sqlite:///${DB_PATH}"
    python3 - <<'PY' "${CONFIG_PATH}" "${DB_URL}"
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
db_url = sys.argv[2]
lines = path.read_text(encoding="utf-8-sig").splitlines()
out = []
for line in lines:
    if line.strip().startswith("database_url"):
        out.append(f"database_url = {db_url}")
    else:
        out.append(line)
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
    log_install INFO "Created default config: ${CONFIG_PATH}"
  else
    log_install WARN "config.example.ini not found; skipped config init"
  fi
else
  log_install INFO "Keeping existing config: ${CONFIG_PATH}"
fi
