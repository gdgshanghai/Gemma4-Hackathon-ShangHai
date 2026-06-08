"""稳一下模式路由 — 三重余额：热量余额、金钱余额、欲望余额"""

from fastapi import APIRouter
from models.balance_mode import balance_mode
from services.budget_service import BudgetService

router = APIRouter()


@router.get("/balance")
async def get_balance(user_id: str = "demo-user", mood: str = "normal"):
    """获取三重余额状态"""
    from api.profile_routes import get_profile

    user = await get_profile(user_id)
    budget_service = BudgetService()
    today_meals = await budget_service.get_today_meals(user_id)

    return balance_mode.calculate_balance(user, today_meals, mood)


@router.get("/balance/check")
async def check_balance_for_meal(user_id: str = "demo-user", meal_type: str = "dinner", mood: str = "normal"):
    """检查当前余额是否适合点餐"""
    from api.profile_routes import get_profile

    user = await get_profile(user_id)
    budget_service = BudgetService()
    today_meals = await budget_service.get_today_meals(user_id)

    balance = balance_mode.calculate_balance(user, today_meals, mood)

    # 判断是否建议点餐
    can_order = balance.overall_status in ["放心吃", "稳一下"]
    warning = None

    if not can_order:
        warning = f"当前状态：{balance.overall_status}。{balance.suggestion}"

    return {
        "can_order": can_order,
        "balance": balance,
        "warning": warning,
        "suggestion": balance.suggestion,
    }
