"""饭点提醒服务 — 根据用户习惯和当前状态生成提醒"""

import uuid
import logging
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field
from services.db_service import db_service
from services.memory_service import memory_service
from services.nutrition_calculator import calculate_bmr, calculate_tdee, get_daily_calorie_target

logger = logging.getLogger(__name__)


class ReminderType(str, Enum):
    """提醒类型"""
    MEAL_TIME = "meal_time"                    # 到饭点
    MISSED_MEAL = "missed_meal"                # 错过饭点
    LONG_GAP_WITHOUT_FOOD = "long_gap_without_food"  # 长时间未进食
    NUTRITION_GAP = "nutrition_gap"            # 营养缺口
    BUDGET_AVAILABLE = "budget_available"      # 预算可用
    LATE_NIGHT_WARNING = "late_night_warning"  # 深夜警告


class Reminder(BaseModel):
    """提醒"""
    reminder_id: str
    reminder_type: ReminderType
    title: str
    message: str
    urgency: str = "normal"  # low / normal / high
    suggested_action: str = ""  # suggest_auto_draft / suggest_record
    meal_type: str = ""  # breakfast / lunch / dinner
    context: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    dismissed: bool = False
    snoozed_until: datetime | None = None


class ReminderService:
    """饭点提醒服务"""

    async def check_reminders(self, user_id: str) -> list[Reminder]:
        """检查是否需要提醒"""
        reminders = []

        # 获取用户信息
        user = await db_service.get_user(user_id)
        if not user:
            return reminders

        # 获取今日用餐记录
        today_meals = await db_service.get_today_meals(user_id)
        now = datetime.now()

        # 检查各种提醒条件
        reminders.extend(await self._check_meal_time(user, today_meals, now))
        reminders.extend(await self._check_missed_meal(user, today_meals, now))
        reminders.extend(await self._check_long_gap(today_meals, now))
        reminders.extend(await self._check_nutrition_gap(user, today_meals))
        reminders.extend(await self._check_budget(user, today_meals))
        reminders.extend(await self._check_late_night(now))

        # LLM 增强提醒消息
        for i, reminder in enumerate(reminders):
            enhanced = await self._llm_enhance_message(reminder, user, today_meals)
            if enhanced:
                reminders[i] = Reminder(
                    reminder_id=reminder.reminder_id,
                    reminder_type=reminder.reminder_type,
                    title=reminder.title,
                    message=enhanced,
                    urgency=reminder.urgency,
                    suggested_action=reminder.suggested_action,
                    meal_type=reminder.meal_type,
                    context=reminder.context,
                    created_at=reminder.created_at,
                )

        return reminders

    async def _check_meal_time(self, user, today_meals: list, now: datetime) -> list[Reminder]:
        """检查是否到饭点"""
        reminders = []
        meal_schedule = user.meal_schedule or {}

        # 默认时间表
        if not meal_schedule:
            meal_schedule = {
                "breakfast": "08:00",
                "lunch": "12:00",
                "dinner": "18:30",
            }

        current_minutes = now.hour * 60 + now.minute

        for meal_type, time_str in meal_schedule.items():
            try:
                parts = time_str.split(":")
                scheduled_minutes = int(parts[0]) * 60 + int(parts[1])
            except:
                continue

            # 检查是否已记录
            recorded = any(m.meal_type == meal_type for m in today_meals)
            if recorded:
                continue

            # 检查是否接近饭点（前后30分钟）
            time_diff = current_minutes - scheduled_minutes
            if -15 <= time_diff <= 30:
                meal_cn = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}.get(meal_type, meal_type)

                reminders.append(Reminder(
                    reminder_id=str(uuid.uuid4())[:8],
                    reminder_type=ReminderType.MEAL_TIME,
                    title=f"接近{meal_cn}时间",
                    message=f"现在接近你的常规{meal_cn}时间。",
                    urgency="normal",
                    suggested_action="suggest_auto_draft",
                    meal_type=meal_type,
                ))

        return reminders

    async def _check_missed_meal(self, user, today_meals: list, now: datetime) -> list[Reminder]:
        """检查是否错过饭点"""
        reminders = []
        meal_schedule = user.meal_schedule or {}

        if not meal_schedule:
            meal_schedule = {
                "breakfast": "08:00",
                "lunch": "12:00",
                "dinner": "18:30",
            }

        current_minutes = now.hour * 60 + now.minute

        for meal_type, time_str in meal_schedule.items():
            try:
                parts = time_str.split(":")
                scheduled_minutes = int(parts[0]) * 60 + int(parts[1])
            except:
                continue

            # 检查是否已记录
            recorded = any(m.meal_type == meal_type for m in today_meals)
            if recorded:
                continue

            # 检查是否已过饭点（超过30分钟）
            time_diff = current_minutes - scheduled_minutes
            if 30 < time_diff < 180:  # 已过30分钟但不超过3小时
                meal_cn = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"}.get(meal_type, meal_type)

                reminders.append(Reminder(
                    reminder_id=str(uuid.uuid4())[:8],
                    reminder_type=ReminderType.MISSED_MEAL,
                    title=f"已过{meal_cn}时间",
                    message=f"已过{meal_cn}时间（{time_str}），你还没有记录用餐。",
                    urgency="high",
                    suggested_action="suggest_auto_draft",
                    meal_type=meal_type,
                ))

        return reminders

    async def _check_long_gap(self, today_meals: list, now: datetime) -> list[Reminder]:
        """检查是否长时间未进食"""
        reminders = []

        if not today_meals:
            # 今天还没有用餐记录
            if now.hour >= 10:
                reminders.append(Reminder(
                    reminder_id=str(uuid.uuid4())[:8],
                    reminder_type=ReminderType.LONG_GAP_WITHOUT_FOOD,
                    title="今天还没有用餐记录",
                    message="你今天还没有记录任何用餐。",
                    urgency="high",
                    suggested_action="suggest_auto_draft",
                ))
        else:
            # 检查距离上次进食时间
            last_meal = max(today_meals, key=lambda m: m.timestamp)
            hours_since = (now - last_meal.timestamp).total_seconds() / 3600

            if hours_since > 5:
                reminders.append(Reminder(
                    reminder_id=str(uuid.uuid4())[:8],
                    reminder_type=ReminderType.LONG_GAP_WITHOUT_FOOD,
                    title="距离上次进食已较久",
                    message=f"你已经 {hours_since:.0f} 小时没有记录正餐了。",
                    urgency="normal",
                    suggested_action="suggest_auto_draft",
                ))

        return reminders

    async def _check_nutrition_gap(self, user, today_meals: list) -> list[Reminder]:
        """检查营养缺口"""
        reminders = []

        # 计算今日营养摄入
        total_calories = sum(m.total_calories for m in today_meals)
        total_protein = sum(m.total_protein for m in today_meals)

        # 计算营养目标
        bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
        tdee = calculate_tdee(bmr, user.activity_level)
        daily_target = get_daily_calorie_target(tdee, user.goal)

        # 检查热量缺口
        calorie_gap = daily_target - total_calories
        if calorie_gap > 500 and len(today_meals) > 0:
            reminders.append(Reminder(
                reminder_id=str(uuid.uuid4())[:8],
                reminder_type=ReminderType.NUTRITION_GAP,
                title="今日热量缺口较大",
                message=f"今日热量缺口 {calorie_gap:.0f} 千卡，蛋白质摄入偏低。",
                urgency="normal",
                suggested_action="suggest_auto_draft",
            ))

        # 检查蛋白质缺口
        protein_target = user.weight_kg * 1.6  # 1.6g/kg
        protein_gap = protein_target - total_protein
        if protein_gap > 30 and len(today_meals) > 0:
            reminders.append(Reminder(
                reminder_id=str(uuid.uuid4())[:8],
                reminder_type=ReminderType.NUTRITION_GAP,
                title="蛋白质摄入不足",
                message=f"今日蛋白质缺口 {protein_gap:.0f} 克。",
                urgency="normal",
                suggested_action="suggest_auto_draft",
            ))

        return reminders

    async def _check_budget(self, user, today_meals: list) -> list[Reminder]:
        """检查预算"""
        reminders = []

        total_spent = sum(m.total_price for m in today_meals)
        remaining = user.daily_budget - total_spent

        if remaining > 20 and len(today_meals) == 0:
            reminders.append(Reminder(
                reminder_id=str(uuid.uuid4())[:8],
                reminder_type=ReminderType.BUDGET_AVAILABLE,
                title="预算充足",
                message=f"今日预算还剩 ¥{remaining:.0f}，可以享用一顿美餐。",
                urgency="low",
                suggested_action="suggest_auto_draft",
            ))

        return reminders

    async def _check_late_night(self, now: datetime) -> list[Reminder]:
        """检查深夜"""
        reminders = []

        if now.hour >= 22 and now.hour < 4:
            reminders.append(Reminder(
                reminder_id=str(uuid.uuid4())[:8],
                reminder_type=ReminderType.LATE_NIGHT_WARNING,
                title="深夜用餐提醒",
                message="深夜进食影响睡眠，建议选择清淡食物。",
                urgency="normal",
                suggested_action="suggest_auto_draft",
            ))

        return reminders

    async def _llm_enhance_message(self, reminder: Reminder, user, today_meals: list) -> str | None:
        """用 LLM 生成个性化提醒消息。失败返回 None。"""
        from core.llm_client import generate_text

        meals_summary = ""
        if today_meals:
            items = []
            for m in today_meals:
                items.append(f"{m.meal_type}: {m.total_calories:.0f}kcal, ¥{m.total_price:.0f}")
            meals_summary = "今日已吃: " + "; ".join(items)
        else:
            meals_summary = "今日尚未用餐"

        total_cal = sum(m.total_calories for m in today_meals)
        total_protein = sum(m.total_protein for m in today_meals)
        bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
        tdee = calculate_tdee(bmr, user.activity_level)
        daily_target = get_daily_calorie_target(tdee, user.goal)
        budget_remaining = user.daily_budget - sum(m.total_price for m in today_meals)

        goal_map = {"lose_weight": "减脂", "maintain": "维持", "gain_muscle": "增肌"}

        system_prompt = """你是一个关心用户的饮食助手，正在给用户发提醒。语气温暖亲切，像一个贴心的朋友。
提醒消息要包含具体的营养/预算数据，让用户知道为什么现在该吃饭了。
消息控制在30字以内，简洁有力。"""

        user_prompt = f"""提醒类型: {reminder.reminder_type.value}
基础消息: {reminder.message}
{meals_summary}
热量进度: {total_cal:.0f}/{daily_target:.0f}kcal
蛋白质: {total_protein:.0f}g
预算剩余: ¥{budget_remaining:.0f}
用户目标: {goal_map.get(user.goal, user.goal)}

请生成一条更个性化的提醒消息。"""

        result = await generate_text(system_prompt, user_prompt)
        if result and not result.startswith("[LLM"):
            return result.strip()
        return None

    def build_reminder_card(self, reminder: Reminder) -> dict:
        """构建提醒卡数据"""
        return {
            "reminder_id": reminder.reminder_id,
            "type": reminder.reminder_type.value,
            "title": reminder.title,
            "message": reminder.message,
            "urgency": reminder.urgency,
            "suggested_action": reminder.suggested_action,
            "meal_type": reminder.meal_type,
            "buttons": [
                {"action": "accept", "label": "帮我搭配"},
                {"action": "snooze", "label": "稍后提醒"},
                {"action": "dismiss", "label": "今天不吃了"},
            ],
        }


# 全局实例
reminder_service = ReminderService()
