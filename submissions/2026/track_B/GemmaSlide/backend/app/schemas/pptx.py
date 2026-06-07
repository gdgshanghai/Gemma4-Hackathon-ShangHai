from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BBoxEmu(BaseModel):
    x: int
    y: int
    width: int
    height: int


class BBoxNorm(BaseModel):
    x: float
    y: float
    width: float
    height: float


class BBoxPx(BaseModel):
    x: int
    y: int
    width: int
    height: int


class TextParagraph(BaseModel):
    text: str
    runs: list[str] = Field(default_factory=list)


class ShapeElement(BaseModel):
    element_id: str
    parent_id: str | None = None
    level: int = 0
    z_index: int
    name: str
    shape_type_code: int
    shape_type_name: str
    is_group: bool
    has_text: bool
    text: str | None = None
    paragraphs: list[TextParagraph] = Field(default_factory=list)
    rotation: float | None = None
    bbox_emu: BBoxEmu
    bbox_norm: BBoxNorm
    bbox_px: BBoxPx | None = None
    media_type: str | None = None
    image_ext: str | None = None
    image_size_bytes: int | None = None
    table_rows: int | None = None
    table_cols: int | None = None
    has_chart: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class SlideImage(BaseModel):
    width_px: int
    height_px: int
    image_base64: str | None = None


class SlideResult(BaseModel):
    slide_index: int
    slide_id: int | None = None
    slide_width_emu: int
    slide_height_emu: int
    image: SlideImage | None = None
    elements: list[ShapeElement]
    warnings: list[str] = Field(default_factory=list)


class ErrorItem(BaseModel):
    code: str
    message: str


class ParsePptxResponse(BaseModel):
    parse_id: str = ""
    file_name: str
    total_slides: int
    total_elements: int
    coordinate_systems: list[str] = Field(
        default_factory=lambda: ["emu", "normalized", "pixel"]
    )
    slides: list[SlideResult]
    errors: list[ErrorItem] = Field(default_factory=list)


class JobStage(str, Enum):
    QUEUED = "queued"
    PARSING = "parsing"
    LLM = "llm"
    ASSEMBLING = "assembling"
    DONE = "done"
    ERROR = "error"


class CueActionType(str, Enum):
    NONE = "NONE"
    CIRCLE = "CIRCLE"
    HIGHLIGHT = "HIGHLIGHT"
    LASER = "LASER"


class CueTiming(str, Enum):
    START = "START"
    MIDDLE = "MIDDLE"
    END = "END"


class AiReadyElement(BaseModel):
    element_id: str
    type: str
    content: str
    normalized_position: str
    bbox_px: BBoxPx | None = None


class VisualCue(BaseModel):
    action_type: CueActionType = CueActionType.NONE
    bbox_px: BBoxPx | None = None
    timing: CueTiming = CueTiming.MIDDLE


class NarrativeSegment(BaseModel):
    text: str
    visual_cue: VisualCue = Field(default_factory=VisualCue)
    timing_placeholder: CueTiming = CueTiming.MIDDLE
    estimated_start_seconds: float = 0.0
    audio_base64: str | None = None


class SlideScript(BaseModel):
    slide_index: int
    narrative_segments: list[NarrativeSegment] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    width_px: int = 0
    height_px: int = 0
    image_base64: str | None = None


class PresentationScriptResult(BaseModel):
    file_name: str
    total_slides: int
    slides: list[SlideScript] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PptxScriptJobSubmitResponse(BaseModel):
    job_id: str
    status: JobStage = JobStage.QUEUED


class PptxScriptJobStatus(BaseModel):
    job_id: str
    request_id: str
    status: JobStage
    message: str = ""
    progress_current: int = 0
    progress_total: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int = 0


class PptxScriptJobRecord(BaseModel):
    status: PptxScriptJobStatus
    result: PresentationScriptResult | None = None


class PptxScriptJobRequest(BaseModel):
    include_images_base64: bool = True
    flatten_groups: bool = True
    element_types: list[str] = Field(default_factory=list)
    llm_model: str | None = None


class PptxScriptSseEvent(BaseModel):
    event: str
    status: PptxScriptJobStatus


class SlideReadySseEvent(BaseModel):
    """SSE event payload for a single completed slide."""

    event: str = "slide_ready"
    slide_index: int
    total_slides: int
    slide: SlideScript
