from pydantic import BaseModel, Field
from enum import Enum


class Goal(str, Enum):
    LOSE_WEIGHT = "lose_weight"
    MAINTAIN = "maintain"
    GAIN_MUSCLE = "gain_muscle"
    SAVE_MONEY = "save_money"
    REGULAR_MEALS = "regular_meals"


class PreferredTone(str, Enum):
    STRICT_COACH = "strict_coach"
    GENTLE_FRIEND = "gentle_friend"
    FUNNY_FRIEND = "funny_friend"


class UserProfile(BaseModel):
    user_id: str = "demo-user"
    name: str = "Demo User"
    height_cm: float = 170.0
    weight_kg: float = 70.0
    age: int = 25
    sex: str = "male"  # male / female
    goal: Goal = Goal.LOSE_WEIGHT
    activity_level: str = "moderate"  # sedentary / light / moderate / active / very_active
    daily_budget: float = 50.0  # CNY
    weekly_budget: float = 300.0  # CNY
    weekly_indulgence_allowance: int = 2  # meals per week
    taste_preferences: list[str] = Field(default_factory=lambda: ["chicken", "coffee"])
    allergies: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)  # 不喜欢的食物
    preferred_tone: PreferredTone = PreferredTone.GENTLE_FRIEND
    meal_schedule: dict[str, str] = Field(
        default_factory=lambda: {
            "breakfast": "08:00",
            "lunch": "12:00",
            "dinner": "18:30",
        }
    )
    onboarding_complete: bool = False
    mode: str = "long_term"  # long_term / quick
