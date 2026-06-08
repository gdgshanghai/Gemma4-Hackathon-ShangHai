"""API endpoints for syncing and updating persistent player profiles, skill trees and missions."""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.llm.parsing import strip_text_artifacts
from app.db.session import get_db
from app.models import orm as models, schemas
from app.services.agents.base import FeynmanContext
from app.services.factory import get_feynman_orchestrator
from app.services.orchestrators import FeynmanOrchestrator
from app.services.storage.artifact_store import LocalArtifactStorage
from app.services.skill_catalog import infer_career_id

logger = logging.getLogger(__name__)
router = APIRouter()

_CAREER_TO_ROLE = {
    "career_data_analyst": "mentor_ying",
    "career_software_engineer": "mentor_ling",
}


def _mission_career_id(mission: models.MissionRecord, user: models.User) -> str:
  return (
      mission.career_id
      or infer_career_id(
          mission_id=mission.mission_id,
          role_id=mission.role_id,
          fallback=user.current_career_id,
      )
  )


def _legacy_display_metadata(mission: models.MissionRecord) -> dict[str, object]:
  metadata = mission.display_metadata
  if metadata:
    return metadata
  return {
      "business_background": mission.description,
      "objectives": mission.delivery_requirements,
      "recommended_skills": [],
      "recommended_resources": [],
      "estimated_time": None,
  }


def _mission_mock_data_url(mission: models.MissionRecord) -> str:
  if mission.mock_data_filename:
    return LocalArtifactStorage().build_url(mission.mock_data_filename)
  return mission.mock_data_url


@router.get(
    "/sync",
    summary="同步玩家全部进度，如果不存在则自动初始化当前玩家",
    response_model=schemas.SyncResponse,
)
async def sync_user_state(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> schemas.SyncResponse:
  """Retrieves or initializes the current player and aggregates full state."""
  user = db.query(models.User).filter_by(id=user_id).first()
  if not user:
    user = models.User(id=user_id, current_career_id="", total_xp=0)
    db.add(user)
    db.commit()
    db.refresh(user)

  skills_orm = db.query(models.SkillProgress).filter_by(user_id=user_id).all()
  skills = [
      schemas.SkillProgressResponse(
          skill_id=s.skill_id,
          level=s.level,
          experience=s.experience,
      )
      for s in skills_orm
  ]

  missions_orm = db.query(models.MissionRecord).filter_by(user_id=user_id).all()
  missions = [
      schemas.MissionRecordResponse(
          mission_id=m.mission_id,
          career_id=_mission_career_id(m, user),
          role_id=m.role_id or _CAREER_TO_ROLE.get(_mission_career_id(m, user)),
          title=m.title,
          description=m.description,
          mock_data_url=_mission_mock_data_url(m),
          delivery_requirements=m.delivery_requirements,
          difficulty=m.difficulty or "medium",
          task_direction=m.task_direction,
          mission_style=m.mission_style,
          reward_xp=m.reward_xp or 150,
          reward_skills=m.reward_skills,
          evaluation_criteria=m.evaluation_criteria,
          display_metadata=_legacy_display_metadata(m),
          status=m.status,
          submission_text=m.submission_text,
          feedback=m.feedback,
          experience_gains=m.experience_gains,
          feynman_active=m.feynman_active,
          feynman_question=m.feynman_question,
          feynman_answer=m.feynman_answer,
          feynman_feedback=m.feynman_feedback,
      )
      for m in missions_orm
  ]

  return schemas.SyncResponse(
      user=schemas.UserProfileResponse(
          id=user.id,
          current_career_id=user.current_career_id,
          total_xp=user.total_xp,
      ),
      skills=skills,
      missions=missions,
  )


@router.post(
    "/career",
    summary="更新当前选中的职业岛屿",
)
async def update_career_island(
    request: schemas.UpdateCareerRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
  """Saves current selected career path to the database."""
  user = db.query(models.User).filter_by(id=user_id).first()
  if not user:
    user = models.User(id=user_id, current_career_id=request.career_id, total_xp=0)
    db.add(user)
  else:
    user.current_career_id = request.career_id
  db.commit()
  return {"status": "success", "current_career_id": request.career_id}


@router.post(
    "/skills/upgrade",
    summary="手动升级/点亮技能节点并保存其经验值",
)
async def upgrade_user_skill(
    request: schemas.UpgradeSkillRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
  """Upserts or updates level / experience of user skill progress."""
  skill = (
      db.query(models.SkillProgress)
      .filter_by(user_id=user_id, skill_id=request.skill_id)
      .first()
  )
  if not skill:
    skill = models.SkillProgress(
        user_id=user_id,
        skill_id=request.skill_id,
        level=request.level,
        experience=request.experience,
    )
    db.add(skill)
  else:
    skill.level = request.level
    skill.experience = request.experience
  db.commit()
  return {
      "status": "success",
      "skill_id": request.skill_id,
      "level": request.level,
      "experience": request.experience,
  }


@router.post(
    "/feynman/submit",
    summary="提交费曼挑战回答并进行大模型/仿真打分",
    response_model=schemas.FeynmanSubmitResponse,
)
async def submit_feynman_challenge(
    request: schemas.FeynmanSubmitRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    orchestrator: FeynmanOrchestrator = Depends(get_feynman_orchestrator),
) -> schemas.FeynmanSubmitResponse:
  """Handles Feynman challenge submission, updates DB, and triggers review."""
  mission = (
      db.query(models.MissionRecord)
      .filter_by(user_id=user_id, mission_id=request.mission_id)
      .first()
  )
  if not mission:
    raise HTTPException(status_code=404, detail="Active mission not found for this user.")

  if mission.status != "active":
    raise HTTPException(status_code=409, detail="Mission is not active.")

  if not mission.feynman_question:
    raise HTTPException(status_code=400, detail="Feynman challenge is not active for this mission.")

  ctx = FeynmanContext(
      mission_id=request.mission_id,
      user_id=user_id,
      question=mission.feynman_question,
      answer=request.answer,
  )
  feedback_text = await orchestrator.review(ctx)

  mission.feynman_answer = request.answer
  mission.feynman_feedback = feedback_text
  mission.feynman_active = False
  mission.status = "completed"

  db.commit()

  return schemas.FeynmanSubmitResponse(
      status="success",
      feedback=strip_text_artifacts(feedback_text),
      mission_status="completed",
  )
