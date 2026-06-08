#!/bin/bash
# Gemma API：Python 3.11 + browser-use（国内镜像）
set -e
cd /root/Gemma

PYENV=/root/miniconda3/envs/gemma311
PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
PLAYWRIGHT_MIRROR="https://npmmirror.com/mirrors/playwright"

echo "==> 1. 创建/确认 conda 环境 Python 3.11"
if [[ ! -x "$PYENV/bin/python" ]]; then
  conda create -n gemma311 python=3.11 -y
fi

echo "==> 2. pip 安装依赖（清华源）"
"$PYENV/bin/pip" install -U pip -i "$PIP_INDEX"
"$PYENV/bin/pip" install -r gemma_api/requirements.txt "browser-use>=0.9.0" -i "$PIP_INDEX"

echo "==> 3. Playwright Chromium（npmmirror 镜像）"
export PLAYWRIGHT_DOWNLOAD_HOST="$PLAYWRIGHT_MIRROR"
"$PYENV/bin/playwright" install chromium

echo "==> 4. 禁用 browser-use 扩展下载（避免 Google CRX 墙）"
export BROWSER_USE_DISABLE_EXTENSIONS=1
export ANONYMIZED_TELEMETRY=false

echo "==> 5. 快速自检"
"$PYENV/bin/python" -c "
import browser_use
from browser_use.llm import ChatOllama
print('Python', __import__('sys').version)
print('browser-use OK')
"

echo ""
echo "完成。启动 API: ./start_gemma_api.sh"
echo "Python: $PYENV/bin/python"
