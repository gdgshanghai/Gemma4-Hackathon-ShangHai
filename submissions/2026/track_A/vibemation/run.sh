#!/usr/bin/env bash
set -e
echo "== n8n Agent - Gemma 4 =="
cd "$(dirname "$0")"
pip install -r requirements.txt -q
echo "启动: http://0.0.0.0:${PORT:-8080}"
uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}
