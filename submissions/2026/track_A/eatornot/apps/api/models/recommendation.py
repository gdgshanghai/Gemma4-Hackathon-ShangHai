from pydantic import BaseModel, Field
from .agent_result import AgentResult
from .debate import DebateResult


class MenuItem(BaseModel):
    name: str
    item_code: str
    category: str = ""
    price: float = 0.0
    calories: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbohydrate: float = 0.0
    sodium: float = 0.0
    tags: list[str] = Field(default_factory=list)


class RecommendationPlan(BaseModel):
    id: str
    title: str
    mode: str  # disciplined / budget_friendly / controlled_indulgence
    items: list[MenuItem] = Field(default_factory=list)
    estimated_price: float = 0.0
    estimated_calories: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbohydrate: float = 0.0
    sodium: float = 0.0
    budget_impact: str = ""  # e.g. "60% of daily budget"
    calorie_impact: str = ""  # e.g. "45% of daily target"
    indulgence_impact: str = ""  # e.g. "1 of 2 weekly allowance"
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    agent_votes: list[AgentResult] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    final_reason: str = ""


class RecommendationResponse(BaseModel):
    user_id: str
    plans: list[RecommendationPlan] = Field(default_factory=list)
    agent_debate: list[AgentResult] = Field(default_factory=list)
    debate: DebateResult | None = None  # 圆桌辩论结果
    summary: str = ""
    safety_warnings: list[str] = Field(default_factory=list)


class OrderDraft(BaseModel):
    user_id: str
    plan_id: str
    items: list[MenuItem] = Field(default_factory=list)
    estimated_price: float = 0.0
    estimated_calories: float = 0.0


class OrderConfirmation(BaseModel):
    order_id: str
    status: str = "confirmed"  # confirmed / simulated / failed
    message: str = ""
    is_mock: bool = True
    items: list[MenuItem] = Field(default_factory=list)
    total_price: float = 0.0
