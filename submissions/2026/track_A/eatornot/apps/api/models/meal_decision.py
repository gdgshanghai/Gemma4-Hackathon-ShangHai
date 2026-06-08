"""统一饮食决策模型"""

from enum import Enum
from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    """触发类型"""
    USER_INITIATED = "user_initiated"      # 用户主动触发
    AGENT_INITIATED = "agent_initiated"    # 系统主动触发


class Scenario(str, Enum):
    """场景类型"""
    QUICK_ORDER = "quick_order"                  # 快速点餐
    MISSED_MEAL_REMINDER = "missed_meal_reminder"  # 错过饭点提醒
    BUDGET_GUARD = "budget_guard"                # 预算守护
    NUTRITION_GAP = "nutrition_gap"              # 营养缺口
    STABILIZE = "stabilize"                      # 稳一下模式
    ROUTINE_MEAL = "routine_meal"                # 常规用餐
    LATE_NIGHT_MEAL = "late_night_meal"          # 深夜用餐
    POST_MEAL_RECORD = "post_meal_record"        # 餐后记录


class MealDecisionRequest(BaseModel):
    """统一饮食决策请求"""
    user_id: str = "demo-user"
    message: str = ""
    trigger_type: TriggerType = TriggerType.USER_INITIATED
    scenario: Scenario = Scenario.QUICK_ORDER
    trigger_reason: str = ""
    suggested_action: str = ""
    context: dict = Field(default_factory=dict)


class NutritionSummary(BaseModel):
    """营养摘要"""
    calories: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0
    sodium: float = 0.0


class OrderDraft(BaseModel):
    """订单草稿"""
    draft_id: str
    provider: str = "mcdonalds"  # mcdonalds | mock_meituan | manual
    items: list = Field(default_factory=list)
    estimated_price: float = 0.0
    nutrition: NutritionSummary = Field(default_factory=NutritionSummary)
    reason: str = ""
    tradeoffs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True


class TripleBalance(BaseModel):
    """三重余额"""
    calorie_balance_cost: float = 0.0  # 热量余额消耗
    budget_balance_cost: float = 0.0   # 预算余额消耗
    indulgence_balance_cost: float = 0.0  # 欲望余额消耗
    explanation: str = ""


class MealDecisionResponse(BaseModel):
    """统一饮食决策响应"""
    decision_id: str
    trigger_type: TriggerType
    scenario: Scenario
    trigger_reason: str

    # 推荐结果
    summary: str = ""
    plans: list = Field(default_factory=list)
    selected_plan: dict | None = None

    # 订单草稿
    order_draft: OrderDraft | None = None

    # 三重余额（稳一下模式）
    triple_balance: TripleBalance | None = None

    # Agent 辩论（解释层）
    debate: dict | None = None

    # 提醒信息
    reminder: dict | None = None

    # 记忆参考
    memory_references: list[str] = Field(default_factory=list)
