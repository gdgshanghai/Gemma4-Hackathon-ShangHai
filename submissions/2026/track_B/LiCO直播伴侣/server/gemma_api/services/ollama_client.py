"""Ollama HTTP 客户端（0.30+ 原生 Gemma4 多模态）。"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from gemma_api.config import (
    NUM_CTX,
    OLLAMA_AUDIO_MODEL,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_VISION_MODEL,
)

logger = logging.getLogger(__name__)


async def generate_raw(
    prompt: str,
    *,
    model: str | None = None,
    stops: list[str] | None = None,
    num_predict: int = 1024,
    timeout: float = 600.0,
) -> tuple[str, str]:
    body: dict[str, Any] = {
        "model": model or OLLAMA_MODEL,
        "prompt": prompt,
        "raw": True,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict,
            "num_ctx": NUM_CTX,
        },
    }
    if stops:
        body["options"]["stop"] = stops
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{OLLAMA_HOST}/api/generate", json=body)
        r.raise_for_status()
        data = r.json()
    return data.get("response", ""), data.get("done_reason", "")


async def generate_raw_stream(
    prompt: str,
    *,
    model: str | None = None,
    stops: list[str] | None = None,
    num_predict: int = 1024,
    timeout: float = 600.0,
) -> AsyncIterator[tuple[str, str]]:
    """流式生成；yield (delta, done_reason)，结束时 done_reason 非空。"""
    body: dict[str, Any] = {
        "model": model or OLLAMA_MODEL,
        "prompt": prompt,
        "raw": True,
        "stream": True,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict,
            "num_ctx": NUM_CTX,
        },
    }
    if stops:
        body["options"]["stop"] = stops
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", f"{OLLAMA_HOST}/api/generate", json=body
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("done"):
                    yield "", data.get("done_reason", "")
                    break
                chunk = data.get("response", "")
                if chunk:
                    yield chunk, ""


async def chat_with_image(
    prompt: str,
    image_bytes: bytes,
    *,
    model: str | None = None,
    num_predict: int = 1024,
    timeout: float = 600.0,
) -> tuple[str, str]:
    """Gemma4 31B-mm 原生视觉。"""
    b64 = base64.b64encode(image_bytes).decode()
    body = {
        "model": model or OLLAMA_VISION_MODEL,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": num_predict, "num_ctx": NUM_CTX},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{OLLAMA_HOST}/api/chat", json=body)
        r.raise_for_status()
        data = r.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    msg = data.get("message", {})
    return msg.get("content", ""), data.get("done_reason", "")


async def chat_with_audio(
    prompt: str,
    audio_bytes: bytes,
    *,
    audio_format: str = "wav",
    model: str | None = None,
    num_predict: int = 1024,
    timeout: float = 600.0,
) -> tuple[str, str, Optional[str]]:
    """Gemma4 E4B-mm 原生音频（OpenAI 兼容 input_audio）。"""
    b64 = base64.b64encode(audio_bytes).decode()
    body = {
        "model": model or OLLAMA_AUDIO_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "input_audio",
                        "input_audio": {"data": b64, "format": audio_format},
                    },
                ],
            }
        ],
        "stream": False,
        "max_tokens": num_predict,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{OLLAMA_HOST}/v1/chat/completions", json=body)
        r.raise_for_status()
        data = r.json()
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content", "")
    transcript = None
    if content:
        for line in content.split("\n"):
            if line.startswith("转录") or line.startswith("转写"):
                transcript = line.split("：", 1)[-1].strip()
                break
    return content, choice.get("finish_reason", ""), transcript


async def health() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        ver = (await client.get(f"{OLLAMA_HOST}/api/version")).json()
        tags = (await client.get(f"{OLLAMA_HOST}/api/tags")).json()
    return {"ollama": ver, "models": tags.get("models", [])}
