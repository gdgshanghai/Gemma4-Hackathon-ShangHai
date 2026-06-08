"""Recommendation endpoint — powered by SupervisorAgent, supports dual mode."""

import uuid
from fastapi import APIRouter
from models.recommendation import RecommendationResponse, RecommendationPlan, MenuItem, OrderDraft, OrderConfirmation
from models.quick_profile import QuickProfile
from models.user_profile import UserProfile, Goal
from providers.factory import get_provider
from agents.supervisor_agent import SupervisorAgent
from services.budget_service import BudgetService
from services.memory_service import MemoryService
from services.active_plan_service import active_plan_service
from services.conversation_service import conversation_service

router = APIRouter()


def _quick_profile_to_user_profile(quick: QuickProfile) -> UserProfile:
    """将快速模式档案转换为完整档案（用于 Agent 计算）"""
    goal_map = {
        "lose_weight": Goal.LOSE_WEIGHT,
        "cheap": Goal.SAVE_MONEY,
        "satisfying": Goal.MAINTAIN,
        "fast": Goal.MAINTAIN,
        "balanced": Goal.MAINTAIN,
    }
    return UserProfile(
        user_id="quick-user",
        name="快速用户",
        goal=goal_map.get(quick.meal_goal.value, Goal.MAINTAIN),
        daily_budget=quick.budget_limit,
        allergies=quick.allergies,
        mode="quick",
    )


@router.post("/recommend", response_model=RecommendationResponse)
async def get_recommendation(body: dict):
    """
    Main recommendation endpoint.
    Body: {
        user_id, message,
        mode: "long_term" | "quick",
        quick_profile: { meal_goal, budget_limit, hunger_level, craving_level, allergies, mood },
        context: { time_pressure, mood, meal_type }
    }
    """
    from api.profile_routes import get_profile

    mode = body.get("mode", "long_term")
    message = body.get("message", "")
    ctx = body.get("context", {})

    # 根据模式获取用户档案
    if mode == "quick" and body.get("quick_profile"):
        quick = QuickProfile(**body["quick_profile"])
        user = _quick_profile_to_user_profile(quick)
        ctx["mood"] = quick.mood
        ctx["hunger_level"] = quick.hunger_level
        ctx["craving_level"] = quick.craving_level
    else:
        user_id = body.get("user_id", "demo-user")
        user = await get_profile(user_id)

    # 通过 Provider 获取菜单
    provider = await get_provider()
    items = await provider.list_items()
    candidates = [
        {
            "name": i.name,
            "item_code": i.item_code,
            "category": i.category,
            "price": i.price,
            "calories": i.calories,
            "protein": i.protein,
            "fat": i.fat,
            "carbohydrate": i.carbohydrate,
            "sodium": i.sodium,
            "tags": i.tags,
        }
        for i in items
    ]

    # Build context for SupervisorAgent
    context = {
        "user": user,
        "candidates": candidates,
        "meal_type": ctx.get("meal_type", "dinner"),
        "mood": ctx.get("mood", "normal"),
        "time_pressure": ctx.get("time_pressure", "normal"),
        "message": message,
        "mode": mode,
        "budget_service": BudgetService(),
        "memory_service": MemoryService(),
    }

    # 记录对话
    await conversation_service.add_message(user.user_id, "user", message)

    # Run SupervisorAgent
    supervisor = SupervisorAgent()
    result = await supervisor.run(context)

    # 记录助手回复
    await conversation_service.add_message(user.user_id, "assistant", result.summary)

    # 为每个方案创建 ActivePlan
    for plan in result.plans:
        active_plan = await active_plan_service.create_plan(
            user_id=user.user_id,
            title=plan.title,
            mode=plan.mode,
            items=plan.items,
            reasons=plan.pros,
            tradeoffs=plan.cons,
        )
        plan.id = active_plan.plan_id  # 关联 plan_id

    return result


@router.post("/order/draft", response_model=dict)
async def create_order_draft(draft: OrderDraft):
    """Create an order draft (no real MCP call)."""
    provider = await get_provider()
    price_info = await provider.calculate_price([i.item_code for i in draft.items])
    return {
        "draft_id": str(uuid.uuid4())[:8],
        "items": price_info.get("items", []),
        "total_price": price_info.get("total_price", 0),
        "status": "draft",
    }


@router.post("/order/confirm", response_model=OrderConfirmation)
async def confirm_order(draft: OrderDraft):
    """Confirm order — uses Provider."""
    provider = await get_provider()
    item_codes = [i.item_code for i in draft.items]
    draft_result = await provider.create_order_draft(item_codes)
    result = await provider.confirm_order(draft_result.get("draft_id", ""), True)

    # Auto-record meal after order confirmation
    try:
        from api.meal_routes import record_meal_internal
        from models.meal_record import MealRecord
        from datetime import datetime
        import logging
        logger = logging.getLogger(__name__)

        items_data = result["items"]
        logger.info(f"Recording meal with {len(items_data)} items, total_price={result['total_price']}")
        meal = MealRecord(
            user_id=draft.user_id,
            meal_type="dinner",
            items=items_data,
            total_price=result["total_price"],
            total_calories=sum(i.get("calories", 0) for i in items_data),
            total_protein=sum(i.get("protein", 0) for i in items_data),
            total_fat=sum(i.get("fat", 0) for i in items_data),
            total_carbs=sum(i.get("carbohydrate", 0) for i in items_data),
            total_sodium=sum(i.get("sodium", 0) for i in items_data),
            plan_mode="manual",
            timestamp=datetime.now(),
        )
        record_meal_internal(meal)
        logger.info("Meal recorded successfully")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to record meal: {e}")

    return OrderConfirmation(
        order_id=result["order_id"],
        status=result["status"],
        message=result["message"],
        is_mock=result["is_mock"],
        items=[MenuItem(**i) for i in result["items"]],
        total_price=result["total_price"],
    )
