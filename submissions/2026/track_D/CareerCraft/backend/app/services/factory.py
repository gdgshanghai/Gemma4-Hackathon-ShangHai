"""Composition root for the agent layer.

Wires concrete subagents + storage into orchestrators. Endpoints depend on
these factories via FastAPI ``Depends``; tests can override the providers
through ``app.dependency_overrides``.
"""

from __future__ import annotations

from functools import lru_cache

from app.services.agents.subagents.evaluate import SubmissionEvaluateSubagent
from app.services.agents.subagents.feynman import FeynmanReviewSubagent
from app.services.agents.subagents.spec import MissionSpecSubagent
from app.services.agents.subagents.artifact import MissionArtifactSubagent
from app.services.orchestrators import (
    EvaluationOrchestrator,
    FeynmanOrchestrator,
    MissionOrchestrator,
)
from app.services.storage.artifact_store import (
    ArtifactStorage,
    LocalArtifactStorage,
)


@lru_cache(maxsize=1)
def get_artifact_storage() -> ArtifactStorage:
  """Process-wide singleton; storage is stateless and thread-safe."""
  return LocalArtifactStorage()


def get_mission_orchestrator() -> MissionOrchestrator:
  return MissionOrchestrator(
      spec_subagent=MissionSpecSubagent(),
      artifact_subagent=MissionArtifactSubagent(),
      storage=get_artifact_storage(),
  )


def get_evaluation_orchestrator() -> EvaluationOrchestrator:
  return EvaluationOrchestrator(
      eval_subagent=SubmissionEvaluateSubagent(),
      storage=get_artifact_storage(),
  )


def get_feynman_orchestrator() -> FeynmanOrchestrator:
  return FeynmanOrchestrator(feynman_subagent=FeynmanReviewSubagent())


__all__ = [
    "get_artifact_storage",
    "get_mission_orchestrator",
    "get_evaluation_orchestrator",
    "get_feynman_orchestrator",
]
