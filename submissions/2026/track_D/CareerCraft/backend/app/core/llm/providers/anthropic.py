"""Anthropic Claude provider adapter using the anthropic SDK.

Claude has no native JSON Schema response format. When a schema is supplied
we coerce structured output via ``tool_use``: register a single tool whose
``input_schema`` is the desired schema, force ``tool_choice`` to that tool,
and serialize the resulting ``input`` dict back to a JSON string.
"""

import json
from typing import Any

from app.core.llm.base import LLMClient, LLMProviderError


class AnthropicAdapter(LLMClient):
  """Adapter for Anthropic Claude models."""

  provider_name = "anthropic"
  default_model = "claude-3-5-sonnet-20241022"

  def __init__(
      self,
      api_key: str,
      model: str | None = None,
      base_url: str | None = None,
      timeout: int = 120,
      max_tokens: int = 4096,
  ) -> None:
    try:
      from anthropic import AsyncAnthropic
    except ImportError as e:
      raise LLMProviderError(
          "anthropic SDK not installed. Run: pip install anthropic"
      ) from e

    self.model = model or self.default_model
    self.timeout = timeout
    self.max_tokens = max_tokens

    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout": timeout,
        "max_retries": 0,
    }
    if base_url:
      client_kwargs["base_url"] = base_url
    self._client = AsyncAnthropic(**client_kwargs)

  async def chat(
      self,
      prompt: str,
      system: str | None = None,
      json_schema: dict | None = None,
  ) -> str:
    kwargs: dict[str, Any] = {
        "model": self.model,
        "max_tokens": self.max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
      kwargs["system"] = system

    if json_schema:
      kwargs["tools"] = [
          {
              "name": "deliver_result",
              "description": "Return the structured result for this task.",
              "input_schema": json_schema,
          }
      ]
      kwargs["tool_choice"] = {"type": "tool", "name": "deliver_result"}

    try:
      resp = await self._client.messages.create(**kwargs)
    except Exception as e:
      raise LLMProviderError(f"Anthropic call failed: {e}") from e

    if json_schema:
      for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
          return json.dumps(block.input, ensure_ascii=False)
      raise LLMProviderError(
          f"Anthropic did not return tool_use block: {resp!r}"
      )

    for block in resp.content:
      if getattr(block, "type", None) == "text":
        return block.text
    raise LLMProviderError(f"Anthropic returned no text block: {resp!r}")
