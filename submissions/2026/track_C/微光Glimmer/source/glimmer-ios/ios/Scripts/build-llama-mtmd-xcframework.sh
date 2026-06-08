#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${IOS_DIR}/../.." && pwd)"

LLAMA_SRC="${LLAMA_SRC:-${REPO_DIR}/outputs/llama.cpp-ios/b9536/llama.cpp-src}"
BUILD_ROOT="${BUILD_ROOT:-${REPO_DIR}/outputs/llama.cpp-ios/b9536/build-mtmd}"
OUTPUT_XCFRAMEWORK="${OUTPUT_XCFRAMEWORK:-${IOS_DIR}/Vendor/llama.xcframework}"
IOS_MIN_VERSION="${IOS_MIN_VERSION:-17.0}"

if [[ ! -d "${LLAMA_SRC}" ]]; then
  echo "Missing llama.cpp source directory: ${LLAMA_SRC}" >&2
  exit 1
fi

if ! command -v cmake >/dev/null 2>&1; then
  echo "cmake is required. Install it with: brew install cmake" >&2
  exit 1
fi

cmake_configure() {
  local build_dir="$1"
  local sdk="$2"
  local archs="$3"
  local platform="$4"

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
    -DCMAKE_SYSTEM_NAME=iOS \
    -DCMAKE_OSX_DEPLOYMENT_TARGET="${IOS_MIN_VERSION}" \
    -DCMAKE_OSX_SYSROOT="${sdk}" \
    -DCMAKE_OSX_ARCHITECTURES="${archs}" \
    -DCMAKE_XCODE_ATTRIBUTE_SUPPORTED_PLATFORMS="${platform}" \
    -DCMAKE_C_FLAGS="-Wno-macro-redefined -Wno-shorten-64-to-32 -Wno-unused-command-line-argument -g" \
    -DCMAKE_CXX_FLAGS="-Wno-macro-redefined -Wno-shorten-64-to-32 -Wno-unused-command-line-argument -g" \
    -S "${LLAMA_SRC}"
}

find_release_lib_in() {
  local build_dir="$1"
  local name="$2"
  local relative_dir="$3"
  local path
  path="$(find "${build_dir}/${relative_dir}" \
    -path "*/build/*" -prune -o \
    -path "*/Release-*/*${name}.a" -print | sort | head -n 1)"
  if [[ -z "${path}" ]]; then
    echo "Missing static library ${name} under ${build_dir}/${relative_dir}" >&2
    exit 1
  fi
  printf '%s\n' "${path}"
}

setup_framework() {
  local build_dir="$1"
  local platform_name="$2"
  local supported_platform="$3"
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
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>llama</string>
    <key>CFBundleIdentifier</key>
    <string>org.ggml.llama.mtmd</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>llama</string>
    <key>CFBundlePackageType</key>
    <string>FMWK</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>MinimumOSVersion</key>
    <string>${IOS_MIN_VERSION}</string>
    <key>CFBundleSupportedPlatforms</key>
    <array>
        <string>${supported_platform}</string>
    </array>
    <key>DTPlatformName</key>
    <string>${platform_name}</string>
    <key>UIDeviceFamily</key>
    <array>
        <integer>1</integer>
        <integer>2</integer>
    </array>
</dict>
</plist>
EOF
}

combine_framework() {
  local build_dir="$1"
  local sdk="$2"
  local archs="$3"
  local min_flag="$4"
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

  local arch_flags=()
  for arch in ${archs//;/ }; do
    arch_flags+=("-arch" "${arch}")
  done

  local force_load_flags=()
  for lib in "${libs[@]}"; do
    force_load_flags+=("-Wl,-force_load,${lib}")
  done

  xcrun -sdk "${sdk}" clang++ -dynamiclib \
    -isysroot "$(xcrun --sdk "${sdk}" --show-sdk-path)" \
    "${arch_flags[@]}" \
    "${min_flag}" \
    "${force_load_flags[@]}" \
    -framework Foundation -framework Metal -framework Accelerate \
    -install_name "@rpath/llama.framework/llama" \
    -o "${output_lib}"
}

if [[ "${CLEAN:-0}" == "1" ]]; then
  rm -rf "${BUILD_ROOT}"
fi
mkdir -p "${BUILD_ROOT}"

SIM_BUILD="${BUILD_ROOT}/ios-sim"
DEVICE_BUILD="${BUILD_ROOT}/ios-device"

cmake_configure "${SIM_BUILD}" iphonesimulator "arm64;x86_64" iphonesimulator
cmake --build "${SIM_BUILD}" --config Release --target mtmd -j "$(sysctl -n hw.logicalcpu)" -- -quiet
setup_framework "${SIM_BUILD}" iphonesimulator iPhoneSimulator
combine_framework "${SIM_BUILD}" iphonesimulator "arm64;x86_64" "-mios-simulator-version-min=${IOS_MIN_VERSION}"

cmake_configure "${DEVICE_BUILD}" iphoneos "arm64" iphoneos
cmake --build "${DEVICE_BUILD}" --config Release --target mtmd -j "$(sysctl -n hw.logicalcpu)" -- -quiet
setup_framework "${DEVICE_BUILD}" iphoneos iPhoneOS
combine_framework "${DEVICE_BUILD}" iphoneos "arm64" "-mios-version-min=${IOS_MIN_VERSION}"

rm -rf "${OUTPUT_XCFRAMEWORK}"
xcrun xcodebuild -create-xcframework \
  -framework "${SIM_BUILD}/framework/llama.framework" \
  -framework "${DEVICE_BUILD}/framework/llama.framework" \
  -output "${OUTPUT_XCFRAMEWORK}"

echo "Created ${OUTPUT_XCFRAMEWORK}"
