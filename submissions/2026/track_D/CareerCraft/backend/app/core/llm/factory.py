"""Factory that constructs and caches the configured LLM client (singleton).

Supported providers:
  * ``gemini``    — Google Gemini via google-genai SDK
  * ``openai``    — OpenAI SDK; works for any OpenAI-compatible endpoint
                    (Qwen DashScope, DeepSeek, Moonshot, MiniMax, Ollama, ...)
                    Just point ``LLM_BASE_URL`` at the right host.
  * ``anthropic`` — Anthropic Claude via anthropic SDK
"""

from functools import lru_cache

from app.core.config import settings
from app.core.llm.audit import AuditingLLMClient
from app.core.llm.base import LLMClient, LLMProviderError
from app.core.llm.providers.anthropic import AnthropicAdapter
from app.core.llm.providers.gemini import GeminiAdapter
from app.core.llm.providers.openai_like import OpenAICompatibleAdapter

_PROVIDERS: dict[str, type[LLMClient]] = {
    "gemini": GeminiAdapter,
    "openai": OpenAICompatibleAdapter,
    "anthropic": AnthropicAdapter,
}


def _build_client() -> LLMClient:
  provider = settings.llm_provider.lower()
  adapter_cls = _PROVIDERS.get(provider)
  if adapter_cls is None:
    raise LLMProviderError(
        f"Unknown LLM provider: '{provider}'. "
        f"Supported: {', '.join(_PROVIDERS)}."
    )

  api_key = settings.llm_api_key
  if not api_key:
    # Permit keyless usage only when caller pointed at a custom base_url
    # (e.g. Ollama at http://localhost:11434/v1 ignores the key).
    if not settings.llm_base_url:
      raise LLMProviderError(
          f"No API key configured for provider '{provider}'. "
          "Set LLM_API_KEY in your .env."
      )
    api_key = "local-placeholder"

  client = adapter_cls(
      api_key=api_key,
      model=settings.llm_model,
      base_url=settings.llm_base_url,
      timeout=settings.llm_timeout,
  )
  return AuditingLLMClient(client)


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
  """Return a cached singleton LLM client for the configured provider."""
  return _build_client()


def reset_llm_client_cache() -> None:
  """Drop the cached client (useful for tests that monkeypatch settings)."""
  get_llm_client.cache_clear()
