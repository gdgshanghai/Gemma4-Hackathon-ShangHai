#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR%/scripts}/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${CF_AIG_TOKEN:-}" ]]; then
  echo "CF_AIG_TOKEN is not set. Export it first or add it to backend/.env" >&2
  return 1 2>/dev/null || exit 1
fi

export GEMMA_PROVIDER="openrouter"
export OPENROUTER_API_URL="${OPENROUTER_API_URL:-https://gateway.ai.cloudflare.com/v1/bbd869342ef49cfea41170378427db5d/default/compat/chat/completions}"
export OPENROUTER_API_KEY="$CF_AIG_TOKEN"
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-google-ai-studio/gemma-4-31b-it}"
export UPLOAD_BASE_URL="${UPLOAD_BASE_URL:-http://localhost:8081/uploads}"

echo "Cloudflare AI Gateway env ready"
echo "  GEMMA_PROVIDER=$GEMMA_PROVIDER"
echo "  OPENROUTER_API_URL=$OPENROUTER_API_URL"
echo "  OPENROUTER_MODEL=$OPENROUTER_MODEL"
echo "  OPENROUTER_API_KEY length: ${#OPENROUTER_API_KEY}"
echo "  UPLOAD_BASE_URL=$UPLOAD_BASE_URL"
