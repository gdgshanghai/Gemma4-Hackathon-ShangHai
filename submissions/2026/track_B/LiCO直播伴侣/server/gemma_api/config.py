import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
# 31B + mmproj：文本、图像（官方 31B 无音频编码器）
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4-31b-mm")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", OLLAMA_MODEL)
# E4B + mmproj：原生语音理解（含 vision+audio）
OLLAMA_AUDIO_MODEL = os.getenv("OLLAMA_AUDIO_MODEL", "gemma4-e4b-mm")

API_HOST = os.getenv("GEMMA_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("GEMMA_API_PORT", "6006"))
GEMMA_API_KEY = os.getenv("GEMMA_API_KEY", "")

# 仅当原生音频失败时降级 Whisper
WHISPER_FALLBACK = os.getenv("WHISPER_FALLBACK", "0") == "1"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "/root/Gemma/whisper-base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "float16")
RECEIVED_AUDIO_DIR = os.getenv("RECEIVED_AUDIO_DIR", "/root/Gemma/received_audio")
# 保存客户端原始请求体（含 base64），用于复现与回放实测；置空可关闭
RECEIVED_REQUEST_DIR = os.getenv("RECEIVED_REQUEST_DIR", "/root/Gemma/received_requests")
SAVE_REQUESTS = os.getenv("SAVE_REQUESTS", "1") == "1"

# 模型调用 web_search（不熟悉）时，自动用 browser-use 深读 TopN 链接（默认开启）
AUTO_BROWSER_USE = os.getenv("AUTO_BROWSER_USE", "1") == "1"
ENABLE_BROWSER_USE = os.getenv("ENABLE_BROWSER_USE", "0") == "1"
BROWSER_USE_MODEL = os.getenv("BROWSER_USE_MODEL", "gemma4-31b-mm") or None
BROWSER_USE_MAX_STEPS = int(os.getenv("BROWSER_USE_MAX_STEPS", "12"))
BROWSER_USE_ENABLE_EXTENSIONS = os.getenv("BROWSER_USE_ENABLE_EXTENSIONS", "0") == "1"
BROWSER_USE_WAIT_BETWEEN_ACTIONS = float(
    os.getenv("BROWSER_USE_WAIT_BETWEEN_ACTIONS", "0.05")
)
BROWSER_USE_IDLE_WAIT_SEC = float(os.getenv("BROWSER_USE_IDLE_WAIT_SEC", "0.2"))
SEARCH_READ_TOP_N = int(os.getenv("SEARCH_READ_TOP_N", "3"))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "5"))
# 千帆百度 AI 搜索（智能搜索生成）
QIANFAN_SEARCH_API_KEY = os.getenv("QIANFAN_SEARCH_API_KEY", "").strip()
QIANFAN_SEARCH_API_KEY_FILE = os.getenv(
    "QIANFAN_SEARCH_API_KEY_FILE", "/root/Gemma/.qianfan_search_api_key"
).strip()
QIANFAN_SEARCH_MODEL = os.getenv("QIANFAN_SEARCH_MODEL", "ernie-4.5-turbo-32k").strip()
QIANFAN_SEARCH_SOURCE = os.getenv("QIANFAN_SEARCH_SOURCE", "baidu_search_v2").strip()
QIANFAN_ENABLE_DEEP_SEARCH = os.getenv("QIANFAN_ENABLE_DEEP_SEARCH", "0") == "1"
QIANFAN_SEARCH_RECENCY_FILTER = os.getenv("QIANFAN_SEARCH_RECENCY_FILTER", "").strip()
# 强制仅使用百度 AI 搜索（baidu_ai）
SEARCH_BACKENDS = [
    b.strip().lower()
    for b in os.getenv("SEARCH_BACKENDS", "baidu_ai").split(",")
    if b.strip()
]
SEARCH_TIMEOUT = float(os.getenv("SEARCH_TIMEOUT", "60"))
NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

Q = '<|"|>'
