"""Demo 服务 — 7 天长期伴随模拟"""

import uuid
from datetime import datetime, timedelta
from models.user_profile import UserProfile, Goal
from services.db_service import db_service
from services.memory_service import memory_service


class DemoService:
    """7 天长期伴随 Demo 服务"""

    async def simulate_week(self, user_id: str = "demo-user") -> dict:
        """模拟 7 天行为"""
        # 检查用户是否已存在
        existing_user = await db_service.get_user(user_id)
        if not existing_user:
            # 创建用户档案
            user = UserProfile(
                user_id=user_id,
                name="高压学生",
                goal=Goal.LOSE_WEIGHT,
                daily_budget=35.0,
                weekly_budget=220.0,
                meal_schedule={"breakfast": "08:30", "lunch": "12:30", "dinner": "18:30"},
            )
            # 保存用户
            await db_service.create_user(user.model_dump())

        # 模拟 7 天用餐记录
        timeline = self._generate_timeline()
        learning_points = []

        for day in timeline:
            for meal in day["meals"]:
                await db_service.create_meal(meal)
            learning_points.extend(day.get("learning", []))

        return {
            "user_id": user_id,
            "days_simulated": 7,
            "meals_recorded": sum(len(d["meals"]) for d in timeline),
            "learning_points": learning_points,
            "timeline": timeline,
        }

    def _generate_timeline(self) -> list[dict]:
        """生成 7 天时间线"""
        base_date = datetime.now() - timedelta(days=7)
        timeline = []

        # Day 1: 用户下午2点才吃午饭
        timeline.append({
            "day": 1,
            "date": (base_date + timedelta(days=1)).isoformat(),
            "scenario": "午餐延迟",
            "meals": [
                self._create_meal(base_date + timedelta(days=1, hours=14), "lunch", 25.0, 450),
                self._create_meal(base_date + timedelta(days=1, hours=19), "dinner", 35.0, 650),
            ],
            "learning": ["用户容易错过午餐时间，通常在14:00后才吃"],
            "system_action": "学到：用户午餐时间不规律",
        })

        # Day 2: 用户拒绝咖啡，换成零度可乐
        timeline.append({
            "day": 2,
            "date": (base_date + timedelta(days=2)).isoformat(),
            "scenario": "口味偏好学习",
            "meals": [
                self._create_meal(base_date + timedelta(days=2, hours=12, minutes=30), "lunch", 28.0, 510),
                self._create_meal(base_date + timedelta(days=2, hours=18, minutes=30), "dinner", 32.0, 580),
            ],
            "learning": ["用户不喜欢咖啡，更接受零度饮料"],
            "system_action": "学到：用户不喜欢咖啡，推荐零度可乐",
        })

        # Day 3: 晚餐预算超支
        timeline.append({
            "day": 3,
            "date": (base_date + timedelta(days=3)).isoformat(),
            "scenario": "预算超支",
            "meals": [
                self._create_meal(base_date + timedelta(days=3, hours=12), "lunch", 22.0, 400),
                self._create_meal(base_date + timedelta(days=3, hours=19), "dinner", 45.0, 850),
            ],
            "learning": ["晚餐容易超预算，需要更严格的控制"],
            "system_action": "学到：晚餐预算容易超支",
        })

        # Day 4: 用户说太累了，想吃爽点
        timeline.append({
            "day": 4,
            "date": (base_date + timedelta(days=4)).isoformat(),
            "scenario": "情绪性进食",
            "meals": [
                self._create_meal(base_date + timedelta(days=4, hours=13), "lunch", 30.0, 550),
                self._create_meal(base_date + timedelta(days=4, hours=20), "dinner", 38.0, 750),
            ],
            "learning": ["用户压力大时更容易选择高热量套餐"],
            "system_action": "触发稳一下模式，保留满足感但控制热量",
        })

        # Day 5: 用户连续快餐，高钠风险升高
        timeline.append({
            "day": 5,
            "date": (base_date + timedelta(days=5)).isoformat(),
            "scenario": "营养风险提醒",
            "meals": [
                self._create_meal(base_date + timedelta(days=5, hours=12, minutes=30), "lunch", 25.0, 480),
                self._create_meal(base_date + timedelta(days=5, hours=18), "dinner", 30.0, 620),
            ],
            "learning": ["用户本周已有3次高钠快餐，需要提醒清淡饮食"],
            "system_action": "提醒下一餐选择清淡选项",
        })

        # Day 6: 系统提前提醒午餐，用户采纳订单草稿
        timeline.append({
            "day": 6,
            "date": (base_date + timedelta(days=6)).isoformat(),
            "scenario": "主动提醒采纳",
            "meals": [
                self._create_meal(base_date + timedelta(days=6, hours=12), "lunch", 28.0, 520),
                self._create_meal(base_date + timedelta(days=6, hours=18, minutes=30), "dinner", 32.0, 580),
            ],
            "learning": ["用户接受系统主动提醒，午餐时间提前到12:00"],
            "system_action": "成功提前提醒午餐，用户采纳",
        })

        # Day 7: 系统生成周总结
        timeline.append({
            "day": 7,
            "date": (base_date + timedelta(days=7)).isoformat(),
            "scenario": "周总结",
            "meals": [
                self._create_meal(base_date + timedelta(days=7, hours=12), "lunch", 26.0, 480),
                self._create_meal(base_date + timedelta(days=7, hours=18, minutes=30), "dinner", 30.0, 550),
            ],
            "learning": ["系统生成周总结，展示改善数据"],
            "system_action": "生成周总结报告",
        })

        return timeline

    def _create_meal(self, timestamp: datetime, meal_type: str, price: float, calories: float) -> dict:
        """创建用餐记录"""
        return {
            "id": str(uuid.uuid4())[:8],
            "user_id": "demo-user",
            "timestamp": timestamp,
            "meal_type": meal_type,
            "items": [{"name": f"模拟菜品-{meal_type}", "price": price, "calories": calories}],
            "total_price": price,
            "total_calories": calories,
            "total_protein": 20.0,
            "total_fat": 15.0,
            "total_carbs": 50.0,
            "total_sodium": 800.0,
            "plan_mode": "disciplined" if meal_type == "lunch" else "controlled_indulgence",
        }

    async def get_timeline(self, user_id: str = "demo-user") -> dict:
        """获取 7 天时间线"""
        meals = await db_service.get_meals(user_id, days=7)

        # 按天分组
        days = {}
        for meal in meals:
            date = meal.timestamp.date().isoformat()
            if date not in days:
                days[date] = []
            days[date].append({
                "time": meal.timestamp.strftime("%H:%M"),
                "meal_type": meal.meal_type,
                "price": meal.total_price,
                "calories": meal.total_calories,
            })

        return {
            "user_id": user_id,
            "days": days,
            "total_meals": len(meals),
        }

    async def get_learning_points(self, user_id: str = "demo-user") -> list[str]:
        """获取学习点"""
        patterns = await memory_service.get_meal_patterns(user_id)
        preferences = await memory_service.get_preferences(user_id)

        points = []

        # 分析用餐时间
        usual_times = patterns.get("usual_times", {})
        if "lunch" in usual_times:
            lunch_time = usual_times["lunch"]
            if lunch_time >= "13:00":
                points.append(f"你经常在 {lunch_time} 后才想起午餐")

        # 分析口味偏好
        avoided = preferences.get("avoided_items", [])
        if avoided:
            points.append(f"你不喜欢：{', '.join(avoided[:3])}")

        # 分析预算
        avg_spend = patterns.get("avg_daily_spend", 0)
        if avg_spend > 0:
            points.append(f"你通常每日餐饮消费在 ¥{avg_spend:.0f} 左右")

        # 分析跳餐
        skipped = patterns.get("skipped_meals", [])
        if skipped:
            points.append(f"你经常跳过：{', '.join(skipped)}")

        # 分析常点菜品
        frequent = patterns.get("frequent_items", [])
        if frequent:
            points.append(f"你最爱点：{', '.join(frequent[:3])}")

        # 分析晚餐时间
        if "dinner" in usual_times:
            dinner_str = usual_times["dinner"]
            if dinner_str and isinstance(dinner_str, str) and ":" in dinner_str:
                dinner_hour = int(dinner_str.split(":")[0])
                if dinner_hour >= 18:
                    points.append(f"你通常晚餐较晚（{dinner_str} 左右），建议 18 点前用餐更利消化")

        # 分析消费波动
        budget_usage = patterns.get("budget_usage", {})
        max_daily = budget_usage.get("max_daily", 0)
        min_daily = budget_usage.get("min_daily", 0)
        if max_daily > 0 and min_daily > 0 and max_daily > min_daily * 1.3:
            points.append(f"你的消费波动较大：最低 ¥{min_daily:.0f}，最高 ¥{max_daily:.0f}")

        return points


# 全局实例
demo_service = DemoService()
