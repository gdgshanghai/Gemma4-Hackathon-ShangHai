#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

build_log="${TMPDIR:-/tmp}/asd-litert-cli-build.log"
if ! swift build >"$build_log" 2>&1; then
  binary_path="$(find .build -path '*/debug/asd-litert-cli' -type f -perm -111 | head -n 1)"
  if [[ -z "$binary_path" ]]; then
    cat "$build_log" >&2
    exit 1
  fi
else
  binary_path="$(find .build -path '*/debug/asd-litert-cli' -type f -perm -111 | head -n 1)"
fi

if [[ -z "$binary_path" ]]; then
  cat "$build_log" >&2
  exit 1
fi

exec "$binary_path" "$@"
