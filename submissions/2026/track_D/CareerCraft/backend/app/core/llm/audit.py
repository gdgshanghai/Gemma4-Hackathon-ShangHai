"""LLM audit logging: decorator client + structured event sink.

`AuditingLLMClient` wraps any `LLMClient` and records one JSON line per
round-trip on the dedicated ``careercraft.llm`` logger. Business code calls
the wrapped client just like any other `LLMClient`; it never sees logging.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from app.core.llm.base import LLMClient

LLM_LOGGER_NAME = "careercraft.llm"

# Per-field cap to keep individual records bounded.
_MAX_FIELD_BYTES = 8 * 1024


@dataclass
class LLMExchangeEvent:
  """One LLM round-trip captured for audit."""

  provider: str
  model: str | None
  system: str | None
  prompt: str
  json_schema: dict | None
  response: str | None
  error: str | None
  latency_ms: float
  extra: dict[str, Any] = field(default_factory=dict)


def _truncate(text: str | None) -> str | None:
  if text is None:
    return None
  data = text.encode("utf-8")
  if len(data) <= _MAX_FIELD_BYTES:
    return text
  return data[:_MAX_FIELD_BYTES].decode("utf-8", errors="ignore") + "...<truncated>"


def log_llm_exchange(event: LLMExchangeEvent) -> None:
  """Emit one JSON line for an exchange. No-op when logger has only NullHandler."""
  record: dict[str, Any] = {
      "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
      "provider": event.provider,
      "model": event.model,
      "latency_ms": round(event.latency_ms, 2),
      "system": _truncate(event.system),
      "prompt": _truncate(event.prompt),
      "json_schema": event.json_schema,
      "response": _truncate(event.response),
      "error": event.error,
  }
  if event.extra:
    record["extra"] = event.extra
  try:
    line = json.dumps(record, ensure_ascii=False)
  except (TypeError, ValueError):
    line = json.dumps({
        "ts": record["ts"],
        "provider": event.provider,
        "model": event.model,
        "error": "log-serialize-failed",
    })
  logging.getLogger(LLM_LOGGER_NAME).info(line)


class AuditingLLMClient(LLMClient):
  """Decorator that records every `chat` call on the inner client."""

  def __init__(self, inner: LLMClient) -> None:
    self._inner = inner

  @property
  def provider_name(self) -> str:  # type: ignore[override]
    return self._inner.provider_name

  @property
  def model(self) -> str | None:
    return getattr(self._inner, "model", None)

  async def chat(
      self,
      prompt: str,
      system: str | None = None,
      json_schema: dict | None = None,
  ) -> str:
    started = time.perf_counter()
    response: str | None = None
    error: str | None = None
    try:
      response = await self._inner.chat(
          prompt=prompt, system=system, json_schema=json_schema
      )
      return response
    except Exception as e:
      error = f"{type(e).__name__}: {e}"
      raise
    finally:
      log_llm_exchange(LLMExchangeEvent(
          provider=self._inner.provider_name,
          model=self.model,
          system=system,
          prompt=prompt,
          json_schema=json_schema,
          response=response,
          error=error,
          latency_ms=(time.perf_counter() - started) * 1000,
      ))

  async def stream_chat(
      self,
      prompt: str,
      system: str | None = None,
  ) -> AsyncIterator[str]:
    # Delegate; streaming audit is out of scope for now.
    async for chunk in self._inner.stream_chat(prompt=prompt, system=system):
      yield chunk
