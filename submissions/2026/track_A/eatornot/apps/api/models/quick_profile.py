from pydantic import BaseModel, Field
from enum import Enum


class MealGoal(str, Enum):
    LOSE_WEIGHT = "lose_weight"
    CHEAP = "cheap"
    SATISFYING = "satisfying"
    FAST = "fast"
    BALANCED = "balanced"


class QuickProfile(BaseModel):
    """快速模式的简易档案"""
    meal_goal: MealGoal = MealGoal.BALANCED
    budget_limit: float = 30.0  # 本次预算上限
    hunger_level: int = 3  # 1-5
    craving_level: int = 2  # 1-5
    allergies: list[str] = Field(default_factory=list)
    mood: str = "normal"  # normal / tired / stressed / happy
