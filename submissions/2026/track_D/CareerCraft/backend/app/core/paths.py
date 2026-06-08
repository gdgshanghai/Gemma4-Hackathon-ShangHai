"""Repository-root and shared asset path helpers."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from app.core.config import settings

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
BACKEND_ROOT: Path = Path(__file__).resolve().parents[2]


@cache
def docs_dir() -> Path:
  """Locate the repository ``docs/`` directory.

  Honors ``settings.docs_dir`` when set; otherwise resolves relative to the
  repository root.
  """
  if settings.docs_dir:
    return Path(settings.docs_dir).expanduser().resolve()
  return REPO_ROOT / "docs"


@cache
def data_dir() -> Path:
  """Locate the bundled ``backend/app/data`` directory."""
  return BACKEND_ROOT / "app" / "data"


@cache
def generated_dir() -> Path:
  """Directory where dynamically generated mission artifacts are written.

  Created on first access so the ``StaticFiles`` mount in ``app.main`` does
  not raise on a fresh checkout.
  """
  d = data_dir() / "generated"
  d.mkdir(parents=True, exist_ok=True)
  return d


@cache
def samples_dir() -> Path:
  """Directory holding fallback artifact samples shipped with the catalog."""
  d = data_dir() / "missions" / "samples"
  d.mkdir(parents=True, exist_ok=True)
  return d
