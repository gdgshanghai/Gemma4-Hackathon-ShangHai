from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from redis import Redis

from app.core.config import settings
from app.schemas.pptx import JobStage, PptxScriptJobRecord, PptxScriptJobStatus

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


class JobStore:
    _client: Redis | None = None

    @classmethod
    def _redis(cls) -> Redis:
        if cls._client is None:
            logger.info("Creating Redis connection to %s", settings.redis_url)
            cls._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return cls._client

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"pptx_script_job:{job_id}"

    @staticmethod
    def _slides_key(job_id: str) -> str:
        return f"pptx_script_job:{job_id}:slides"

    @classmethod
    def create_job(cls, request_id: str) -> PptxScriptJobStatus:
        now = _utc_now()
        job_id = str(uuid4())
        status = PptxScriptJobStatus(
            job_id=job_id,
            request_id=request_id,
            status=JobStage.QUEUED,
            message="Job queued",
            progress_current=0,
            progress_total=0,
            error=None,
            created_at=now,
            updated_at=now,
            version=1,
        )
        record = PptxScriptJobRecord(status=status, result=None)
        cls._redis().setex(
            cls._job_key(job_id),
            settings.job_state_ttl_seconds,
            record.model_dump_json(),
        )
        return status

    @classmethod
    def get_job(cls, job_id: str) -> PptxScriptJobRecord | None:
        raw = cls._redis().get(cls._job_key(job_id))
        if not raw:
            return None
        return PptxScriptJobRecord.model_validate(json.loads(raw))

    @classmethod
    def update_status(
        cls,
        job_id: str,
        *,
        stage: JobStage,
        message: str,
        progress_current: int | None = None,
        progress_total: int | None = None,
        error: str | None = None,
    ) -> PptxScriptJobStatus:
        record = cls.get_job(job_id)
        if record is None:
            raise KeyError(f"Unknown job_id: {job_id}")

        status = record.status.model_copy()
        status.status = stage
        status.message = message
        if progress_current is not None:
            status.progress_current = progress_current
        if progress_total is not None:
            status.progress_total = progress_total
        status.error = error
        status.updated_at = _utc_now()
        status.version += 1

        updated = PptxScriptJobRecord(status=status, result=record.result)
        cls._redis().setex(
            cls._job_key(job_id),
            settings.job_state_ttl_seconds,
            updated.model_dump_json(),
        )
        return status

    @classmethod
    def set_result(cls, job_id: str, result_json: dict) -> PptxScriptJobStatus:
        record = cls.get_job(job_id)
        if record is None:
            raise KeyError(f"Unknown job_id: {job_id}")

        status = record.status.model_copy()
        status.status = JobStage.DONE
        status.message = "Job completed"
        status.error = None
        status.updated_at = _utc_now()
        status.version += 1

        updated = PptxScriptJobRecord.model_validate(
            {
                "status": status.model_dump(mode="json"),
                "result": result_json,
            }
        )
        cls._redis().setex(
            cls._job_key(job_id),
            settings.job_state_ttl_seconds,
            updated.model_dump_json(),
        )
        return status

    @classmethod
    def append_slide(cls, job_id: str, slide_json: dict) -> int:
        """Append a single slide to the job's partial slides list in Redis.
        Returns the number of slides appended so far."""
        key = cls._slides_key(job_id)
        redis = cls._redis()
        count = redis.rpush(key, json.dumps(slide_json))
        redis.expire(key, settings.job_state_ttl_seconds)
        logger.info("append_slide job=%s key=%s count=%d", job_id, key, count)
        return count

    @classmethod
    def get_slide_count(cls, job_id: str) -> int:
        """Return how many slides are currently in the partial slides list."""
        key = cls._slides_key(job_id)
        r = cls._redis()
        print(f"[JOBSTORE_DBG] get_slide_count job={job_id} key={key} calling llen", flush=True)
        count = r.llen(key)
        result = count if count is not None else 0
        print(f"[JOBSTORE_DBG] get_slide_count job={job_id} key={key} llen={count} result={result}", flush=True)
        logger.info("get_slide_count job=%s key=%s count=%d", job_id, key, result)
        return result

    @classmethod
    def clear_slides(cls, job_id: str) -> None:
        """Delete the partial slides list for a job (cleanup after done/error)."""
        cls._redis().delete(cls._slides_key(job_id))

    @classmethod
    def get_slides_range(
        cls, job_id: str, start: int, end: int
    ) -> list[dict]:
        """Return slides in the given index range (0-based, inclusive end)."""
        key = cls._slides_key(job_id)
        raw_items = cls._redis().lrange(key, start, end)
        logger.info("get_slides_range job=%s start=%d end=%d raw_count=%d", job_id, start, end, len(raw_items))
        slides: list[dict] = []
        for item in raw_items:
            try:
                slides.append(json.loads(item))
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("get_slides_range parse error: %s data=%s", exc, str(item)[:200])
                continue
        logger.info("get_slides_range parsed %d slides", len(slides))
        return slides
