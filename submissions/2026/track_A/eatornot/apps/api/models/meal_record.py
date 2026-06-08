from pydantic import BaseModel, Field
from datetime import datetime


class MealRecord(BaseModel):
    id: str = ""
    user_id: str = "demo-user"
    timestamp: datetime = Field(default_factory=datetime.now)
    meal_type: str = "dinner"  # breakfast / lunch / dinner / snack
    items: list[dict] = Field(default_factory=list)  # list of {name, item_code, price, calories, ...}
    total_price: float = 0.0
    total_calories: float = 0.0
    total_protein: float = 0.0
    total_fat: float = 0.0
    total_carbs: float = 0.0
    total_sodium: float = 0.0
    plan_mode: str = ""  # which plan was selected
    satisfaction: int | None = None  # 1-5 feedback
    notes: str = ""
