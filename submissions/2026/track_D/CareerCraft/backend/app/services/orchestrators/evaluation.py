"""Submission evaluation orchestrator: optional artifact context → eval."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.services.agents.base import (
    EvaluationContext,
    Subagent,
    invoke_with_fallback,
)
from app.services.storage.artifact_store import ArtifactStorage

logger = logging.getLogger(__name__)


class EvaluationOrchestrator:
  """Hydrate evaluation context with the stored artifact, then evaluate."""

  def __init__(
      self,
      eval_subagent: Subagent[EvaluationContext, dict[str, Any]],
      storage: ArtifactStorage,
  ) -> None:
    self._eval = eval_subagent
    self._storage = storage

  async def evaluate(
      self,
      ctx: EvaluationContext,
      *,
      mock_data_filename: str | None = None,
  ) -> dict[str, Any]:
    if (
        settings.eval_use_artifact_context
        and mock_data_filename
        and ctx.artifact_excerpt is None
    ):
      try:
        ctx.artifact_excerpt = self._storage.read_text(mock_data_filename)
      except FileNotFoundError:
        # Missing files are tolerable -- the LLM still has the submission
        # text and mission description. Logging here is sufficient.
        logger.warning(
            "evaluation: artifact missing on disk, skipping excerpt: %s",
            mock_data_filename,
        )

    result = await invoke_with_fallback(
        self._eval, ctx,
        log_extra={"career_id": ctx.career_id, "mission_id": ctx.mission_id},
    )
    return result.payload


__all__ = ["EvaluationOrchestrator"]
