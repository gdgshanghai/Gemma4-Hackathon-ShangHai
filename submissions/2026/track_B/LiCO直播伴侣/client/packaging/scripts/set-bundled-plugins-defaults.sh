#!/usr/bin/env bash
set -euo pipefail

PLUGINS_DIR="${1:-}"
if [[ -z "${PLUGINS_DIR}" ]] || [[ ! -d "${PLUGINS_DIR}" ]]; then
  echo "Plugins dir not found: ${PLUGINS_DIR}" >&2
  exit 0
fi

python3 - <<'PY' "${PLUGINS_DIR}"
import json
import pathlib
import sys

plugins_dir = pathlib.Path(sys.argv[1])
for plugin_dir in plugins_dir.iterdir():
    cfg_path = plugin_dir / "plugin.json"
    if not cfg_path.is_file():
        continue
    raw = cfg_path.read_text(encoding="utf-8-sig")
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError:
        print(f"Skip invalid: {cfg_path}", file=sys.stderr)
        continue
    if cfg.get("enabled") is True:
        cfg["enabled"] = False
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Disabled bundled plugin by default: {plugin_dir.name}")
PY
