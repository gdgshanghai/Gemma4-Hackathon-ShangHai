"""Canonical low-level LLM helpers shared by every subagent.

Lifted from ``app.services.agent`` so subagents and future orchestrators do
not depend on the legacy module. ``app.services.agent`` re-exports these
names for backward compatibility while shims exist.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings
from app.core.llm import LLMProviderError, get_llm_client

logger = logging.getLogger(__name__)


async def call_llm(
    prompt: str,
    system: str | None = None,
    json_schema: dict | None = None,
) -> str:
  """Forward a chat call to the configured provider with audit logging."""
  client = get_llm_client()
  try:
    return await client.chat(prompt=prompt, system=system, json_schema=json_schema)
  except LLMProviderError as e:
    logger.warning("LLM provider error: %s", e)
    raise
  except Exception:
    logger.exception("LLM call unexpected exception")
    raise


async def call_llm_json(
    prompt: str,
    system: str | None = None,
    json_schema: dict | None = None,
) -> dict[str, Any]:
  """Forward a structured-output call; returns a parsed JSON object.

  Adds bounded retries for transient network failures (timeout /
  connection reset) when ``settings.llm_retry_on_timeout`` is enabled.
  Up to 2 retry attempts are made with exponential back-off (2s, 4s ...).
  SDK internal retry is disabled so all back-off logic is application-controlled.
  Additionally, when ``settings.llm_retry_on_schema_violation`` is enabled,
  a single retry is attempted on schema-violation responses with the prior
  error appended to the prompt as a counter-example -- this fixes the
  common case where a model returns valid JSON but with the wrong key
  shape.
  """
  client = get_llm_client()
  network_retry_left = 2 if settings.llm_retry_on_timeout else 0
  schema_retry_left = 1 if settings.llm_retry_on_schema_violation else 0
  current_prompt = prompt
  attempt = 0
  while True:
    attempt += 1
    try:
      return await client.chat_json(
          prompt=current_prompt, system=system, json_schema=json_schema
      )
    except LLMProviderError as e:
      msg = str(e)
      if (
          schema_retry_left > 0
          and json_schema is not None
          and msg.lower().startswith("schema violation")
      ):
        schema_retry_left -= 1
        current_prompt = (
            prompt
            + "\n\n上一次回复违反了 JSON Schema，错误如下：\n"
            + msg
            + "\n请仅返回符合上述 Schema 的 JSON 对象，不要包含额外字段，也不要省略 required 字段。"
        )
        logger.warning(
            "LLM schema violation on attempt %d (%s); retrying with error hint",
            attempt, msg,
        )
        continue
      if network_retry_left > 0 and _is_transient_network_error(e):
        network_retry_left -= 1
        backoff = 2 ** attempt
        logger.warning(
            "LLM transient error on attempt %d (%s); retrying in %.1fs",
            attempt, e, backoff,
        )
        await asyncio.sleep(backoff)
        continue
      logger.warning("LLM provider error: %s", e)
      raise
    except Exception:
      logger.exception("LLM call unexpected exception")
      raise


def _is_transient_network_error(exc: Exception) -> bool:
  """Heuristic match for retry-worthy upstream errors."""
  msg = str(exc).lower()
  return any(token in msg for token in ("timed out", "timeout", "connection"))


def llm_disabled() -> bool:
  """Subagents short-circuit to fallback() when this returns True."""
  return bool(settings.mock_agent_output) or not settings.llm_api_key


def unwrap_to_required_keys(
    payload: dict[str, Any],
    required: tuple[str, ...],
    max_depth: int = 3,
) -> dict[str, Any] | None:
  """Find the first nested dict containing every key in ``required``.

  LLMs frequently wrap responses in containers (``task``, ``task_config``,
  ``context``, ``deliverables`` ...). Instead of teaching the schema each
  variant, we walk a bounded depth and unwrap when possible. Returns
  ``None`` when no candidate matches -- callers should treat that as a
  contract failure and use a fallback (Fail-Fast at the boundary).
  """
  if max_depth < 0 or not isinstance(payload, dict):
    return None
  if all(k in payload for k in required):
    return payload
  for v in payload.values():
    if isinstance(v, dict):
      found = unwrap_to_required_keys(v, required, max_depth - 1)
      if found is not None:
        return found
  return None


__all__ = [
    "call_llm",
    "call_llm_json",
    "llm_disabled",
    "unwrap_to_required_keys",
]
