#!/bin/bash
# Madori — 一键运行：本地 Gemma 4 读一张户型图 → 生成四视图网页 demo
#
#   ./run.sh                          # 用默认样例 samples/madorizu_1f.png
#   ./run.sh samples/floorplan.png    # 或指定你自己的户型图
#
# 前置：本机已安装 Ollama (https://ollama.com) 和 Python 3。
set -e
cd "$(dirname "$0")"
IMG="${1:-samples/madorizu_1f.png}"

echo "▸ 1/4 确认 Ollama 服务…"
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "   启动 ollama serve（后台）…"
  ollama serve >/dev/null 2>&1 &
  sleep 3
fi

echo "▸ 2/4 确认 Gemma 4 多模态模型…"
ollama list 2>/dev/null | grep -q "gemma4:e4b" || { echo "   拉取 gemma4:e4b（约 9.6GB，首次较久）…"; ollama pull gemma4:e4b; }

echo "▸ 3/4 读图分析: $IMG"
python3 pipeline/plan_read.py "$IMG"

echo "▸ 4/4 启动网页 → 浏览器打开 http://localhost:8000/madori.html"
echo "   （Ctrl+C 停止）"
python3 -m http.server 8000 --directory web
