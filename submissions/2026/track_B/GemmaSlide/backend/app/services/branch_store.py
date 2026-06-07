"""Redis store for precomputed branch trees, keyed by parse_id + slide_index."""

from __future__ import annotations

import json
import logging

from redis import Redis

from app.core.config import settings
from app.schemas.live import BranchNode

logger = logging.getLogger(__name__)

TTL_SECONDS = 600  # Align with ParseCache


class BranchStore:
    _client: Redis | None = None

    @classmethod
    def _redis(cls) -> Redis:
        if cls._client is None:
            cls._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return cls._client

    @staticmethod
    def _key(parse_id: str, slide_index: int) -> str:
        return f"branch:{parse_id}:{slide_index}"

    @staticmethod
    def _ready_key(parse_id: str) -> str:
        return f"branch:{parse_id}:ready"

    @classmethod
    def put(cls, parse_id: str, slide_index: int, branches: list[BranchNode]) -> None:
        data = json.dumps([b.model_dump(mode="json") for b in branches])
        cls._redis().setex(cls._key(parse_id, slide_index), TTL_SECONDS, data)

    @classmethod
    def get(cls, parse_id: str, slide_index: int) -> list[BranchNode] | None:
        raw = cls._redis().get(cls._key(parse_id, slide_index))
        if raw is None:
            return None
        try:
            return [BranchNode.model_validate(n) for n in json.loads(raw)]
        except Exception:
            logger.exception("BranchStore: failed to parse %s", cls._key(parse_id, slide_index))
            return None

    @classmethod
    def get_all(cls, parse_id: str, total_slides: int) -> dict[int, list[BranchNode]]:
        result: dict[int, list[BranchNode]] = {}
        for idx in range(total_slides):
            branches = cls.get(parse_id, idx)
            if branches is not None:
                result[idx] = branches
        return result

    @classmethod
    def is_ready(cls, parse_id: str, total_slides: int) -> bool:
        return cls.get_all(parse_id, total_slides).__len__() == total_slides
