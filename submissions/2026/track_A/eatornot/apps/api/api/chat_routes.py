"""Simple chat endpoint for demo interaction."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    user_id: str = "demo-user"
    message: str = ""
    context: dict = {}


class ChatResponse(BaseModel):
    reply: str
    action: str = "none"  # none / recommend / order / feedback


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Simple keyword-based chat router (Phase 2: add LLM)."""
    msg = req.message.lower()

    if any(kw in msg for kw in ["麦当劳", "mcdonald", "想吃", "饿", "吃什么"]):
        return ChatResponse(
            reply="看起来你想吃点东西！让我帮你分析一下最佳选择。",
            action="recommend",
        )
    elif any(kw in msg for kw in ["确认", "下单", "confirm", "order"]):
        return ChatResponse(
            reply="好的，请确认你的选择。我会为你创建订单。",
            action="order",
        )
    elif any(kw in msg for kw in ["预算", "budget", "花了多少"]):
        return ChatResponse(
            reply="让我帮你看看今天的预算情况。",
            action="budget",
        )
    else:
        return ChatResponse(
            reply="你好！我是 EatOrNot，你的智能饮食助手。告诉我你想吃什么，我来帮你分析！",
            action="none",
        )
