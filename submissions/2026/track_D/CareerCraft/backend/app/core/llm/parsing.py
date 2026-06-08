"""Tolerant JSON parsing for LLM responses.

Providers occasionally return JSON wrapped in markdown code fences, or
double-encoded as a JSON string whose content is itself a JSON object.
``parse_json_object`` normalises these shapes into a plain ``dict`` and
raises :class:`LLMOutputFormatError` when the payload genuinely cannot be
interpreted as a JSON object.
"""

from __future__ import annotations

import json
import re
from typing import Any

import jsonschema

from app.core.llm.base import LLMProviderError

_FENCE_OPEN = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"\s*```$")
_FIRST_OBJECT = re.compile(r"\{[\s\S]*\}")


class LLMOutputFormatError(LLMProviderError):
  """Raised when an LLM response cannot be parsed as a JSON object."""


def parse_json_object(raw: str) -> dict[str, Any]:
  """Parse ``raw`` into a dict, tolerating common provider quirks."""
  text = (raw or "").strip()
  if not text:
    raise LLMOutputFormatError("empty LLM response")

  if text.startswith("```"):
    text = _FENCE_OPEN.sub("", text)
    text = _FENCE_CLOSE.sub("", text)

  try:
    value: Any = json.loads(text)
  except json.JSONDecodeError as exc:
    match = _FIRST_OBJECT.search(text)
    if not match:
      raise LLMOutputFormatError(f"not valid JSON: {exc.msg}") from exc
    try:
      value = json.loads(match.group(0))
    except json.JSONDecodeError as inner:
      raise LLMOutputFormatError(f"not valid JSON: {inner.msg}") from inner

  # Some providers double-encode: top-level JSON is a string whose body is JSON.
  if isinstance(value, str):
    try:
      value = json.loads(value)
    except json.JSONDecodeError as exc:
      raise LLMOutputFormatError(
          "response was a JSON string but inner content is not JSON"
      ) from exc

  if not isinstance(value, dict):
    raise LLMOutputFormatError(
        f"expected JSON object, got {type(value).__name__}"
    )
  return value


def validate_against_schema(payload: dict[str, Any], schema: dict[str, Any]) -> None:
  """Validate ``payload`` against a JSON Schema; raise on contract violation.

  Keeps the contract check beside the parser so every caller of
  ``chat_json`` gets the same fail-fast semantics (DbC).
  """
  try:
    jsonschema.validate(instance=payload, schema=schema)
  except jsonschema.ValidationError as exc:
    path = "/".join(str(p) for p in exc.absolute_path) or "<root>"
    raise LLMOutputFormatError(
        f"schema violation at {path}: {exc.message}"
    ) from exc


_WS_RUNS = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_FENCE_OPEN_ANY_LANG = re.compile(r"^```[^\n`]*\n?")


def strip_text_artifacts(raw: str | None) -> str:
  """Normalise free-form LLM text replies for direct user display.

  Strips markdown code fences (``` and ```lang), collapses long blank-line
  runs and trims surrounding whitespace. Does NOT attempt to parse JSON;
  use :func:`parse_json_object` for structured responses.
  """
  if not raw:
    return ""
  text = raw.strip()
  if text.startswith("```"):
    text = _FENCE_OPEN_ANY_LANG.sub("", text)
    text = _FENCE_CLOSE.sub("", text)
  text = _WS_RUNS.sub(" ", text)
  text = _BLANK_LINES.sub("\n\n", text)
  return text.strip()
