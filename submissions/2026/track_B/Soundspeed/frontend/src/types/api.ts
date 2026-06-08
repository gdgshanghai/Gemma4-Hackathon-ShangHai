// 后端 boundary 类型（snake_case）。派生自 backend/db/dal.py（Take / TranscriptSegment）
// 与 backend/core/events.py（WS payload）。应用内部只在此层用 snake_case，其余读自 typed store。

export type TakeStatus = "keep" | "ng" | "pass" | "tbd"

// ── Scene DTO（GET /api/v1/scenes，spec v0.3 §2.5）──

export interface SceneDTO {
  scene_id: number
  scene_code: string
  description: string | null
  shoot_date: string | null
  is_active: number // SQLite 0 | 1，非 bool；pickActiveScene 的 truthy 检查照常工作
  created_at: number
  int_ext: string | null // slugline 内外景：室内 / 室外（v2，可能 null）
  time_of_day: string | null // slugline 时间：日 / 夜 …（v2，可能 null）
  location: string | null // slugline 地点：街道 / 咖啡馆 …（v2，可能 null）
  has_script?: number // 该场是否已有剧本（0/1）；剧本面板据此跳过无剧本空场
}

// ── Scene 写操作（2.C）──

// POST /api/v1/scenes body。scene_code 必填，其余可选 slugline / 元数据。
export interface CreateSceneBody {
  scene_code: string
  description?: string
  shoot_date?: string
  int_ext?: string
  time_of_day?: string
  location?: string
}

// POST /api/v1/scenes 响应。created 区分新建 / 复用（两者都 200）。
export interface CreateSceneResult {
  scene_id: number
  scene_code: string
  created: boolean
  is_active: number
}

// POST /api/v1/scenes/{scene_id}/activate 响应。
export interface ActivateSceneResult {
  scene_id: number
  scene_code: string
}

// PATCH /api/v1/takes/{id} body，全可选。status ∈ keep/ng/pass/tbd。
export interface PatchTakeBody {
  status?: TakeStatus
  scene_id?: number
  shot?: string | null
  take_number?: number
  notes?: string | null
}

// ── Script DTO（GET /api/v1/scenes/{scene_id}/script，spec 2026-06-01 §2.3）──

export interface ScriptLineDTO {
  line_no: number
  character: string | null // null → 动作描述（无说话人）；有值 → 台词说话人
  text: string
}

export interface ScriptDTO {
  script_id: number
  version: number
  lines: ScriptLineDTO[]
}

// 无 line_no 的剧本行（解析预览 / 增量对照 / 提交入参共用形状；ScriptLineDTO 是带 line_no 的读侧形状）
export type ScriptLineInput = { character: string | null; text: string }

// 单场解析结果（POST /scripts/parse-single 文本入口 / /scripts/parse-images 照片入口，不入库，供预览/确认）
export interface ParseSingleResult {
  scene_code: string | null
  int_ext: string | null
  time_of_day: string | null
  location: string | null
  lines: ScriptLineInput[]
  raw_text: string // 解析依据的源文本（文本=粘贴原文；照片=视觉 OCR 转写）；提交时作为该版本 raw_text
}

// 选中场更新结果（POST /scenes/{id}/script）。skipped=true → 内容无变化未新建版本
export interface ScriptCommitResult {
  scene_id: number
  script_id: number
  version: number
  line_count: number
  skipped: boolean
}

// 增量对照（POST /scenes/{id}/script/diff）：新解析行与该场最新版逐行对齐。
// status：equal=未变 / changed=改动（取新） / added=新增 / kept=旧有新无（保留旧，防 OCR 漏）。
export interface ScriptDiffRow {
  status: "equal" | "changed" | "added" | "kept"
  old: ScriptLineInput | null
  new: ScriptLineInput | null
}

export interface ScriptDiffResult {
  has_old: boolean // false → 该场无旧版，rows 全 added、merged 即新行
  rows: ScriptDiffRow[]
  merged: ScriptLineInput[] // 确认时提交给 updateSceneScript 的合并行
  merged_raw_text: string // 由 merged 重建的源文本，确认时作为 raw_text 提交（与 merged 行一致）
}

// ── L2 输出：takes.script_diff JSON 顶层形状（docs/specs/2026-05-27-l2-pipeline.md §）──

export interface LineMatch {
  line_no: number // insertion 时为 -1
  diff_type: "match" | "missing" | "substitution" | "insertion"
  detail: string | null
  seg_idx?: number[] // 对齐的转录段下标（juxtaposition 用），可缺省
}

