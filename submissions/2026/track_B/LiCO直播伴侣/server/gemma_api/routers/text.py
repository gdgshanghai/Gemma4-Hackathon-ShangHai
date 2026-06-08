from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from gemma_api.config import OLLAMA_MODEL  # gemma4-31b-mm
from gemma_api.schemas import AnalyzeResponse, RequestType, TextSummarizeRequest
from gemma_api.services import agent
from gemma_api.services.sse import sse_line

router = APIRouter(prefix="/text", tags=["text"])


@router.post("/summarize")
async def summarize_text(body: TextSummarizeRequest):
    if body.stream:

        async def event_stream():
            async for payload in agent.iter_process_text(
                body.prompt,
                body.text,
                enable_search=body.enable_search,
                include_thinking=body.include_thinking,
            ):
                yield sse_line(payload)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    answer, tools, used, meta = await agent.process_text(
        body.prompt,
        body.text,
        enable_search=body.enable_search,
        include_thinking=body.include_thinking,
    )
    return AnalyzeResponse(
        request_type=RequestType.TEXT,
        model=OLLAMA_MODEL,
        answer=answer,
        tool_calls=tools,
        used_search=used,
        meta=meta,
    )
