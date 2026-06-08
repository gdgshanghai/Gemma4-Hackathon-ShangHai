"""统一饮食决策路由"""

from fastapi import APIRouter
from models.meal_decision import MealDecisionRequest, MealDecisionResponse
from services.meal_decision_flow import meal_decision_flow

router = APIRouter()


@router.post("/decision", response_model=MealDecisionResponse)
async def meal_decision(request: MealDecisionRequest):
    """
    统一的饮食决策入口

    支持两种触发方式：
    1. user_initiated - 用户主动触发（"我想吃麦当劳"）
    2. agent_initiated - 系统主动触发（饭点提醒）

    所有入口都进入同一个 MealDecisionFlow
    """
    return await meal_decision_flow.execute(request)


@router.post("/decision/remind", response_model=MealDecisionResponse)
async def remind_meal(user_id: str = "demo-user"):
    """
    系统主动提醒入口

    检查用户状态，如果需要提醒，生成提醒卡
    """
    request = MealDecisionRequest(
        user_id=user_id,
        trigger_type="agent_initiated",
        scenario="missed_meal_reminder",
        trigger_reason="系统检测到需要提醒",
        suggested_action="suggest_auto_draft",
    )
    return await meal_decision_flow.execute(request)
