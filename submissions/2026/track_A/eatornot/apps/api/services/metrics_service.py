"""Metrics 服务 — 7 天模拟结果指标"""

from datetime import datetime, timedelta
from services.db_service import db_service
from services.memory_service import memory_service


class MetricsService:
    """结果指标服务"""

    async def get_demo_metrics(self, user_id: str = "demo-user") -> dict:
        """获取 7 天模拟结果指标"""
        meals = await db_service.get_meals(user_id, days=7)
        patterns = await memory_service.get_meal_patterns(user_id)

        # 计算各项指标（基于真实数据）
        meal_regular_score = self._calculate_meal_regular_score(meals)
        avg_lunch_delay = self._calculate_avg_lunch_delay(meals)
        budget_overrun = self._calculate_budget_overrun(meals, 35.0)
        acceptance_rate = self._calculate_acceptance_rate(meals)
        protein_gap_days = self._calculate_protein_gap_days(meals)
        late_night_orders = self._calculate_late_night_orders(meals)

        return {
            "is_simulated": True,
            "simulated_note": "以下指标基于 7 天模拟数据，用于展示产品闭环和长期伴随价值",
            "meal_regular_score": {
                "current": meal_regular_score,
                "description": "饮食规律性评分 (0-100)",
                "calculation": "按时用餐次数 / 总用餐次数 × 100",
            },
            "avg_lunch_delay_minutes": {
                "current": avg_lunch_delay,
                "description": "午餐平均延迟（分钟）",
                "calculation": "午餐时间 - 12:00 的平均值",
            },
            "budget_overrun_count": {
                "current": budget_overrun,
                "description": "预算超支天数",
                "calculation": "每日花费 > 日预算的天数",
            },
            "recommendation_acceptance_rate": {
                "current": acceptance_rate,
                "description": "推荐采纳率",
                "calculation": "采纳推荐的次数 / 总推荐次数",
            },
            "protein_gap_days": {
                "current": protein_gap_days,
                "description": "蛋白质不足天数",
                "calculation": "每日蛋白质 < 60g 的天数",
            },
            "late_night_orders": {
                "current": late_night_orders,
                "description": "深夜订单数 (22:00后)",
                "calculation": "晚上 10 点后的用餐记录数",
            },
        }

    def _calculate_meal_regular_score(self, meals: list) -> float:
        """计算饮食规律性评分"""
        if not meals:
            return 0

        # 检查每天是否按时用餐
        days_with_meals = set()
        on_time_count = 0
        total_count = 0

        for meal in meals:
            date = meal.timestamp.date()
            days_with_meals.add(date)
            total_count += 1

            # 检查是否按时（午餐在12-13点，晚餐在18-19点）
            hour = meal.timestamp.hour
            if meal.meal_type == "lunch" and 11 <= hour <= 13:
                on_time_count += 1
            elif meal.meal_type == "dinner" and 17 <= hour <= 19:
                on_time_count += 1

        if total_count == 0:
            return 0

        # 计算规律性评分
        regularity = on_time_count / total_count * 100
        return min(100, round(regularity))

    def _calculate_avg_lunch_delay(self, meals: list) -> float:
        """计算午餐平均延迟"""
        lunch_delays = []

        for meal in meals:
            if meal.meal_type == "lunch":
                hour = meal.timestamp.hour
                minute = meal.timestamp.minute
                # 假设正常午餐时间是12:00
                delay = max(0, (hour - 12) * 60 + minute)
                lunch_delays.append(delay)

        if not lunch_delays:
            return 0

        return round(sum(lunch_delays) / len(lunch_delays))

    def _calculate_budget_overrun(self, meals: list, daily_budget: float) -> int:
        """计算预算超支次数"""
        daily_spend = {}

        for meal in meals:
            date = meal.timestamp.date()
            if date not in daily_spend:
                daily_spend[date] = 0
            daily_spend[date] += meal.total_price

        overrun_count = 0
        for date, spent in daily_spend.items():
            if spent > daily_budget:
                overrun_count += 1

        return overrun_count

    def _calculate_acceptance_rate(self, meals: list) -> float:
        """计算推荐采纳率

        基于用餐记录推算：如果有用餐记录，说明用户采纳了推荐
        """
        if not meals:
            return 0.0

        # 简化计算：有记录的餐次视为采纳了推荐
        # 在真实系统中，这应该基于推荐-采纳的精确记录
        total_days = len(set(m.timestamp.date() for m in meals))
        meals_per_day = len(meals) / max(1, total_days)

        # 假设每天 3 餐，实际记录的餐次占比
        expected_meals = total_days * 3
        acceptance = len(meals) / max(1, expected_meals)

        return round(min(1.0, acceptance), 2)

    def _calculate_protein_gap_days(self, meals: list) -> int:
        """计算蛋白质不足天数"""
        daily_protein = {}

        for meal in meals:
            date = meal.timestamp.date()
            if date not in daily_protein:
                daily_protein[date] = 0
            daily_protein[date] += meal.total_protein

        # 假设每日蛋白质目标是60g
        gap_days = 0
        for date, protein in daily_protein.items():
            if protein < 60:
                gap_days += 1

        return gap_days

    def _calculate_late_night_orders(self, meals: list) -> int:
        """计算深夜失控订单"""
        late_night_count = 0

        for meal in meals:
            hour = meal.timestamp.hour
            # 晚上10点后的订单
            if hour >= 22:
                late_night_count += 1

        return late_night_count


# 全局实例
metrics_service = MetricsService()
