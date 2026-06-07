"""
In-memory cache for PPTX parse results.

Stores SlideResult lists keyed by parse_id so the Live Co-Present
WebSocket can look them up without the frontend round-tripping image_base64.
"""

from __future__ import annotations

import logging
import time
import uuid

from app.schemas.pptx import SlideResult

logger = logging.getLogger(__name__)

# Entries older than this (seconds) are evicted on access.
DEFAULT_TTL_SECONDS = 600  # 10 minutes


class ParseCache:
    """Thread-safe in-memory store for parse-only results.

    Usage::

        slides: list[SlideResult] = [...]
        parse_id = ParseCache.put(slides)

        # later, in WebSocket handler:
        slides = ParseCache.get(parse_id)
    """

    _store: dict[str, tuple[float, list[SlideResult]]] = {}

    @classmethod
    def put(cls, slides: list[SlideResult]) -> str:
        """Store slides, return a parse_id for later retrieval."""
        parse_id = uuid.uuid4().hex[:16]
        cls._store[parse_id] = (time.monotonic(), slides)
        logger.debug("ParseCache: stored %d slides under %s", len(slides), parse_id)
        return parse_id

    @classmethod
    def get(cls, parse_id: str) -> list[SlideResult] | None:
        """Retrieve slides by parse_id. Returns None if missing or expired."""
        entry = cls._store.get(parse_id)
        if entry is None:
            return None
        ts, slides = entry
        if time.monotonic() - ts > DEFAULT_TTL_SECONDS:
            del cls._store[parse_id]
            logger.debug("ParseCache: %s expired", parse_id)
            return None
        return slides
