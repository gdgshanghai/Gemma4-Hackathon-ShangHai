#!/usr/bin/env bash
# 只编译 macOS arm64 的 llama mtmd 框架切片，然后把它和【现有的】iOS 真机/模拟器切片
# 合并成新的 llama.xcframework（避免重编 iOS，省时间）。
# 依赖 build-llama-mtmd-xcframework.sh 同款 cmake 配置，保持 ABI 一致（同一 b9536 源码）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${IOS_DIR}/../.." && pwd)"

LLAMA_SRC="${LLAMA_SRC:-${REPO_DIR}/outputs/llama.cpp-ios/b9536/llama.cpp-src}"
BUILD_ROOT="${BUILD_ROOT:-${REPO_DIR}/outputs/llama.cpp-ios/b9536/build-mtmd}"
OUTPUT_XCFRAMEWORK="${OUTPUT_XCFRAMEWORK:-${IOS_DIR}/Vendor/llama.xcframework}"
MAC_MIN_VERSION="${MAC_MIN_VERSION:-14.0}"

if [[ ! -d "${LLAMA_SRC}" ]]; then
  echo "Missing llama.cpp source directory: ${LLAMA_SRC}" >&2
  exit 1
fi
command -v cmake >/dev/null 2>&1 || { echo "cmake required" >&2; exit 1; }

cmake_configure_macos() {
  local build_dir="$1"
  cmake -B "${build_dir}" -G Xcode \
    -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED=NO \
    -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY="" \
    -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO \
    -DBUILD_SHARED_LIBS=OFF \
    -DLLAMA_BUILD_APP=OFF \
    -DLLAMA_BUILD_COMMON=ON \
    -DLLAMA_BUILD_EXAMPLES=OFF \
    -DLLAMA_BUILD_TOOLS=ON \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_SERVER=OFF \
    -DLLAMA_OPENSSL=OFF \
    -DGGML_METAL=ON \
    -DGGML_METAL_EMBED_LIBRARY=ON \
    -DGGML_BLAS_DEFAULT=ON \
    -DGGML_METAL_USE_BF16=ON \
    -DGGML_NATIVE=OFF \
    -DGGML_OPENMP=OFF \
    -DCMAKE_OSX_DEPLOYMENT_TARGET="${MAC_MIN_VERSION}" \
    -DCMAKE_OSX_SYSROOT=macosx \
    -DCMAKE_OSX_ARCHITECTURES="arm64" \
    -DCMAKE_XCODE_ATTRIBUTE_SUPPORTED_PLATFORMS="macosx" \
    -DCMAKE_C_FLAGS="-Wno-macro-redefined -Wno-shorten-64-to-32 -Wno-unused-command-line-argument -g" \
    -DCMAKE_CXX_FLAGS="-Wno-macro-redefined -Wno-shorten-64-to-32 -Wno-unused-command-line-argument -g" \
    -S "${LLAMA_SRC}"
}

