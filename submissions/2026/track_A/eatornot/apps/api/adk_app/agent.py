"""ADK Agent — EatOrNot 根 Agent"""

import logging
from google.adk import Agent
from google.adk.tools import FunctionTool
from core.config import get_settings

from .skills_loader import build_skill_instructions
from .food_provider_tools import (
    search_menu,
    get_nutrition,
    calculate_price,
    create_order_draft,
    confirm_order,
)
from .mcp_tools import (
    mcd_list_nutrition_foods,
    mcd_query_nearby_stores,
    mcd_calculate_price,
    mcd_create_order,
)

logger = logging.getLogger(__name__)

# 加载 Skills 指令
SKILL_INSTRUCTIONS = build_skill_instructions()

SYSTEM_INSTRUCTION = f"""你是 EatOrNot，一个双模式智能饮食决策助手。

你不是麦当劳 MCP 的简单包装器。你帮助用户在以下维度之间做出平衡的饮食决策：
- 健康目标（减脂/增肌/维持）
- 身体档案（身高/体重/年龄/BMI）
- 营养需求（蛋白质/脂肪/碳水/钠）
- 预算限制（日预算/周预算）
- 口腹之欲（情绪/渴望）
- 时间压力
- 安全（过敏/极端饮食）
- 未来影响

## 工作模式

1. **长期管理模式**：用户有完整档案，追踪长期目标
2. **快速选择模式**：用户只想要一顿饭的建议

## 决策流程

1. 理解用户需求和约束
2. 使用 FoodProvider 工具获取菜单和营养数据
3. 综合各维度分析，给出 3 个推荐方案：
   - 自律方案（最健康）
   - 省钱方案（最实惠）
   - 放纵方案（最满足）
4. 解释每个方案的利弊
5. 用户选择后支持多轮精炼
6. 下单前必须用户明确确认

## 重要规则

- 绝不自动创建真实订单
- 对过敏信息要特别小心
- 不提供医疗诊断
- 极端饮食目标要警告
- 使用中文交流
- 用鼓励而非指责的语气

{SKILL_INSTRUCTIONS}
"""

# 创建 ADK Agent
settings = get_settings()
root_agent = Agent(
    name="eatornot_root_agent",
    model=settings.GEMMA_MODEL,
    description="双模式多 Agent 饮食决策助手",
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        # FoodProvider 工具
        FunctionTool(search_menu),
        FunctionTool(get_nutrition),
        FunctionTool(calculate_price),
        FunctionTool(create_order_draft),
        FunctionTool(confirm_order),
        # MCP 工具
        FunctionTool(mcd_list_nutrition_foods),
        FunctionTool(mcd_query_nearby_stores),
        FunctionTool(mcd_calculate_price),
        FunctionTool(mcd_create_order),
    ],
)

logger.info("ADK Agent initialized with %d tools", len(root_agent.tools))


async def get_agent_response(message: str, context: dict = None) -> str:
    """
    获取 Agent 响应（适配器函数）

    Args:
        message: 用户消息
        context: 上下文信息

    Returns:
        Agent 响应文本
    """
    try:
        from google.adk.runners import InMemoryRunner
        from google.adk.sessions import Session

        runner = InMemoryRunner(agent=root_agent)

        # 创建会话
        session = await runner.session_service.create_session(
            app_name="eatornot",
            user_id="demo-user",
        )

        # 运行 Agent
        from google.genai import types
        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)]
        )

        response_text = ""
        async for event in runner.run_async(
            user_id="demo-user",
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        return response_text or "抱歉，我无法处理这个请求。"

    except Exception as e:
        logger.error(f"ADK Agent error: {e}")
        return f"[Agent 错误: {str(e)}]"
