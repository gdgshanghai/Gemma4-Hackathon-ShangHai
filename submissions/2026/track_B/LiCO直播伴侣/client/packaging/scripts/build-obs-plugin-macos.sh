#!/usr/bin/env bash
# Build obs-blivechat-bridge.plugin for macOS (requires OBS SDK / CMake).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

PROJECT_ROOT="$(project_root_from "${SCRIPT_DIR}")"
VENDOR_DIR="${PROJECT_ROOT}/packaging/vendor"
BUILD_DIR="${PROJECT_ROOT}/obs-blivechat-bridge/build-macos"

mkdir -p "${VENDOR_DIR}"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

if [[ ! -d "/Applications/OBS.app" ]]; then
  echo "OBS.app not found. Install OBS Studio first." >&2
  exit 1
fi

cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build . --config RelWithDebInfo -j"$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"

PLUGIN_SRC=""
for candidate in \
  "${BUILD_DIR}/obs-blivechat-bridge.plugin" \
  "${BUILD_DIR}/RelWithDebInfo/obs-blivechat-bridge.plugin" \
  "${BUILD_DIR}/Release/obs-blivechat-bridge.plugin"; do
  if [[ -d "${candidate}" ]]; then
    PLUGIN_SRC="${candidate}"
    break
  fi
done

if [[ -z "${PLUGIN_SRC}" ]]; then
  echo "Built .plugin bundle not found under ${BUILD_DIR}" >&2
  exit 1
fi

rm -rf "${VENDOR_DIR}/obs-blivechat-bridge.plugin"
cp -R "${PLUGIN_SRC}" "${VENDOR_DIR}/obs-blivechat-bridge.plugin"
echo "Copied plugin to ${VENDOR_DIR}/obs-blivechat-bridge.plugin"