// L2 修正输出：原始转录 → 对齐剧本后的文本。diff 显示的主内容。
export interface CorrectedSegment {
  idx: number
  original: string
  corrected: string
}

// 并置文档一行（缺口③）：剧本台词 ‖ 实际说的。take 详情两列对照视图直接渲染它。
// line_no=-1 → insertion（剧本无此行）；spoken_text=null → 漏说该行。
export interface JuxtaLine {
  line_no: number
  character: string | null // 角色（剧本侧）；insertion 为 null
  script_text: string | null // 剧本台词；insertion 为 null
  spoken_text: string | null // 实际说的（转录原文）；漏说为 null
  speaker: string | null // 谁说的（角色名/说话人N）；漏说为 null
  diff_type: "match" | "missing" | "substitution" | "insertion" | null
  // 本行对齐到的真实转录段 segment_id（稳定主键）。History 合并视图据此把"实录侧"重接到
  // 最新可编辑的转录段（说话人纠正即时同步）；漏说/老库为空或缺省，前端回退到 spoken_text/speaker。
  segment_ids?: number[]
}

export interface ScriptDiff {
  script_diff_summary: string | null // 无剧本场景可为 null
  line_matches: LineMatch[]
  corrected_segments?: CorrectedSegment[]
  juxtaposition?: JuxtaLine[] // 并置文档；老库/无剧本路径可缺省
}

// ── Take DTO（dal.Take 投影）──
// performer_issues / audio_quality 属 NP Pipeline 输出，1.J–1.L 不暴露，有意省略（spec §2.1）。

export interface TakeDTO {
  take_id: number
  scene_id: number
  shot: string | null
  take_number: number
  take_suffix: string // 冲突后缀：'' / '+' / '++'…，显示时拼成 `Take 3+`（formatTakeLabel）
  start_ts: number
  end_ts: number | null
  status: TakeStatus
  script_diff: ScriptDiff | null
  notes: string | null
  deleted_at: number | null // 软删时间戳，null 表示未删除；restore 后回 null
  created_at: number
  updated_at: number
  // diarization 回填后的结构化转录（ASR + speaker 整合，v4）；未回填时 null/缺省。
  structured_transcript?: StructuredTranscript | null
}

// takes.structured_transcript JSON 形状（backend diarization.backfill.build_structured_transcript）。
export interface StructuredTranscriptEntry {
  speaker: string | null
  text: string
  start_ms: number
  end_ms: number
}

export interface StructuredTranscript {
  version: number
  ch1: StructuredTranscriptEntry[]
}

// 转录片段（dal.TranscriptSegment 投影）。start_frame / end_frame 单位毫秒。
export interface TranscriptSegmentDTO {
  segment_id: number
  ch: 1 | 2
  speaker: string | null
  text: string
  start_frame: number
  end_frame: number
}

// GET /api/v1/takes/{id} 返回：TakeDTO + segments。
export interface TakeDetailDTO extends TakeDTO {
  segments: TranscriptSegmentDTO[]
}

// 已注册演员(speaker) — GET/POST /api/v1/speakers（backend SpeakerOut）。
export interface SpeakerDTO {
  speaker_id: number
  display_name: string
  has_enrollment: boolean   // 是否已录入声纹
  sample_count: number
  scope_key: string | null
  created_at: number
  updated_at: number
}

// ── WS 信封 + payload（events.py）──

export interface WsEnvelope {
  topic: string
  payload: unknown
}

// asr.partial / asr.final 的 payload。⚠ ch 不在 payload 里，编码在 topic 后缀（asr.partial.ch1）。
export interface AsrMsg {
  text: string
  start_frame: number
  end_frame: number
  speaker: string | null
  take_id: number | null
  is_partial: boolean
}

// take.changed 只携带这 5 个字段（spec §3.4 patch-merge 源，刻意 Pick 在类型层锁死契约）。
export type TakeChangedMsg = Pick<
  TakeDTO,
  "take_id" | "scene_id" | "take_number" | "status" | "script_diff"
>

// take.segments.updated：diarization 回填完成，通知前端 refetch GET /takes/{id}
// 用带 speaker 的 segments 替换 Live 框里只有 ASR 文本的内容。
export interface TakeSegmentsUpdatedMsg {
  take_id: number
  scene_id: number
}

// take.deleted（2.C）：删某条 take 后广播，让历史列表移除该条。
export interface TakeDeletedMsg {
  take_id: number
  scene_id: number
}

// take.processing：take.end 后处理进度（Live 框状态条）。
export type TakeProcessingPhase = "diarizing" | "summarizing" | "done" | "error"
export interface TakeProcessingMsg {
  take_id: number
  scene_id: number
  phase: TakeProcessingPhase
  detail: string | null
}

