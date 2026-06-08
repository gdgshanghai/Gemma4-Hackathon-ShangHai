"""Nutrition and calorie calculation utilities."""

import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"

_guidelines_cache: dict | None = None


def _load_guidelines() -> dict:
    global _guidelines_cache
    if _guidelines_cache is None:
        path = _DATA_DIR / "mock_nutrition_foods.json"
        with open(path, "r", encoding="utf-8") as f:
            _guidelines_cache = json.load(f)["daily_guidelines"]
    return _guidelines_cache


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m ** 2), 1)


def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Mifflin-St Jeor equation."""
    if sex == "male":
        return round(10 * weight_kg + 6.25 * height_cm - 5 * age + 5, 0)
    else:
        return round(10 * weight_kg + 6.25 * height_cm - 5 * age - 161, 0)


def calculate_tdee(bmr: float, activity_level: str) -> float:
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    return round(bmr * multipliers.get(activity_level, 1.375), 0)


def get_daily_calorie_target(tdee: float, goal: str) -> float:
    """Adjust daily calories based on goal."""
    guidelines = _load_guidelines()
    deficit = guidelines.get("calorie_deficit_kcal", 300)
    if goal == "lose_weight":
        return round(tdee - deficit, 0)
    elif goal == "gain_muscle":
        return round(tdee + 200, 0)
    return round(tdee, 0)


def get_meal_calorie_budget(daily_target: float, meal_type: str) -> float:
    """Split daily budget across meals."""
    splits = {"breakfast": 0.25, "lunch": 0.35, "dinner": 0.30, "snack": 0.10}
    return round(daily_target * splits.get(meal_type, 0.30), 0)


def evaluate_nutrition(item: dict) -> dict:
    """Evaluate a single food item's nutrition quality."""
    guidelines = _load_guidelines()
    sodium_limit = guidelines["sodium_mg"]["recommended_max"]
    flags = []
    score = 0.0

    # Protein score
    if item.get("protein", 0) >= 20:
        flags.append("good_protein")
        score += 0.3

    # Fat check
    if item.get("fat", 0) > 25:
        flags.append("high_fat")
        score -= 0.2
    elif item.get("fat", 0) < 10:
        flags.append("low_fat")
        score += 0.1

    # Sodium check
    if item.get("sodium", 0) > sodium_limit * 0.4:
        flags.append("high_sodium")
        score -= 0.2
    elif item.get("sodium", 0) < 200:
        flags.append("low_sodium")
        score += 0.1

    # Sugar-related (check tags)
    if "sugary" in item.get("tags", []):
        flags.append("sugary")
        score -= 0.1
    if "zero_sugar" in item.get("tags", []):
        flags.append("zero_sugar")
        score += 0.1

    # Low calorie bonus
    if item.get("calories", 0) < 200:
        flags.append("low_calorie")
        score += 0.1

    return {
        "score": round(max(-1, min(1, score)), 2),
        "flags": flags,
    }
