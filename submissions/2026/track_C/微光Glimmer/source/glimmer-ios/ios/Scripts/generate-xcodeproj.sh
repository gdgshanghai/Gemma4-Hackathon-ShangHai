#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"
env_file="${project_dir}/.env"

cd "${project_dir}"

if [[ ! -f "${env_file}" ]]; then
  echo "Missing ${env_file}" >&2
  echo "Create it from .env.example and set local signing values." >&2
  exit 1
fi

set -a
source "${env_file}"
set +a

required_vars=(
  GEMMASCREEN_PRODUCT_BUNDLE_IDENTIFIER
  GEMMASCREEN_DEVELOPMENT_TEAM
  GLIMMER_GALLERY_PRODUCT_BUNDLE_IDENTIFIER
  GLIMMER_GALLERY_DEVELOPMENT_TEAM
)

for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
done

if ! command -v xcodegen >/dev/null 2>&1; then
  echo "xcodegen is required but was not found in PATH." >&2
  exit 1
fi

xcodegen generate
