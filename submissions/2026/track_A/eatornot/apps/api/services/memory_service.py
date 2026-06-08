"""长期记忆服务 — 记录用户饮食习惯，形成用户画像"""

from datetime import datetime, timedelta
from collections import Counter
from services.db_service import db_service


class MemoryService:
    """管理用户用餐历史和偏好，形成长期记忆"""

    async def get_recent_meals(self, user_id: str, days: int = 7) -> list:
        """获取最近的用餐记录"""
        return await db_service.get_meals(user_id, days)

    async def get_preferences(self, user_id: str) -> dict:
        """从历史记录推断偏好"""
        recent = await self.get_recent_meals(user_id, days=30)
        if not recent:
            return {"preferred_items": [], "avoided_items": []}

        # 统计菜品频率
        item_counts: dict[str, int] = {}
        for meal in recent:
            for item in (meal.items or []):
                name = item.get("name", "unknown")
                item_counts[name] = item_counts.get(name, 0) + 1

        # 按频率排序
        sorted_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)
        preferred = [name for name, count in sorted_items[:5]]

        # 从反馈中找出不喜欢的食物
        feedbacks = await db_service.get_feedbacks(user_id)
        avoided = []
        for feedback in feedbacks:
            if feedback.satisfaction <= 2:
                meal_id = feedback.meal_id
                for meal in recent:
                    if meal.id == meal_id:
                        for item in (meal.items or []):
                            avoided.append(item.get("name", ""))
                        break

        return {
            "preferred_items": preferred,
            "avoided_items": list(set(avoided))[:5],
        }

    async def get_indulgence_count_this_week(self, user_id: str) -> int:
        """本周放纵次数"""
        meals = await db_service.get_meals(user_id, days=7)
        count = 0
        for meal in meals:
            if meal.plan_mode == "controlled_indulgence":
                count += 1
        return count

    async def get_meal_patterns(self, user_id: str) -> dict:
        """分析用餐模式"""
        recent = await self.get_recent_meals(user_id, days=30)
        if not recent:
            return {
                "usual_times": {},
                "frequent_items": [],
                "skipped_meals": [],
                "avg_daily_spend": 0,
                "budget_usage": {},
            }

        # 分析用餐时间
        meal_times = {"breakfast": [], "lunch": [], "dinner": [], "snack": []}
        daily_spend = {}

        for meal in recent:
            hour = meal.timestamp.hour
            meal_type = meal.meal_type

            if meal_type in meal_times:
                meal_times[meal_type].append(hour)

            date = meal.timestamp.date()
            if date not in daily_spend:
                daily_spend[date] = 0
            daily_spend[date] += meal.total_price

        # 计算常见用餐时间
        usual_times = {}
        for meal_type, times in meal_times.items():
            if times:
                avg_hour = sum(times) / len(times)
                usual_times[meal_type] = f"{int(avg_hour):02d}:00"

        # 计算平均每日花费
        avg_daily_spend = sum(daily_spend.values()) / len(daily_spend) if daily_spend else 0

        # 识别跳过的餐次
        skipped_meals = []
        for meal_type in ["breakfast", "lunch", "dinner"]:
            if not meal_times[meal_type]:
                skipped_meals.append(meal_type)

        # 频繁点的菜品
        frequent_items = []
        item_counts = Counter()
        for meal in recent:
            for item in (meal.items or []):
                item_counts[item.get("name", "")] += 1
        frequent_items = [name for name, _ in item_counts.most_common(5)]

        # 预算使用习惯
        budget_usage = {
            "avg_daily": round(avg_daily_spend, 2),
            "max_daily": round(max(daily_spend.values()) if daily_spend else 0, 2),
            "min_daily": round(min(daily_spend.values()) if daily_spend else 0, 2),
        }

        return {
            "usual_times": usual_times,
            "frequent_items": frequent_items,
            "skipped_meals": skipped_meals,
            "avg_daily_spend": round(avg_daily_spend, 2),
            "budget_usage": budget_usage,
        }

    async def save_feedback(self, user_id: str, meal_id: str, satisfaction: int, notes: str) -> None:
        """保存反馈"""
        await db_service.create_feedback({
            "user_id": user_id,
            "meal_id": meal_id,
            "satisfaction": satisfaction,
            "notes": notes,
        })

    # ==================== 新增：用户画像方法 ====================

    async def get_dietary_habits(self, user_id: str) -> dict:
        """
        获取饮食习惯

        Returns:
            {
                "usual_meal_times": {"breakfast": "08:30", ...},
                "frequent_skip": ["breakfast"],  # 经常跳过的餐次
                "frequent_items": ["麦辣鸡腿堡", ...],
                "price_range": (15, 35),  # 常用价格区间
                "meal_scenarios": ["work", "late_night"],  # 用餐场景
            }
        """
        patterns = await self.get_meal_patterns(user_id)
        recent = await self.get_recent_meals(user_id, days=30)

        # 分析价格区间
        prices = []
        for meal in recent:
            if meal.total_price > 0:
                prices.append(meal.total_price)

        price_range = (15, 35)
        if prices:
            prices.sort()
            price_range = (
                round(prices[len(prices) // 4], 0),  # 25分位
                round(prices[len(prices) * 3 // 4], 0),  # 75分位
            )

        # 分析用餐场景（基于时间推断）
        meal_scenarios = []
        for meal in recent:
            hour = meal.timestamp.hour
            if hour >= 22 or hour < 4:
                meal_scenarios.append("late_night")
            elif 6 <= hour < 9:
                meal_scenarios.append("morning_rush")
            elif 11 <= hour < 14:
                meal_scenarios.append("work_lunch")

        return {
            "usual_meal_times": patterns.get("usual_times", {}),
            "frequent_skip": patterns.get("skipped_meals", []),
            "frequent_items": patterns.get("frequent_items", []),
            "price_range": price_range,
            "meal_scenarios": list(set(meal_scenarios))[:3],
        }

    async def get_taste_preferences(self, user_id: str) -> dict:
        """
        获取口味偏好

        Returns:
            {
                "liked_items": ["麦辣鸡腿堡", ...],
                "disliked_items": ["咖啡", ...],
                "flavor_preference": "spicy",  # sweet/spicy/fried/balanced
                "drink_preference": "zero_sugar",
                "willing_to_substitute": True,
            }
        """
        preferences = await self.get_preferences(user_id)
        recent = await self.get_recent_meals(user_id, days=30)

        # 分析口味偏好
        flavor_counts = {"sweet": 0, "spicy": 0, "fried": 0, "balanced": 0}
        drink_counts = {"zero_sugar": 0, "regular": 0, "coffee": 0}

        for meal in recent:
            for item in (meal.items or []):
                tags = item.get("tags", [])
                name = item.get("name", "")

                # 分析口味
                if "spicy" in tags or "辣" in name:
                    flavor_counts["spicy"] += 1
                elif "fried" in tags or "炸" in name:
                    flavor_counts["fried"] += 1
                elif "sweet" in tags or "甜" in name:
                    flavor_counts["sweet"] += 1
                else:
                    flavor_counts["balanced"] += 1

                # 分析饮料偏好
                if "zero_sugar" in tags or "零度" in name:
                    drink_counts["zero_sugar"] += 1
                elif "coffee" in tags or "咖啡" in name:
                    drink_counts["coffee"] += 1
                elif "drink" in tags:
                    drink_counts["regular"] += 1

        # 确定主要偏好
        flavor_preference = max(flavor_counts, key=flavor_counts.get) if any(flavor_counts.values()) else "balanced"
        drink_preference = max(drink_counts, key=drink_counts.get) if any(drink_counts.values()) else "zero_sugar"

        return {
            "liked_items": preferences.get("preferred_items", []),
            "disliked_items": preferences.get("avoided_items", []),
            "flavor_preference": flavor_preference,
            "drink_preference": drink_preference,
            "willing_to_substitute": True,  # 默认愿意替换
        }

    async def get_budget_patterns(self, user_id: str) -> dict:
        """
        获取预算习惯

        Returns:
            {
                "avg_daily_spend": 25.5,
                "weekly_spend_velocity": 0.8,  # 花钱速度
                "month_end_tight": False,
                "frequent_over_budget": False,
            }
        """
        patterns = await self.get_meal_patterns(user_id)
        budget_usage = patterns.get("budget_usage", {})

        # 分析是否经常超预算
        recent = await self.get_recent_meals(user_id, days=30)
        over_budget_count = 0
        total_days = 0

        daily_spend = {}
        for meal in recent:
            date = meal.timestamp.date()
            if date not in daily_spend:
                daily_spend[date] = 0
            daily_spend[date] += meal.total_price

        # 这里需要用户的 daily_budget，暂时用默认值
        daily_budget = 50.0
        for date, spent in daily_spend.items():
            total_days += 1
            if spent > daily_budget:
                over_budget_count += 1

        return {
            "avg_daily_spend": budget_usage.get("avg_daily", 0),
            "weekly_spend_velocity": budget_usage.get("avg_daily", 0) * 7 / 300,  # 假设周预算300
            "month_end_tight": False,  # 需要更复杂的逻辑
            "frequent_over_budget": over_budget_count > total_days * 0.3 if total_days > 0 else False,
        }

    async def get_nutrition_patterns(self, user_id: str) -> dict:
        """
        获取营养模式

        Returns:
            {
                "protein_deficit": True,
                "high_sodium": False,
                "late_night_high_cal": True,
                "irregular_meals": False,
            }
        """
        recent = await self.get_recent_meals(user_id, days=14)

        if not recent:
            return {
                "protein_deficit": False,
                "high_sodium": False,
                "late_night_high_cal": False,
                "irregular_meals": False,
            }

        # 分析蛋白质摄入
        total_protein = sum(m.total_protein for m in recent)
        avg_protein = total_protein / len(recent) if recent else 0
        protein_deficit = avg_protein < 20  # 每餐低于20g

        # 分析钠摄入
        total_sodium = sum(m.total_sodium for m in recent)
        avg_sodium = total_sodium / len(recent) if recent else 0
        high_sodium = avg_sodium > 800  # 每餐超过800mg

        # 分析深夜高热量
        late_night_meals = [m for m in recent if m.timestamp.hour >= 22]
        late_night_high_cal = any(m.total_calories > 500 for m in late_night_meals)

        # 分析不规律用餐
        meal_dates = set(m.timestamp.date() for m in recent)
        if len(meal_dates) > 7:
            # 检查每天是否都有记录
            dates_with_meals = len(meal_dates)
            irregular_meals = dates_with_meals < 10  # 14天内少于10天有记录
        else:
            irregular_meals = False

        return {
            "protein_deficit": protein_deficit,
            "high_sodium": high_sodium,
            "late_night_high_cal": late_night_high_cal,
            "irregular_meals": irregular_meals,
        }

    async def get_recommendation_context(self, user_id: str) -> dict:
        """
        获取推荐上下文（用于展示给用户）

        Returns:
            {
                "frequent_items": ["麦辣鸡腿堡", ...],
                "avoided_items": ["咖啡", ...],
                "budget_range": "25-35元",
                "dietary_notes": ["你最近3次都不喜欢咖啡", ...],
            }
        """
        preferences = await self.get_preferences(user_id)
        habits = await self.get_dietary_habits(user_id)
        patterns = await self.get_meal_patterns(user_id)

        # 构建推荐说明
        dietary_notes = []

        avoided = preferences.get("avoided_items", [])
        if avoided:
            dietary_notes.append(f"你最近不喜欢：{', '.join(avoided[:3])}")

        price_range = habits.get("price_range", (15, 35))
        dietary_notes.append(f"你通常午餐预算在 ¥{price_range[0]:.0f}-{price_range[1]:.0f}")

        frequent = habits.get("frequent_items", [])
        if frequent:
            dietary_notes.append(f"你常点：{', '.join(frequent[:3])}")

        return {
            "frequent_items": frequent,
            "avoided_items": avoided,
            "budget_range": f"¥{price_range[0]:.0f}-{price_range[1]:.0f}",
            "dietary_notes": dietary_notes,
        }


# 全局实例
memory_service = MemoryService()
