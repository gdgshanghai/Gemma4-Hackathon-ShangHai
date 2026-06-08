"""OpenAI-compatible provider adapter.

Works with any service exposing an OpenAI ``/v1/chat/completions`` endpoint:
OpenAI itself, Alibaba Qwen (DashScope compatible mode), DeepSeek, Moonshot,
MiniMax, Ollama local server, etc. Switch between them by setting
``LLM_BASE_URL`` and ``LLM_MODEL`` in ``.env``.
"""

import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.core.llm.base import LLMClient, LLMProviderError

logger = logging.getLogger(__name__)

# Endpoints known to honor ``response_format={"type":"json_schema",...}``.
_STRICT_SCHEMA_BASE_URL = re.compile(
    r"(dashscope\.aliyuncs\.com|api\.openai\.com|api\.deepseek\.com|api\.moonshot\.cn)",
    re.IGNORECASE,
)


def _supports_strict_schema(base_url: str | None) -> bool:
  override = settings.llm_use_json_schema_response_format
  if override is not None:
    return override
  if not base_url:
    return True  # default OpenAI endpoint
  return bool(_STRICT_SCHEMA_BASE_URL.search(base_url))


def _schema_hint(schema: dict[str, Any]) -> str:
  """Render a compact human-readable hint of the required schema shape.

  Injected into the user message so models that ignore ``response_format``
  still see the required field contract.
  """
  required = schema.get("required") or []
  props = schema.get("properties") or {}
  lines: list[str] = []
  for key in required:
    spec = props.get(key, {})
    t = spec.get("type", "any")
    enum = spec.get("enum")
    desc = spec.get("description", "")
    parts = [f"- {key} ({t})"]
    if enum:
      parts.append(f"enum={enum}")
    if desc:
      parts.append(f"// {desc}")
    lines.append(" ".join(parts))
  required_keys = ", ".join(required) if required else "(none)"
  return (
      "你的回复必须是一个 JSON 对象，且顶层键集合必须**恰好**为："
      f" [{required_keys}]，不得新增、缺失或重命名任何键。各键约束：\n"
      + "\n".join(lines)
      + "\n完整 JSON Schema 见：\n"
      + json.dumps(schema, ensure_ascii=False)
  )


class OpenAICompatibleAdapter(LLMClient):
  """Adapter using the official ``openai`` SDK against any compatible endpoint."""

  provider_name = "openai"
  default_model = "gpt-4o-mini"

  def __init__(
      self,
      api_key: str,
      model: str | None = None,
      base_url: str | None = None,
      timeout: int = 120,
  ) -> None:
    try:
      from openai import AsyncOpenAI
    except ImportError as e:
      raise LLMProviderError(
          "openai SDK not installed. Run: pip install openai"
      ) from e

    self.model = model or self.default_model
    self.timeout = timeout
    self.base_url = base_url

    client_kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout": timeout,
        "max_retries": 0,
    }
    if base_url:
      client_kwargs["base_url"] = base_url
    self._client = AsyncOpenAI(**client_kwargs)

  async def chat(
      self,
      prompt: str,
      system: str | None = None,
      json_schema: dict | None = None,
  ) -> str:
    messages: list[dict[str, Any]] = []
    if system:
      messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
    if json_schema:
      # 1. Always inject a textual schema hint so models that ignore the
      #    ``response_format`` directive still see the required field contract.
      messages[-1]["content"] += "\n\n" + _schema_hint(json_schema)
      messages[-1]["content"] += "\n\n请严格以JSON格式回复，且仅输出该 JSON 对象本体。"

      # 2. Prefer strict json_schema mode when the endpoint is known to
      #    support it; fall back to json_object on any SDK error.
      if _supports_strict_schema(self.base_url):
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "reply",
                "schema": json_schema,
                "strict": True,
            },
        }
      else:
        kwargs["response_format"] = {"type": "json_object"}

    try:
      resp = await self._client.chat.completions.create(**kwargs)
    except Exception as e:
      # Only fall back to the looser ``json_object`` mode when the upstream
      # explicitly rejects ``response_format={"type":"json_schema",...}`` —
      # i.e. an HTTP 400 (BadRequestError). Network / timeout / auth errors
      # must surface immediately so the outer retry loop in
      # ``app.services.agent.call_llm_json`` (with backoff) handles them
      # instead of issuing an unbacked-off duplicate request here.
      try:
        from openai import BadRequestError as _BadRequestError
      except ImportError:  # pragma: no cover - SDK presence guarded in __init__
        _BadRequestError = ()  # type: ignore[assignment]
      is_strict_attempt = (
          bool(json_schema)
          and isinstance(kwargs.get("response_format"), dict)
          and kwargs["response_format"].get("type") == "json_schema"
      )
      if is_strict_attempt and isinstance(e, _BadRequestError):
        logger.warning(
            "strict json_schema rejected by %s, falling back to json_object: %s",
            self.base_url, e,
        )
        kwargs["response_format"] = {"type": "json_object"}
        try:
          resp = await self._client.chat.completions.create(**kwargs)
        except Exception as inner:
          raise LLMProviderError(
              f"OpenAI-compatible call failed: {inner}"
          ) from inner
      else:
        raise LLMProviderError(f"OpenAI-compatible call failed: {e}") from e

    if not resp.choices:
      raise LLMProviderError(f"No choices returned: {resp!r}")
    content = resp.choices[0].message.content
    if content is None:
      raise LLMProviderError("Empty content returned")
    return content
