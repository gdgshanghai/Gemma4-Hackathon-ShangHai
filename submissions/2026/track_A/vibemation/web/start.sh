#!/usr/bin/env bash
set -e
echo "Starting n8n Agent Web UI..."
cd "$(dirname "$0")/.."
uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080} --reload
