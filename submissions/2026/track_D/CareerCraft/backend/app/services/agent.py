"""Backward-compatibility shim over ``app.services.agents``.

This module used to host the procedural mission/evaluation logic. The
implementation has moved into per-subagent modules under
``app.services.agents.subagents``; this file now re-exports the same
public names so existing callers and tests continue to work unchanged.

Will be retired in PR-3 once orchestrators are wired into the API layer.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator

from app.core.config import settings
from app.services.agents.base import (
    EvaluationContext,
    FeynmanContext,
    MissionContext,
    invoke_with_fallback,
)
from app.services.agents.llm_io import (
    _is_transient_network_error,  # noqa: F401  (re-exported for tests/back-compat)
    call_llm,
    call_llm_json,
    llm_disabled as _llm_disabled,
    unwrap_to_required_keys as _unwrap_to_required_keys,
)
from app.services.agents.subagents.evaluate import (
    SubmissionEvaluateSubagent,
    build_eval_schema as _build_eval_schema,
    eval_error_fallback as _eval_error_fallback,
    eval_offline_fallback as _eval_offline_fallback,
)
from app.services.agents.subagents.feynman import FeynmanReviewSubagent
from app.services.agents.subagents.spec import (
    MissionSpecSubagent,
    generic_mission_fallback as _generic_mission_fallback,
    mission_from_catalog as _mission_from_spec,
)
from app.services.role_mapping import resolve_role_id
from app.services.role_prompts import get_system_prompt
from app.services.role_replies import get_fallback_reply

logger = logging.getLogger(__name__)

__all__ = [
    "call_llm",
    "call_llm_json",
    "create_mission",
    "evaluate_submission",
    "feynman_review",
    "act_as_role",
    "get_system_prompt",
    "settings",
]


# --------------------------------------------------------------------------- #
# Public façades preserving the legacy procedural signatures.                 #
# --------------------------------------------------------------------------- #


async def create_mission(
    role_id: str,
    difficulty: str,
    task_index: int = 1,
) -> dict[str, Any]:
  """Generate a mission spec; falls back to the generic stub on LLM failure."""
  ctx = MissionContext(
      role_id=role_id,
      difficulty=difficulty,
      task_index=task_index,
      mission_id="",
      user_id="",
  )
  result = await invoke_with_fallback(
      MissionSpecSubagent(), ctx, log_extra={"role_id": role_id},
  )
  return result.payload


async def evaluate_submission(
    submission_text: str,
    mission_description: str,
    career_id: str = "career_data_analyst",
) -> dict[str, Any]:
  """Evaluate a player submission; returns structured feedback + xp gains."""
  ctx = EvaluationContext(
      mission_id="",
      user_id="",
      submission_text=submission_text,
      mission_description=mission_description,
      career_id=career_id,
  )
  result = await invoke_with_fallback(
      SubmissionEvaluateSubagent(), ctx, log_extra={"career_id": career_id},
  )
  return result.payload


async def feynman_review(question: str, answer: str) -> str:
  """Short-form review of a Feynman explanation."""
  ctx = FeynmanContext(mission_id="", user_id="", question=question, answer=answer)
  result = await invoke_with_fallback(FeynmanReviewSubagent(), ctx)
  return result.payload


# --------------------------------------------------------------------------- #
# Role-play streaming                                                         #
# --------------------------------------------------------------------------- #


def _fetch_active_mission(user_id: str) -> Any | None:
  # Local imports to avoid circular dependency at module load time.
  from app.db.session import session_local
  from app.models import orm as models

  db = session_local()
  try:
    return (
        db.query(models.MissionRecord)
        .filter_by(user_id=user_id, status="active")
        .first()
    )
  finally:
    db.close()


def _build_chat_system(role_id: str, active_mission: Any | None) -> str:
  system_inst = get_system_prompt(role_id)
  if not active_mission:
    return system_inst
  return (
      f"{system_inst}\n\n当前玩家正在进行的任务环境信息：\n"
      f"任务标题：{active_mission.title}\n"
      f"任务描述：{active_mission.description}\n"
      f"任务交付物审计要求：{active_mission.delivery_requirements_json}\n\n"
      "在和玩家对话时，请务必关注当前这个任务的背景和要求，"
      "给与贴合任务、有深度、且符合你身份与性格的指导或反馈。"
  )


# Hard cap for streamed role-play replies. Prompt asks for ~80 chars; this is
# a safety net against runaway generations that would block the SSE stream.
_MAX_ROLEPLAY_CHARS = 200


async def act_as_role(
    role_name: str,
    user_input: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
  """Stream a role-played, mission-aware reply char-by-char (typewriter)."""
  role_id = resolve_role_id(role_name)
  active_mission = _fetch_active_mission(user_id)
  mission_id = active_mission.mission_id if active_mission else ""

  response_text = ""
  if not _llm_disabled():
    system_inst = _build_chat_system(role_id, active_mission)
    prompt = (
        f"玩家对你说：“{user_input}”。请结合你的性格、口头禅、背景职责和当前任务背景，"
        f"给出一个有态度、沉浸、极其拟真的简短口头回复（通常不超过80字），不要胡编乱造其他废话。"
    )
    try:
      response_text = await call_llm(prompt=prompt, system=system_inst, json_schema=None)
    except Exception as e:
      logger.warning("LLM chat streaming failed, falling back: %s", e)

  if not response_text:
    response_text = get_fallback_reply(role_id, mission_id, user_input)

  if len(response_text) > _MAX_ROLEPLAY_CHARS:
    response_text = response_text[:_MAX_ROLEPLAY_CHARS] + "…"

  for char in response_text:
    yield char
    await asyncio.sleep(0.04)
