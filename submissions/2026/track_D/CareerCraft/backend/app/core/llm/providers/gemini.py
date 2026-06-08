"""Gemini provider adapter using the google-genai SDK."""

import json
from typing import Any

from app.core.llm.base import LLMClient, LLMProviderError
from app.core.llm.schema import to_gemini_schema


class GeminiAdapter(LLMClient):
  """Adapter for Google's Gemini API via google-genai SDK."""

  provider_name = "gemini"
  default_model = "gemini-1.5-flash"

  def __init__(
      self,
      api_key: str,
      model: str | None = None,
      base_url: str | None = None,
      timeout: int = 120,
  ) -> None:
    try:
      from google import genai
    except ImportError as e:
      raise LLMProviderError(
          "google-genai SDK not installed. Run: pip install google-genai"
      ) from e

    self._genai = genai
    self.model = model or self.default_model
    self.timeout = timeout

    http_options: dict[str, Any] = {
        "timeout": timeout * 1000,
        "connect_timeout": timeout * 500,
    }
    if base_url:
      http_options["base_url"] = base_url

    self._client = genai.Client(api_key=api_key, http_options=http_options)

  async def chat(
      self,
      prompt: str,
      system: str | None = None,
      json_schema: dict | None = None,
  ) -> str:
    config: dict[str, Any] = {}
    if system:
      config["system_instruction"] = system
    if json_schema:
      config["response_mime_type"] = "application/json"
      config["response_schema"] = to_gemini_schema(json_schema)

    try:
      resp = await self._client.aio.models.generate_content(
          model=self.model,
          contents=prompt,
          config=config or None,
      )
    except Exception as e:
      raise LLMProviderError(f"Gemini call failed: {e}") from e

    text = getattr(resp, "text", None)
    if text is None:
      raise LLMProviderError(f"Gemini returned empty response: {resp!r}")

    if json_schema:
      # Validate it parses; raise early if the model misbehaved.
      try:
        json.loads(text)
      except json.JSONDecodeError as e:
        raise LLMProviderError(
            f"Gemini returned non-JSON despite schema: {text[:200]}"
        ) from e
    return text
