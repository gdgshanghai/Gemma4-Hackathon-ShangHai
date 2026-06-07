from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.schemas.pptx import (
    JobStage,
    ParsePptxResponse,
    PptxScriptJobRecord,
    PptxScriptJobStatus,
    PptxScriptJobSubmitResponse,
    PptxScriptSseEvent,
    PresentationScriptResult,
    SlideReadySseEvent,
)
from app.services.file_service import FileService
from app.services.job_store import JobStore
from app.services.pptx_service import PptxService
from app.tasks.pptx_jobs import run_pptx_script_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_job_or_404(job_id: str) -> PptxScriptJobRecord:
    record = JobStore.get_job(job_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    return record


@router.post("/pptx-script", response_model=PptxScriptJobSubmitResponse)
async def submit_pptx_script_job(
    file: UploadFile = File(...),
    include_images_base64: bool = Query(default=True),
    flatten_groups: bool = Query(default=True),
    element_types: list[str] = Query(default=[]),
    llm_model: str | None = Query(default=None),
) -> PptxScriptJobSubmitResponse:
    request_id, file_path = await FileService.save_upload(file)

    try:
        job_status = JobStore.create_job(request_id=request_id)
        run_pptx_script_job.delay(
            job_id=job_status.job_id,
            request_id=request_id,
            file_path=str(file_path),
            include_images_base64=include_images_base64,
            flatten_groups=flatten_groups,
            element_types=element_types,
            llm_model=llm_model,
        )
        return PptxScriptJobSubmitResponse(
            job_id=job_status.job_id, status=job_status.status
        )
    except Exception:
        FileService.cleanup_request_dir(request_id)
        raise


@router.post("/pptx/parse-only", response_model=ParsePptxResponse)
async def parse_pptx_only(
    file: UploadFile = File(...),
    include_images_base64: bool = Query(default=True),
    flatten_groups: bool = Query(default=True),
    element_types: list[str] = Query(default=[]),
) -> ParsePptxResponse:
    """Parse PPTX structure only — no LLM script generation, no TTS.

    Used by Live Co-Present mode to get slide text/elements/images
    without running the full auto-present pipeline.
    """
    from app.services.parse_cache import ParseCache

    request_id, file_path = await FileService.save_upload(file)
    try:
        filters = {item.strip().lower() for item in element_types if item.strip()}
        result = PptxService.parse_file(
            file_path=file_path,
            include_images_base64=include_images_base64,
            flatten_groups=flatten_groups,
            element_types=(filters if filters else None),
        )
        result.parse_id = ParseCache.put(result.slides)

        # Kick off parallel branch precomputation for every slide
        _start_branch_batch(
            parse_id=result.parse_id,
            slides=result.slides,
        )

        return result
    finally:
        FileService.cleanup_request_dir(request_id)


def _start_branch_batch(parse_id: str, slides: list) -> None:
    """Spawn a SINGLE Celery task that processes ALL slides in parallel.

    The task uses asyncio.gather with a semaphore to run multiple LLM
    calls concurrently, rather than queueing N separate tasks.
    """
    from app.tasks.branch_jobs import generate_all_branches

    slides_data: list[dict] = []
    total = len(slides)
    for idx, slide in enumerate(slides):
        if not slide.image or not slide.image.image_base64:
            continue
        prev_text = _extract_slide_text_static(slides[idx - 1]) if idx > 0 else None
        next_text = _extract_slide_text_static(slides[idx + 1]) if idx + 1 < total else None
        slides_data.append({
            "slide_index": idx,
            "image_b64": slide.image.image_base64,
            "prev_text": prev_text,
            "next_text": next_text,
        })

    if slides_data:
        generate_all_branches.delay(
            parse_id=parse_id,
            total_slides=total,
            slides_data=slides_data,
        )


def _extract_slide_text_static(slide) -> str | None:
    lines = [el.text.strip() for el in slide.elements if el.text and el.text.strip()]
    return "\n".join(lines) if lines else None


@router.get("/{job_id}", response_model=PptxScriptJobStatus)
def get_job_status(job_id: str) -> PptxScriptJobStatus:
    return _get_job_or_404(job_id).status


@router.get("/{job_id}/result", response_model=PresentationScriptResult)
def get_job_result(job_id: str) -> PresentationScriptResult:
    record = _get_job_or_404(job_id)
    if record.result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Result is not ready yet.",
        )
    return record.result


