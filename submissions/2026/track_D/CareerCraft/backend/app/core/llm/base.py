"""Abstract base class for LLM provider adapters (strategy pattern)."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class LLMProviderError(Exception):
  """Raised when a provider adapter fails to fulfill a request."""


class LLMClient(ABC):
  """Unified async interface every provider adapter must implement."""

  provider_name: str = "base"

  @abstractmethod
  async def chat(
      self,
      prompt: str,
      system: str | None = None,
      json_schema: dict | None = None,
  ) -> str:
    """Send a single-turn request and return the model text.

    Args:
      prompt: User-facing prompt content.
      system: Optional system instruction shaping role behavior.
      json_schema: Optional standard JSON Schema (lowercase types). When
        provided, the return value must be a valid JSON string parseable
        by ``json.loads`` and conforming to the schema.
    """

  async def chat_json(
      self,
      prompt: str,
      system: str | None = None,
      json_schema: dict | None = None,
  ) -> dict[str, Any]:
    """Send a request and return a parsed JSON object.

    The default implementation calls :meth:`chat` and normalises the result
    via :func:`app.core.llm.parsing.parse_json_object`. When ``json_schema``
    is supplied it is enforced via
    :func:`app.core.llm.parsing.validate_against_schema` so the post-condition
    "returns a dict matching the declared schema" is honored uniformly across
    every adapter (Liskov).
    """
    from app.core.llm.parsing import parse_json_object, validate_against_schema

    raw = await self.chat(prompt=prompt, system=system, json_schema=json_schema)
    parsed = parse_json_object(raw)
    if json_schema is not None:
      validate_against_schema(parsed, json_schema)
    return parsed

  async def stream_chat(
      self,
      prompt: str,
      system: str | None = None,
  ) -> AsyncIterator[str]:
    """Stream incremental text chunks.

    Default implementation calls ``chat`` then yields the full string as a
    single chunk. Concrete adapters should override for real token streaming.
    """
    full = await self.chat(prompt=prompt, system=system)
    yield full
