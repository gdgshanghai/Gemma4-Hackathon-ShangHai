from __future__ import annotations

import httpx

from app.core.config import settings


def build_chat_model(model_override: str | None = None, max_tokens: int | None = None, request_timeout: float | None = None):
    model_name = model_override or settings.llm_model
    from langchain_openai import ChatOpenAI

    kwargs: dict = {
        "model": model_name,
        "temperature": settings.llm_temperature,
        "max_tokens": max_tokens if max_tokens is not None else settings.llm_max_tokens,
    }
    if settings.llm_endpoint:
        kwargs["base_url"] = settings.llm_endpoint

    if request_timeout is not None:
        kwargs["http_client"] = httpx.Client(timeout=request_timeout)

    return ChatOpenAI(**kwargs)


def build_live_chat_model():
    """Build a ChatOpenAI client for live co-present suggestions.

    Uses LIVE_LLM_* env vars — a separate endpoint/model optimized for low latency.
    Falls back to build_chat_model() if LIVE_LLM_ENDPOINT is not configured.
    """
    if not settings.live_llm_endpoint:
        # No live endpoint configured — use the main LLM
        return build_chat_model(max_tokens=settings.live_llm_max_tokens, request_timeout=settings.live_llm_request_timeout)

    from langchain_openai import ChatOpenAI

    kwargs: dict = {
        "model": settings.live_llm_model,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.live_llm_max_tokens,
        "base_url": settings.live_llm_endpoint,
    }
    if settings.live_llm_api_key:
        kwargs["api_key"] = settings.live_llm_api_key
        # LangChain ChatOpenAI reads OPENAI_API_KEY by default;
        # pass it explicitly so we can use a different key for live.
        kwargs["openai_api_key"] = settings.live_llm_api_key
    if settings.live_llm_request_timeout > 0:
        kwargs["http_client"] = httpx.Client(timeout=settings.live_llm_request_timeout)

    return ChatOpenAI(**kwargs)
