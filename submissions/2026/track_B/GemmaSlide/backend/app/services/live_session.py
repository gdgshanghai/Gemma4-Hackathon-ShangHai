from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid

from fastapi import WebSocket

from app.schemas.live import (
    AsrSentence,
    BranchActionType,
    BranchTrackResult,
    LiveWsIncoming,
    LiveWsIncomingType,
    LiveWsOutgoing,
    LiveWsOutgoingType,
    ScriptSuggestion,
)
from app.schemas.pptx import SlideScript
from app.services.asr_service import AsrSession
from app.services.branch_tracker import BranchTracker

logger = logging.getLogger(__name__)


class LiveSession:
    """Bridges a frontend WebSocket to ASR + ScriptAdapter."""

    def __init__(self, session_id: str, ws: WebSocket):
        self.session_id = session_id
        self._ws = ws
        self._asr: AsrSession | None = None
        self._tasks: list[asyncio.Task] = []

        # Slide state
        self._parse_id: str = ""
        self._slides: list[SlideScript] = []
        self._current_slide_index = 0
        self._user_speech_parts: list[str] = []

        # Branch tracking (stateful per-slide tracker)
        self._branch_tracker = BranchTracker()

    @property
    def _current_slide(self) -> SlideScript | None:
        if 0 <= self._current_slide_index < len(self._slides):
            return self._slides[self._current_slide_index]
        return None

    @property
    def _previous_summary(self) -> str:
        if self._current_slide_index <= 0:
            return ""
        prev = self._slides[self._current_slide_index - 1]
        return prev.summary

    async def run(self) -> None:
        """Main loop: handle START, then audio + ASR + adapter."""
        self._asr = AsrSession()

        try:
            # Wait for START message before starting ASR
            raw = await self._ws.receive_text()
            msg = LiveWsIncoming.model_validate_json(raw)
            if msg.type != LiveWsIncomingType.START:
                await self._send_error("Expected START message first")
                return

            self._load_slides(parse_id=msg.parse_id, slides_raw=msg.slides_raw)
            self._asr.start()
            logger.info("LiveSession %s started (%d slides)", self.session_id, len(self._slides))

            # Launch ASR result forwarding
            self._tasks.append(asyncio.create_task(self._forward_asr_results()))

            # Track audio stats for periodic logging
            _audio_chunk_count = 0
            _audio_byte_count = 0

            while True:
                raw = await self._ws.receive_text()
                msg = LiveWsIncoming.model_validate_json(raw)

                if msg.type == LiveWsIncomingType.AUDIO and msg.audio_base64:
                    pcm = base64.b64decode(msg.audio_base64)
                    _audio_chunk_count += 1
                    _audio_byte_count += len(pcm)
                    if _audio_chunk_count % 50 == 1:
                        logger.debug(
                            "LiveSession %s audio: %d chunks, %d bytes total",
                            self.session_id,
                            _audio_chunk_count,
                            _audio_byte_count,
                        )
                    await self._asr.feed_audio(pcm)

        except Exception as exc:
            logger.warning("LiveSession %s disconnected: %s", self.session_id, exc)
        finally:
            await self._cleanup()

    def _load_slides(self, *, parse_id: str = "", slides_raw: str = "") -> None:
        """Load slides from parse cache (preferred) or legacy JSON string."""
        if parse_id:
            from app.services.parse_cache import ParseCache

            self._parse_id = parse_id
            cached = ParseCache.get(parse_id)
            if cached:
                self._slides = [
                    SlideScript(
                        slide_index=s.slide_index,
                        width_px=s.image.width_px if s.image else 0,
                        height_px=s.image.height_px if s.image else 0,
                        image_base64=s.image.image_base64 if s.image else None,
                    )
                    for s in cached
                ]
                logger.info("LiveSession %s loaded %d slides from parse cache", self.session_id, len(self._slides))
                return
            logger.warning("LiveSession %s parse_id %s not found in cache", self.session_id, parse_id)

        if slides_raw:
            data = json.loads(slides_raw)
            self._slides = [SlideScript.model_validate(s) for s in data]

    async def _forward_asr_results(self) -> None:
        """Read ASR results, forward to frontend, run branch tracker + adapter."""
        try:
            async for sentence in self._asr.results():
                logger.debug(
                    "LiveSession %s ASR result: text=%r is_sentence_end=%s",
                    self.session_id,
                    sentence.text,
                    sentence.is_sentence_end,
                )
                event_type = (
                    LiveWsOutgoingType.ASR_SENTENCE_END
                    if sentence.is_sentence_end
                    else LiveWsOutgoingType.ASR_INTERMEDIATE
                )
                out = LiveWsOutgoing(type=event_type, sentence=sentence)
                await self._ws.send_text(out.model_dump_json())

                # ── Branch tracking (stateful, with hysteresis + punctuation) ──
                if sentence.text.strip():
                    from app.services.branch_store import BranchStore

                    branches = BranchStore.get(self._parse_id, self._current_slide_index)
                    track = self._branch_tracker.process(
                        asr_text=sentence.text,
                        is_sentence_end=sentence.is_sentence_end,
                        branches=branches or [],
                    )

                    out = LiveWsOutgoing(
                        type=LiveWsOutgoingType.BRANCH_MATCH,
                        match_result=track.match,
                        track_result=track,
                    )
                    await self._ws.send_text(out.model_dump_json())

                    match_id = track.match.branch_id if track.match else None
                    match_conf = track.match.confidence if track.match else 0.0
                    match_action = track.match.action.type if track.match else "N/A"
                    logger.info(
                        "LiveSession %s branch track: slide=%d/%d match=%s conf=%.3f action=%s covered=%s segments=%d",
                        self.session_id,
                        self._current_slide_index + 1,
                        len(self._slides),
                        match_id or "no match",
                        match_conf,
                        match_action,
                        track.covered_ids,
                        track.segment_count,
                    )

                    # Auto-transition if match says "transition" and sentence is complete
                    if (
                        track.match
                        and track.match.action.type == BranchActionType.TRANSITION
                        and sentence.is_sentence_end
                        and self._current_slide_index + 1 < len(self._slides)
                    ):
                        self._current_slide_index += 1
                        self._user_speech_parts.clear()
                        self._branch_tracker.reset()
                        logger.info(
                            "LiveSession %s ▶ TRANSITION to slide %d/%d (branch=%s, conf=%.3f)",
                            self.session_id,
                            self._current_slide_index + 1,
                            len(self._slides),
                            track.match.branch_id,
                            track.match.confidence,
                        )
                        # Push updated slide index to frontend.
                        # Do NOT send the stale match/track from the previous slide —
                        # the frontend will start fresh on the new slide.
                        out = LiveWsOutgoing(
                            type=LiveWsOutgoingType.SLIDE_CHANGE,
                            slide_index=self._current_slide_index,
                        )
                        await self._ws.send_text(out.model_dump_json())
                    elif track.match and sentence.is_sentence_end:
                        # Diagnose why auto-transition was NOT triggered
                        reasons = []
                        if track.match.action.type != BranchActionType.TRANSITION:
                            reasons.append(f"action={track.match.action.type} (need TRANSITION)")
                        if self._current_slide_index + 1 >= len(self._slides):
                            reasons.append("already at last slide")
                        logger.debug(
                            "LiveSession %s auto-transition SKIPPED: %s",
                            self.session_id,
                            "; ".join(reasons),
                        )

                if sentence.is_sentence_end and sentence.text.strip():
                    self._user_speech_parts.append(sentence.text)
        except asyncio.CancelledError:
            logger.info("LiveSession %s ASR forwarding cancelled", self.session_id)
            raise
        except Exception:
            logger.exception("LiveSession %s ASR result forwarding error", self.session_id)

    async def _send_error(self, detail: str) -> None:
        out = LiveWsOutgoing(type=LiveWsOutgoingType.ERROR, error=detail)
        await self._ws.send_text(out.model_dump_json())

    async def _cleanup(self) -> None:
        if self._asr:
            self._asr.stop()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("LiveSession %s cleaned up", self.session_id)


class LiveSessionManager:
    """Singleton registry of active LiveSessions."""

    _sessions: dict[str, LiveSession] = {}

    @classmethod
    def create(cls, ws: WebSocket) -> LiveSession:
        session_id = uuid.uuid4().hex[:12]
        session = LiveSession(session_id, ws)
        cls._sessions[session_id] = session
        return session

    @classmethod
    def remove(cls, session_id: str) -> None:
        cls._sessions.pop(session_id, None)

    @classmethod
    def cleanup_stale_sessions(cls, max_age_seconds: int = 300) -> int:
        """Placeholder — WebSocket disconnect already triggers cleanup via LiveSession._cleanup."""
        return 0
