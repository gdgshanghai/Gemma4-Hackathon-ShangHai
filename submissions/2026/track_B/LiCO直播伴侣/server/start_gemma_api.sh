#!/bin/bash
set -e
cd /root/Gemma

# Python 3.11（browser-use 需要）；未创建则: bash scripts/setup_gemma311_cn.sh
if [[ -x /root/miniconda3/envs/gemma311/bin/python ]]; then
  PYTHON=/root/miniconda3/envs/gemma311/bin/python
else
  PYTHON=python3
fi

export HF_ENDPOINT="https://hf-mirror.com"
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
# H800 提速：并发槽位 + 常驻显存 + flash attention + KV量化
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-4}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}"
export OLLAMA_FLASH_ATTENTION="${OLLAMA_FLASH_ATTENTION:-1}"
export OLLAMA_KV_CACHE_TYPE="${OLLAMA_KV_CACHE_TYPE:-q8_0}"
export OLLAMA_MAX_LOADED_MODELS="${OLLAMA_MAX_LOADED_MODELS:-2}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4-31b-mm}"
export OLLAMA_VISION_MODEL="${OLLAMA_VISION_MODEL:-gemma4-31b-mm}"
export OLLAMA_AUDIO_MODEL="${OLLAMA_AUDIO_MODEL:-gemma4-e4b-mm}"
# 强制仅使用百度AI搜索
export SEARCH_BACKENDS="${SEARCH_BACKENDS:-baidu_ai}"
export AUTO_BROWSER_USE="${AUTO_BROWSER_USE:-1}"
export BROWSER_USE_MODEL="${BROWSER_USE_MODEL:-gemma4-31b-mm}"
export BROWSER_USE_MAX_STEPS="${BROWSER_USE_MAX_STEPS:-12}"
export BROWSER_USE_ENABLE_EXTENSIONS="${BROWSER_USE_ENABLE_EXTENSIONS:-0}"
export BROWSER_USE_WAIT_BETWEEN_ACTIONS="${BROWSER_USE_WAIT_BETWEEN_ACTIONS:-0.05}"
export BROWSER_USE_IDLE_WAIT_SEC="${BROWSER_USE_IDLE_WAIT_SEC:-0.2}"
export SEARCH_READ_TOP_N="${SEARCH_READ_TOP_N:-3}"
# 扩展开关（默认关）；开时会尝试下载默认扩展。国内可配镜像前缀避免卡住 Google：
# BROWSER_USE_EXTENSION_DOWNLOAD_MIRROR_PREFIX=https://ghfast.top/
export BROWSER_USE_DISABLE_EXTENSIONS="${BROWSER_USE_DISABLE_EXTENSIONS:-1}"
export ANONYMIZED_TELEMETRY="${ANONYMIZED_TELEMETRY:-false}"
export QIANFAN_SEARCH_API_KEY="${QIANFAN_SEARCH_API_KEY:-bce-v3/ALTAK-rg0DrNZyUoMsgQi0XPpIa/6f65b3411a951da5b51a722a797183a46d22c660}"
export QIANFAN_SEARCH_API_KEY_FILE="${QIANFAN_SEARCH_API_KEY_FILE:-/root/Gemma/.qianfan_search_api_key}"
export QIANFAN_SEARCH_MODEL="${QIANFAN_SEARCH_MODEL:-ernie-4.5-turbo-32k}"
export QIANFAN_SEARCH_SOURCE="${QIANFAN_SEARCH_SOURCE:-baidu_search_v2}"
export QIANFAN_ENABLE_DEEP_SEARCH="${QIANFAN_ENABLE_DEEP_SEARCH:-0}"
export QIANFAN_SEARCH_RECENCY_FILTER="${QIANFAN_SEARCH_RECENCY_FILTER:-}"
export SEARCH_TIMEOUT="${SEARCH_TIMEOUT:-60}"
export GEMMA_API_KEY="${GEMMA_API_KEY:-sk-crazy-thursday-viwo50}"
export GEMMA_API_HOST="${GEMMA_API_HOST:-0.0.0.0}"
export GEMMA_API_PORT="${GEMMA_API_PORT:-6006}"
CUDA12_PY_LIB="/root/miniconda3/envs/gemma311/lib/python3.11/site-packages/nvidia"
export LD_LIBRARY_PATH="${CUDA12_PY_LIB}/cublas/lib:${CUDA12_PY_LIB}/cudnn/lib:${CUDA12_PY_LIB}/cuda_nvrtc/lib:${LD_LIBRARY_PATH:-}"
export WHISPER_DEVICE="${WHISPER_DEVICE:-cuda}"
export WHISPER_COMPUTE="${WHISPER_COMPUTE:-float16}"
export WHISPER_MODEL="${WHISPER_MODEL:-/root/Gemma/whisper-base}"
export RECEIVED_AUDIO_DIR="${RECEIVED_AUDIO_DIR:-/root/Gemma/received_audio}"

# 确保 Ollama 在运行
if ! curl -sf "${OLLAMA_HOST}/api/version" >/dev/null 2>&1; then
  echo "启动 ollama serve..."
  nohup /usr/local/bin/ollama serve >> /root/Gemma/ollama_serve.log 2>&1 &
  sleep 4
fi

LOG_FILE="gemma_$(date +%Y%m%d_%H%M%S).log"
echo "Gemma API is starting in background. Logging to $LOG_FILE"
nohup "$PYTHON" -m uvicorn gemma_api.main:app --host "$GEMMA_API_HOST" --port "$GEMMA_API_PORT" > "$LOG_FILE" 2>&1 &
