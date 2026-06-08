"""安全边界和隐私声明路由"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/safety/policy")
async def get_safety_policy():
    """获取安全边界和隐私声明"""
    return {
        "version": "1.0",
        "last_updated": "2026-05-31",
        "sections": [
            {
                "id": "medical_disclaimer",
                "title": "非医疗声明",
                "content": "EatOrNot 是饮食与消费决策助手，不是医疗诊断系统。所有营养建议仅供参考，不构成医疗建议。如有健康问题，请咨询专业医生。",
                "icon": "🏥"
            },
            {
                "id": "allergy_safety",
                "title": "过敏安全",
                "content": "系统会检查用户提供的过敏信息，但无法保证 100% 准确识别所有过敏原。用户应自行确认食物成分，对严重过敏者建议咨询医生。",
                "icon": "⚠️"
            },
            {
                "id": "order_confirmation",
                "title": "订单确认",
                "content": "系统不会自动创建真实订单。所有订单草稿必须经用户明确确认后才能提交。用户确认前可随时取消。",
                "icon": "✅"
            },
            {
                "id": "budget_advisory",
                "title": "预算建议",
                "content": "预算建议仅供参考，不构成财务建议。用户应根据自身实际情况做出消费决策。",
                "icon": "💰"
            },
            {
                "id": "data_privacy",
                "title": "数据隐私",
                "content": "用户饮食、健康和消费数据仅用于提供个性化建议。数据存储在本地数据库，不会未经授权分享给第三方。用户可随时删除自己的数据。",
                "icon": "🔒"
            },
            {
                "id": "extreme_diet_warning",
                "title": "极端饮食警告",
                "content": "系统不鼓励极端节食或不健康的饮食行为。如检测到极端饮食目标，系统会发出警告并建议调整。",
                "icon": "🚨"
            }
        ],
        "high_risk_actions": [
            {
                "action": "create_order",
                "description": "创建订单",
                "requires_confirmation": True,
                "warning": "订单创建前必须用户确认"
            },
            {
                "action": "share_health_data",
                "description": "分享健康数据",
                "requires_confirmation": True,
                "warning": "分享健康数据前必须用户确认"
            }
        ],
        "contact": {
            "issues": "如有安全问题，请联系项目维护者",
            "github": "https://github.com/fgh23333/eatornot/issues"
        }
    }


@router.get("/safety/check")
async def safety_check(
    user_id: str = "demo-user",
    action: str = "recommend",
    context: dict = {}
):
    """安全检查"""
    warnings = []

    # 检查过敏
    allergies = context.get("allergies", [])
    if allergies:
        warnings.append({
            "type": "allergy",
            "message": f"用户有过敏信息：{', '.join(allergies)}",
            "severity": "high"
        })

    # 检查极端饮食目标
    goal = context.get("goal", "")
    weight = context.get("weight", 0)
    if goal == "lose_weight" and weight < 50:
        warnings.append({
            "type": "extreme_diet",
            "message": "体重已偏低，建议维持而非继续减重",
            "severity": "high"
        })

    # 检查预算超支
    daily_budget = context.get("daily_budget", 0)
    estimated_price = context.get("estimated_price", 0)
    if daily_budget > 0 and estimated_price > daily_budget:
        warnings.append({
            "type": "budget_exceeded",
            "message": f"预估价格 ¥{estimated_price} 超过日预算 ¥{daily_budget}",
            "severity": "medium"
        })

    return {
        "action": action,
        "safe": len([w for w in warnings if w["severity"] == "high"]) == 0,
        "warnings": warnings,
        "requires_confirmation": action in ["create_order", "share_health_data"],
    }
