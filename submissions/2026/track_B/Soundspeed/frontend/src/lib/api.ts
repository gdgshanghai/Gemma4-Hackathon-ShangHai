import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { API_BASE } from "@/lib/config"
import type { FileNameFormat } from "@/lib/filename-format"
import { randomId } from "@/lib/uuid"
import { useSessionStore } from "@/store/session"
import type {
  ActivateSceneResult,
  CreateSceneBody,
  CreateSceneResult,
  NoteCreateResponse,
  NoteListResponse,
  ParseSingleResult,
  PatchTakeBody,
  QueryResponse,
  SceneDTO,
  ScriptCommitResult,
  ScriptDiffResult,
  ScriptDTO,
  ScriptLineInput,
  SpeakerDTO,
  TakeDTO,
  TakeDetailDTO,
  TranscriptSegmentDTO,
} from "@/types/api"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

// token 在调用时读取（SettingsDialog 保存后会变），不在模块加载时固化。
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = useSessionStore.getState().token
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    throw new ApiError(res.status, `${init?.method ?? "GET"} ${path} → ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

// multipart/form-data 上传共用（enrollSpeaker / postVoiceNote）：token + fetch（不设 JSON
// Content-Type，浏览器自动补 multipart boundary）+ 统一 !res.ok → 解析 detail → ApiError。
async function requestMultipart<T>(path: string, fd: FormData): Promise<T> {
  const token = useSessionStore.getState().token
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  })
  if (!res.ok) {
    let detail = `POST ${path} → ${res.status}`
    try {
      const j = await res.json()
      if (j?.detail) detail = String(j.detail)
    } catch {
      /* 忽略非 JSON 错误体 */
    }
    throw new ApiError(res.status, detail)
  }
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

// ── REST ──

export async function getScenes(): Promise<SceneDTO[]> {
  const data = await request<{ scenes: SceneDTO[] }>(`/api/v1/scenes`)
  return data.scenes
}

// 取活跃场次（is_active），无则退回第一条，全空返回 undefined。
export function pickActiveScene(scenes: SceneDTO[] | undefined): SceneDTO | undefined {
  if (!scenes || scenes.length === 0) return undefined
  return scenes.find((s) => s.is_active) ?? scenes[0]
}

// 取某场最新剧本（GET /scenes/{id}/script）。无剧本 → 后端返回 {script:null}，这里返回 null。
export async function getSceneScript(sceneId: number): Promise<ScriptDTO | null> {
  const data = await request<{ script: ScriptDTO | null }>(
    `/api/v1/scenes/${sceneId}/script`,
  )
  return data.script
}

// 整部戏跨场去重角色清单（GET /scenes/characters）。供声纹注册"选角色"下拉用。
export async function listCharacters(): Promise<string[]> {
  const data = await request<{ characters: string[] }>(`/api/v1/scenes/characters`)
  return data.characters
}

// 单场解析预览（原生 FC，不入库）：一段剧本文本 → 结构化一场，供"选中场更新"对话框预览。
export async function parseSingleScene(text: string): Promise<ParseSingleResult> {
  return request<ParseSingleResult>(`/api/v1/scripts/parse-single`, {
    method: "POST",
    body: JSON.stringify({ text }),
  })
}

// 照片 → 单场预览：多张图片 multipart 上传，后端视觉 OCR 转写 → 同 parse-single 解析，返回同形状结果。
// sceneCode：目标场号，后端据此从多页 OCR 里只取该场内容（丢相邻场的尾/头）。
export async function parseScenesFromImages(
  files: File[],
  sceneCode?: string | null,
): Promise<ParseSingleResult> {
  const fd = new FormData()
  for (const f of files) fd.append("files", f)
  if (sceneCode) fd.append("scene_code", sceneCode)
  return requestMultipart<ParseSingleResult>(`/api/v1/scripts/parse-images`, fd)
}

// 新解析行 vs 该场最新版的增量对照（不落库）：给确认弹窗展示「改/增/旧保留」，确认时提交 merged。
// has_old=false → 该场无旧版，rows 全 added、merged 即新行。
export async function diffSceneScript(
  sceneId: number,
  lines: ScriptLineInput[],
): Promise<ScriptDiffResult> {
  return request<ScriptDiffResult>(`/api/v1/scenes/${sceneId}/script/diff`, {
    method: "POST",
    body: JSON.stringify({ lines }),
  })
}

// 把选中场更新成新版本（版本追加；raw_text 与最新版相同 → skipped=true 不刷版本）。
export async function updateSceneScript(
  sceneId: number,
  rawText: string,
  lines: ScriptLineInput[],
): Promise<ScriptCommitResult> {
  return request<ScriptCommitResult>(`/api/v1/scenes/${sceneId}/script`, {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText, lines }),
  })
}

export async function getTakes(sceneId?: number): Promise<TakeDTO[]> {
  const qs = sceneId !== undefined ? `?scene_id=${sceneId}` : ""
  const data = await request<{ takes: TakeDTO[] }>(`/api/v1/takes${qs}`)
  return data.takes
}

export function getTake(id: number): Promise<TakeDetailDTO> {
  return request<TakeDetailDTO>(`/api/v1/takes/${id}`)
}

// speakerIds：本 take 在场的已注册演员 id（diarization 回填只在这些演员里匹配；空 → 全匿名说话人N）。
// takeNumber：用户在底部 Take 弹窗手动指定的待录号。省略/undefined → 后端按 (scene,shot) 自动 MAX+1。
export function startTake(
  sceneId: number,
  shot?: string | null,
  speakerIds?: number[],
  takeNumber?: number | null,
): Promise<void> {
  return request<void>(`/api/v1/take/start`, {
    method: "POST",
    body: JSON.stringify({
      scene_id: sceneId,
      shot: shot ?? null,
      speaker_ids: speakerIds ?? [],
      take_number: takeNumber ?? null,
    }),
  })
}

// ── 已注册演员(speaker) CRUD + enroll ──

export function listSpeakers(): Promise<SpeakerDTO[]> {
  return request<SpeakerDTO[]>(`/api/v1/speakers`)
}

export function createSpeaker(displayName: string): Promise<SpeakerDTO> {
  return request<SpeakerDTO>(`/api/v1/speakers`, {
    method: "POST",
    body: JSON.stringify({ display_name: displayName }),
  })
}

export function deleteSpeaker(speakerId: number): Promise<void> {
  return request<void>(`/api/v1/speakers/${speakerId}`, { method: "DELETE" })
}

// enroll 走 multipart/form-data。file 建议 WAV 16kHz 单声道；后端自动重采样、≥2s。返回更新后的 SpeakerDTO。
export function enrollSpeaker(speakerId: number, file: File): Promise<SpeakerDTO> {
  const fd = new FormData()
  fd.append("file", file)
  return requestMultipart<SpeakerDTO>(`/api/v1/speakers/${speakerId}/enroll`, fd)
}

// 无 body 的 POST（enroll start/stop/cancel）：带 token，错误体解析 detail → ApiError，
// 让弹窗能显示「正在 Capture」「没收到声音」等后端原因。
async function postNoBody<T>(path: string): Promise<T> {
  const token = useSessionStore.getState().token
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    let detail = `POST ${path} → ${res.status}`
    try {
      const j = await res.json()
      if (j?.detail) detail = String(j.detail)
    } catch {
      /* 忽略非 JSON 错误体 */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

// 现场麦录声纹（后端设备，与 Capture 同源）。start → stop 提声纹存库 → 返回 SpeakerDTO；
// cancel 放弃并释放设备。enrollSpeaker（上传）保留作内部原语。
export function enrollStart(speakerId: number): Promise<{ status: string; speaker_id: number }> {
  return postNoBody(`/api/v1/speakers/${speakerId}/enroll/start`)
}

export function enrollStop(speakerId: number): Promise<SpeakerDTO> {
  return postNoBody<SpeakerDTO>(`/api/v1/speakers/${speakerId}/enroll/stop`)
}

export function enrollCancel(speakerId: number): Promise<void> {
  return postNoBody<void>(`/api/v1/speakers/${speakerId}/enroll/cancel`)
}

export function endTake(): Promise<void> {
  return request<void>(`/api/v1/take/end`, {
    method: "POST",
    body: JSON.stringify({}),
  })
}

// ── Scene / Take 写操作（2.C）──
// 失败抛 ApiError（带 .status）：409 take_in_progress / take_number_conflict / scene_not_active，
// 404 不存在。调用处按 status catch。

// 建场或复用同 scene_code 的场（都 200，created 区分）。
export function createScene(body: CreateSceneBody): Promise<CreateSceneResult> {
  return request<CreateSceneResult>(`/api/v1/scenes`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

// 把某场置为活跃。录制中 → 409 take_in_progress；不存在 → 404。
export function activateScene(sceneId: number): Promise<ActivateSceneResult> {
  return request<ActivateSceneResult>(`/api/v1/scenes/${sceneId}/activate`, {
    method: "POST",
    body: JSON.stringify({}),
  })
}

// 改某条 take（status/shot/scene_id/take_number/notes 全可选）。录制中改 scene_id/take_number → 409。
// 撞号后端自动加后缀返回 200（带新 take_suffix），不再 409 take_number_conflict。
// 目标场不存在 / take 不存在 → 404。
export function patchTake(takeId: number, body: PatchTakeBody): Promise<TakeDTO> {
  return request<TakeDTO>(`/api/v1/takes/${takeId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

// 软删某条 take。204 无 body；录制中 → 409；不存在 → 404。可经 restoreTake 撤销。
export function deleteTake(takeId: number): Promise<void> {
  return request<void>(`/api/v1/takes/${takeId}`, { method: "DELETE" })
}

// 撤销软删，返回恢复后的 TakeDTO。未软删 / 不存在 → 404。
// ⚠ 若该 take 的三元（scene_id, take_number, take_suffix）已被新 take 占用，后端 UNIQUE 约束会报 500，
// 调用处需 catch 并优雅提示（见 useRestoreTake / handleUndoDelete）。
export function restoreTake(takeId: number): Promise<TakeDTO> {
  return request<TakeDTO>(`/api/v1/takes/${takeId}/restore`, {
    method: "POST",
    body: JSON.stringify({}),
  })
}

// 纠正某条 segment 的 speaker 归属（PATCH，落库）。speaker=null 表示置「未知」。
// null 必须显式带进 body（不能省略字段），后端用它区分「置未知」与「漏传」。
export function correctSegmentSpeaker(
  takeId: number,
  segmentId: number,
  speaker: string | null,
): Promise<TranscriptSegmentDTO> {
  return request<TranscriptSegmentDTO>(
    `/api/v1/takes/${takeId}/segments/${segmentId}`,
    { method: "PATCH", body: JSON.stringify({ speaker }) },
  )
}

// ── 剧本导入（3.D：上传文件 → Gemma 分场 → 入库）──

// 单个已入库场次（upload 返回）。
export interface ImportedScene {
  scene_id: number
  script_id: number
  scene_code: string | null
  int_ext: string | null
  time_of_day: string | null
  location: string | null
  line_count: number
  lines: { line_no: number; character: string | null; text: string }[]
}

// 重复场冲突项（needs_confirmation 时）。
export interface ImportConflict {
  scene_id: number
  scene_code: string | null
  original: { raw_text: string; lines: unknown[] }
  incoming: { raw_text: string; lines: unknown[] }
}

// 解析（parse）/ confirm 统一响应。
export interface UploadScriptResult {
  status: "imported" | "needs_confirmation"
  scenes: ImportedScene[]
  conflicts: ImportConflict[]
  plan: Record<string, unknown> | null
}

// 阶段 1（上传）响应：只表示已存入 DB，未解析。
export interface UploadSavedResult {
  upload_id: number
  filename: string
  char_count: number
  status: string // "uploaded"
}

// 上传记录（含解析状态/进度）。status: uploaded|parsing|parsed|error；detail 是进度/结果/错误文案。
export interface ScriptUploadInfo {
  upload_id: number
  filename: string
  char_count: number
  status: "uploaded" | "parsing" | "parsed" | "error"
  detail: string | null
  created_at: number
  updated_at: number
}

// 阶段 1：上传剧本文件（multipart）→ 提取 + 入库。秒回、不碰 Gemma。
// 失败抛 ApiError（带后端 detail）。解析是独立的一步（parseUpload）。
export async function uploadScript(file: File): Promise<UploadSavedResult> {
  const token = useSessionStore.getState().token
  const fd = new FormData()
  fd.append("file", file)
  const res = await fetch(`${API_BASE}/api/v1/scripts/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  })
  if (!res.ok) {
    let detail = `upload → ${res.status}`
    try {
      const j = await res.json()
      if (j?.detail) detail = String(j.detail)
    } catch { /* 忽略非 JSON 错误体 */ }
    throw new ApiError(res.status, detail)
  }
  return res.json()
}

// 阶段 2：启动后台解析（瞬时切场 → 后台逐场结构化）。立即返回 status=parsing。
// 进度/结果通过轮询 listScriptUploads 的 status/detail 获取。
// onConflict=version（multi_scene 更新全本）：命中已有场追加新版本（内容无变化则幂等跳过）。
// 默认 skip：首次导入语义（命中已有场跳过不替换）。
export function parseUpload(
  uploadId: number,
  target: "multi_scene" | "current_scene" = "multi_scene",
  onConflict: "skip" | "version" = "skip",
): Promise<ScriptUploadInfo> {
  return request<ScriptUploadInfo>(
    `/api/v1/scripts/uploads/${uploadId}/parse?target=${target}&on_conflict=${onConflict}`,
    { method: "POST" },
  )
}

// 列出所有上传记录（含解析状态/进度），用于轮询。
export function listScriptUploads(): Promise<ScriptUploadInfo[]> {
  return request<ScriptUploadInfo[]>(`/api/v1/scripts/uploads`)
}

// ── 音频输入设备（真实枚举 + 选择）──
export interface InputDeviceDTO {
  index: number
  name: string
  max_input_channels: number
  is_default: boolean
}

export interface DevicesResponse {
  devices: InputDeviceDTO[]
  // 后端权威「实际会采集的 index」（持久化设备不在场时已是 fallback 设备的 index）。
  selected: number | null
  // 持久化设备当前在不在场；未启用 live ASR 时 null。
  selected_available: boolean | null
  // 当前选中设备名；未启用 live ASR 时 null。
  selected_name: string | null
}

export function getDevices(): Promise<DevicesResponse> {
  return request<DevicesResponse>(`/api/v1/devices`)
}

// 选择下次 take 用的输入设备。未启用实时 ASR 时后端返回 409（这里由调用方 catch）。
export function selectDevice(index: number): Promise<void> {
  return request<void>(`/api/v1/devices/select`, {
    method: "POST",
    body: JSON.stringify({ index }),
  })
}

// 热插刷新：后端 reinit PortAudio 重扫设备（启动后插的声卡用这个刷出来，免重启后端）。
// 正在录制（take）时后端返回 409（调用方 catch 显示提示）。返回最新设备列表。
export function refreshDevices(): Promise<DevicesResponse> {
  return request<DevicesResponse>(`/api/v1/devices/refresh`, { method: "POST" })
}

// ── ASR 运行配置（转录语言 + 当前模型）──
export interface AsrConfigResponse {
  enabled: boolean
  language: string | null
  model: string | null
  languages: string[]
}

export function getAsrConfig(): Promise<AsrConfigResponse> {
  return request<AsrConfigResponse>(`/api/v1/asr`)
}

// 切换转录语言（即时生效）。未启用实时 ASR → 后端 409（调用方 catch）。
export function setAsrLanguage(language: string): Promise<void> {
  return request<void>(`/api/v1/asr/language`, {
    method: "POST",
    body: JSON.stringify({ language }),
  })
}

// dev-only 合成 ASR 注入（后端仅 SOUNDSPEED_DEV=1 挂载 /api/v1/debug/asr）。
// 服务端补 start/end_frame，前端只发 ch/text/speaker/is_partial。
export interface DebugAsrSeg {
  ch: 1 | 2
  text: string
  speaker: string | null
  is_partial: boolean
}

export function injectDebugAsr(seg: DebugAsrSeg): Promise<void> {
  return request<void>(`/api/v1/debug/asr`, {
    method: "POST",
    body: JSON.stringify(seg),
  })
}

// dev-only 剧本注入（后端仅 SOUNDSPEED_DEV=1 挂载 /api/v1/debug/script）。
// 注入后持久化到场次，L2 才能按剧本逐行比对产出真实 diff。sceneId 省略时后端用活跃场次。
export interface DebugScriptLine {
  character: string | null
  text: string
}

export interface DebugScriptResult {
  script_id: number
  scene_id: number
  line_count: number
}

// 可选 slugline heading，随注入剧本一起写到场次（后端部分更新，只写非空字段）。
export interface DebugScriptHeading {
  int_ext?: string
  time_of_day?: string
  location?: string
}

// dev-only 全量清库（后端仅 SOUNDSPEED_DEV=1 挂载 /api/v1/debug/reset-db）。
// 清空所有业务表，后端用 seed_dev_scene 重播种一个 active 空场，返回 {status, reseeded}。
// 危险操作不可恢复，调用处需二次确认。成功后建议整页 reload 派生干净状态。
export interface ResetDbResult {
  status: string
  reseeded: boolean
}

export function resetDb(): Promise<ResetDbResult> {
  return request<ResetDbResult>(`/api/v1/debug/reset-db`, {
    method: "POST",
  })
}

export function injectDebugScript(
  lines: DebugScriptLine[],
  sceneId?: number,
  heading?: DebugScriptHeading,
): Promise<DebugScriptResult> {
  const body: Record<string, unknown> = { lines }
  if (sceneId !== undefined) body.scene_id = sceneId
  // 后端已忽略空串（DAL 归一为不更新）；这里仍过滤空字段，避免发送无意义的空值。
  if (heading) {
    for (const key of ["int_ext", "time_of_day", "location"] as const) {
      const v = heading[key]?.trim()
      if (v) body[key] = v
    }
  }
  return request<DebugScriptResult>(`/api/v1/debug/script`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

// ── Note API ──

export function postNote(
  text: string,
  ts?: number,
  clientId?: string,
  connId?: string,
): Promise<NoteCreateResponse> {
  return request<NoteCreateResponse>(`/api/v1/notes`, {
    method: "POST",
    body: JSON.stringify({ text, ts: ts ?? undefined, client_id: clientId, conn_id: connId }),
  })
}

export function getTakeNotes(takeId: number): Promise<NoteListResponse> {
  return request<NoteListResponse>(`/api/v1/takes/${takeId}/notes`)
}

// QP 同步直连：跑 tool-loop 并在 HTTP body 返回答案。仅用于「↩ 其实是提问」显式强制查询
//（绕过 /notes 自动分类器）。一次性 conn_id：/api/v1/query 也广播到 qp.answer.{conn_id}，但前端
// 只认领 qp.answer.{CONN_ID}，这条广播到无人订阅的 topic 故无害；答案靠同步返回就地 resolveQa。
// 正常打字 memo 走 postNote(…,CONN_ID) 由后端自动判 note/query，不经此路。
export function postQuery(text: string): Promise<QueryResponse> {
  const connId = randomId("qp")
  return request<QueryResponse>(`/api/v1/query`, {
    method: "POST",
    body: JSON.stringify({ text, conn_id: connId }),
  })
}

// 语音 note（4.K/4.L）：浏览器麦 WAV 直传（multipart，POST /notes/voice）。后端 202
// fire-and-forget，类别/正文由 Gemma 从音频听+判，不在响应里返回——故返回值无用（Promise<void>）：
// 前端乐观 pending 占位，结果经 WS 回灌。
//
// connId（与文本 postNote 对称）：带上 → 后端走 voice dispatch 判 note/query；
// note 分支照旧经 note.processed / note.failed 回灌，query 分支把答案广播到
// qp.answer.{conn_id}（复用块③气泡），202 时不返回 kind，故 Promise<void> 不变。
export function postVoiceNote(
  blob: Blob,
  clientId: string,
  ts?: number,
  connId?: string,
): Promise<void> {
  const fd = new FormData()
  fd.append("file", blob, "note.wav")
  fd.append("client_id", clientId)
  if (ts !== undefined) fd.append("ts", String(ts))
  if (connId) fd.append("conn_id", connId)
  return requestMultipart<void>(`/api/v1/notes/voice`, fd)
}

// ── react-query 查询键 + hooks ──

export const scenesQueryKey = () => ["scenes"] as const

export const takesQueryKey = (sceneId?: number) =>
  ["takes", sceneId ?? null] as const

export const takeQueryKey = (id: number) => ["take", id] as const

export const sceneScriptQueryKey = (sceneId: number | null | undefined) =>
  ["scene-script", sceneId ?? null] as const

export const devicesQueryKey = () => ["devices"] as const

export function useDevices() {
  return useQuery({
    queryKey: devicesQueryKey(),
    queryFn: getDevices,
  })
}

export const asrConfigQueryKey = () => ["asr-config"] as const

export function useAsrConfig() {
  return useQuery({
    queryKey: asrConfigQueryKey(),
    queryFn: getAsrConfig,
  })
}

export const speakersQueryKey = () => ["speakers"] as const

export function useSpeakers() {
  return useQuery({
    queryKey: speakersQueryKey(),
    queryFn: listSpeakers,
  })
}

export const charactersQueryKey = () => ["characters"] as const

export function useCharacters() {
  return useQuery({
    queryKey: charactersQueryKey(),
    queryFn: listCharacters,
  })
}

export function useScenes() {
  return useQuery({
    queryKey: scenesQueryKey(),
    queryFn: getScenes,
  })
}

export function useSceneScript(sceneId: number | null | undefined) {
  return useQuery({
    queryKey: sceneScriptQueryKey(sceneId),
    queryFn: () => getSceneScript(sceneId as number),
    enabled: sceneId != null,
  })
}

export function useTakes(sceneId?: number) {
  return useQuery({
    queryKey: takesQueryKey(sceneId),
    queryFn: () => getTakes(sceneId),
  })
}

export function useTake(id: number, enabled: boolean) {
  return useQuery({
    queryKey: takeQueryKey(id),
    queryFn: () => getTake(id),
    enabled,
  })
}

// ── mutation hooks（2.C）──
// 后端是否在这些写操作上 publish WS 未明（只 take.deleted / scene.changed 是新增明确事件）。
// 故每个 mutation 成功后自助 invalidate，不依赖 WS 回灌。用 invalidate→refetch（而非乐观更新），
// 避免与 WS patch-merge 双写。

export function useCreateScene() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createScene,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scenesQueryKey() })
    },
  })
}

export function useActivateScene() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sceneId: number) => activateScene(sceneId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: scenesQueryKey() })
    },
  })
}

export function usePatchTake() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ takeId, body }: { takeId: number; body: PatchTakeBody }) =>
      patchTake(takeId, body),
    onSuccess: () => {
      // 改 scene_id/take_number 可能挪场，takes 与 scenes 都可能受影响。
      queryClient.invalidateQueries({ queryKey: ["takes"] })
      queryClient.invalidateQueries({ queryKey: scenesQueryKey() })
    },
  })
}

export function useDeleteTake() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (takeId: number) => deleteTake(takeId),
    onSuccess: (_data, takeId) => {
      // seedTakes 只增不删，invalidate→refetch 不会把已删条目从 store Map 抹掉。
      // 必须显式 removeTake，否则 HistoryTakes 仍显示该条（与 take.deleted WS 处理对称）。
      useSessionStore.getState().removeTake(takeId)
      queryClient.invalidateQueries({ queryKey: ["takes"] })
    },
  })
}

export function useRestoreTake() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (takeId: number) => restoreTake(takeId),
    onSuccess: () => {
      // 恢复后 take 重新出现：refetch 把它 seed 回 store Map。
      queryClient.invalidateQueries({ queryKey: ["takes"] })
    },
  })
}

// startTake / endTake 自助 invalidate ["takes"]：take.changed（5 字段 Pick）不带 end_ts，
// 只有 refetch 能把真实 end_ts / shot / start_ts 填进 store Map。REC 状态机判「take 是否已结束」
// 读 end_ts，故必须 await 这个 mutation（含 onSuccess 的 invalidate）后再做下一步决策。
export function useStartTake() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      sceneId,
      shot,
      speakerIds,
      takeNumber,
    }: {
      sceneId: number
      shot?: string | null
      speakerIds?: number[]
      takeNumber?: number | null
    }) => startTake(sceneId, shot, speakerIds, takeNumber),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["takes"] }),
  })
}

export function useEndTake() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => endTake(),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["takes"] }),
  })
}

// 阶段 1：上传剧本（只入库，不改场次，无需 invalidate）。
export function useUploadScript() {
  return useMutation({
    mutationFn: ({ file }: { file: File }) => uploadScript(file),
  })
}

// 阶段 2：启动后台解析（立即返回 parsing；进度/结果靠 useScriptUploads 轮询）。
export function useParseUpload() {
  return useMutation({
    mutationFn: ({
      uploadId,
      target,
      onConflict,
    }: {
      uploadId: number
      target?: "multi_scene" | "current_scene"
      onConflict?: "skip" | "version"
    }) => parseUpload(uploadId, target, onConflict),
  })
}

export const scriptUploadsQueryKey = () => ["script-uploads"] as const

// 上传记录查询：常驻启用（每次挂载都拉一次，故切走再回来能恢复进度），
// 仅当有「解析中」记录时每 1.5s 轮询；否则不轮询。后台解析与前端解耦，
// 进度由服务器 status/detail 派生，切 tab 卸载组件不影响后台任务。
export function useScriptUploads() {
  return useQuery({
    queryKey: scriptUploadsQueryKey(),
    queryFn: listScriptUploads,
    refetchInterval: (query) => {
      const data = query.state.data as ScriptUploadInfo[] | undefined
      return data?.some((u) => u.status === "parsing") ? 1500 : false
    },
  })
}

// ── 导出场记单 CSV ──

// 导出文件名由前端权威生成（纯 ASCII，恒带 .csv 后缀）。不依赖响应的 Content-Disposition——
// 跨域代理可能 strip 或改写该头，浏览器读到的值不可信，曾导致下载名乱码 / 丢后缀。
// scope 标出范围（today/all），日期用本地日期。
export function buildExportFilename(scope: "today" | "all", now = new Date()): string {
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, "0")
  const d = String(now.getDate()).padStart(2, "0")
  return `soundspeed_takes_${scope}_${y}-${m}-${d}.csv`
}

// "今天" 的导出区间：本地零点起 24h（[from, to) Unix 秒）。收 now 参数便于测试。
// 注：固定加 86400，DST 切换当天本地日严格说不是恒定 86400 秒，此处沿用现有行为不做日历修正。
export function todayRange(now = new Date()): { from: number; to: number } {
  const from = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
  return { from, to: from + 86400 }
}

// 装配导出请求：把 fmt 摊成 query（后端用同一算法生成 FileName 列），range 给定时附 ts_from/ts_to，
// token 给定时带 Authorization。纯函数，便于直接测 URL/参数/鉴权头，不碰 fetch/DOM。
export function buildExportRequest(
  fmt: FileNameFormat,
  range: { from: number; to: number } | undefined,
  token: string | null,
): { url: string; headers: Record<string, string> } {
  const params = new URLSearchParams({
    scene_prefix: fmt.scene.prefix,
    scene_pad: String(fmt.scene.pad),
    shot_prefix: fmt.shot.prefix,
    shot_pad: String(fmt.shot.pad),
    take_prefix: fmt.take.prefix,
    take_pad: String(fmt.take.pad),
    sep: fmt.sep,
  })
  if (range) {
    params.set("ts_from", String(range.from))
    params.set("ts_to", String(range.to))
  }
  return {
    url: `${API_BASE}/api/v1/takes/export?${params.toString()}`,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }
}

// 导出 take 为 CSV 并触发浏览器下载。FileName 列按用户当前命名格式渲染（与 UI 一致）：
// 把 fmt 摊成 query 传后端，后端用同一算法生成 FileName，CSV 装配/转义/BOM 全在后端。
// range 给定时只导该 take 开录时间区间（[from, to) Unix 秒，"今天"=本地零点起 24h）；
// 省略即导全部。不弹 modal——下拉选完直接下载（blob + 隐藏 a 标签）。
export async function exportTakesCsv(
  fmt: FileNameFormat,
  scope: "today" | "all",
  range?: { from: number; to: number },
): Promise<void> {
  const token = useSessionStore.getState().token
  const { url, headers } = buildExportRequest(fmt, range, token)
  const res = await fetch(url, { headers })
  if (!res.ok) {
    throw new ApiError(res.status, `GET /api/v1/takes/export → ${res.status}`)
  }

  const blob = await res.blob()
  // 强制声明为 CSV 的 blob 类型；文件名前端权威生成，不读 Content-Disposition。
  const csvBlob = blob.type ? blob : new Blob([blob], { type: "text/csv;charset=utf-8" })
  const filename = buildExportFilename(scope)

  const objectUrl = URL.createObjectURL(csvBlob)
  try {
    const a = document.createElement("a")
    a.href = objectUrl
    a.download = filename
    a.rel = "noopener"
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}
