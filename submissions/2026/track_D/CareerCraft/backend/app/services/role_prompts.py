"""Role system-prompt loader.

Each role is backed by a markdown file under
``docs/prompts/system_prompts/<role_id>.md``. Missing files fall back to a
generic mentor string with a warning, so a single missing asset never breaks
the call chain.
"""

from __future__ import annotations

import logging
from functools import cache

from app.core.paths import docs_dir

logger = logging.getLogger(__name__)

ROLE_PROMPT_FILES: dict[str, str] = {
    "mentor_ling": "mentor_ling.md",
    "mentor_ying": "mentor_ying.md",
    "pm_amy": "pm_amy.md",
    "colleague_marketing": "colleague_marketing.md",
    "colleague_operations": "colleague_operations.md",
    "stakeholder_sales": "stakeholder_sales.md",
    "stakeholder_product": "stakeholder_product.md",
}

_GENERIC_FALLBACK = (
    "你是一名专业的 AI 职业导师。旨在通过实战任务和互动对话，指导并帮助玩家提升其专业技能。"
)


@cache
def get_system_prompt(role_id: str) -> str:
  """Return the markdown system prompt for ``role_id`` (cached)."""
  file_name = ROLE_PROMPT_FILES.get(role_id)
  if not file_name:
    logger.warning("Unknown role_id %r; using generic system prompt.", role_id)
    return _GENERIC_FALLBACK

  prompt_path = docs_dir() / "prompts" / "system_prompts" / file_name
  try:
    return prompt_path.read_text(encoding="utf-8")
  except FileNotFoundError:
    logger.warning("System prompt not found: %s; using generic fallback.", prompt_path)
    return _GENERIC_FALLBACK
  except OSError:
    logger.exception("Failed reading system prompt at %s", prompt_path)
    return _GENERIC_FALLBACK