@router.get("/{job_id}/events")
async def stream_job_events(job_id: str):
    _get_job_or_404(job_id)

    async def event_generator():
        last_version = -1
        last_slide_count = 0
        elapsed = 0.0

        print(f"[SSE_DBG] event_generator started for job={job_id}", flush=True)

        while True:
            record = JobStore.get_job(job_id)
            if record is None:
                print(f"[SSE_DBG] job={job_id} record is None, breaking", flush=True)
                break

            status_payload = record.status

            # Check for new slides (progressive delivery)
            current_count = JobStore.get_slide_count(job_id)
            print(
                f"[SSE_DBG] job={job_id} status={status_payload.status} "
                f"last_slide={last_slide_count} current_slide={current_count}",
                flush=True,
            )
            logger.info(
                "SSE poll job=%s status=%s last_slide=%d current_slide=%d",
                job_id, status_payload.status, last_slide_count, current_count,
            )
            if current_count > last_slide_count:
                print(
                    f"[SSE_DBG] Found new slides! last={last_slide_count} current={current_count}",
                    flush=True,
                )
                new_slides = JobStore.get_slides_range(
                    job_id, last_slide_count, current_count - 1
                )
                print(
                    f"[SSE_DBG] get_slides_range returned {len(new_slides)} slides",
                    flush=True,
                )
                for slide_data in new_slides:
                    slide_event = SlideReadySseEvent(
                        slide_index=slide_data.get("slide_index", 0),
                        total_slides=status_payload.progress_total or current_count,
                        slide=slide_data,
                    )
                    # Debug: check if audio_base64 is present
                    segments = slide_data.get("narrative_segments", [])
                    audio_status = []
                    for seg in segments:
                        b64 = seg.get("audio_base64")
                        audio_status.append(f"{len(b64)}b" if b64 else "NO_AUDIO")
                    print(
                        f"[SSE_DBG] YIELDING slide_ready slide_index={slide_event.slide_index} "
                        f"segments_audio=[{','.join(audio_status)}]",
                        flush=True,
                    )
                    yield f"event: slide_ready\ndata: {slide_event.model_dump_json()}\n\n"
                last_slide_count = current_count

            # Check for status changes
            if status_payload.version != last_version:
                event = PptxScriptSseEvent(event="status", status=status_payload)
                print(
                    f"[SSE_DBG] YIELDING status version={status_payload.version} stage={status_payload.status}",
                    flush=True,
                )
                yield f"event: status\ndata: {event.model_dump_json()}\n\n"
                last_version = status_payload.version
                elapsed = 0.0
            else:
                elapsed += settings.sse_poll_interval_seconds
                if elapsed >= settings.sse_heartbeat_seconds:
                    heartbeat = PptxScriptSseEvent(
                        event="heartbeat", status=status_payload
                    )
                    yield f"event: heartbeat\ndata: {heartbeat.model_dump_json()}\n\n"
                    elapsed = 0.0

            if status_payload.status in {JobStage.DONE, JobStage.ERROR}:
                # Before sending the terminal event, flush any slides that
                # may not have been read yet (e.g. if clear_slides ran or
                # the slides key expired before we polled).
                if record.result is not None and record.result.slides:
                    unread = record.result.slides[last_slide_count:]
                    print(
                        f"[SSE_DBG] DONE/ERROR: flushing {len(unread)} unread slides",
                        flush=True,
                    )
                    for slide_data in unread:
                        slide_event = SlideReadySseEvent(
                            slide_index=slide_data.slide_index,
                            total_slides=len(record.result.slides),
                            slide=slide_data.model_dump(mode="json"),
                        )
                        yield f"event: slide_ready\ndata: {slide_event.model_dump_json()}\n\n"
                terminal = PptxScriptSseEvent(event="done", status=status_payload)
                print(f"[SSE_DBG] YIELDING done event", flush=True)
                yield f"event: done\ndata: {terminal.model_dump_json()}\n\n"
                break

            print(f"[SSE_DBG] Sleeping {settings.sse_poll_interval_seconds}s...", flush=True)
            await asyncio.sleep(settings.sse_poll_interval_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
