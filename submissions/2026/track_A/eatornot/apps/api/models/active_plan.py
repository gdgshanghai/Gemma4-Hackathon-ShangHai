from pydantic import BaseModel, Field
from .recommendation import MenuItem


class ChangeLogEntry(BaseModel):
    version: int
    what_changed: str
    why: str
    impact: str  # 对热量/价格/营养的影响
    # Delta 字段
    calories_delta: float = 0.0
    price_delta: float = 0.0
    protein_delta: float = 0.0
    fat_delta: float = 0.0
    sodium_delta: float = 0.0
    carbs_delta: float = 0.0


class ActivePlan(BaseModel):
    plan_id: str
    version: int = 1
    items: list[MenuItem] = Field(default_factory=list)
    nutrition: dict = Field(default_factory=lambda: {
        "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "sodium": 0
    })
    price: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    change_log: list[ChangeLogEntry] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)  # 用户的限制条件
    title: str = ""
    mode: str = ""  # disciplined / budget_friendly / controlled_indulgence
