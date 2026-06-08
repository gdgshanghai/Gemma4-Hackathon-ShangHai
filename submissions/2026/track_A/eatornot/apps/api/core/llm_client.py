import json
import logging
import re
from openai import AsyncOpenAI
from core.config import get_settings

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _get_client() -> AsyncOpenAI | None:
    settings = get_settings()
    # 优先使用 Gemini 官方 API
    if settings.GEMINI_API_KEY:
        return AsyncOpenAI(
            api_key=settings.GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
        )
    # 降级到 Cloudflare AI Gateway
    if settings.CF_AIG_TOKEN:
        return AsyncOpenAI(
            api_key=settings.CF_AIG_TOKEN,
            base_url=settings.CF_AIG_BASE_URL,
        )
    logger.warning("No LLM API key configured (GEMINI_API_KEY or CF_AIG_TOKEN)")
    return None


def _get_model() -> str:
    settings = get_settings()
    if settings.GEMINI_API_KEY:
        return settings.GEMINI_MODEL
    # CF AIG 模式
    return settings.GEMMA_MODEL


async def generate_json(system_prompt: str, user_prompt: str, schema_hint: dict | None = None) -> dict:
    """Call LLM and parse JSON response. Returns fallback on failure."""
    client = _get_client()
    if client is None:
        return {"error": "LLM not configured", "fallback": True}

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if schema_hint:
            messages[0]["content"] += f"\n\nRespond with valid JSON matching this schema:\n{json.dumps(schema_hint)}"

        response = await client.chat.completions.create(
            model=_get_model(),
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )
        text = response.choices[0].message.content or "{}"
        # Strip Gemma 4 <thought> tags
        text = re.sub(r'<thought>[\s\S]*?</thought>', '', text).strip()
        # Try to extract JSON from markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"LLM generate_json failed: {e}")
        return {"error": str(e), "fallback": True}


async def generate_text(system_prompt: str, user_prompt: str) -> str:
    """Call LLM and return plain text. Returns fallback on failure."""
    client = _get_client()
    if client is None:
        return "[LLM not configured]"

    try:
        response = await client.chat.completions.create(
            model=_get_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content or ""
        return strip_thought_tags(raw)
    except Exception as e:
        logger.error(f"LLM generate_text failed: {e}")
        return f"[LLM error: {e}]"


def strip_thought_tags(text: str) -> str:
    """Remove Gemma 4 <thought>...</thought> tags from text."""
    return re.sub(r'<thought>[\s\S]*?</thought>', '', text).strip()
