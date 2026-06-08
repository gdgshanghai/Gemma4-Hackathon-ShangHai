"""Mission catalog: load static mission specs from JSON and cycle by index."""

from __future__ import annotations

import json
import logging
from functools import cache
from typing import Any

from app.core.paths import data_dir

logger = logging.getLogger(__name__)

# role_id → JSON file name under data/missions/
_ROLE_CATALOG_FILES: dict[str, str] = {
    "mentor_ying": "data_analyst.json",
    "mentor_ling": "software_engineer.json",
}
_DEFAULT_CATALOG_FILE = "software_engineer.json"
_CYCLE_SIZE = 4


@cache
def _load_catalog(file_name: str) -> list[dict[str, Any]]:
  path = data_dir() / "missions" / file_name
  with path.open("r", encoding="utf-8") as f:
    catalog = json.load(f)
  if not isinstance(catalog, list) or not catalog:
    raise ValueError(f"Mission catalog at {path} must be a non-empty JSON array.")
  return catalog


def get_mission_spec(role_id: str, task_index: int) -> dict[str, Any]:
  """Return the mission spec for ``role_id`` at the given 1-based task index.

  Index is cycled within ``[1, _CYCLE_SIZE]``. Unknown roles fall back to the
  software engineer catalog.
  """
  file_name = _ROLE_CATALOG_FILES.get(role_id, _DEFAULT_CATALOG_FILE)
  catalog = _load_catalog(file_name)
  safe_index = ((task_index - 1) % _CYCLE_SIZE) + 1
  # Catalog list is 0-indexed; spec at position safe_index - 1.
  return catalog[safe_index - 1]
