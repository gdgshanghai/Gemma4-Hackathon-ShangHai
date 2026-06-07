from __future__ import annotations

import asyncio
import base64
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TTS_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"


async def generate_audio(text: str) -> str | None:
    """Call Qwen TTS via Aliyun DashScope REST API.

    Non-streaming mode returns a WAV download URL.  We download the WAV and
    return it as a base64 data URI.
    """
    if not settings.tts_enabled:
        logger.info("TTS is disabled via settings, skipping audio generation")
        return None

    api_key = settings.dashscope_api_key
    if not api_key:
        logger.error("DASHSCOPE_API_KEY is not set, cannot call Qwen TTS")
        return None

    payload = {
        "model": settings.tts_model,
        "input": {
            "text": text,
            "voice": settings.tts_voice,
            "language_type": "Chinese",
        },
    }

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(settings.tts_max_retries):
            try:
                resp = await client.post(
                    TTS_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                # --- 429 Too Many Requests — exponential backoff & retry ---
                if resp.status_code == 429:
                    retry_after = min(15.0 * (2**attempt), 120.0)
                    logger.warning(
                        "TTS attempt %d hit 429, waiting %.0fs before retry...",
                        attempt + 1,
                        retry_after,
                    )
                    if attempt < settings.tts_max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    logger.error(
                        "TTS gave up after %d attempts (all 429)",
                        settings.tts_max_retries,
                    )
                    return None

                resp.raise_for_status()
                data = resp.json()

                # Check for DashScope API error (the response has no "status_code" in body
                # for this endpoint; errors appear as "code"/"message" fields).
                if "code" in data:
                    logger.error(
                        "TTS API error: code=%s message=%s",
                        data.get("code"),
                        data.get("message", ""),
                    )
                    return None

                audio_url = data.get("output", {}).get("audio", {}).get("url")
                if not audio_url:
                    # Some models may return base64 data inline instead
                    audio_data = data.get("output", {}).get("audio", {}).get("data")
                    if audio_data:
                        return f"data:audio/wav;base64,{audio_data}"
                    logger.error("TTS response has no audio URL or data: %s", data)
                    return None

                # Download the WAV file from the URL
                logger.info(
                    "TTS attempt %d success, downloading WAV from URL (len %d chars)",
                    attempt + 1,
                    len(audio_url),
                )
                wav_resp = await client.get(audio_url)
                wav_resp.raise_for_status()
                wav_bytes = wav_resp.content

                b64 = base64.b64encode(wav_bytes).decode("ascii")
                logger.info(
                    "TTS download complete: %d bytes WAV → %d chars base64",
                    len(wav_bytes),
                    len(b64),
                )
                return f"data:audio/wav;base64,{b64}"

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    retry_after = min(15.0 * (2**attempt), 120.0)
                    logger.warning(
                        "TTS attempt %d HTTP 429, waiting %.0fs...",
                        attempt + 1,
                        retry_after,
                    )
                    if attempt < settings.tts_max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    logger.error(
                        "TTS gave up after %d attempts (all 429)",
                        settings.tts_max_retries,
                    )
                    return None
                raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "TTS attempt %d failed: %s", attempt + 1, exc, exc_info=True
                )
                if attempt < settings.tts_max_retries - 1:
                    continue
                raise

    if last_error is not None:
        raise last_error  # type: ignore[misc]
    return None
