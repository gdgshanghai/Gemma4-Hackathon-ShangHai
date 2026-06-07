"""Celery tasks for precomputing branch trees in parallel after PPTX parse.

Architecture:
  One batch task (generate_all_branches) processes ALL slides in parallel
  using asyncio.gather, rather than spawning N separate Celery tasks.
  This avoids Celery scheduling overhead and keeps parallelism simple.

  After each slide completes, the result is stored in BranchStore AND
  published to a Redis pub/sub channel so the SSE endpoint can stream
  progress to the frontend in real time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from app.celery_app import celery_app
from app.services.branch_generator import BranchGenerator
from app.services.branch_store import BranchStore

logger = logging.getLogger(__name__)

# Max concurrent LLM calls — tune based on API rate limits.
# The branch LLM is I/O-bound (HTTP), so 4-8 concurrent calls
# will saturate most endpoints without hitting rate limits.
MAX_CONCURRENT = 6

# Pub/sub channel prefix for SSE progress streaming
PUBSUB_CHANNEL = "branch:events"


def _publish_branch_ready(parse_id: str, slide_index: int, branch_count: int) -> None:
    """Publish a branch_ready event to Redis pub/sub."""
    try:
        from redis import Redis
        from app.core.config import settings
        r = Redis.from_url(settings.redis_url, decode_responses=True)
        payload = json.dumps({
            "event": "branch_ready",
            "parse_id": parse_id,
            "slide_index": slide_index,
            "branch_count": branch_count,
        })
        r.publish(f"{PUBSUB_CHANNEL}:{parse_id}", payload)
        r.close()
    except Exception:
        logger.warning("Failed to publish branch_ready for parse=%s slide=%d", parse_id, slide_index, exc_info=True)


async def _generate_one_slide(
    generator: BranchGenerator,
    parse_id: str,
    slide_index: int,
    total_slides: int,
    image_b64: str,
    prev_text: str | None,
    next_text: str | None,
) -> None:
    """Generate branches for one slide and store+publish the result."""
    logger.info("Branch batch: starting slide %d/%d", slide_index + 1, total_slides)
    result = await generator.generate(
        slide_image_base64=image_b64,
        slide_index=slide_index,
        total_slides=total_slides,
        max_depth=3,
        prev_slide_text=prev_text,
        next_slide_text=next_text,
    )
    if result.error:
        logger.error("Branch batch: slide %d failed: %s", slide_index, result.error)
        BranchStore.put(parse_id, slide_index, [])
        _publish_branch_ready(parse_id, slide_index, 0)
    else:
        logger.info(
            "Branch batch: slide %d done — %d top-level branches (%.0fms)",
            slide_index,
            len(result.branches),
            result.generation_time_ms,
        )
        BranchStore.put(parse_id, slide_index, result.branches)
        _publish_branch_ready(parse_id, slide_index, len(result.branches))


@celery_app.task(name="app.tasks.branch_jobs.generate_all_branches")
def generate_all_branches(
    parse_id: str,
    total_slides: int,
    slides_data: list[dict],
) -> None:
    """Batch task: generate branches for ALL slides in parallel.

    Args:
        parse_id: The parse cache ID.
        total_slides: Total number of slides (for progress tracking).
        slides_data: List of dicts, each with keys:
            slide_index, image_b64, prev_text (str|None), next_text (str|None).
    """
    t0 = time.monotonic()
    logger.info("Branch batch: starting %d slides for parse=%s (max_concurrent=%d)",
                len(slides_data), parse_id, MAX_CONCURRENT)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    generator = BranchGenerator()

    async def bounded(sd: dict) -> None:
        async with semaphore:
            await _generate_one_slide(
                generator=generator,
                parse_id=parse_id,
                slide_index=sd["slide_index"],
                total_slides=total_slides,
                image_b64=sd["image_b64"],
                prev_text=sd.get("prev_text"),
                next_text=sd.get("next_text"),
            )

    async def run_all() -> None:
        tasks = [bounded(sd) for sd in slides_data]
        await asyncio.gather(*tasks, return_exceptions=False)

    try:
        asyncio.run(run_all())
        elapsed = time.monotonic() - t0
        logger.info("Branch batch: ALL %d slides done in %.1fs (%.1fs/slide avg)",
                    len(slides_data), elapsed, elapsed / max(len(slides_data), 1))

        # Publish a final "done" event
        try:
            from redis import Redis
            from app.core.config import settings
            r = Redis.from_url(settings.redis_url, decode_responses=True)
            payload = json.dumps({
                "event": "done",
                "parse_id": parse_id,
                "total_slides": total_slides,
                "elapsed_s": round(elapsed, 1),
            })
            r.publish(f"{PUBSUB_CHANNEL}:{parse_id}", payload)
            r.close()
        except Exception:
            logger.warning("Failed to publish done event for parse=%s", parse_id, exc_info=True)

    except Exception:
        logger.exception("Branch batch: fatal error for parse=%s", parse_id)
        # Store empty results for any slides that didn't finish
        for sd in slides_data:
            if BranchStore.get(parse_id, sd["slide_index"]) is None:
                BranchStore.put(parse_id, sd["slide_index"], [])


# ── Legacy per-slide task (kept for backward compatibility) ──

@celery_app.task(name="app.tasks.branch_jobs.generate_branches_for_slide")
def generate_branches_for_slide(
    parse_id: str,
    slide_index: int,
    total_slides: int,
    slide_image_base64: str,
    prev_slide_text: str | None = None,
    next_slide_text: str | None = None,
) -> None:
    """Generate branch tree for a single slide, store in Redis.

    DEPRECATED: Prefer generate_all_branches for parallel execution.
    This task exists for backward compatibility and ad-hoc single-slide regeneration.
    """
    try:
        logger.info("Branch job: generating slide %d/%d (parse=%s)", slide_index + 1, total_slides, parse_id)
        async def _run():
            gen = BranchGenerator()
            return await gen.generate(
                slide_image_base64=slide_image_base64,
                slide_index=slide_index,
                total_slides=total_slides,
                max_depth=3,
                prev_slide_text=prev_slide_text,
                next_slide_text=next_slide_text,
            )
        result = asyncio.run(_run())
        if result.error:
            logger.error("Branch job: slide %d failed: %s", slide_index, result.error)
            BranchStore.put(parse_id, slide_index, [])
        else:
            logger.info(
                "Branch job: slide %d done — %d top-level branches (%.0fms)",
                slide_index,
                len(result.branches),
                result.generation_time_ms,
            )
            BranchStore.put(parse_id, slide_index, result.branches)
        _publish_branch_ready(parse_id, slide_index, len(result.branches) if not result.error else 0)
    except Exception:
        logger.exception("Branch job: slide %d unexpected error", slide_index)
        BranchStore.put(parse_id, slide_index, [])
        _publish_branch_ready(parse_id, slide_index, 0)
