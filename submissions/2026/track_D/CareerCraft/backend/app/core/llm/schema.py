"""JSON Schema normalization helpers for cross-provider compatibility.

Internal convention: callers always supply *standard* JSON Schema using
lowercase type names (``"object"``, ``"string"``, ``"array"``, ``"boolean"``,
``"number"``, ``"integer"``). Each provider adapter translates as needed.
"""

from copy import deepcopy
from typing import Any

_GEMINI_TYPE_MAP = {
    "object": "OBJECT",
    "string": "STRING",
    "array": "ARRAY",
    "boolean": "BOOLEAN",
    "number": "NUMBER",
    "integer": "INTEGER",
    "null": "NULL",
}


def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
  """Convert a standard JSON Schema dict to Gemini's uppercase-type format."""
  result = deepcopy(schema)
  _uppercase_types(result)
  return result


def _uppercase_types(node: Any) -> None:
  if isinstance(node, dict):
    t = node.get("type")
    if isinstance(t, str) and t in _GEMINI_TYPE_MAP:
      node["type"] = _GEMINI_TYPE_MAP[t]
    for value in node.values():
      _uppercase_types(value)
  elif isinstance(node, list):
    for item in node:
      _uppercase_types(item)
