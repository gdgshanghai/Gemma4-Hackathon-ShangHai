from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class LiveWsIncomingType(str, enum.Enum):
    START = "start"
    AUDIO = "audio"


class LiveWsOutgoingType(str, enum.Enum):
    ASR_INTERMEDIATE = "asr_intermediate"
    ASR_SENTENCE_END = "asr_sentence_end"
    SUGGESTION = "suggestion"
    BRANCH_MATCH = "branch_match"
    SLIDE_CHANGE = "slide_change"
    ERROR = "error"


class AsrSentence(BaseModel):
    text: str
    is_sentence_end: bool = False
    begin_time: int = 0
    end_time: int = 0


class ScriptSuggestion(BaseModel):
    next_suggestion: str
    transition_ready: bool = False


class LiveWsOutgoing(BaseModel):
    type: LiveWsOutgoingType
    sentence: AsrSentence | None = None
    suggestion: ScriptSuggestion | None = None
    match_result: "BranchMatchResult | None" = None
    track_result: "BranchTrackResult | None" = None
    error: str | None = None
    slide_index: int | None = None  # Non-null when the backend advances to a new slide


class LiveWsIncoming(BaseModel):
    type: LiveWsIncomingType
    audio_base64: str = ""
    parse_id: str = ""  # Preferred: parse_id from /api/v1/pptx/parse-only
    slides_raw: str = ""  # Legacy: JSON-serialized list of SlideScript


# ── Phase 3: Branch prediction types ──


class BranchActionType(str, enum.Enum):
    HIGHLIGHT = "highlight"
    CIRCLE = "circle"
    ARROW = "arrow"
    TRANSITION = "transition"
    NONE = "none"


class BranchAction(BaseModel):
    type: BranchActionType = BranchActionType.NONE
    bbox_1000: list[int] = Field(default_factory=list, description="[ymin, xmin, ymax, xmax] in 0-1000 normalized coords")
    duration_ms: int = 3000


class BranchNode(BaseModel):
    """A single branch in the prediction tree. Contains predicted text, action,
    teleprompter hint, and optional child branches for next-level prediction."""

    branch_id: str
    predicted_text: str = ""
    action: BranchAction = Field(default_factory=BranchAction)
    teleprompter: str = ""
    next_branches: list["BranchNode"] = Field(default_factory=list)


class BranchTreeResponse(BaseModel):
    """Full branch tree for a slide."""

    slide_index: int
    total_slides: int
    branches: list[BranchNode] = Field(default_factory=list)
    generation_time_ms: float = 0.0
    error: str | None = None


class BranchGenerateRequest(BaseModel):
    parse_id: str
    slide_index: int = 0
    max_depth: int = 3  # How many levels deep to generate


# ── Phase 3b: Branch matching types ──


class BranchMatchResult(BaseModel):
    branch_id: str
    predicted_text: str = ""
    action: BranchAction = Field(default_factory=BranchAction)
    teleprompter: str = ""
    confidence: float = 0.0
    elapsed_ms: float = 0.0
    candidates_scanned: int = 0
    is_covered: bool = False  # True if this branch was just covered in this result


class BranchTrackResult(BaseModel):
    """Per-ASR-result output from the stateful BranchTracker."""

    match: BranchMatchResult | None = None
    covered_ids: list[str] = Field(default_factory=list)  # branches covered in THIS call
    all_covered_ids: list[str] = Field(default_factory=list)  # all covered so far on this slide
    segment_count: int = 0  # how many clauses were processed this call


class BranchMatchRequest(BaseModel):
    slide_index: int
    text: str


class PrecomputedBranchesResponse(BaseModel):
    parse_id: str
    total_slides: int
    ready: bool
    branches: dict[int, list[BranchNode]] = Field(default_factory=dict)