// scene.changed（2.C）：建/切场后广播，让场次列表 + 活跃场显示刷新。
export interface SceneChangedMsg {
  scene_id: number
  scene_code: string
  is_active: number // SQLite 0 | 1，与 SceneDTO.is_active 对齐
}

// device.warning：持久化设备被拔走 / 不在场，后端已回落到 fallback 设备，通知前端提示。
export interface DeviceWarningMsg {
  message: string
  device_name: string
}

export type LlmState = "idle" | "loading" | "running" | "downloading"

export interface LlmStatusMsg {
  state: LlmState
  task_type: string | null
  take_id: number | null
}

// ── Note DTO（4.C POST /notes + GET /takes/{id}/notes）──

export interface NoteDTO {
  event_id: number
  take_id: number
  scene_code: string | null
  take_number: number | null
  category: string // "note" | "issue" | "keep" | "ng" | "pass"
  content: string
  raw_text: string
  ts: number
}

export interface NoteListResponse {
  take_id: number
  notes_aggregated: string | null
  events: NoteDTO[]
}

// POST /notes 202 响应（NP Pipeline 非阻塞归置）。
// note 分支带 category/content；入口调度器判定为查询时后端返 {status,kind:"query"}（无 category/content），
// 故全放宽为可选，调用方据 kind 分支（query 撤掉乐观 pending，答案走 qp.answer 气泡）。
export interface NoteCreateResponse {
  status: "processing"
  category?: string
  content?: string
  kind?: "query"
}

// WS qp.answer.{conn_id} payload（入口调度器 query 分支：QP 跑完把答案广播回发起 tab）。
// client_id：发起这条 query 的乐观去重键。队列模型据此把答案 resolveQa 到对应那条 qaItem。
// 文本 query 由 /notes 调度分支透传；语音 query 由 voice dispatch 透传（与 voice-qp 共享契约）。
// 直连 /api/v1/query demo 不带，故可选。
export interface QpAnswerMsg {
  connection_id: string
  answer_text: string
  client_id?: string
}

// 前端 pending note（已提交、等待 LLM 归置）
export interface PendingNote {
  client_id: string // 乐观去重键（crypto.randomUUID），note.processed 原样回传后据此精确移除
  kind: "text" | "voice" // 显式区分文本/语音 pending（渲染与重试据此分支，不靠 voiceBlob 在场反推）
  ts: number
  category: string // 语音 pending 时类别未知（模型判），不渲染；text 时为 @语法解析结果
  content: string
  rawText: string // 提交的原始文字，note.failed 后「重试」据此重投 POST /notes（语音为空）
  failedReason?: string // 置位=NP 失败（4.I），渲染失败态 + 重试；undefined=处理中
  voiceBlob?: Blob // 语音 note（4.L）：录音 WAV，重试据此重传 POST /notes/voice
}

// WS note.processed payload
export interface NoteProcessedMsg {
  event_id: number
  take_id: number
  category: string
  content: string
  ts: number
  client_id: string | null // 后端原样回传前端提交时的去重键；null=异常/旧链路
}

// WS note.failed payload（4.I）：NP 失败兜底，前端据此把对应 pending 转失败态。
export interface NoteFailedMsg {
  reason: string // take_not_found / parse_error / timeout / model_unavailable（后端 NP 失败）；upload_failed（前端网络/上传层失败，不进后端）
  ts: number
  client_id: string | null // 定位要标失败的 pending；null=异常/旧链路，不误标
}

// 就地队列的 note 回执（done 态，3s 自走）。由 note.processed 派生。
export interface FeedReceipt {
  client_id: string
  category: string // keep/pass/ng/issue/note
  content: string
  rawText: string // 提交原文，「↩ 其实是提问」改判据此重发 query（取自对应 pending；语音/缺失回退 content）
  ts: number
}

// POST /api/v1/query 返回（QP tool-loop 同步答案）。后端实际返回 {status, answer}；这里只声明用到的字段。
export interface QueryResponse {
  status: string
  answer: string
}

// 就地队列 + 档案共用的问答项。done 持久供档案（P5）；inlineDismissed 控制是否还在就地层显示。
export interface QaItem {
  client_id: string
  question: string
  status: "processing" | "done" | "failed"
  answer?: string
  failedReason?: string
  ts: number
  inlineDismissed?: boolean
}

// viewer.count：当前连着 /ws 的客户端总数（含场记自己），连接建立 / 断开时后端广播。
// 驱动 header 眼睛计数。
export interface ViewerCountMsg {
  count: number
}
