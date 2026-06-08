"""方案精炼路由"""

import json
import logging
from fastapi import APIRouter
from models.active_plan import ActivePlan
from models.recommendation import MenuItem
from services.active_plan_service import active_plan_service
from services.conversation_service import conversation_service
from core.llm_client import generate_json

logger = logging.getLogger(__name__)

router = APIRouter()


async def _parse_refinement_request(message: str, current_items: list[MenuItem]) -> dict:
    """
    使用 LLM 解析用户的修改请求

    Returns:
        dict: {
            "action": "remove" | "replace" | "add" | "sort" | "constraint",
            "target_items": list[str],  # 要操作的菜品名称
            "replacement": str | None,  # 替换成什么
            "constraint": str | None,   # 约束条件（如 "price<25"）
            "reason": str,              # 原因
        }
    """
    # 构建当前菜品列表
    items_desc = ", ".join([f"{i.name}(¥{i.price}, {i.calories}kcal)" for i in current_items])

    system_prompt = """你是一个饮食方案修改助手。用户的修改请求，解析成结构化的操作。

返回 JSON 格式：
{
    "action": "remove" | "replace" | "add" | "sort" | "constraint",
    "target_items": ["要操作的菜品名称"],
    "replacement": "替换成什么（如果是replace操作）",
    "constraint": "约束条件（如 price<25, calories<500）",
    "reason": "修改原因"
}

常见场景：
- "不要咖啡" -> action: remove, target_items: ["咖啡相关"]
- "换成零度可乐" -> action: replace, replacement: "零度可乐"
- "太贵了，控制在25以内" -> action: constraint, constraint: "price<25"
- "来点便宜的" -> action: sort, constraint: "price_asc"
- "加个薯条" -> action: add, target_items: ["薯条"]"""

    user_prompt = f"当前菜品：{items_desc}\n\n用户请求：{message}"

    result = await generate_json(system_prompt, user_prompt)

    # 如果 LLM 调用失败，使用简单的关键词匹配作为 fallback
    if result.get("fallback") or result.get("error"):
        return _fallback_parse(message)

    return result


def _fallback_parse(message: str) -> dict:
    """简单的关键词匹配 fallback"""
    message_lower = message.lower()

    # 移除操作
    if any(kw in message_lower for kw in ["不要", "去掉", "删除", "换掉"]):
        target = []
        if "咖啡" in message:
            target.append("咖啡")
        if "可乐" in message and "零度" not in message:
            target.append("可口可乐")
        if "炸" in message:
            target.append("炸")
        if "甜" in message:
            target.append("甜")
        return {
            "action": "remove",
            "target_items": target or [message],
            "replacement": None,
            "constraint": None,
            "reason": f"用户不想吃：{', '.join(target)}"
        }

    # 替换操作
    if "换成" in message or "改为" in message:
        return {
            "action": "replace",
            "target_items": [],
            "replacement": message,
            "constraint": None,
            "reason": f"用户要求替换"
        }

    # 价格约束
    if any(kw in message_lower for kw in ["便宜", "省钱", "预算"]):
        return {
            "action": "constraint",
            "target_items": [],
            "replacement": None,
            "constraint": "price_asc",
            "reason": "用户希望更便宜"
        }

    # 默认：作为约束处理
    return {
        "action": "constraint",
        "target_items": [],
        "replacement": None,
        "constraint": message,
        "reason": f"用户要求：{message}"
    }


