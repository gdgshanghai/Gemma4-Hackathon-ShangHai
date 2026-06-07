export interface BBoxEmu {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BBoxNorm {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BBoxPx {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TextParagraph {
  text: string;
  runs: string[];
}

export interface ShapeElement {
  element_id: string;
  parent_id: string | null;
  level: number;
  z_index: number;
  name: string;
  shape_type_code: number;
  shape_type_name: string;
  is_group: boolean;
  has_text: boolean;
  text: string | null;
  paragraphs: TextParagraph[];
  rotation: number | null;
  bbox_emu: BBoxEmu;
  bbox_norm: BBoxNorm;
  bbox_px: BBoxPx | null;
  media_type: string | null;
  image_ext: string | null;
  image_size_bytes: number | null;
  table_rows: number | null;
  table_cols: number | null;
  has_chart: boolean;
  extra: Record<string, unknown>;
}

export interface SlideImage {
  width_px: number;
  height_px: number;
  image_base64: string | null;
}

export interface SlideResult {
  slide_index: number;
  slide_id: number | null;
  slide_width_emu: number;
  slide_height_emu: number;
  image: SlideImage | null;
  elements: ShapeElement[];
  warnings: string[];
}

export interface ParseErrorItem {
  code: string;
  message: string;
}

export interface ParsePptxResponse {
  parse_id: string;
  file_name: string;
  total_slides: number;
  total_elements: number;
  coordinate_systems: string[];
  slides: SlideResult[];
  errors: ParseErrorItem[];
}

export type JobStage =
  | "queued"
  | "parsing"
  | "llm"
  | "assembling"
  | "done"
  | "error";

export interface PptxScriptJobSubmitResponse {
  job_id: string;
  status: JobStage;
}

export interface PptxScriptJobStatus {
  job_id: string;
  request_id: string;
  status: JobStage;
  message: string;
  progress_current: number;
  progress_total: number;
  error: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export const CueActionType = {
  NONE: "NONE",
  CIRCLE: "CIRCLE",
  HIGHLIGHT: "HIGHLIGHT",
  LASER: "LASER",
} as const;

export type CueActionType = (typeof CueActionType)[keyof typeof CueActionType];

export const CueTiming = {
  START: "START",
  MIDDLE: "MIDDLE",
  END: "END",
} as const;

export type CueTiming = (typeof CueTiming)[keyof typeof CueTiming];

export interface VisualCue {
  action_type: CueActionType;
  bbox_px: BBoxPx | null;
  timing: CueTiming;
}

export interface NarrativeSegment {
  text: string;
  visual_cue: VisualCue;
  timing_placeholder: CueTiming;
  estimated_start_seconds: number;
  audio_base64: string | null;
}

export interface SlideScript {
  slide_index: number;
  narrative_segments: NarrativeSegment[];
  summary: string;
  warnings: string[];
  width_px: number;
  height_px: number;
  image_base64: string | null;
}

export interface PresentationScriptResult {
  file_name: string;
  total_slides: number;
  slides: SlideScript[];
  warnings: string[];
}

export interface PptxScriptSseEvent {
  event: string;
  status: PptxScriptJobStatus;
}

export interface SlideReadySseEvent {
  event: "slide_ready";
  slide_index: number;
  total_slides: number;
  slide: SlideScript;
}

// ── Live Co-Present types ──

export interface AsrSentence {
  text: string;
  is_sentence_end: boolean;
  begin_time: number;
  end_time: number;
}

export type LiveWsOutgoingType =
  | "asr_intermediate"
  | "asr_sentence_end"
  | "suggestion"
  | "branch_match"
  | "slide_change"
  | "error";

export interface LiveWsMessage {
  type: LiveWsOutgoingType;
  sentence: AsrSentence | null;
  suggestion: ScriptSuggestion | null;
  match_result: BranchMatchResult | null;
  track_result: BranchTrackResult | null;
  error: string | null;
  slide_index: number | null;
}

export interface ScriptSuggestion {
  next_suggestion: string;
  transition_ready: boolean;
}

export type LiveSessionStatus = "idle" | "connecting" | "recording" | "error";

export interface LiveSessionState {
  status: LiveSessionStatus;
  asrText: string;
  asrVisible: boolean;
  lastSentence: AsrSentence | null;
  suggestion: ScriptSuggestion | null;
}

// ── Phase 3: Branch prediction types ──

export type BranchActionType =
  | "highlight"
  | "circle"
  | "arrow"
  | "transition"
  | "none";

export interface BranchAction {
  type: BranchActionType;
  bbox_1000: number[]; // [ymin, xmin, ymax, xmax] in 0-1000 normalized coords
  duration_ms: number;
}

export interface BranchNode {
  branch_id: string;
  predicted_text: string;
  action: BranchAction;
  teleprompter: string;
  next_branches: BranchNode[];
}

export interface BranchTreeResponse {
  slide_index: number;
  total_slides: number;
  branches: BranchNode[];
  generation_time_ms: number;
  error: string | null;
}

export interface BranchGenerateRequest {
  parse_id: string;
  slide_index: number;
  max_depth: number;
}

// ── Phase 3b: Branch matching types ──

export interface BranchMatchResult {
  branch_id: string;
  predicted_text: string;
  action: BranchAction;
  teleprompter: string;
  confidence: number;
  elapsed_ms: number;
  candidates_scanned: number;
  is_covered: boolean;
}

export interface BranchTrackResult {
  match: BranchMatchResult | null;
  covered_ids: string[];
  all_covered_ids: string[];
  segment_count: number;
}

export interface PrecomputedBranchesResponse {
  parse_id: string;
  total_slides: number;
  ready: boolean;
  branches: Record<number, BranchNode[]>;
}