find_release_lib_in() {
  local build_dir="$1" name="$2" relative_dir="$3" path
  path="$(find "${build_dir}/${relative_dir}" \
    -path "*/build/*" -prune -o \
    -path "*/Release*/*${name}.a" -print | sort | head -n 1)"
  [[ -n "${path}" ]] || { echo "Missing static library ${name} under ${build_dir}/${relative_dir}" >&2; exit 1; }
  printf '%s\n' "${path}"
}

setup_framework() {
  local build_dir="$1" platform_name="$2" supported_platform="$3"
  local framework_dir="${build_dir}/framework/llama.framework"
  rm -rf "${framework_dir}"
  mkdir -p "${framework_dir}/Headers" "${framework_dir}/Modules"
  cp "${LLAMA_SRC}/include/llama.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/ggml/include/ggml.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/ggml/include/ggml-opt.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/ggml/include/ggml-alloc.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/ggml/include/ggml-backend.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/ggml/include/ggml-metal.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/ggml/include/ggml-cpu.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/ggml/include/ggml-blas.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/ggml/include/gguf.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/tools/mtmd/mtmd.h" "${framework_dir}/Headers/"
  cp "${LLAMA_SRC}/tools/mtmd/mtmd-helper.h" "${framework_dir}/Headers/"
  cat > "${framework_dir}/Modules/module.modulemap" <<'EOF'
framework module llama {
    umbrella "Headers"
    link "c++"
    link framework "Accelerate"
    link framework "Metal"
    link framework "Foundation"
    export *
}
EOF
  cat > "${framework_dir}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key><string>en</string>
    <key>CFBundleExecutable</key><string>llama</string>
    <key>CFBundleIdentifier</key><string>org.ggml.llama.mtmd</string>
    <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
    <key>CFBundleName</key><string>llama</string>
    <key>CFBundlePackageType</key><string>FMWK</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>LSMinimumSystemVersion</key><string>${MAC_MIN_VERSION}</string>
    <key>CFBundleSupportedPlatforms</key><array><string>${supported_platform}</string></array>
    <key>DTPlatformName</key><string>${platform_name}</string>
</dict>
</plist>
EOF
}

# macOS 框架必须是版本化结构（Versions/A/...），不能用 iOS 的扁平结构
setup_framework_macos() {
  local build_dir="$1"
  local fw="${build_dir}/framework/llama.framework"
  rm -rf "${fw}"
  mkdir -p "${fw}/Versions/A/Headers" "${fw}/Versions/A/Modules" "${fw}/Versions/A/Resources"
  local H="${fw}/Versions/A/Headers"
  cp "${LLAMA_SRC}/include/llama.h" "${H}/"
  cp "${LLAMA_SRC}/ggml/include/ggml.h" "${H}/"
  cp "${LLAMA_SRC}/ggml/include/ggml-opt.h" "${H}/"
  cp "${LLAMA_SRC}/ggml/include/ggml-alloc.h" "${H}/"
  cp "${LLAMA_SRC}/ggml/include/ggml-backend.h" "${H}/"
  cp "${LLAMA_SRC}/ggml/include/ggml-metal.h" "${H}/"
  cp "${LLAMA_SRC}/ggml/include/ggml-cpu.h" "${H}/"
  cp "${LLAMA_SRC}/ggml/include/ggml-blas.h" "${H}/"
  cp "${LLAMA_SRC}/ggml/include/gguf.h" "${H}/"
  cp "${LLAMA_SRC}/tools/mtmd/mtmd.h" "${H}/"
  cp "${LLAMA_SRC}/tools/mtmd/mtmd-helper.h" "${H}/"
  cat > "${fw}/Versions/A/Modules/module.modulemap" <<'EOF'
framework module llama {
    umbrella "Headers"
    link "c++"
    link framework "Accelerate"
    link framework "Metal"
    link framework "Foundation"
    export *
}
EOF
  cat > "${fw}/Versions/A/Resources/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key><string>en</string>
    <key>CFBundleExecutable</key><string>llama</string>
    <key>CFBundleIdentifier</key><string>org.ggml.llama.mtmd</string>
    <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
    <key>CFBundleName</key><string>llama</string>
    <key>CFBundlePackageType</key><string>FMWK</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>CFBundleVersion</key><string>1</string>
    <key>LSMinimumSystemVersion</key><string>${MAC_MIN_VERSION}</string>
</dict>
</plist>
EOF
  ln -sfh A "${fw}/Versions/Current"
  ln -sfh Versions/Current/Headers "${fw}/Headers"
  ln -sfh Versions/Current/Modules "${fw}/Modules"
  ln -sfh Versions/Current/Resources "${fw}/Resources"
  ln -sfh Versions/Current/llama "${fw}/llama"
}

combine_framework_macos() {
  local build_dir="$1"
  local output_lib="${build_dir}/framework/llama.framework/Versions/A/llama"
  local libs=(
    "$(find_release_lib_in "${build_dir}" libllama src)"
    "$(find_release_lib_in "${build_dir}" libggml ggml/src)"
    "$(find_release_lib_in "${build_dir}" libggml-base ggml/src)"
    "$(find_release_lib_in "${build_dir}" libggml-cpu ggml/src)"
    "$(find_release_lib_in "${build_dir}" libggml-metal ggml/src/ggml-metal)"
    "$(find_release_lib_in "${build_dir}" libggml-blas ggml/src/ggml-blas)"
    "$(find_release_lib_in "${build_dir}" libmtmd tools/mtmd)"
  )
  local force_load_flags=(); for lib in "${libs[@]}"; do force_load_flags+=("-Wl,-force_load,${lib}"); done
  xcrun -sdk macosx clang++ -dynamiclib \
    -isysroot "$(xcrun --sdk macosx --show-sdk-path)" \
    -arch arm64 "-mmacosx-version-min=${MAC_MIN_VERSION}" \
    "${force_load_flags[@]}" \
    -framework Foundation -framework Metal -framework Accelerate \
    -install_name "@rpath/llama.framework/Versions/A/llama" \
    -o "${output_lib}"
}

combine_framework() {
  local build_dir="$1" sdk="$2" archs="$3" min_flag="$4"
  local output_lib="${build_dir}/framework/llama.framework/llama"
  local libs=(
    "$(find_release_lib_in "${build_dir}" libllama src)"
    "$(find_release_lib_in "${build_dir}" libggml ggml/src)"
    "$(find_release_lib_in "${build_dir}" libggml-base ggml/src)"
    "$(find_release_lib_in "${build_dir}" libggml-cpu ggml/src)"
    "$(find_release_lib_in "${build_dir}" libggml-metal ggml/src/ggml-metal)"
    "$(find_release_lib_in "${build_dir}" libggml-blas ggml/src/ggml-blas)"
    "$(find_release_lib_in "${build_dir}" libmtmd tools/mtmd)"
  )
  local arch_flags=(); for arch in ${archs//;/ }; do arch_flags+=("-arch" "${arch}"); done
  local force_load_flags=(); for lib in "${libs[@]}"; do force_load_flags+=("-Wl,-force_load,${lib}"); done
  xcrun -sdk "${sdk}" clang++ -dynamiclib \
    -isysroot "$(xcrun --sdk "${sdk}" --show-sdk-path)" \
    "${arch_flags[@]}" "${min_flag}" "${force_load_flags[@]}" \
    -framework Foundation -framework Metal -framework Accelerate \
    -install_name "@rpath/llama.framework/llama" \
    -o "${output_lib}"
}

# 1) 校验现有 iOS 切片在位（要复用）
DEVICE_FW="${OUTPUT_XCFRAMEWORK}/ios-arm64/llama.framework"
SIM_FW="${OUTPUT_XCFRAMEWORK}/ios-arm64_x86_64-simulator/llama.framework"
[[ -d "${DEVICE_FW}" && -d "${SIM_FW}" ]] || { echo "现有 iOS 切片缺失，需先跑完整脚本" >&2; exit 1; }

# 2) 编 macOS arm64
MAC_BUILD="${BUILD_ROOT}/macos"
echo ">>> configure macOS arm64"
cmake_configure_macos "${MAC_BUILD}"
echo ">>> build mtmd (macOS)"
cmake --build "${MAC_BUILD}" --config Release --target mtmd -j "$(sysctl -n hw.logicalcpu)" -- -quiet
setup_framework_macos "${MAC_BUILD}"
combine_framework_macos "${MAC_BUILD}"

# 3) 把现有 iOS 切片拷出来，重组 xcframework（device + sim + macos）
TMP="$(mktemp -d)"
mkdir -p "${TMP}/device" "${TMP}/sim"
cp -R "${DEVICE_FW}" "${TMP}/device/llama.framework"
cp -R "${SIM_FW}" "${TMP}/sim/llama.framework"
# 先合成到临时输出，成功后再原子替换，避免失败时把原 xcframework 删没了
NEW_XC="${TMP}/llama.xcframework"
xcrun xcodebuild -create-xcframework \
  -framework "${TMP}/device/llama.framework" \
  -framework "${TMP}/sim/llama.framework" \
  -framework "${MAC_BUILD}/framework/llama.framework" \
  -output "${NEW_XC}"
rm -rf "${OUTPUT_XCFRAMEWORK}"
mv "${NEW_XC}" "${OUTPUT_XCFRAMEWORK}"

echo "Done. Slices now:"
ls "${OUTPUT_XCFRAMEWORK}"
