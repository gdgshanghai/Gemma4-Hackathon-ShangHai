from __future__ import annotations

import asyncio
import json
import logging

from redis import Redis
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.live import (
    BranchGenerateRequest,
    BranchMatchRequest,
    BranchMatchResult,
    BranchTreeResponse,
    PrecomputedBranchesResponse,
)
from app.services.branch_generator import BranchGenerator
from app.services.branch_matcher import match_branch
from app.services.branch_store import BranchStore
from app.services.live_session import LiveSessionManager
from app.services.parse_cache import ParseCache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live"])


def _extract_slide_text(slide) -> str:
    """Extract all text from a SlideResult's elements as a compact summary."""
    lines: list[str] = []
    for el in slide.elements:
        if el.text and el.text.strip():
            lines.append(el.text.strip())
    return "\n".join(lines)


@router.websocket("/ws/live")
async def live_websocket(ws: WebSocket):
    await ws.accept()
    session = LiveSessionManager.create(ws)
    try:
        await session.run()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session.session_id)
    except Exception:
        logger.exception("Unexpected error in live session %s", session.session_id)
    finally:
        LiveSessionManager.remove(session.session_id)


@router.post("/branches", response_model=BranchTreeResponse)
async def generate_branches(req: BranchGenerateRequest) -> BranchTreeResponse:
    """Generate a branch prediction tree for a slide.

    Looks up the slide image from ParseCache by parse_id, then calls the
    multimodal LLM to generate a 3-level branch tree with predicted text
    and visual actions (highlight/circle/arrow/transition).
    """
    # Look up slide from parse cache
    slides = ParseCache.get(req.parse_id)
    if not slides:
        raise HTTPException(status_code=404, detail=f"Parse cache not found for id: {req.parse_id}")

    if req.slide_index < 0 or req.slide_index >= len(slides):
        raise HTTPException(
            status_code=400,
            detail=f"slide_index {req.slide_index} out of range (0-{len(slides) - 1})",
        )

    slide = slides[req.slide_index]
    if not slide.image or not slide.image.image_base64:
        raise HTTPException(status_code=400, detail="Slide has no image")

    # Pass adjacent slide TEXT (not images) for narrative continuity awareness
    prev_text = None
    if req.slide_index > 0:
        prev_text = _extract_slide_text(slides[req.slide_index - 1]) or None

    next_text = None
    if req.slide_index + 1 < len(slides):
        next_text = _extract_slide_text(slides[req.slide_index + 1]) or None

    generator = BranchGenerator()
    return await generator.generate(
        slide_image_base64=slide.image.image_base64,
        slide_index=req.slide_index,
        total_slides=len(slides),
        max_depth=req.max_depth,
        prev_slide_text=prev_text,
        next_slide_text=next_text,
    )


@router.get("/branches/{parse_id}", response_model=PrecomputedBranchesResponse)
async def get_precomputed_branches(parse_id: str) -> PrecomputedBranchesResponse:
    """Return all precomputed branch trees for a given parse_id."""
    slides = ParseCache.get(parse_id)
    if not slides:
        raise HTTPException(status_code=404, detail=f"Parse cache not found for id: {parse_id}")

    total = len(slides)
    branches = BranchStore.get_all(parse_id, total)
    ready = len(branches) == total

    return PrecomputedBranchesResponse(
        parse_id=parse_id,
        total_slides=total,
        ready=ready,
        branches=branches,
    )


@router.get("/branches/{parse_id}/events")
async def stream_branch_events(parse_id: str):
    """SSE stream: push branch_ready events as each slide's branches are computed.

    - On connect, first sends all already-ready branches.
    - Then subscribes to Redis pub/sub for new completions.
    - Sends a final "done" event when all slides are ready.

    Frontend replaces polling GET /branches/{parse_id} with a single
    long-lived connection to this endpoint.
    """
    slides = ParseCache.get(parse_id)
    if not slides:
        raise HTTPException(status_code=404, detail=f"Parse cache not found for id: {parse_id}")

    total = len(slides)

    async def event_generator():
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        channel = f"branch:events:{parse_id}"

        try:
            # ── Phase 1: Send all already-ready branches ──
            already = BranchStore.get_all(parse_id, total)
            for idx in range(total):
                branches = already.get(idx)
                if branches is not None:
                    yield _sse_event("branch_ready", {
                        "parse_id": parse_id,
                        "slide_index": idx,
                        "branch_count": len(branches),
                        "branches": [b.model_dump(mode="json") for b in branches],
                    })

            # If all done already, send done and exit
            if len(already) == total:
                yield _sse_event("done", {
                    "parse_id": parse_id,
                    "total_slides": total,
                    "elapsed_s": 0.0,
                })
                return

            # ── Phase 2: Subscribe and stream new completions ──
            pubsub.subscribe(channel)
            ready_count = len(already)

            while ready_count < total:
                # Use get_message with timeout so we can check for client disconnect
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    try:
                        data = json.loads(msg["data"])
                    except json.JSONDecodeError:
                        continue

                    event_type = data.get("event")
                    if event_type == "branch_ready":
                        slide_idx = data.get("slide_index")
                        # Fetch actual branches from store (pub/sub only sends count)
                        branches = BranchStore.get(parse_id, slide_idx)
                        if branches is not None:
                            ready_count += 1
                            yield _sse_event("branch_ready", {
                                "parse_id": parse_id,
                                "slide_index": slide_idx,
                                "branch_count": len(branches),
                                "branches": [b.model_dump(mode="json") for b in branches],
                            })
                    elif event_type == "done":
                        pass  # Will break below when ready_count == total

                await asyncio.sleep(0.05)  # Avoid tight loop

            yield _sse_event("done", {
                "parse_id": parse_id,
                "total_slides": total,
            })

        finally:
            try:
                pubsub.unsubscribe(channel)
                pubsub.close()
                redis.close()
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/branches/{parse_id}/match")
async def match_branch_endpoint(
    parse_id: str,
    req: BranchMatchRequest,
) -> dict:
    """Debug endpoint: match a text string against precomputed branches for a slide."""
    branches = BranchStore.get(parse_id, req.slide_index)
    if branches is None:
        raise HTTPException(
            status_code=404,
            detail=f"No branches found for parse_id={parse_id} slide={req.slide_index}",
        )

    result = match_branch(req.text, branches)
    return {"match": result.model_dump() if result else None}


def _sse_event(event_type: str, data: dict) -> str:
    """Format a dict as an SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
