"""Profile routes — 档案管理"""

import json
from pathlib import Path
from fastapi import APIRouter
from models.user_profile import UserProfile
from models.quick_profile import QuickProfile
from services.db_service import db_service

router = APIRouter()

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_demo_profile() -> dict:
    """从 JSON 加载 demo 用户数据"""
    path = _DATA_DIR / "demo_user.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/demo/profile", response_model=UserProfile)
async def get_demo_profile():
    """加载 demo 用户档案"""
    user = await db_service.get_user("demo-user")
    if not user:
        # 从 JSON 加载 demo 用户并创建
        demo_data = _load_demo_profile()
        user = await db_service.create_user(demo_data)

    return UserProfile(
        user_id=user.user_id,
        name=user.name,
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        age=user.age,
        sex=user.sex,
        goal=user.goal,
        activity_level=user.activity_level,
        daily_budget=user.daily_budget,
        weekly_budget=user.weekly_budget,
        weekly_indulgence_allowance=user.weekly_indulgence_allowance,
        taste_preferences=user.taste_preferences or [],
        allergies=user.allergies or [],
        dislikes=user.dislikes or [],
        preferred_tone=user.preferred_tone,
        meal_schedule=user.meal_schedule or {},
        onboarding_complete=bool(user.onboarding_complete),
        mode=user.mode,
    )


@router.get("/profile", response_model=UserProfile)
async def get_profile(user_id: str = "demo-user"):
    """获取用户档案"""
    user = await db_service.get_user(user_id)
    if not user:
        # 如果不存在，创建一个默认用户
        demo_data = _load_demo_profile()
        demo_data["user_id"] = user_id
        user = await db_service.create_user(demo_data)

    return UserProfile(
        user_id=user.user_id,
        name=user.name,
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        age=user.age,
        sex=user.sex,
        goal=user.goal,
        activity_level=user.activity_level,
        daily_budget=user.daily_budget,
        weekly_budget=user.weekly_budget,
        weekly_indulgence_allowance=user.weekly_indulgence_allowance,
        taste_preferences=user.taste_preferences or [],
        allergies=user.allergies or [],
        dislikes=user.dislikes or [],
        preferred_tone=user.preferred_tone,
        meal_schedule=user.meal_schedule or {},
        onboarding_complete=bool(user.onboarding_complete),
        mode=user.mode,
    )


@router.post("/profile", response_model=UserProfile)
async def save_profile(profile: UserProfile):
    """保存用户档案"""
    user = await db_service.get_user(profile.user_id)
    if user:
        # 更新
        await db_service.update_user(profile.user_id, profile.model_dump())
    else:
        # 创建
        await db_service.create_user(profile.model_dump())

    return profile


@router.post("/profile/reset")
async def reset_profile(body: dict):
    """重置用户档案"""
    user_id = body.get("user_id", "demo-user")
    await db_service.delete_user(user_id)
    return {"success": True, "message": "档案已重置"}


@router.post("/profile/quick", response_model=QuickProfile)
async def save_quick_profile(quick: QuickProfile):
    """保存快速模式档案（不持久化，仅返回）"""
    return quick
