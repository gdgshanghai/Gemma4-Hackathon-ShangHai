"""Mission generation orchestrator: spec → artifact → storage."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.agents.base import (
    MissionContext,
    Subagent,
    invoke_with_fallback,
)
from app.services.storage.artifact_store import ArtifactStorage, MissionArtifact

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MissionGenerationResult:
  """Final payload produced by :class:`MissionOrchestrator`."""

  mission_id: str
  title: str
  description: str
  delivery_requirements: list[str]
  display_metadata: dict[str, Any]
  evaluation_criteria: list[str]
  mock_data_url: str
  mock_data_filename: str
  used_spec_fallback: bool
  used_artifact_fallback: bool


def _storage_key(user_id: str, mission_id: str) -> str:
  """Namespace storage filenames per (user, mission) pair.

  Catalog mission ids (``mvp_mission_data_1`` etc.) are reused across
  users; embedding ``user_id`` in the storage key prevents two players on
  the same mission from clobbering each other's artifact.
  """
  user_part = user_id or "anon"
  return f"{user_part}__{mission_id}"


class MissionOrchestrator:
  """Sequence the spec and artifact subagents, persist the artifact."""

  def __init__(
      self,
      spec_subagent: Subagent[MissionContext, dict[str, Any]],
      artifact_subagent: Subagent[MissionContext, MissionArtifact],
      storage: ArtifactStorage,
  ) -> None:
    self._spec = spec_subagent
    self._artifact = artifact_subagent
    self._storage = storage

  async def generate(self, ctx: MissionContext) -> MissionGenerationResult:
    log_extra = {"role_id": ctx.role_id, "user_id": ctx.user_id}

    spec_result = await invoke_with_fallback(self._spec, ctx, log_extra=log_extra)
    spec_payload = dict(spec_result.payload)
    mission_id = spec_payload.get("mission_id") or ""

    # Mutate ctx in place so the artifact subagent sees the freshly-resolved
    # mission_id and full spec; orchestrator is the only writer of ctx.
    ctx.spec = spec_payload
    ctx.mission_id = mission_id

    artifact_result = await invoke_with_fallback(
        self._artifact, ctx, log_extra={**log_extra, "mission_id": mission_id},
    )
    artifact: MissionArtifact = artifact_result.payload

    key = _storage_key(ctx.user_id, mission_id)
    sample_path = (artifact_result.meta or {}).get("sample_path")
    if artifact_result.used_fallback and sample_path:
      stored = self._storage.copy_sample(key, Path(sample_path))
    else:
      stored = self._storage.persist(key, artifact)

    public_url = self._storage.build_url(stored)
    display_metadata = {
        "business_background": spec_payload.get("business_background"),
        "objectives": spec_payload.get("objectives"),
        "recommended_skills": spec_payload.get("recommended_skills"),
        "recommended_resources": spec_payload.get("recommended_resources"),
        "estimated_time": spec_payload.get("estimated_time"),
    }

    return MissionGenerationResult(
        mission_id=mission_id,
        title=spec_payload["title"],
        description=spec_payload["description"],
        delivery_requirements=list(spec_payload["delivery_requirements"]),
        display_metadata=display_metadata,
        evaluation_criteria=list(spec_payload.get("evaluation_criteria") or []),
        mock_data_url=public_url,
        mock_data_filename=stored,
        used_spec_fallback=spec_result.used_fallback,
        used_artifact_fallback=artifact_result.used_fallback,
    )


__all__ = ["MissionOrchestrator", "MissionGenerationResult"]
