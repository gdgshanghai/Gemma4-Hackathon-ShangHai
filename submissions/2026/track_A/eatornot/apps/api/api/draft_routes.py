"""自动搭配订单草稿路由"""

from fastapi import APIRouter
from services.auto_draft_service import auto_draft_service

router = APIRouter()


@router.get("/draft/auto")
async def get_auto_draft(user_id: str = "demo-user", meal_type: str = None):
    """获取自动搭配的订单草稿"""
    from api.profile_routes import get_profile

    user = await get_profile(user_id)
    return await auto_draft_service.generate_draft(user, meal_type)


@router.post("/draft/auto/confirm")
async def confirm_auto_draft(draft: dict):
    """确认自动搭配的订单草稿"""
    from api.recommend_routes import confirm_order
    from models.recommendation import OrderDraft, MenuItem

    # 转换为 OrderDraft
    items = [MenuItem(**i) for i in draft.get("items", [])]
    order_draft = OrderDraft(
        user_id=draft.get("user_id", "demo-user"),
        plan_id=draft.get("draft_id", ""),
        items=items,
        estimated_price=draft.get("total_price", 0),
        estimated_calories=draft.get("nutrition", {}).get("calories", 0),
    )

    return await confirm_order(order_draft)
