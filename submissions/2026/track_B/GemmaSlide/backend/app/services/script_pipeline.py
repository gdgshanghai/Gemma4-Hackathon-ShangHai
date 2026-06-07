from __future__ import annotations

import asyncio
import logging

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.schemas.pptx import (
    BBoxPx,
    CueActionType,
    CueTiming,
    NarrativeSegment,
    ParsePptxResponse,
    PresentationScriptResult,
    SlideResult,
    SlideScript,
    VisualCue,
)
from app.services.llm_factory import build_chat_model

logger = logging.getLogger(__name__)


class _LlmVisualCue(BaseModel):
    action_type: CueActionType = CueActionType.NONE
    box: tuple[int, int, int, int] | None = None
    timing: CueTiming = CueTiming.MIDDLE


class _LlmNarrativeSegment(BaseModel):
    text: str
    visual_cue: _LlmVisualCue = Field(default_factory=_LlmVisualCue)


class _LlmSlideScript(BaseModel):
    narrative_segments: list[_LlmNarrativeSegment] = Field(default_factory=list)
    summary: str = ""


class ScriptPipelineService:
    _MAX_STRUCTURED_JSON_ATTEMPTS = 3

    @staticmethod
    def _is_retryable_json_error(exc: Exception) -> bool:
        if isinstance(exc, ValidationError):
            return "Invalid JSON" in str(exc)
        text = str(exc)
        return "Invalid JSON" in text and "_LlmSlideScript" in text

    @classmethod
    def _invoke_structured_with_retries(cls, structured_model, messages):
        from langchain_core.messages import HumanMessage

        last_error: Exception | None = None
        for attempt in range(cls._MAX_STRUCTURED_JSON_ATTEMPTS):
            try:
                return structured_model.invoke(messages)
            except ValidationError as exc:
                last_error = exc
                if attempt == cls._MAX_STRUCTURED_JSON_ATTEMPTS - 1:
                    raise
                logger.warning(
                    "LLM JSON validation error (attempt %d/%d): %s",
                    attempt + 1,
                    cls._MAX_STRUCTURED_JSON_ATTEMPTS,
                    exc,
                )
                messages.append(
                    HumanMessage(
                        content=(
                            f"The previous response failed JSON validation. "
                            f"Error: {exc}\n\n"
                            f"Return ONLY valid raw JSON matching the required schema — "
                            f"no markdown, no code fences, and no extra characters."
                        )
                    )
                )
            except Exception as exc:
                if not cls._is_retryable_json_error(exc):
                    raise
                last_error = exc
                if attempt == cls._MAX_STRUCTURED_JSON_ATTEMPTS - 1:
                    raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("Structured output invocation failed without an exception.")

    @staticmethod
    def _box_1000_to_bbox_px(
        box: tuple[int, int, int, int],
        image_width_px: int,
        image_height_px: int,
    ) -> BBoxPx:
        ymin, xmin, ymax, xmax = box
        x = round(xmin / 1000 * image_width_px)
        y = round(ymin / 1000 * image_height_px)
        x2 = round(xmax / 1000 * image_width_px)
        y2 = round(ymax / 1000 * image_height_px)
        width = x2 - x
        height = y2 - y
        return BBoxPx(x=x, y=y, width=width, height=height)

    @staticmethod
    def _build_user_content(
        image_base64: str | None,
        previous_context: str,
    ) -> list[dict]:
        text_prompt = (
            "Write a spoken script for this slide. For each sentence, decide whether a visual cue is needed. "
            "Use the same language as the PPT slide content. "
            "If needed, output visual_cue.box in normalized 0-1000 coordinates as [ymin, xmin, ymax, xmax]. "
            "Backend will convert visual_cue.box (0-1000) into visual_cue.bbox_px for rendering. "
            "Do not output element IDs. "
            "Keep the flow connected to previous context when available.\n\n"
            f"Previous context:\n{previous_context or 'None'}\n\n"
        )

        if not image_base64:
            return [{"type": "text", "text": text_prompt}]

        return [
            {"type": "text", "text": text_prompt},
            {
                "type": "image_url",
                "image_url": {"url": image_base64},
            },
        ]

    @staticmethod
    def _estimate_segment_start_seconds(segments: list[NarrativeSegment]) -> None:
        running = 0.0
        words_per_second = 2.3
        for segment in segments:
            segment.estimated_start_seconds = round(running, 2)
            words = max(1, len(segment.text.split()))
            running += words / words_per_second

    @classmethod
    def generate_single_slide_script(
        cls,
        slide: SlideResult,
        previous_context: str,
        *,
        llm_model: str | None = None,
        tts_enabled: bool = True,
    ) -> SlideScript:
        """Generate script + optional per-segment TTS for a single slide."""
        from langchain_core.messages import HumanMessage, SystemMessage

        chat_model = build_chat_model(llm_model)
        structured = chat_model.with_structured_output(_LlmSlideScript)

        image_width_px = slide.image.width_px if slide.image else 0
        image_height_px = slide.image.height_px if slide.image else 0

        messages = [
            SystemMessage(
                content=(
                    "You are an Expert Script Writer and Presentation Coach. "
                    "Generate concise presenter-friendly narrative. "
                    "Use the same language as the PPT slide content. "
                    "Return strictly valid JSON only, with no markdown, no code fences, and no trailing characters. "
                    "When adding a visual cue, you must provide visual_cue.box as [ymin, xmin, ymax, xmax] in normalized 0-1000 coordinates. "
                    "Use visual cues only when they improve audience focus."
                )
            ),
            HumanMessage(
                content=cls._build_user_content(
                    slide.image.image_base64 if slide.image else None,
                    previous_context,
                )
            ),
        ]
        llm_output = cls._invoke_structured_with_retries(structured, messages)

        segments: list[NarrativeSegment] = []
        slide_warnings: list[str] = []
        for item in llm_output.narrative_segments:
            cue = item.visual_cue
            cue_bbox_px = (
                None
                if cue.box is None
                else cls._box_1000_to_bbox_px(
                    cue.box, image_width_px, image_height_px
                )
            )
            segment = NarrativeSegment(
                text=item.text,
                visual_cue=VisualCue(
                    action_type=cue.action_type,
                    bbox_px=cue_bbox_px,
                    timing=cue.timing,
                ),
                timing_placeholder=cue.timing,
                estimated_start_seconds=0.0,
            )
            segments.append(segment)

        cls._estimate_segment_start_seconds(segments)

        # Per-segment TTS
        if tts_enabled and settings.tts_enabled:
            cls._populate_segment_audio(segments)

        summary = llm_output.summary.strip()
        if not summary:
            summary = " ".join(seg.text.strip() for seg in segments[:2]).strip()[:300]

        return SlideScript(
            slide_index=slide.slide_index,
            narrative_segments=segments,
            summary=summary,
            warnings=slide_warnings,
            width_px=image_width_px,
            height_px=image_height_px,
            image_base64=slide.image.image_base64 if slide.image else None,
        )

    @classmethod
    def _populate_segment_audio(
        cls, segments: list[NarrativeSegment]
    ) -> None:
        """Call TTS for each segment, populating audio_base64. Failures log a warning."""
        from app.services.tts_service import generate_audio

        for seg in segments:
            try:
                seg.audio_base64 = asyncio.run(generate_audio(seg.text))
                if seg.audio_base64 is None:
                    logger.warning(
                        "TTS returned None for segment text=%s... — all %d retries exhausted",
                        seg.text[:60],
                        settings.tts_max_retries,
                    )
            except Exception:
                logger.warning(
                    "TTS failed for segment text=%s...",
                    seg.text[:60],
                    exc_info=True,
                )
                # audio_base64 stays None; non-blocking

    @classmethod
    def generate_presentation_script(
        cls,
        parsed: ParsePptxResponse,
        *,
        llm_model: str | None = None,
    ) -> PresentationScriptResult:
        slides: list[SlideScript] = []
        previous_context = ""
        warnings: list[str] = []

        for slide in parsed.slides:
            slide_script = cls.generate_single_slide_script(
                slide,
                previous_context,
                llm_model=llm_model,
                tts_enabled=True,
            )
            previous_context = slide_script.summary[: settings.llm_slide_context_chars]
            slides.append(slide_script)
            warnings.extend(slide_script.warnings)

        return PresentationScriptResult(
            file_name=parsed.file_name,
            total_slides=parsed.total_slides,
            slides=slides,
            warnings=warnings,
        )
