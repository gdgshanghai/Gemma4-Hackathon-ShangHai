"""Feynman review orchestrator: trivial single-stage flow."""

from __future__ import annotations

import logging

from app.services.agents.base import (
    FeynmanContext,
    Subagent,
    invoke_with_fallback,
)

logger = logging.getLogger(__name__)


class FeynmanOrchestrator:
  """Wrap a single Feynman review subagent invocation."""

  def __init__(self, feynman_subagent: Subagent[FeynmanContext, str]) -> None:
    self._feynman = feynman_subagent

  async def review(self, ctx: FeynmanContext) -> str:
    result = await invoke_with_fallback(
        self._feynman, ctx,
        log_extra={"mission_id": ctx.mission_id, "user_id": ctx.user_id},
    )
    return result.payload


__all__ = ["FeynmanOrchestrator"]
