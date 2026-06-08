"""仪表盘路由 — 今日饮食状态概览"""

from fastapi import APIRouter
from models.user_profile import UserProfile
from services.dashboard_service import dashboard_service

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(user_id: str = "demo-user"):
    """获取今日仪表盘数据"""
    from api.profile_routes import get_profile

    user = await get_profile(user_id)
    return await dashboard_service.get_today_dashboard(user)


@router.get("/dashboard/reminders")
async def get_reminders(user_id: str = "demo-user"):
    """获取饭点提醒"""
    from api.profile_routes import get_profile

    user = await get_profile(user_id)
    dashboard = await dashboard_service.get_today_dashboard(user)

    reminders = []
    suggestion = dashboard.get("next_meal_suggestion", {})

    if suggestion.get("meal_type") and suggestion.get("urgency") != "none":
        meal_type = suggestion["meal_type"]
        urgency = suggestion["urgency"]

        meal_cn = {
            "breakfast": "早餐",
            "lunch": "午餐",
            "dinner": "晚餐",
            "snack": "加餐",
        }.get(meal_type, meal_type)

        if urgency == "high":
            reminders.append({
                "type": "meal_overdue",
                "meal_type": meal_type,
                "message": f"已过{meal_cn}时间，建议尽快用餐",
                "suggestion": suggestion,
            })
        else:
            reminders.append({
                "type": "meal_upcoming",
                "meal_type": meal_type,
                "message": f"快到{meal_cn}时间了",
                "suggestion": suggestion,
            })

    # 营养缺口提醒
    nutrition = dashboard.get("nutrition", {})
    if nutrition.get("gap", 0) > 500:
        reminders.append({
            "type": "calorie_gap",
            "message": f"今日热量缺口较大（{nutrition['gap']}千卡），注意补充",
        })

    # 预算提醒
    budget = dashboard.get("budget", {})
    if budget.get("remaining", 0) < 15:
        reminders.append({
            "type": "budget_low",
            "message": f"今日预算仅剩 ¥{budget['remaining']}，建议选择性价比高的选项",
        })

    return {
        "reminders": reminders,
        "dashboard": dashboard,
    }
