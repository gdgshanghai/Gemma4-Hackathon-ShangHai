"""稳一下模式 — 三重余额：热量余额、金钱余额、欲望余额"""

from pydantic import BaseModel, Field


class BalanceStatus(BaseModel):
    """三重余额状态"""
    calorie_balance: float = 0.0  # 热量余额 (千卡)
    money_balance: float = 0.0    # 金钱余额 (元)
    desire_balance: float = 0.0   # 欲望余额 (0-100)

    # 状态描述
    calorie_status: str = ""  # 充足 / 适中 / 紧张 / 已超标
    money_status: str = ""    # 充足 / 适中 / 紧张 / 已超标
    desire_status: str = ""   # 充足 / 适中 / 紧张 / 已超标

    # 综合建议
    overall_status: str = ""  # 放心吃 / 稳一下 / 控制一下 / 别吃了
    suggestion: str = ""


class BalanceMode:
    """稳一下模式控制器"""

    def calculate_balance(self, user, today_meals: list, mood: str = "normal") -> BalanceStatus:
        """计算三重余额"""
        from services.nutrition_calculator import calculate_bmr, calculate_tdee, get_daily_calorie_target

        # 1. 热量余额
        bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
        tdee = calculate_tdee(bmr, user.activity_level)
        daily_target = get_daily_calorie_target(tdee, user.goal.value)
        consumed_calories = sum(m.total_calories for m in today_meals)
        calorie_balance = daily_target - consumed_calories

        # 2. 金钱余额
        consumed_money = sum(m.total_price for m in today_meals)
        money_balance = user.daily_budget - consumed_money

        # 3. 欲望余额
        # 基于本周放纵次数和当前情绪
        weekly_indulgence_used = sum(1 for m in today_meals if m.plan_mode == "controlled_indulgence")
        desire_balance = 100 - (weekly_indulgence_used / max(1, user.weekly_indulgence_allowance) * 100)

        # 根据情绪调整欲望余额
        mood_modifier = {
            "tired": -20,
            "stressed": -15,
            "sad": -10,
            "normal": 0,
            "happy": 10,
        }
        desire_balance = max(0, min(100, desire_balance + mood_modifier.get(mood, 0)))

        # 计算状态
        calorie_status = self._get_status(calorie_balance, daily_target, is_calorie=True)
        money_status = self._get_status(money_balance, user.daily_budget, is_calorie=False)
        desire_status = self._get_desire_status(desire_balance)

        # 综合建议
        overall_status, suggestion = self._get_overall_advice(
            calorie_status, money_status, desire_status
        )

        return BalanceStatus(
            calorie_balance=round(calorie_balance),
            money_balance=round(money_balance, 2),
            desire_balance=round(desire_balance),
            calorie_status=calorie_status,
            money_status=money_status,
            desire_status=desire_status,
            overall_status=overall_status,
            suggestion=suggestion,
        )

    def _get_status(self, balance: float, total: float, is_calorie: bool) -> str:
        """获取状态"""
        ratio = balance / total if total > 0 else 0

        if ratio > 0.5:
            return "充足"
        elif ratio > 0.2:
            return "适中"
        elif ratio > 0:
            return "紧张"
        else:
            return "已超标"

    def _get_desire_status(self, balance: float) -> str:
        """获取欲望余额状态"""
        if balance > 70:
            return "充足"
        elif balance > 40:
            return "适中"
        elif balance > 10:
            return "紧张"
        else:
            return "已耗尽"

    def _get_overall_advice(self, calorie: str, money: str, desire: str) -> tuple:
        """获取综合建议"""
        # 统计紧张/超标数量
        紧张_count = sum(1 for s in [calorie, money, desire] if s in ["紧张", "已超标", "已耗尽"])

        if 紧张_count == 0:
            return "放心吃", "三重余额充足，可以放心选择"
        elif 紧张_count == 1:
            return "稳一下", "有一项余额紧张，建议适当控制"
        elif 紧张_count == 2:
            return "控制一下", "多项余额紧张，建议选择清淡/低价选项"
        else:
            return "别吃了", "三重余额都紧张，建议休息或选择极简餐"


# 全局实例
balance_mode = BalanceMode()
