import json
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.services.agents.base import EvaluationContext
from app.services.orchestrators import EvaluationOrchestrator
from app.services.skill_catalog import allowed_skills_for, infer_career_id
from app.models import orm as models
from app.models.schemas import (
    SubmissionEvaluateRequest,
    SubmissionEvaluateResponse,
)

logger = logging.getLogger(__name__)


async def evaluate_user_submission(
    request: SubmissionEvaluateRequest,
    db: Session,
    user_id: str,
    orchestrator: EvaluationOrchestrator,
) -> SubmissionEvaluateResponse:
  """Orchestrates AI peer review, updates DB records, and handles Feynman triggers."""
  # Resolve career_id *before* evaluation so the LLM sees the right whitelist.
  user = db.query(models.User).filter_by(id=user_id).first()
  mission = (
      db.query(models.MissionRecord)
      .filter_by(user_id=user_id, mission_id=request.mission_id)
      .first()
  )
  if not mission:
    raise HTTPException(status_code=404, detail="Active mission not found for this user.")
  if mission.status != "active":
    raise HTTPException(status_code=409, detail="Mission is not active.")

  career_id = infer_career_id(
      mission_id=request.mission_id,
      role_id=mission.role_id,
      fallback=mission.career_id or (user.current_career_id if user else None),
  )
  allowed = allowed_skills_for(career_id)
  active_mission = mission
  ctx = EvaluationContext(
      mission_id=request.mission_id,
      user_id=user_id,
      submission_text=request.submission_text,
      career_id=career_id,
      mission_description=active_mission.description,
  )
  payload = await orchestrator.evaluate(
      ctx,
      mock_data_filename=(
          active_mission.mock_data_filename if active_mission else None
      ),
  )

  # Drop any skill keys outside this career's whitelist before the response
  # and DB writes diverge.
  raw_gains = payload.get("experience_gains") or {}
  unknown = sorted(set(raw_gains) - allowed)
  if unknown:
    logger.warning(
        "Dropping experience_gains keys outside %s whitelist: %s",
        career_id, unknown,
    )
  payload["experience_gains"] = {k: v for k, v in raw_gains.items() if k in allowed}

  response = SubmissionEvaluateResponse(**payload)
  validated_gains: dict[str, int] = response.experience_gains.root

  active_mission.submission_text = request.submission_text
  active_mission.feedback = response.feedback
  active_mission.experience_gains_json = json.dumps(validated_gains)

  if response.trigger_feynman_challenge:
    active_mission.feynman_active = True
    active_mission.feynman_question = response.feynman_question
  else:
    active_mission.status = "completed"
    active_mission.feynman_active = False

  if not user:
    user = models.User(id=user_id, current_career_id=career_id, total_xp=0)
    db.add(user)

  for skill_id, amount in validated_gains.items():
    if amount <= 0:
      continue
    user.total_xp += amount
    skill_prog = (
        db.query(models.SkillProgress)
        .filter_by(user_id=user_id, skill_id=skill_id)
        .first()
    )
    if not skill_prog:
      skill_prog = models.SkillProgress(
          user_id=user_id, skill_id=skill_id, level=0, experience=amount,
      )
      db.add(skill_prog)
    else:
      skill_prog.experience += amount

  db.commit()
  return response.model_copy(update={
      "mission_status": active_mission.status,
      "feynman_active": active_mission.feynman_active,
  })

