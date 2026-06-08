"""Shared agent abstractions: protocol, contexts, results, error type.

These types are deliberately minimal. They define a uniform contract so
orchestrators can sequence heterogeneous subagents without knowing which
LLM provider, prompt, or fallback strategy each one uses.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Generic, Iterator, Protocol, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
CtxT = TypeVar("CtxT", contravariant=True)


class SubagentError(Exception):
  """Raised by a subagent when it cannot produce a valid payload.

  Crossing this single failure type is what lets orchestrators decide
  whether to fall back, propagate, or retry without coupling to the
  internal cause (LLM error, schema violation, oversize, etc.).
  """


@dataclass
class SubagentResult(Generic[T]):
  """Uniform return shape: payload + observability metadata."""

  payload: T
  used_fallback: bool = False
  elapsed_ms: int = 0
  meta: dict[str, Any] = field(default_factory=dict)


class Subagent(Protocol[CtxT, T]):
  """A single LLM-driven (or mocked) production stage.

  Implementations must:
  - Raise :class:`SubagentError` (only) when ``run`` cannot honor its
    schema; orchestrator's ``_invoke`` translates that into a fallback.
  - Have a ``fallback`` that always succeeds and never raises.
  """

  name: str

  async def run(self, ctx: CtxT) -> SubagentResult[T]: ...
  async def fallback(self, ctx: CtxT) -> SubagentResult[T]: ...


@contextmanager
def stopwatch() -> Iterator[Callable[[], int]]:
  """Yield a closure returning elapsed milliseconds since enter."""
  start = time.perf_counter()
  yield lambda: int((time.perf_counter() - start) * 1000)


async def invoke_with_fallback(
    subagent: Subagent[CtxT, T],
    ctx: CtxT,
    *,
    log_extra: dict[str, Any] | None = None,
) -> SubagentResult[T]:
  """Run ``subagent.run(ctx)``; on :class:`SubagentError` call ``fallback``.

  Emits one structured log line per stage covering both paths.
  """
  extra = dict(log_extra or {})
  try:
    result = await subagent.run(ctx)
    logger.info(
        "subagent.ok name=%s elapsed_ms=%d used_fallback=%s extra=%s",
        subagent.name, result.elapsed_ms, result.used_fallback, extra,
    )
    return result
  except SubagentError as e:
    logger.warning(
        "subagent.fallback name=%s reason=%s extra=%s",
        subagent.name, e, extra,
    )
    result = await subagent.fallback(ctx)
    result.used_fallback = True
    return result


# --------------------------------------------------------------------------- #
# Per-flow context dataclasses                                                #
# --------------------------------------------------------------------------- #


@dataclass
class MissionContext:
  """State carried through the mission-generation pipeline."""

  role_id: str
  difficulty: str
  task_index: int
  mission_id: str
  user_id: str
  task_direction: str | None = None
  mission_style: str | None = None
  spec: dict[str, Any] | None = None  # populated after MissionSpecSubagent runs


@dataclass
class EvaluationContext:
  """State carried through the submission-evaluation pipeline."""

  mission_id: str
  user_id: str
  submission_text: str
  career_id: str
  mission_description: str
  artifact_excerpt: str | None = None


@dataclass
class FeynmanContext:
  """State carried through the Feynman-review pipeline."""

  mission_id: str
  user_id: str
  question: str
  answer: str


__all__ = [
    "Subagent",
    "SubagentError",
    "SubagentResult",
    "MissionContext",
    "EvaluationContext",
    "FeynmanContext",
    "invoke_with_fallback",
    "stopwatch",
]
