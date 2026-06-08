"""Mission service: orchestrates generation + persistence.

The LLM/artifact pipeline lives in :class:`MissionOrchestrator`; this
module owns the DB writes (career-prefix counting, replacing the active
record, persisting the new row) so the API layer stays thin.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import orm as models
from app.models.schemas import (
    MissionDisplayMetadata,
    MissionGenerateRequest,
    MissionGenerateResponse,
)
from app.services.agents.base import MissionContext
from app.services.orchestrators import MissionOrchestrator
from app.services.skill_catalog import allowed_skills_for, infer_career_id

logger = logging.getLogger(__name__)


_CAREER_PREFIX = {
    "mentor_ying": "mvp_mission_data_",
    "mentor_ling": "mvp_mission_software_",
}
_MISSION_CYCLE = 4
_DEFAULT_REWARD_XP = {
    "easy": 100,
    "medium": 150,
    "hard": 220,
}
_DEFAULT_CRITERIA = [
    "Problem understanding is clear",
    "Deliverables are complete",
    "Recommendations are actionable",
]
_DEFAULT_TASK_DIRECTION = {
    "career_data_analyst": "data-cleaning",
    "career_software_engineer": "bug-fix",
}
_DEFAULT_MISSION_STYLE = "ticket"
_DEFAULT_ESTIMATED_TIME = {
    "easy": "20-30 min",
    "medium": "40-60 min",
    "hard": "60-90 min",
}
_ROLE_AI_LEAD = {
    "mentor_ying": "数据分析主管",
    "mentor_ling": "软件工程导师",
}


def _reward_xp_for(difficulty: str) -> int:
  return _DEFAULT_REWARD_XP.get(difficulty, 150)


def _reward_skills_for(career_id: str) -> list[str]:
  return sorted(allowed_skills_for(career_id))[:3]


def _clean_string(value: Any, fallback: str, *, max_length: int = 800) -> str:
  if not isinstance(value, str):
    value = fallback
  cleaned = value.strip()
  if not cleaned:
    cleaned = fallback.strip()
  return cleaned[:max_length]


def _clean_string_list(
    value: Any,
    fallback: list[str],
    *,
    max_items: int = 6,
    max_item_length: int = 180,
) -> list[str]:
  raw_items = value if isinstance(value, list) else fallback
  cleaned: list[str] = []
  for item in raw_items:
    if not isinstance(item, str):
      continue
    text = item.strip()
    if text:
      cleaned.append(text[:max_item_length])
    if len(cleaned) >= max_items:
      break
  if cleaned:
    return cleaned
  return fallback[:max_items]


def _normalize_display_metadata(
    raw: dict[str, Any],
    *,
    role_id: str,
    difficulty: str,
    description: str,
    delivery_requirements: list[str],
) -> MissionDisplayMetadata:
  objectives = _clean_string_list(
      raw.get("objectives"),
      delivery_requirements,
      max_items=4,
  )
  return MissionDisplayMetadata(
      ai_lead=_clean_string(raw.get("ai_lead"), _ROLE_AI_LEAD.get(role_id, "AI Mission Orchestrator"), max_length=80),
      business_background=_clean_string(
          raw.get("business_background"),
          description,
          max_length=1200,
      ),
      objectives=objectives,
      recommended_skills=_clean_string_list(
          raw.get("recommended_skills"),
          [],
          max_items=6,
      ),
      recommended_resources=_clean_string_list(
          raw.get("recommended_resources"),
          [],
          max_items=6,
      ),
      estimated_time=_clean_string(
          raw.get("estimated_time"),
          _DEFAULT_ESTIMATED_TIME.get(difficulty, "40-60 min"),
          max_length=40,
      ),
  )


def _resolve_task_index(db: Session, user_id: str, role_id: str) -> int:
  """Cycle 1..4 based on how many missions the user finished on this track."""
  prefix = _CAREER_PREFIX.get(role_id, "mvp_mission_software_")
  completed = (
      db.query(models.MissionRecord)
      .filter(
          models.MissionRecord.user_id == user_id,
          models.MissionRecord.status == "completed",
          models.MissionRecord.mission_id.like(f"{prefix}%"),
      )
      .count()
  )
  return (completed % _MISSION_CYCLE) + 1


async def generate_mission(
    request: MissionGenerateRequest,
    db: Session,
    user_id: str,
    orchestrator: MissionOrchestrator,
) -> MissionGenerateResponse:
  """Generate, persist, and return a new mission for ``user_id``."""
  task_index = _resolve_task_index(db, user_id, request.role_id)
  career_id = infer_career_id(role_id=request.role_id)
  task_direction = request.task_direction or _DEFAULT_TASK_DIRECTION.get(career_id)
  mission_style = request.mission_style or _DEFAULT_MISSION_STYLE
  reward_xp = _reward_xp_for(request.difficulty)
  reward_skills = _reward_skills_for(career_id)

  ctx = MissionContext(
      role_id=request.role_id,
      difficulty=request.difficulty,
      task_index=task_index,
      mission_id="",
      user_id=user_id,
      task_direction=task_direction,
      mission_style=mission_style,
  )
  result = await orchestrator.generate(ctx)
  delivery_requirements = _clean_string_list(
      result.delivery_requirements,
      ["Submit a concise task report"],
      max_items=6,
      max_item_length=220,
  )
  evaluation_criteria = _clean_string_list(
      result.evaluation_criteria,
      _DEFAULT_CRITERIA,
      max_items=6,
      max_item_length=220,
  )
  display_metadata = _normalize_display_metadata(
      result.display_metadata,
      role_id=request.role_id,
      difficulty=request.difficulty,
      description=result.description,
      delivery_requirements=delivery_requirements,
  )

  # Abandon any prior active mission so the player has at most one in flight.
  (
      db.query(models.MissionRecord)
      .filter_by(user_id=user_id, status="active")
      .update({"status": "failed"})
  )

  mission_rec = models.MissionRecord(
      user_id=user_id,
      mission_id=result.mission_id,
      career_id=career_id,
      role_id=request.role_id,
      title=result.title,
      description=result.description,
      mock_data_url=result.mock_data_url,
      mock_data_filename=result.mock_data_filename,
      delivery_requirements_json=json.dumps(delivery_requirements),
      difficulty=request.difficulty,
      task_direction=task_direction,
      mission_style=mission_style,
      reward_xp=reward_xp,
      reward_skills_json=json.dumps(reward_skills),
      evaluation_criteria_json=json.dumps(evaluation_criteria),
      display_metadata_json=display_metadata.model_dump_json(),
      status="active",
      feynman_active=False,
  )
  db.add(mission_rec)
  db.commit()

  return MissionGenerateResponse(
      mission_id=result.mission_id,
      career_id=career_id,
      role_id=request.role_id,
      title=result.title,
      description=result.description,
      mock_data_url=result.mock_data_url,
      delivery_requirements=delivery_requirements,
      difficulty=request.difficulty,
      task_direction=task_direction,
      mission_style=mission_style,
      status="active",
      reward_xp=reward_xp,
      reward_skills=reward_skills,
      evaluation_criteria=evaluation_criteria,
      display_metadata=display_metadata,
  )
