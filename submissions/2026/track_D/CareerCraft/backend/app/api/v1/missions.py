from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models import schemas
from app.services import eval as eval_service
from app.services import mission as mission_service
from app.services.factory import (
    get_evaluation_orchestrator,
    get_mission_orchestrator,
)
from app.services.orchestrators import (
    EvaluationOrchestrator,
    MissionOrchestrator,
)

router = APIRouter()


@router.post(
    "/generate",
    summary="动态创建匹配难度与角色的职业任务",
    response_model=schemas.MissionGenerateResponse,
)
async def generate_new_mission(
    request: schemas.MissionGenerateRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    orchestrator: MissionOrchestrator = Depends(get_mission_orchestrator),
) -> schemas.MissionGenerateResponse:
  """Dispatches creation workflow delegating to the mission orchestrator."""
  return await mission_service.generate_mission(request, db, user_id, orchestrator)


@router.post(
    "/evaluate",
    summary="提交报告并获得多维结构化打分与经验反馈",
    response_model=schemas.SubmissionEvaluateResponse,
)
async def evaluate_mission_submission(
    request: schemas.SubmissionEvaluateRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    orchestrator: EvaluationOrchestrator = Depends(get_evaluation_orchestrator),
) -> schemas.SubmissionEvaluateResponse:
  """Processes submission evaluating quality and checking Feynman criteria."""
  return await eval_service.evaluate_user_submission(
      request, db, user_id, orchestrator,
  )

