#!/usr/bin/env bash
# Build frontend + PyInstaller bundle (+ optional OBS .plugin) on macOS.
# Must be run on a Mac (PyInstaller cannot cross-compile to .app from Windows).
set -euo pipefail

SKIP_FRONTEND=0
SKIP_PLUGIN=0
SKIP_DMG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --skip-plugin) SKIP_PLUGIN=1 ;;
    --skip-dmg) SKIP_DMG=1 ;;
    -h|--help)
      echo "Usage: $0 [--skip-frontend] [--skip-plugin] [--skip-dmg]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must run on macOS (Darwin)." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

PROJECT_ROOT="$(project_root_from "${SCRIPT_DIR}")"
PACKAGING_DIR="${PROJECT_ROOT}/packaging"
DIST_DIR="${PACKAGING_DIR}/dist"
VENDOR_DIR="${PACKAGING_DIR}/vendor"

echo "Project root: ${PROJECT_ROOT}"

if [[ "${SKIP_FRONTEND}" -eq 0 ]]; then
  pushd "${PROJECT_ROOT}/frontend" >/dev/null
  if [[ ! -d node_modules ]]; then
    npm install
  fi
  npm run build
  popd >/dev/null
fi

echo "Installing Python build deps..."
python3 -m pip install -r "${PROJECT_ROOT}/requirements.txt"
python3 -m pip install -r "${PACKAGING_DIR}/requirements-build.txt"

pushd "${PACKAGING_DIR}" >/dev/null
python3 -m PyInstaller --noconfirm --clean blivechat.spec
popd >/dev/null

APP_BUNDLE=""
if APP_BUNDLE="$(mac_app_bundle_dir "${DIST_DIR}")"; then
  APP_DIR="${APP_BUNDLE}"
  EXE_PATH="$(mac_app_executable "${APP_BUNDLE}")"
  echo "Application bundle: ${APP_BUNDLE}"
else
  APP_DIR="${DIST_DIR}/blivechat"
  EXE_PATH="${APP_DIR}/blivechat"
  echo "Application folder: ${APP_DIR}"
fi

if PLUGINS_DIR="$(find_bundled_plugins_dir "${APP_DIR}")"; then
  bash "${SCRIPT_DIR}/set-bundled-plugins-defaults.sh" "${PLUGINS_DIR}"
else
  echo "WARN: bundled plugins dir not found under ${APP_DIR}" >&2
fi

if [[ "${SKIP_PLUGIN}" -eq 0 ]]; then
  if [[ ! -d "${VENDOR_DIR}/obs-blivechat-bridge.plugin" ]]; then
    if [[ -x "${SCRIPT_DIR}/build-obs-plugin-macos.sh" ]]; then
      bash "${SCRIPT_DIR}/build-obs-plugin-macos.sh" || echo "WARN: OBS plugin build failed; continuing without vendor plugin"
    fi
  fi
fi

if [[ -d "${VENDOR_DIR}/obs-blivechat-bridge.plugin" ]]; then
  mkdir -p "${APP_DIR}/vendor"
  rm -rf "${APP_DIR}/vendor/obs-blivechat-bridge.plugin"
  cp -R "${VENDOR_DIR}/obs-blivechat-bridge.plugin" "${APP_DIR}/vendor/"
  echo "Vendor plugin copied into app bundle"
fi

# Optional: zip for distribution
RELEASE_DIR="${PACKAGING_DIR}/release"
mkdir -p "${RELEASE_DIR}"
VERSION="$(python3 -c "import json;print(json.load(open('${PROJECT_ROOT}/frontend/package.json'))['version'])")"
ZIP_OUT="${RELEASE_DIR}/blivechat-${VERSION}-macos-$(uname -m).zip"

if [[ -n "${APP_BUNDLE}" ]]; then
  ditto -c -k --sequesterRsrc --keepParent "${APP_BUNDLE}" "${ZIP_OUT}"
else
  (cd "${DIST_DIR}" && ditto -c -k --sequesterRsrc "blivechat" "${ZIP_OUT}")
fi
echo "Release zip: ${ZIP_OUT}"

if [[ "${SKIP_DMG}" -eq 0 ]] && command -v hdiutil >/dev/null 2>&1; then
  DMG_OUT="${RELEASE_DIR}/blivechat-${VERSION}-macos.dmg"
  STAGING="${PACKAGING_DIR}/dmg-staging"
  rm -rf "${STAGING}"
  mkdir -p "${STAGING}"
  if [[ -n "${APP_BUNDLE}" ]]; then
    cp -R "${APP_BUNDLE}" "${STAGING}/"
  else
    cp -R "${APP_DIR}" "${STAGING}/blivechat"
  fi
  ln -sf /Applications "${STAGING}/Applications"
  rm -f "${DMG_OUT}"
  hdiutil create -volname "blivechat" -srcfolder "${STAGING}" -ov -format UDZO "${DMG_OUT}"
  rm -rf "${STAGING}"
  echo "Release dmg: ${DMG_OUT}"
fi

echo ""
echo "Next steps:"
echo "  1. Open: ${EXE_PATH}"
echo "  2. Edit config: ${HOME}/Library/Application Support/blivechat/data/config.ini"
echo "  3. Visit: http://127.0.0.1:12450/"
