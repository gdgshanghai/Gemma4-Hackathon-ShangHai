"""AI 导师角色扮演流式会话路由."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from app.api.deps import get_current_user_id
from app.services import agent

router = APIRouter()


@router.get(
    "/chat",
    summary="与 AI 导师/同事进行沉浸式流式对话",
    response_class=StreamingResponse,
)
async def chat_with_agent_stream(
    role_name: str = Query("高凌 (Tech Lead)", description="扮演角色"),
    message: str = Query(..., description="用户输入的消息"),
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
  """Streams incremental typewriter chunks mapping to SSE protocol."""
  async def sse_adapter():
    async for char in agent.act_as_role(
        role_name=role_name, user_input=message, user_id=user_id,
    ):
      yield f"data: {char}\n\n"

  return StreamingResponse(sse_adapter(), media_type="text/event-stream")