async def _apply_refinement(plan: ActivePlan, parsed: dict) -> list[MenuItem]:
    """根据解析结果应用修改"""
    from providers.factory import get_provider

    new_items = list(plan.items)
    action = parsed.get("action", "constraint")
    target_items = parsed.get("target_items", [])
    replacement = parsed.get("replacement")
    constraint = parsed.get("constraint", "")

    if action == "remove":
        # 移除匹配的菜品
        filtered = []
        for item in new_items:
            should_remove = False
            for target in target_items:
                if target in item.name or target in str(item.tags):
                    should_remove = True
                    break
            if not should_remove:
                filtered.append(item)
        new_items = filtered

    elif action == "replace":
        # 移除旧菜品，添加新菜品
        if target_items:
            filtered = []
            for item in new_items:
                should_remove = False
                for target in target_items:
                    if target in item.name:
                        should_remove = True
                        break
                if not should_remove:
                    filtered.append(item)
            new_items = filtered

        # 查找替代品
        if replacement:
            provider = await get_provider()
            all_items = await provider.list_items()
            for item in all_items:
                if replacement in item.name:
                    new_items.append(MenuItem(
                        name=item.name,
                        item_code=item.item_code,
                        category=item.category,
                        price=item.price,
                        calories=item.calories,
                        protein=item.protein,
                        fat=item.fat,
                        carbohydrate=item.carbohydrate,
                        sodium=item.sodium,
                        tags=item.tags,
                    ))
                    break

    elif action == "sort":
        # 按约束排序
        if "price" in constraint:
            new_items.sort(key=lambda x: x.price)
        elif "calories" in constraint or "cal" in constraint:
            new_items.sort(key=lambda x: x.calories)

    elif action == "constraint":
        # 价格约束
        if "price" in constraint or "便宜" in constraint:
            # 提取价格限制
            import re
            price_match = re.search(r'(\d+)', constraint)
            if price_match:
                max_price = float(price_match.group(1))
                # 保留价格最低的菜品
                new_items.sort(key=lambda x: x.price)
                # 累加价格，超过限制就停止
                total = 0
                filtered = []
                for item in new_items:
                    if total + item.price <= max_price:
                        filtered.append(item)
                        total += item.price
                new_items = filtered

    return new_items


@router.post("/plan/refine", response_model=ActivePlan)
async def refine_plan(body: dict):
    """
    精炼当前方案
    Body: { plan_id, message, constraints }
    """
    plan_id = body.get("plan_id", "")
    message = body.get("message", "")
    constraints = body.get("constraints", [])

    plan = await active_plan_service.get_plan(plan_id)
    if not plan:
        return {"error": "方案不存在"}

    # 使用 LLM 解析用户的修改请求
    parsed = await _parse_refinement_request(message, plan.items)
    logger.info(f"Parsed refinement: {parsed}")

    # 应用修改
    new_items = await _apply_refinement(plan, parsed)

    # 构建变更描述
    what_changed = parsed.get("reason", message)
    why = f"用户要求：{message}"

    # 精炼方案
    refined = await active_plan_service.refine_plan(
        plan_id=plan_id,
        new_items=new_items,
        what_changed=what_changed,
        why=why,
        constraints=constraints,
    )

    if not refined:
        return {"error": "精炼失败"}

    # 记录对话
    change_log = refined.change_log[-1] if refined.change_log else None
    assistant_reply = f"已更新方案：{what_changed}"
    if change_log:
        assistant_reply += f"。{change_log.impact}"

    await conversation_service.add_message("demo-user", "user", message)
    await conversation_service.add_message("demo-user", "assistant", assistant_reply)

    return refined


@router.get("/plan/{plan_id}", response_model=ActivePlan)
async def get_plan(plan_id: str):
    """获取当前方案"""
    plan = await active_plan_service.get_plan(plan_id)
    if not plan:
        return {"error": "方案不存在"}
    return plan


@router.post("/plan/reset")
async def reset_plan(body: dict):
    """重置指定方案"""
    plan_id = body.get("plan_id", "")
    success = await active_plan_service.reset_plan(plan_id)
    return {"success": success, "message": "方案已重置" if success else "方案不存在"}


@router.get("/conversation/history")
async def get_conversation_history(user_id: str = "demo-user", limit: int = 50):
    """获取对话历史"""
    messages = await conversation_service.get_history(user_id, limit)
    return {
        "user_id": user_id,
        "messages": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}
            for m in messages
        ]
    }


@router.post("/conversation/reset")
async def reset_conversation(body: dict):
    """重置对话历史"""
    user_id = body.get("user_id", "demo-user")
    success = await conversation_service.reset_conversation(user_id)
    # 同时重置所有方案
    active_plan_service.reset_all()
    return {"success": success, "message": "对话已重置"}
