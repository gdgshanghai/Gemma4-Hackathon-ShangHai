"""Offline fallback replies for ``act_as_role`` when the LLM is unavailable."""

from __future__ import annotations

import json
import logging
from functools import cache
from typing import Any

from app.core.paths import data_dir

logger = logging.getLogger(__name__)

_GENERIC_FALLBACK = "收到关于这个任务的信息。让我们共同配合推进它！"


@cache
def _load_replies() -> dict[str, dict[str, str]]:
  path = data_dir() / "fallback_replies.json"
  with path.open("r", encoding="utf-8") as f:
    data: Any = json.load(f)
  if not isinstance(data, dict):
    raise ValueError(f"Fallback replies at {path} must be a JSON object.")
  return data


def get_fallback_reply(role_id: str, mission_id: str, user_input: str) -> str:
  """Return a hand-crafted reply for ``role_id`` matching the active mission.

  Mission-specific entry wins; otherwise the role's ``default`` template (which
  may contain ``{user_input}``) is rendered; otherwise a generic string.
  """
  replies = _load_replies()
  role_replies = replies.get(role_id, {})

  if mission_id and mission_id in role_replies:
    return role_replies[mission_id]

  template = role_replies.get("default", _GENERIC_FALLBACK)
  try:
    return template.format(user_input=user_input)
  except (KeyError, IndexError):
    return template
