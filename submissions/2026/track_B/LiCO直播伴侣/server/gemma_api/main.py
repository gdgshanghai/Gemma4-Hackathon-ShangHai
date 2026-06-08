"""
Gemma 4 31B 多模态分析 API
监听 0.0.0.0:6006

启动:
  cd /root/Gemma && pip install -r gemma_api/requirements.txt
  export OLLAMA_HOST=http://127.0.0.1:11434
  python -m uvicorn gemma_api.main:app --host 0.0.0.0 --port 6006
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gemma_api.config import API_HOST, API_PORT, OLLAMA_MODEL
from gemma_api.routers import audio, image, text, openai_compat
from gemma_api.services.ollama_client import health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemma_api")

app = FastAPI(
    title="Gemma 4 多模态 API",
    description=(
        "需求1 文字+prompt总结(31B-mm) | "
        "需求2 原生语音理解+总结(E4B-mm) | "
        "需求3 原生识图+总结(31B-mm) | "
        "知识不足时 web_search"
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(text.router, prefix="/api/v1")
app.include_router(audio.router, prefix="/api/v1")
app.include_router(image.router, prefix="/api/v1")
app.include_router(openai_compat.router)


@app.on_event("startup")
async def _prewarm():
    """启动即把主模型加载进显存、并预热 Whisper，避免首个真实请求付冷启动延迟。"""
    import asyncio
    import httpx

    from gemma_api.config import OLLAMA_HOST

    async def warm_ollama():
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                await client.post(
                    f"{OLLAMA_HOST}/v1/chat/completions",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": [{"role": "user", "content": "ok"}],
                        "max_tokens": 1,
                        "stream": False,
                    },
                )
            logger.info("prewarm: ollama model %s loaded", OLLAMA_MODEL)
        except Exception as e:
            logger.warning("prewarm: ollama warm failed: %s", e)

    async def warm_whisper():
        try:
            from gemma_api.services.stt import _get_whisper

            await asyncio.to_thread(_get_whisper)
            logger.info("prewarm: whisper model loaded")
        except Exception as e:
            logger.warning("prewarm: whisper warm skipped: %s", e)

    asyncio.create_task(warm_ollama())
    asyncio.create_task(warm_whisper())


@app.get("/health")
async def health_check():
    try:
        info = await health()
        return {"status": "ok", "ollama": info, "default_model": OLLAMA_MODEL}
    except Exception as e:
        return {"status": "degraded", "error": str(e), "default_model": OLLAMA_MODEL}


@app.get("/api/v1/examples")
async def examples():
    """三种请求类型的示例输入与 curl。"""
    base = f"http://{API_HOST}:{API_PORT}" if API_HOST != "0.0.0.0" else "http://<服务器IP>:6006"
    from gemma_api.config import OLLAMA_AUDIO_MODEL

    return {
        "base_url": base,
        "models": {
            "text_and_image": OLLAMA_MODEL,
            "audio": OLLAMA_AUDIO_MODEL,
        },
        "request_types": {
            "text": {
                "description": "文字 + prompt → 内容总结",
                "method": "POST",
                "path": "/api/v1/text/summarize",
                "content_type": "application/json",
                "example_body": {
                    "prompt": "请用三条要点总结以下内容，保留关键数字。",
                    "text": (
                        "OpenAI 发布新模型，上下文窗口提升至 128K。"
                        "业界认为开源模型 Gemma 4 在边缘部署上具有优势。"
                    ),
                    "enable_search": True,
                    "include_thinking": False,
                    "stream": False,
                },
                "curl": (
                    f'curl -X POST "{base}/api/v1/text/summarize" \\\n'
                    '  -H "Content-Type: application/json" \\\n'
                    '  -d \'{"prompt":"请用三条要点总结","text":"待总结的正文...","enable_search":true,"include_thinking":false}\''
                ),
                "curl_stream": (
                    f'curl -N -X POST "{base}/api/v1/text/summarize" \\\n'
                    '  -H "Content-Type: application/json" \\\n'
                    '  -d \'{"prompt":"请回答","text":"张雪峰和巧乐兹的关系？","enable_search":true,"include_thinking":true,"stream":true}\''
                ),
            },
            "audio": {
                "description": "语音文件 → Gemma4 E4B-mm 原生音频理解+总结（31B 无音频编码器）",
                "method": "POST",
                "path": "/api/v1/audio/summarize",
                "content_type": "multipart/form-data",
                "form_fields": {
                    "prompt": "请转写并总结这段语音的核心内容。",
                    "enable_search": True,
                    "file": "<音频文件 binary>",
                },
                "curl": (
                    f'curl -X POST "{base}/api/v1/audio/summarize" \\\n'
                    '  -F "prompt=请转写并总结这段语音" \\\n'
                    '  -F "enable_search=true" \\\n'
                    '  -F "file=@/path/to/meeting.wav"'
                ),
            },
            "image": {
                "description": "图片 → Gemma4 31B-mm 原生视觉 → Agent 总结+可搜索",
                "method": "POST",
                "path": "/api/v1/image/analyze",
                "content_type": "multipart/form-data",
                "form_fields": {
                    "prompt": "请描述图片中的文字、物体和场景。",
                    "enable_search": True,
                    "file": "<图片文件 binary>",
                },
                "curl": (
                    f'curl -X POST "{base}/api/v1/image/analyze" \\\n'
                    '  -F "prompt=请识别图片中的内容" \\\n'
                    '  -F "enable_search=true" \\\n'
                    '  -F "file=@/path/to/photo.jpg"'
                ),
            },
        },
        "search": {
            "tool_name": "web_search",
            "flow": "模型不熟悉→调用 web_search→国内搜 Top5→自动 browser-use 深读 Top5",
            "env": {
                "AUTO_BROWSER_USE": "默认 1，web_search 时自动深读",
                "SEARCH_READ_TOP_N": "默认 5",
                "BROWSER_USE_MODEL": "默认 gemma4-e4b-mm",
                "SEARCH_BACKENDS": "baidu,sogou",
            },
        },
        "docs": {"swagger": f"{base}/docs", "redoc": f"{base}/redoc"},
    }


@app.get("/")
async def root():
    return {
        "service": "Gemma 4 多模态 API",
        "endpoints": {
            "health": "/health",
            "examples": "/api/v1/examples",
            "text": "POST /api/v1/text/summarize",
            "audio": "POST /api/v1/audio/summarize",
            "image": "POST /api/v1/image/analyze",
        },
    }
