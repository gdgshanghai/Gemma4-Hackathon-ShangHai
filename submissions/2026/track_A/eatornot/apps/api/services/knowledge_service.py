"""知识库服务 — 为 Agent 提供营养学知识支持"""

import json
from pathlib import Path

_KNOWLEDGE_DIR = Path(__file__).parent.parent.parent.parent / "knowledge"
_knowledge_cache: dict | None = None


def _load_knowledge() -> dict:
    """加载知识库"""
    global _knowledge_cache
    if _knowledge_cache is None:
        knowledge_path = _KNOWLEDGE_DIR / "nutrition.json"
        with open(knowledge_path, "r", encoding="utf-8") as f:
            _knowledge_cache = json.load(f)
    return _knowledge_cache


def get_evidence_for_agent(agent_name: str, context: dict | None = None) -> list[str]:
    """
    根据 Agent 名称获取相关证据

    Args:
        agent_name: Agent 名称
        context: 上下文信息（可选）

    Returns:
        证据列表
    """
    knowledge = _load_knowledge()
    evidence = []

    if agent_name == "档案Agent":
        # 档案相关的证据
        evidence.append(knowledge["sources"]["chinese_dietary_guidelines_2022"]["name"])
        evidence.append(f"Mifflin-St Jeor 公式: {knowledge['formulas']['mifflin_st_jeor']['source']}")

    elif agent_name == "减脂Agent":
        # 减脂相关的证据
        evidence.append(f"热量缺口理论: {knowledge['formulas']['calorie_deficit']['guidelines']['safe_deficit']}")
        evidence.append(f"TDEE 计算: {knowledge['formulas']['tdee_multiplier']['name']}")

    elif agent_name == "营养Agent":
        # 营养相关的证据
        evidence.append(knowledge["sources"]["chinese_food_composition_6th"]["name"])
        evidence.append(knowledge["sources"]["who_nutrition_guidelines"]["name"])

    elif agent_name == "预算Agent":
        # 预算相关的证据
        evidence.append("用户设定的预算限制")
        evidence.append("当前菜单价格分析")

    elif agent_name == "食欲Agent":
        # 食欲相关的证据
        evidence.append(knowledge["emotional_eating"]["name"])
        evidence.append(f"管理策略: {knowledge['emotional_eating']['management_strategies'][0]}")

    elif agent_name == "时间Agent":
        # 时间相关的证据
        evidence.append("快餐出餐效率数据")
        evidence.append("用户时间压力评估")

    elif agent_name == "安全Agent":
        # 安全相关的证据
        evidence.append("食品过敏原数据库")
        evidence.append(knowledge["sources"]["chinese_dietary_guidelines_2022"]["key_points"][-1])

    elif agent_name == "未来模拟Agent":
        # 未来模拟相关的证据
        evidence.append("热量-预算平衡模型")
        evidence.append("今日剩余用餐计划")

    else:
        evidence.append("综合分析")

    return evidence[:2]  # 最多返回2条


def get_knowledge_point(category: str, key: str) -> str | None:
    """
    获取特定知识点

    Args:
        category: 知识类别
        key: 知识键

    Returns:
        知识内容
    """
    knowledge = _load_knowledge()

    if category == "source":
        source_key = key
        if source_key in knowledge["sources"]:
            return knowledge["sources"][source_key]["name"]

    elif category == "formula":
        formula_key = key
        if formula_key in knowledge["formulas"]:
            return knowledge["formulas"][formula_key]["description"]

    elif category == "food":
        # 食物分类知识
        if "food_categories" in knowledge:
            food_data = knowledge["food_categories"]
            if key in food_data:
                return str(food_data[key])

    return None
