#!/usr/bin/env bash
# 一键启动（开发模式）：拉起端侧 Gemma 4 + 后端服务
set -euo pipefail

echo "[1/4] 检查 Ollama..."
if ! command -v ollama >/dev/null 2>&1; then
  echo "  未检测到 Ollama，请先安装：https://ollama.com/download"
  echo "  （或改用 docker compose 启动，见 README）"; exit 1
fi

echo "[2/4] 拉取并启动端侧 Gemma 4 4B（Q4 量化）..."
ollama pull "${GEMMA_EDGE_MODEL:-gemma-4-4b-it-q4}" || true
( ollama serve >/tmp/ollama.log 2>&1 & ) || true

echo "[3/4] 安装 Python 依赖..."
python3 -m pip install -r requirements.txt

echo "[4/4] 启动后端 (http://127.0.0.1:9000)..."
cp -n .env.example .env || true
set -a && . ./.env && set +a
uvicorn src.main:app --host 0.0.0.0 --port 9000 --reload
