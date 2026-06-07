from __future__ import annotations

import asyncio
import logging
import traceback
from pathlib import Path

from app.celery_app import celery_app
from app.schemas.pptx import JobStage
from app.services.file_service import FileService
from app.services.job_store import JobStore
from app.services.pptx_service import PptxService

logger = logging.getLogger(__name__)

# Max concurrent LLM+TTS calls for slide script generation.
# The LLM and TTS calls are I/O-bound (HTTP), so 4-8 concurrent
# calls will saturate most endpoints without hitting rate limits.
MAX_CONCURRENT_SCRIPTS = 6


@celery_app.task(name="app.tasks.pptx_jobs.run_pptx_script_job")
def run_pptx_script_job(
    *,
    job_id: str,
    request_id: str,
    file_path: str,
    include_images_base64: bool,
    flatten_groups: bool,
    element_types: list[str],
    llm_model: str | None,
) -> None:
    from app.services.script_pipeline import ScriptPipelineService

    try:
        # ---- Stage 1: Parse ----
        JobStore.update_status(
            job_id,
            stage=JobStage.PARSING,
            message="Parsing PPTX and extracting metadata",
            progress_current=0,
            progress_total=100,
        )

        filters = {item.strip().lower() for item in element_types if item.strip()}
        parsed = PptxService.parse_file(
            file_path=Path(file_path),
            include_images_base64=include_images_base64,
            flatten_groups=flatten_groups,
            element_types=(filters if filters else None),
        )

        total = len(parsed.slides)

        # ---- Stage 2: Concurrent per-slide generation (LLM + TTS) ----
        JobStore.update_status(
            job_id,
            stage=JobStage.LLM,
            message=f"Generating all {total} slides concurrently",
            progress_current=0,
            progress_total=total,
        )

        async def _generate_slides_concurrently() -> list[tuple[int, object]]:
            """Generate all slides in parallel using asyncio.gather + semaphore."""
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRIPTS)
            loop = asyncio.get_running_loop()

            async def _generate_one(idx: int, slide) -> tuple[int, object]:
                async with semaphore:
                    logger.info(
                        "Script generation: starting slide %d/%d", idx, total
                    )
                    # Run sync generate_single_slide_script in thread pool
                    # (no cross-slide context when generating concurrently)
                    slide_script = await loop.run_in_executor(
                        None,
                        lambda s=slide: ScriptPipelineService.generate_single_slide_script(
                            s,
                            previous_context="",
                            llm_model=llm_model,
                            tts_enabled=True,
                        ),
                    )
                    logger.info(
                        "Script generation: slide %d/%d done", idx, total
                    )
                    return (idx, slide_script)

            tasks = [
                _generate_one(idx, slide)
                for idx, slide in enumerate(parsed.slides, start=1)
            ]
            results = await asyncio.gather(*tasks)
            # Sort by original slide index to maintain order
            results.sort(key=lambda x: x[0])
            return results

        results = asyncio.run(_generate_slides_concurrently())

        all_slides_json: list[dict] = []
        for idx, slide_script in results:
            slide_json = slide_script.model_dump(mode="json")
            JobStore.append_slide(job_id, slide_json)
            all_slides_json.append(slide_json)
            JobStore.update_status(
                job_id,
                stage=JobStage.LLM,
                message=f"Generated slide {idx}/{total}",
                progress_current=idx,
                progress_total=total,
            )

        # ---- Stage 3: Assemble final result ----
        JobStore.update_status(
            job_id,
            stage=JobStage.ASSEMBLING,
            message="Assembling final response",
            progress_current=total,
            progress_total=total,
        )

        result_json = {
            "file_name": parsed.file_name,
            "total_slides": parsed.total_slides,
            "slides": all_slides_json,
            "warnings": [],
        }
        JobStore.set_result(job_id, result_json)

    except Exception as exc:
        JobStore.update_status(
            job_id,
            stage=JobStage.ERROR,
            message="Job failed",
            progress_current=100,
            progress_total=100,
            error=f"{exc}\n{traceback.format_exc()}",
        )
    finally:
        FileService.cleanup_request_dir(request_id)
