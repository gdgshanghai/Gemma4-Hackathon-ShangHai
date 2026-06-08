#!/usr/bin/env bash
# 一键打 macOS 更新版(不带模型) dmg。
# 复用 ~/Library/Application Support/GlimmerModels/ 里已播种的模型，
# 用户拿到后只要拖进"应用程序"覆盖即可。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${IOS_DIR}"

echo ">>> 编 Release"
xcodebuild -project GemmaScreen.xcodeproj -scheme GlimmerMac \
  -configuration Release -destination 'platform=macOS,arch=arm64' \
  -derivedDataPath build/mac-lite-rel \
  build CODE_SIGNING_ALLOWED=NO 2>&1 | grep -E "error:|BUILD (SUCCEEDED|FAILED)" | tail -5

APP="build/mac-lite-rel/Build/Products/Release/GlimmerMac.app"
[[ -d "${APP}" ]] || { echo "✗ 编译产物缺失" >&2; exit 1; }

echo ">>> ad-hoc 签名"
codesign --force --deep --sign - "${APP}" >/dev/null

OUT="build/dist"; mkdir -p "${OUT}"
DMG="${OUT}/微光Glimmer-更新版.dmg"
echo ">>> 打 dmg"
TMP=$(mktemp -d); cp -R "${APP}" "${TMP}/"; ln -s /Applications "${TMP}/Applications"
rm -f "${DMG}"
hdiutil create -volname "微光 Glimmer (更新版)" -srcfolder "${TMP}" -ov -format UDZO "${DMG}" 2>&1 | tail -1

ls -lh "${DMG}" | awk '{print "✅", $9, "(" $5 ")"}'
