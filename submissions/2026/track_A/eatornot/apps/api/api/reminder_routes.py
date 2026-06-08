"""饭点提醒路由"""

from fastapi import APIRouter
from services.reminder_service import reminder_service

router = APIRouter()


@router.get("/reminders")
async def get_reminders(user_id: str = "demo-user"):
    """获取当前提醒"""
    reminders = await reminder_service.check_reminders(user_id)
    return {
        "reminders": [reminder_service.build_reminder_card(r) for r in reminders],
        "count": len(reminders),
    }


@router.post("/reminders/{reminder_id}/accept")
async def accept_reminder(reminder_id: str, user_id: str = "demo-user"):
    """接受提醒，进入 MealDecisionFlow"""
    from models.meal_decision import MealDecisionRequest
    from services.meal_decision_flow import meal_decision_flow

    request = MealDecisionRequest(
        user_id=user_id,
        trigger_type="agent_initiated",
        scenario="missed_meal_reminder",
        trigger_reason=f"用户接受提醒 {reminder_id}",
        suggested_action="build_order_draft",
    )
    return await meal_decision_flow.execute(request)


@router.post("/reminders/{reminder_id}/snooze")
async def snooze_reminder(reminder_id: str, minutes: int = 30):
    """稍后提醒"""
    return {
        "status": "snoozed",
        "reminder_id": reminder_id,
        "snooze_minutes": minutes,
        "message": f"将在 {minutes} 分钟后再次提醒",
    }


@router.post("/reminders/{reminder_id}/dismiss")
async def dismiss_reminder(reminder_id: str):
    """忽略提醒"""
    return {
        "status": "dismissed",
        "reminder_id": reminder_id,
        "message": "已忽略此提醒",
    }
