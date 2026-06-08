"""Local-filesystem storage adapter for mission artifacts.

The orchestrator depends on the :class:`ArtifactStorage` protocol; the
concrete :class:`LocalArtifactStorage` writes files under
``backend/app/data/generated/`` and exposes them through the
``/mock_data`` ``StaticFiles`` mount declared in :mod:`app.main`.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.paths import generated_dir

logger = logging.getLogger(__name__)


# Mime-type → canonical extension. The artifact subagent constrains the LLM
# to this whitelist; keep both in sync.
MIME_EXTENSIONS: dict[str, str] = {
    "text/csv": ".csv",
    "application/json": ".json",
    "text/markdown": ".md",
    "text/plain": ".txt",
    "text/x-python": ".py",
    "text/x-log": ".log",
}


@dataclass(frozen=True)
class MissionArtifact:
  """Subagent-produced artifact ready for persistence."""

  filename: str
  mime_type: str
  content: str


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize(name: str) -> str:
  """Strip path separators and collapse unsafe characters."""
  base = Path(name).name  # drop any directory component
  cleaned = _SAFE_NAME_RE.sub("_", base).strip("._-")
  return cleaned or "artifact"


class ArtifactStorage(Protocol):
  """Persistence + retrieval contract used by the mission orchestrator."""

  def persist(self, mission_id: str, artifact: MissionArtifact) -> str: ...
  def copy_sample(self, mission_id: str, sample_path: Path) -> str: ...
  def read_text(self, stored_filename: str, max_bytes: int = 8192) -> str: ...
  def build_url(self, stored_filename: str) -> str: ...


class LocalArtifactStorage:
  """Writes artifacts to ``generated_dir()`` and builds public URLs."""

  def __init__(self, base_dir: Path | None = None, public_base: str | None = None) -> None:
    self._base_dir = base_dir or generated_dir()
    self._public_base = (public_base or settings.mock_data_public_base).rstrip("/")
    self._base_dir.mkdir(parents=True, exist_ok=True)

  def persist(self, mission_id: str, artifact: MissionArtifact) -> str:
    expected_ext = MIME_EXTENSIONS.get(artifact.mime_type)
    if expected_ext is None:
      raise ValueError(f"Unsupported mime_type: {artifact.mime_type!r}")

    safe = _sanitize(artifact.filename)
    if not safe.lower().endswith(expected_ext):
      safe = Path(safe).stem + expected_ext

    stored = f"{_sanitize(mission_id)}__{safe}"
    target = self._base_dir / stored
    target.write_text(artifact.content, encoding="utf-8")
    logger.info(
        "artifact.persisted mission_id=%s file=%s bytes=%d",
        mission_id, stored, target.stat().st_size,
    )
    return stored

  def copy_sample(self, mission_id: str, sample_path: Path) -> str:
    if not sample_path.is_file():
      raise FileNotFoundError(f"Sample artifact missing: {sample_path}")
    stored = f"{_sanitize(mission_id)}__{_sanitize(sample_path.name)}"
    target = self._base_dir / stored
    shutil.copyfile(sample_path, target)
    logger.info(
        "artifact.sample_copied mission_id=%s source=%s file=%s",
        mission_id, sample_path.name, stored,
    )
    return stored

  def read_text(self, stored_filename: str, max_bytes: int = 8192) -> str:
    target = self._base_dir / _sanitize(stored_filename)
    if not target.is_file():
      raise FileNotFoundError(f"Artifact not found: {stored_filename}")
    data = target.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="replace")

  def build_url(self, stored_filename: str) -> str:
    return f"{self._public_base}/{stored_filename}"
