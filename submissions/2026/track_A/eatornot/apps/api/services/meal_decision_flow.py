"""统一饮食决策流程 — Dual-Trigger MealDecisionFlow"""

import uuid
import logging
from datetime import datetime
from models.meal_decision import (
    MealDecisionRequest, MealDecisionResponse,
    TriggerType, Scenario, OrderDraft, NutritionSummary, TripleBalance
)
from models.user_profile import UserProfile
from services.db_service import db_service
from services.memory_service import memory_service
from services.budget_service import BudgetService
from services.dashboard_service import DashboardService
from services.auto_draft_service import AutoDraftService
from services.nutrition_calculator import calculate_bmr, calculate_tdee, get_daily_calorie_target

logger = logging.getLogger(__name__)


class MealDecisionFlow:
    """统一饮食决策流程"""

    def __init__(self):
        self.budget_service = BudgetService()
        self.dashboard_service = DashboardService()
        self.auto_draft_service = AutoDraftService()

    async def execute(self, request: MealDecisionRequest) -> MealDecisionResponse:
        """
        执行统一的饮食决策流程

        流程: collect_context → detect_scenario → run_agents → build_order_draft → explain_decision
        """
        decision_id = str(uuid.uuid4())[:8]

        # 1. 收集上下文
        context = await self._collect_context(request)

        # 2. 检测场景（如果未指定）
        scenario = request.scenario
        if scenario == Scenario.QUICK_ORDER and request.trigger_type == TriggerType.AGENT_INITIATED:
            scenario = await self._detect_scenario(context)

        # 3. 获取记忆参考
        memory_refs = await self._get_memory_references(request.user_id, context)

        # 4. 运行 Agent 分析
        agent_results = await self._run_agents(context, scenario)

        # 5. 构建订单草稿
        order_draft = await self._build_order_draft(context, scenario, agent_results)

        # 6. 生成三重余额（稳一下模式）
        triple_balance = None
        if scenario == Scenario.STABILIZE:
            triple_balance = await self._calculate_triple_balance(context)

        # 7. 生成辩论数据
        debate = self._build_debate_summary(agent_results)

        # 8. 构建响应
        return MealDecisionResponse(
            decision_id=decision_id,
            trigger_type=request.trigger_type,
            scenario=scenario,
            trigger_reason=request.trigger_reason,
            summary=self._build_summary(scenario, context),
            order_draft=order_draft,
            triple_balance=triple_balance,
            debate=debate,
            memory_references=memory_refs,
        )

    async def _collect_context(self, request: MealDecisionRequest) -> dict:
        """收集上下文信息"""
        user = await db_service.get_user(request.user_id)
        if not user:
            # 创建默认用户
            from api.profile_routes import _load_demo_profile
            demo_data = _load_demo_profile()
            demo_data["user_id"] = request.user_id
            user = await db_service.create_user(demo_data)

        # 转换为 UserProfile
        user_profile = UserProfile(
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
        )

        # 获取今日状态
        dashboard = await self.dashboard_service.get_today_dashboard(user_profile)

        # 获取记忆
        preferences = await memory_service.get_preferences(request.user_id)
        patterns = await memory_service.get_meal_patterns(request.user_id)

        return {
            "user": user_profile,
            "dashboard": dashboard,
            "preferences": preferences,
            "patterns": patterns,
            "message": request.message,
            "trigger_type": request.trigger_type,
            "scenario": request.scenario,
            "user_id": request.user_id,
        }

    async def _detect_scenario(self, context: dict) -> Scenario:
        """根据上下文检测场景"""
        dashboard = context.get("dashboard", {})
        now = datetime.now()
        hour = now.hour

        # 检查是否错过饭点
        next_meal = dashboard.get("next_meal_suggestion", {})
        if next_meal.get("urgency") == "high":
            return Scenario.MISSED_MEAL_REMINDER

        # 检查营养缺口
        nutrition = dashboard.get("nutrition", {})
        if nutrition.get("gap", 0) > 500:
            return Scenario.NUTRITION_GAP

        # 检查预算
        budget = dashboard.get("budget", {})
        if budget.get("remaining", 0) < 15:
            return Scenario.BUDGET_GUARD

        # 检查深夜
        if hour >= 22:
            return Scenario.LATE_NIGHT_MEAL

        # 默认常规用餐
        return Scenario.ROUTINE_MEAL

    async def _get_memory_references(self, user_id: str, context: dict) -> list[str]:
        """获取记忆参考"""
        refs = []
        preferences = context.get("preferences", {})
        patterns = context.get("patterns", {})

        # 常点餐品
        frequent = patterns.get("frequent_items", [])
        if frequent:
            refs.append(f"你最近常点：{', '.join(frequent[:3])}")

        # 不喜欢的食物
        avoided = preferences.get("avoided_items", [])
        if avoided:
            refs.append(f"你不喜欢：{', '.join(avoided[:3])}")

        # 预算习惯
        avg_spend = patterns.get("avg_daily_spend", 0)
        if avg_spend > 0:
            refs.append(f"你通常午餐预算在 ¥{avg_spend:.0f} 左右")

        return refs

    async def _run_agents(self, context: dict, scenario: Scenario) -> list:
        """运行 Agent 分析"""
        from agents.supervisor_agent import SupervisorAgent

        supervisor = SupervisorAgent()
        result = await supervisor.run(context)
        return result.agent_debate

    async def _build_order_draft(self, context: dict, scenario: Scenario,
                                   agent_results: list) -> OrderDraft:
        """构建订单草稿"""
        user = context["user"]

        # 使用 AutoDraftService 生成草稿
        draft_data = await self.auto_draft_service.generate_draft(user)

        # 计算营养摘要
        nutrition = NutritionSummary(
            calories=draft_data.get("nutrition", {}).get("calories", 0),
            protein=draft_data.get("nutrition", {}).get("protein", 0),
            fat=draft_data.get("nutrition", {}).get("fat", 0),
            carbs=draft_data.get("nutrition", {}).get("carbs", 0),
            sodium=draft_data.get("nutrition", {}).get("sodium", 0),
        )

        # 生成理由和权衡
        reason = self._build_draft_reason(draft_data, context, scenario)
        tradeoffs = self._build_tradeoffs(draft_data, context)
        warnings = self._build_warnings(draft_data, context)

        return OrderDraft(
            draft_id=draft_data.get("draft_id", str(uuid.uuid4())[:8]),
            provider="mcdonalds",
            items=draft_data.get("items", []),
            estimated_price=draft_data.get("total_price", 0),
            nutrition=nutrition,
            reason=reason,
            tradeoffs=tradeoffs,
            warnings=warnings,
            requires_confirmation=True,
        )

    def _build_draft_reason(self, draft_data: dict, context: dict, scenario: Scenario) -> str:
        """生成草稿理由"""
        reasons = draft_data.get("reasons", [])
        memory_refs = []

        preferences = context.get("preferences", {})
        patterns = context.get("patterns", {})

        # 添加记忆参考
        frequent = patterns.get("frequent_items", [])
        if frequent:
            memory_refs.append(f"参考了你最近常点的菜品")

        avoided = preferences.get("avoided_items", [])
        if avoided:
            memory_refs.append(f"避开了你不喜欢的食物")

        all_reasons = reasons + memory_refs
        return "；".join(all_reasons) if all_reasons else "为你搭配了这餐"

    def _build_tradeoffs(self, draft_data: dict, context: dict) -> list[str]:
        """生成权衡说明"""
        tradeoffs = []
        nutrition = draft_data.get("nutrition", {})
        user = context["user"]

        if user.goal.value == "lose_weight":
            if nutrition.get("calories", 0) > 500:
                tradeoffs.append("热量略高，但蛋白质充足")

        return tradeoffs

    def _build_warnings(self, draft_data: dict, context: dict) -> list[str]:
        """生成警告"""
        warnings = []
        user = context["user"]
        nutrition = draft_data.get("nutrition", {})

        # 过敏检查
        if user.allergies:
            warnings.append("请注意检查过敏原")

        # 高钠警告
        if nutrition.get("sodium", 0) > 1000:
            warnings.append("钠含量较高，建议多喝水")

        return warnings

    async def _calculate_triple_balance(self, context: dict) -> TripleBalance:
        """计算三重余额"""
        user = context["user"]
        dashboard = context.get("dashboard", {})

        nutrition = dashboard.get("nutrition", {})
        budget = dashboard.get("budget", {})

        # 计算余额消耗
        calorie_balance = nutrition.get("gap", 0)
        budget_balance = budget.get("remaining", 0)

        # 欲望余额
        indulgence_used = await memory_service.get_indulgence_count_this_week(user.user_id)
        indulgence_remaining = max(0, user.weekly_indulgence_allowance - indulgence_used)

        return TripleBalance(
            calorie_balance_cost=calorie_balance,
            budget_balance_cost=budget_balance,
            indulgence_balance_cost=indulgence_remaining,
            explanation="这不是放纵失控，而是可控放纵",
        )

    def _build_debate_summary(self, agent_results: list) -> dict:
        """构建辩论摘要"""
        if not agent_results:
            return {}

        stages = {
            "stage_1_initial_opinions": [],
            "stage_2_conflicts": [],
            "stage_3_compromise": [],
            "stage_4_final_vote": [],
        }

        for result in agent_results:
            if result.agent_name == "菜单Agent":
                continue

            opinion = {
                "agent": result.agent_name,
                "position": result.reasons[0] if result.reasons else "",
                "evidence": result.reasons[:2],
                "confidence": abs(result.score),
            }
            stages["stage_1_initial_opinions"].append(opinion)

            vote = {
                "agent": result.agent_name,
                "vote": result.decision,
                "warning": result.warnings[0] if result.warnings else None,
            }
            stages["stage_4_final_vote"].append(vote)

        return stages

    def _build_summary(self, scenario: Scenario, context: dict) -> str:
        """构建摘要"""
        user = context["user"]
        dashboard = context.get("dashboard", {})

        scenario_cn = {
            Scenario.QUICK_ORDER: "快速点餐",
            Scenario.MISSED_MEAL_REMINDER: "饭点提醒",
            Scenario.BUDGET_GUARD: "预算守护",
            Scenario.NUTRITION_GAP: "营养补充",
            Scenario.STABILIZE: "稳一下模式",
            Scenario.ROUTINE_MEAL: "常规用餐",
            Scenario.LATE_NIGHT_MEAL: "深夜用餐",
            Scenario.POST_MEAL_RECORD: "餐后记录",
        }.get(scenario, "饮食建议")

        goal_cn = {
            "lose_weight": "减脂",
            "maintain": "维持",
            "gain_muscle": "增肌",
        }.get(user.goal.value, user.goal.value)

        return f"根据您的档案（目标：{goal_cn}），为您生成{scenario_cn}方案"


# 全局实例
meal_decision_flow = MealDecisionFlow()
