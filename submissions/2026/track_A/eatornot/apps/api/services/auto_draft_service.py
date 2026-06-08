"""自动搭配订单草稿服务 — 根据当前状态自动生成一餐方案"""

from datetime import datetime
from models.user_profile import UserProfile
from models.recommendation import MenuItem
from services.nutrition_calculator import calculate_bmr, calculate_tdee, get_daily_calorie_target, get_meal_calorie_budget
from services.budget_service import BudgetService
from services.memory_service import MemoryService
from providers.factory import get_provider


class AutoDraftService:
    """自动搭配订单草稿"""

    def __init__(self):
        self.budget_service = BudgetService()
        self.memory_service = MemoryService()

    async def generate_draft(self, user: UserProfile, meal_type: str = None) -> dict:
        """
        根据当前状态自动生成一餐方案

        Args:
            user: 用户档案
            meal_type: 餐次 (breakfast/lunch/dinner)，如果为 None 则自动判断

        Returns:
            订单草稿
        """
        now = datetime.now()

        # 自动判断餐次
        if meal_type is None:
            meal_type = self._guess_meal_type(now)

        # 获取今日已用餐情况
        today_meals = await self.budget_service.get_today_meals(user.user_id)
        total_calories = sum(m.total_calories for m in today_meals)
        total_spent = sum(m.total_price for m in today_meals)

        # 计算营养目标
        bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
        tdee = calculate_tdee(bmr, user.activity_level)
        daily_target = get_daily_calorie_target(tdee, user.goal.value)
        meal_budget = get_meal_calorie_budget(daily_target, meal_type)

        # 计算剩余预算
        calorie_remaining = daily_target - total_calories
        money_remaining = user.daily_budget - total_spent

        # 获取用户偏好和记忆
        preferences = await self.memory_service.get_preferences(user.user_id)
        patterns = await self.memory_service.get_meal_patterns(user.user_id)
        taste_prefs = await self.memory_service.get_taste_preferences(user.user_id)
        dietary_notes = []

        # 通过 Provider 获取菜单
        provider = await get_provider()
        items = await provider.list_items()
        menu_items = [
            {
                "name": i.name,
                "item_code": i.item_code,
                "category": i.category,
                "price": i.price,
                "calories": i.calories,
                "protein": i.protein,
                "fat": i.fat,
                "carbohydrate": i.carbohydrate,
                "sodium": i.sodium,
                "tags": i.tags,
            }
            for i in items
        ]

        # 根据目标筛选和搭配
        selected_items = self._select_items(
            menu_items=menu_items,
            meal_type=meal_type,
            calorie_budget=min(meal_budget, calorie_remaining),
            money_budget=money_remaining,
            user=user,
            preferences=preferences,
            taste_prefs=taste_prefs,
        )

        # 计算总价和营养
        total_price = sum(i["price"] for i in selected_items)
        total_nutrition = {
            "calories": sum(i["calories"] for i in selected_items),
            "protein": sum(i.get("protein", 0) for i in selected_items),
            "fat": sum(i.get("fat", 0) for i in selected_items),
            "carbs": sum(i.get("carbohydrate", 0) for i in selected_items),
            "sodium": sum(i.get("sodium", 0) for i in selected_items),
        }

        # 生成理由
        reasons = self._generate_reasons(
            selected_items, meal_type, user, calorie_remaining, money_remaining,
            preferences, patterns, taste_prefs
        )

        return {
            "draft_id": f"auto-{now.strftime('%Y%m%d%H%M%S')}",
            "meal_type": meal_type,
            "items": selected_items,
            "total_price": round(total_price, 2),
            "nutrition": total_nutrition,
            "reasons": reasons,
            "status": "draft",
            "created_at": now.isoformat(),
        }

    def _guess_meal_type(self, now: datetime) -> str:
        """根据时间猜测餐次"""
        hour = now.hour
        if hour < 10:
            return "breakfast"
        elif hour < 14:
            return "lunch"
        elif hour < 21:
            return "dinner"
        else:
            return "snack"

    def _select_items(self, menu_items: list, meal_type: str,
                       calorie_budget: float, money_budget: float,
                       user: UserProfile, preferences: dict,
                       taste_prefs: dict = None) -> list:
        """根据约束选择菜品，利用记忆做个性化"""
        # 分类菜单
        mains = [i for i in menu_items if i.get("category") != "drink"]
        drinks = [i for i in menu_items if i.get("category") == "drink"]

        # 获取不喜欢的食物
        avoided_items = preferences.get("avoided_items", [])

        # 过滤掉不喜欢的食物
        mains = [i for i in mains if i["name"] not in avoided_items]
        drinks = [i for i in drinks if i["name"] not in avoided_items]

        # 根据用户目标和口味偏好排序
        if user.goal.value == "lose_weight":
            mains.sort(key=lambda x: x["calories"])
        elif user.goal.value == "save_money":
            mains.sort(key=lambda x: x["price"])
        elif taste_prefs:
            # 根据口味偏好排序
            flavor = taste_prefs.get("flavor_preference", "balanced")
            if flavor == "spicy":
                mains.sort(key=lambda x: x.get("tags", []).count("spicy"), reverse=True)
            elif flavor == "fried":
                mains.sort(key=lambda x: x.get("tags", []).count("fried"), reverse=True)
            else:
                mains.sort(key=lambda x: x.get("tags", []).count("popular"), reverse=True)
        else:
            # 按受欢迎程度排序
            mains.sort(key=lambda x: x.get("tags", []).count("popular"), reverse=True)

        # 选择主食
        selected = []
        remaining_cal = calorie_budget
        remaining_money = money_budget

        for item in mains:
            if item["calories"] <= remaining_cal and item["price"] <= remaining_money:
                selected.append(item)
                remaining_cal -= item["calories"]
                remaining_money -= item["price"]

                # 主食最多选2个
                if len([i for i in selected if i.get("category") != "drink"]) >= 2:
                    break

        # 选择饮料（根据口味偏好）
        drink_preference = taste_prefs.get("drink_preference", "zero_sugar") if taste_prefs else "zero_sugar"

        if drink_preference == "zero_sugar" or user.goal.value == "lose_weight":
            # 优先选择零糖饮料
            zero_drinks = [d for d in drinks if "zero_sugar" in d.get("tags", [])]
            if zero_drinks and zero_drinks[0]["price"] <= remaining_money:
                selected.append(zero_drinks[0])
        elif drink_preference == "coffee":
            # 优先选择咖啡
            coffee_drinks = [d for d in drinks if "coffee" in d.get("tags", [])]
            if coffee_drinks and coffee_drinks[0]["price"] <= remaining_money:
                selected.append(coffee_drinks[0])
        else:
            # 选择便宜的饮料
            cheap_drinks = sorted(drinks, key=lambda x: x["price"])
            if cheap_drinks and cheap_drinks[0]["price"] <= remaining_money:
                selected.append(cheap_drinks[0])

        return selected

    def _generate_reasons(self, items: list, meal_type: str, user: UserProfile,
                           calorie_remaining: float, money_remaining: float,
                           preferences: dict = None, patterns: dict = None,
                           taste_prefs: dict = None) -> list:
        """生成推荐理由，包含记忆参考"""
        reasons = []

        meal_cn = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}.get(meal_type, meal_type)
        reasons.append(f"为您搭配了{meal_cn}")

        total_cal = sum(i["calories"] for i in items)
        total_price = sum(i["price"] for i in items)

        if user.goal.value == "lose_weight":
            reasons.append(f"热量 {total_cal} 千卡，符合减脂目标")
        elif user.goal.value == "save_money":
            reasons.append(f"总价 ¥{total_price}，性价比优先")

        if total_price < money_remaining * 0.5:
            reasons.append("预算充裕，可以再加点什么")

        # 添加记忆参考
        if preferences:
            avoided = preferences.get("avoided_items", [])
            if avoided:
                reasons.append(f"避开了你不喜欢的食物")

        if patterns:
            frequent = patterns.get("frequent_items", [])
            if frequent:
                reasons.append(f"参考了你常点的菜品")

        if taste_prefs:
            drink_pref = taste_prefs.get("drink_preference", "")
            if drink_pref == "zero_sugar":
                reasons.append("选择了零糖饮料")

        return reasons


# 全局实例
auto_draft_service = AutoDraftService()
