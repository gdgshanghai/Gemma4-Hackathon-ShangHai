#!/usr/bin/env bash
# 把已编好的 GlimmerMac.app 用 Developer ID 签名 + 公证 + staple，打成可分发的 .dmg。
#
# 前置：
#   1) 已有 "Developer ID Application" 证书在钥匙串
#   2) 已存公证凭据：xcrun notarytool store-credentials "glimmer-notary" \
#         --apple-id <你的AppleID邮箱> --team-id XN9XFCT4XH --password <App专用密码>
#
# 用法：
#   DEVID="Developer ID Application: 你的名字 (XN9XFCT4XH)" \
#   NOTARY_PROFILE="glimmer-notary" \
#   bash Scripts/package-mac-dmg.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

APP="${APP:-${IOS_DIR}/build/mac-release/Build/Products/Release/GlimmerMac.app}"
DEVID="${DEVID:?请设置 DEVID=Developer ID Application 证书名}"
NOTARY_PROFILE="${NOTARY_PROFILE:-glimmer-notary}"
OUT_DIR="${OUT_DIR:-${IOS_DIR}/build/dist}"
DMG="${OUT_DIR}/微光Glimmer.dmg"

[[ -d "${APP}" ]] || { echo "找不到 app：${APP}（先 Release 编译 GlimmerMac）" >&2; exit 1; }
mkdir -p "${OUT_DIR}"

echo ">>> 1/5 签名内嵌 llama.framework（Developer ID + Hardened Runtime + 时间戳）"
FW="${APP}/Contents/Frameworks/llama.framework"
if [[ -d "${FW}" ]]; then
  codesign --force --options runtime --timestamp --sign "${DEVID}" "${FW}/Versions/A/llama"
  codesign --force --options runtime --timestamp --sign "${DEVID}" "${FW}"
fi

echo ">>> 2/5 签名 app 主体"
codesign --force --options runtime --timestamp \
  --sign "${DEVID}" "${APP}"
codesign --verify --deep --strict --verbose=2 "${APP}"

echo ">>> 3/5 打 dmg"
rm -f "${DMG}"
TMP_DMG_DIR="$(mktemp -d)"
cp -R "${APP}" "${TMP_DMG_DIR}/"
ln -s /Applications "${TMP_DMG_DIR}/Applications"
hdiutil create -volname "微光 Glimmer" -srcfolder "${TMP_DMG_DIR}" -ov -format UDZO "${DMG}"

echo ">>> 4/5 公证（提交给 Apple，等待结果）"
xcrun notarytool submit "${DMG}" --keychain-profile "${NOTARY_PROFILE}" --wait

echo ">>> 5/5 staple（把公证票据钉进 dmg）"
xcrun stapler staple "${DMG}"
xcrun stapler validate "${DMG}"

echo ""
echo "✅ 完成：${DMG}"
echo "   发给别人，双击挂载 → 拖进 Applications 即可运行。"
