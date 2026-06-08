import { useEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { miniPill } from "@/lib/styles"
import { API_BASE, DEFAULT_API_BASE, LS_API_BASE_KEY, LS_TOKEN_KEY } from "@/lib/config"
import { DEV_ASR_SAMPLE, DEV_SCRIPT_SAMPLE } from "@/data/devFixtures"
import { useSessionStore } from "@/store/session"
import type { ToolCallEntry } from "@/store/session"
import {
  asrConfigQueryKey,
  devicesQueryKey,
  endTake,
  injectDebugAsr,
  injectDebugScript,
  pickActiveScene,
  refreshDevices,
  resetDb,
  selectDevice,
  setAsrLanguage,
  startTake,
  useAsrConfig,
  useDevices,
  useScenes,
  type DebugAsrSeg,
  type DebugScriptLine,
} from "@/lib/api"
import { FlaskConical, RefreshCw, Server, Trash2 } from "lucide-react"
import ActorManagementPanel from "@/components/admin/ActorManagementPanel"
import { useFileNameFormat } from "@/store/filename"
import {
  formatFileName,
  FILENAME_SAMPLE,
  FILENAME_PRESETS,
  SCENE_PREFIXES,
  SHOT_PREFIXES,
  TAKE_PREFIXES,
  SEPARATORS,
  PAD_OPTIONS,
  type SegFormat,
} from "@/lib/filename-format"

// 真实音频输入设备下拉：读 GET /api/v1/devices，下拉值直接用后端权威的 selected（实际会采集的 index，
// 持久化设备不在场时已是 fallback 设备的 index）。切换时 POST /devices/select（未启用实时 ASR 时后端 409，
// 这里 catch 不崩）。持久化设备掉线（selected_available===false）时下方提示当前实际使用的设备。
function AudioInputSelect() {
  const { data, isLoading, error } = useDevices()
  const qc = useQueryClient()
  const [refreshing, setRefreshing] = useState(false)
  const [refreshErr, setRefreshErr] = useState<string | null>(null)
  const devices = data?.devices ?? []
  const value = data?.selected != null ? String(data.selected) : undefined
  // 保存的设备当前不在场：提示当前实际使用的设备（selected 是后端权威 fallback index）。
  const fellBack = data?.selected_available === false && !!data?.selected_name
  const fallbackName =
    devices.find((d) => d.index === data?.selected)?.name ?? "默认输入"

  const onChange = async (v: string) => {
    try {
      await selectDevice(Number(v))
      qc.invalidateQueries({ queryKey: devicesQueryKey() })
    } catch (err) {
      console.error("selectDevice failed", err)
    }
  }

  // 热插刷新：后端 reinit PortAudio 重扫，再 invalidate 让列表重拉。正在录制时后端 409。
  const onRefresh = async () => {
    setRefreshing(true)
    setRefreshErr(null)
    try {
      await refreshDevices()
      await qc.invalidateQueries({ queryKey: devicesQueryKey() })
    } catch (err) {
      setRefreshErr(err instanceof Error ? err.message : "刷新设备失败")
    } finally {
      setRefreshing(false)
    }
  }

  if (isLoading) {
    return <div className="text-xs text-muted-foreground">检测设备中…</div>
  }
  // 注意：刷新按钮在「未检测到设备」时也要在 —— 启动前没插声卡的场景，正靠它热插刷出来。
  const noDevices = !!error || devices.length === 0
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center gap-2">
        {noDevices ? (
          <div className="flex-1 text-xs text-destructive">未检测到输入设备</div>
        ) : (
          <Select value={value} onValueChange={onChange}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="选择输入设备" />
            </SelectTrigger>
            <SelectContent>
              {devices.map((d) => (
                <SelectItem key={d.index} value={String(d.index)}>
                  {d.name}
                  {d.is_default ? "（默认）" : ""} · {d.max_input_channels}ch
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <Button
          variant="outline"
          size="icon"
          className="shrink-0"
          onClick={() => void onRefresh()}
          disabled={refreshing}
          title="重扫设备（启动后插的声卡用这个刷出来，免重启后端）"
        >
          <RefreshCw className={"size-4" + (refreshing ? " animate-spin" : "")} />
        </Button>
      </div>
      {refreshErr && <span className="text-xs text-destructive">{refreshErr}</span>}
      {fellBack && (
        <span className="text-xs text-amber-600">
          保存的设备「{data?.selected_name}」未连接，当前使用「{fallbackName}」
        </span>
      )}
    </div>
  )
}

const ASR_LANG_LABEL: Record<string, string> = {
  zh: "简体中文",
  en: "English",
  auto: "自动检测",
}

// 转录语言（ASR whisper.cpp）下拉 + 当前模型展示。默认 zh；切换即时生效（POST /asr/language）。
function AsrLanguageSelect() {
  const { data, isLoading } = useAsrConfig()
  const qc = useQueryClient()
  const langs = data?.languages ?? ["zh", "en", "auto"]
  const value = data?.language ?? "zh"

  const onChange = async (v: string) => {
    try {
      await setAsrLanguage(v)
      qc.invalidateQueries({ queryKey: asrConfigQueryKey() })
    } catch (err) {
      console.error("setAsrLanguage failed", err)
    }
  }

  if (isLoading) {
    return <div className="text-xs text-muted-foreground">加载…</div>
  }
  return (
    <div className="grid gap-1.5">
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="选择转录语言" />
        </SelectTrigger>
        <SelectContent>
          {langs.map((l) => (
            <SelectItem key={l} value={l}>
              {ASR_LANG_LABEL[l] ?? l}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <span className="text-[11px] text-muted-foreground">
        当前模型：{data?.model ?? "—"}
        {data && !data.enabled ? "（实时 ASR 未启用）" : ""}
      </span>
    </div>
  )
}

function statusTextClass(kind: "info" | "error" | "done"): string {
  return kind === "error"
    ? "text-xs text-destructive"
    : kind === "done"
      ? "text-xs text-green-600"
      : "text-xs text-muted-foreground"
}

// 环境感知默认 API base：有 VITE_API_BASE 用它，否则回落 config 的 DEFAULT_API_BASE（字面量唯一来源）。
// 去尾斜杠后供 handleSaveApiBase 判「输入等于默认 → removeItem 不留冗余 override」。
const ENV_DEFAULT_API_BASE = (import.meta.env.VITE_API_BASE ?? DEFAULT_API_BASE).replace(/\/$/, "")

// epoch 秒 → HH:MM:SS（本地时区）。tool.call 的 ts 是 float 秒。
function fmtTs(ts: number): string {
  const d = new Date(ts * 1000)
  const p = (n: number) => String(n).padStart(2, "0")
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

// arguments 是原样 JSON 字符串：能 parse 就 2 空格缩进美化，失败 fallback 原串。
function prettyArgs(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

// token 用量摘要：prompt/completion/total 各有才显示（null 跳过）。全 null → 返回 null（不渲染该行）。
function tokensSummary(t: ToolCallEntry): string | null {
  const parts: string[] = []
  if (t.prompt_tokens != null) parts.push(`prompt ${t.prompt_tokens}`)
  if (t.completion_tokens != null) parts.push(`completion ${t.completion_tokens}`)
  if (t.total_tokens != null) parts.push(`total ${t.total_tokens}`)
  return parts.length ? parts.join(" / ") : null
}

// 单条 tool call 渲染成结构化小块（v2 payload）。框 h-72 够高，多行无妨。
function ToolCallBlock({ t }: { t: ToolCallEntry }) {
  const tokens = tokensSummary(t)
  return (
    <div className="border-b border-border/40 py-2 last:border-b-0">
      {/* 第一行：时间 · task_type · tool_name（高亮加粗），右侧 finish_reason */}
      <div className="flex items-baseline gap-1">
        <span className="text-muted-foreground/60">[{fmtTs(t.ts)}]</span>
        <span className="text-muted-foreground">{t.task_type}</span>
        <span className="text-muted-foreground/40">·</span>
        <span className="font-bold text-primary">{t.tool_name}</span>
        {t.finish_reason && (
          <span className="ml-auto text-[10px] text-muted-foreground/60">
            {t.finish_reason}
          </span>
        )}
      </div>

      {/* arguments：JSON 美化多行 */}
      <pre className="mt-1 whitespace-pre-wrap break-all text-foreground/90">
        {prettyArgs(t.arguments)}
      </pre>

      {/* 元数据：model · token 用量（有才显示） */}
      {(t.model || tokens) && (
        <div className="mt-1 text-[10px] text-muted-foreground/70">
          {[t.model, tokens].filter(Boolean).join(" · ")}
        </div>
      )}

      {/* 可用工具 + tool_choice（available_tools 空就整行不显示） */}
      {t.available_tools.length > 0 && (
        <div className="text-[10px] text-muted-foreground/70">
          tools: {t.available_tools.join(", ")}
          {t.tool_choice && <span> · choice: {t.tool_choice}</span>}
        </div>
      )}
    </div>
  )
}

// 开发者 tab：后端 agent tool-call 实时日志框。订阅 store.toolCalls（tool.call WS 有界缓冲），
// 新条目到达自动滚到底。空态给灰字占位。等宽、固定高、可滚。
function ToolCallLog() {
  const toolCalls = useSessionStore((s) => s.toolCalls)
  const scrollRef = useRef<HTMLDivElement>(null)

  // 新条目到达自动滚到底（依赖 length，只在条数变化时滚）。
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [toolCalls.length])

  return (
    <div className="grid gap-1.5">
      <span className="text-xs font-medium text-foreground">Logs</span>
      <div
        ref={scrollRef}
        className="h-72 overflow-y-auto rounded-md border bg-muted/50 p-2 font-mono text-[11px] leading-relaxed"
      >
        {toolCalls.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center text-muted-foreground/60">
            暂无 tool call —— 跑一次「一键跑完整 take」后这里实时显示 Gemma 的工具调用
          </div>
        ) : (
          toolCalls.map((t, i) => <ToolCallBlock key={i} t={t} />)
        )}
      </div>
    </div>
  )
}

// ── 文件名显示格式设置（常规 tab）：场镜次 → 录音机文件名风格，分项可配 + 实时预览 ──
const PREFIX_NONE = "·none·" // radix SelectItem 不允许空 value，空前缀编码占位
const SEP_LABEL: Record<string, string> = {
  "_": "下划线 _",
  "-": "连字符 -",
  " · ": "中点 ·",
  " ": "空格",
}
const PAD_LABEL: Record<number, string> = { 0: "不补零", 1: "1 位", 2: "2 位（01）", 3: "3 位（001）" }

function PrefixSelect({
  value,
  options,
  onChange,
}: {
  value: string
  options: readonly string[]
  onChange: (v: string) => void
}) {
  return (
    <Select
      value={value === "" ? PREFIX_NONE : value}
      onValueChange={(v) => onChange(v === PREFIX_NONE ? "" : v)}
    >
      <SelectTrigger className="h-9 w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o || PREFIX_NONE} value={o === "" ? PREFIX_NONE : o}>
            {o === "" ? "（无）" : o}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function PadSelect({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <Select value={String(value)} onValueChange={(v) => onChange(Number(v))}>
      <SelectTrigger className="h-9">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {PAD_OPTIONS.map((p) => (
          <SelectItem key={p} value={String(p)}>
            {PAD_LABEL[p]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function FileNameFormatSettings() {
  const format = useFileNameFormat((s) => s.format)
  const setFormat = useFileNameFormat((s) => s.setFormat)
  const preview = formatFileName(FILENAME_SAMPLE, format)
  const updateSeg = (key: "scene" | "shot" | "take", patch: Partial<SegFormat>) =>
    setFormat({ ...format, [key]: { ...format[key], ...patch } })

  // 三段前缀下拉同构（只差 label/options/段键），抽成本地渲染函数避免三份拷贝。
  const prefixField = (key: "scene" | "shot" | "take", label: string, options: readonly string[]) => (
    <div className="grid gap-1 w-[4.5rem]">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <PrefixSelect
        value={format[key].prefix}
        options={options}
        onChange={(v) => updateSeg(key, { prefix: v })}
      />
    </div>
  )

  return (
    <div className="grid gap-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">文件名显示格式</span>
        <span className="font-mono text-xs text-muted-foreground truncate">
          Scene 1·Shot 1·Take 1 →{" "}
          <span className="text-primary font-semibold">{preview || "—"}</span>
        </span>
      </div>

      {/* 预设快选：选了即套用（不保持选中态）。 */}
      <Select
        value=""
        onValueChange={(v) => {
          const p = FILENAME_PRESETS[Number(v)]
          if (p) setFormat(p.value)
        }}
      >
        <SelectTrigger className="w-full">
          <SelectValue placeholder="套用预设…" />
        </SelectTrigger>
        <SelectContent>
          {FILENAME_PRESETS.map((p, i) => (
            <SelectItem key={p.label} value={String(i)}>
              {p.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 前缀成一组、Take 补零+分隔符成一组；两组紧凑横排始终一行（不换行），窄屏横向滚动兜底。 */}
      <div className="flex items-end gap-x-5 overflow-x-auto pb-0.5">
        <div className="flex items-end gap-2 flex-shrink-0">
          {prefixField("scene", "Scene 前缀", SCENE_PREFIXES)}
          {prefixField("shot", "Shot 前缀", SHOT_PREFIXES)}
          {prefixField("take", "Take 前缀", TAKE_PREFIXES)}
        </div>
        <div className="flex items-end gap-2 flex-shrink-0">
          <div className="grid gap-1 w-28">
            <span className="text-[11px] text-muted-foreground">Take 补零</span>
            <PadSelect value={format.take.pad} onChange={(v) => updateSeg("take", { pad: v })} />
          </div>
          <div className="grid gap-1 w-28">
            <span className="text-[11px] text-muted-foreground">分隔符</span>
            <Select value={format.sep} onValueChange={(v) => setFormat({ ...format, sep: v })}>
              <SelectTrigger className="h-9 w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SEPARATORS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {SEP_LABEL[s] ?? s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>
    </div>
  )
}

const DEBUG_ASR_PLACEHOLDER = `{
  "speakers": ["SPEAKER_00", "SPEAKER_01"],
  "turns": [
    { "start": 2.88, "end": 5.63, "speaker": "SPEAKER_00", "text": "你昨天为什么没告诉我真相。" },
    { "start": 5.70, "end": 8.10, "speaker": "SPEAKER_01", "text": "因为我不想让你再卷进来。" }
  ]
}

// 也接受纯段数组：[{ "ch": 1, "speaker": "...", "text": "...", "is_partial": false }]`

// 容错解析，三种输入形状（按优先级）：
// 1. diarize 导出 {turns:[{speaker,text,start,end,...}]} → 每条 turn 映射为 ch1 final 段（单声道）。
// 2. 顶层数组 [{ch?=1, speaker?=null, text, is_partial?=false}]。
// 3. {segments:[...]} 包裹，同 (2)。
// 每项需非空 text，缺 text 的项跳过（不报错）。speaker 任意字符串（speakerColor 哈希分色）。
function parseDebugAsr(raw: string): { segs: DebugAsrSeg[]; error: string | null } {
  let data: unknown
  try {
    data = JSON.parse(raw)
  } catch {
    return { segs: [], error: "JSON 解析失败：检查格式（{turns:[...]} 或段数组）" }
  }

  // 形状 1：diarize {turns:[...]}。turns 是 final，单声道 = ch1；忽略 start/end，按数组顺序注入
  //（后端 /debug/asr 盖单调 server frame，顺序保留）。
  if (data && typeof data === "object" && Array.isArray((data as { turns?: unknown }).turns)) {
    const turns = (data as { turns: unknown[] }).turns
    const segs: DebugAsrSeg[] = []
    for (const t of turns) {
      if (!t || typeof t !== "object") continue
      const o = t as Record<string, unknown>
      if (typeof o.text !== "string" || !o.text.trim()) continue
      segs.push({
        ch: 1,
        text: o.text,
        speaker: typeof o.speaker === "string" ? o.speaker : null,
        is_partial: false,
      })
    }
    if (segs.length === 0) return { segs: [], error: "turns 里没有带 text 的有效条目" }
    return { segs, error: null }
  }

  // 形状 2 / 3：顶层数组 或 {segments:[...]}。
  const arr = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as { segments?: unknown }).segments)
      ? (data as { segments: unknown[] }).segments
      : null
  if (!arr) return { segs: [], error: "需要 {turns:[...]}、段数组、或 {segments:[...]}" }
  if (arr.length === 0) return { segs: [], error: "段数组为空" }

  const segs: DebugAsrSeg[] = []
  for (const item of arr) {
    if (!item || typeof item !== "object") continue
    const o = item as Record<string, unknown>
    if (typeof o.text !== "string" || !o.text.trim()) continue
    segs.push({
      ch: o.ch === 2 ? 2 : 1,
      text: o.text,
      speaker: typeof o.speaker === "string" ? o.speaker : null,
      is_partial: o.is_partial === true,
    })
  }
  if (segs.length === 0) return { segs: [], error: "没有带 text 的有效段" }
  return { segs, error: null }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

// slugline heading 三个输入的配置（key 对应 DebugScriptHeading）。
const HEADING_FIELDS = [
  { key: "int_ext", label: "内外景", placeholder: "室外" },
  { key: "time_of_day", label: "时间", placeholder: "日" },
  { key: "location", label: "地点", placeholder: "街道" },
] as const

const DEBUG_SCRIPT_PLACEHOLDER = `SZA：你昨天为什么没告诉我真相。
YY：因为我不想让你再卷进来。
那你打算什么时候告诉我。

// 也接受 JSON：[{ "character": "SZA", "text": "..." }] 或 {lines:[...]}`

// 剧本文本解析，两种输入形状（按优先级）：
// 1. JSON 数组 [{character?, text}] 或 {lines:[...]}（容错，同 ASR parser）。
// 2. 纯文本，每行一句：按首个全角「：」或半角「:」切分 → {character: 冒号前, text: 冒号后}；
//    无冒号的行 → {character: null, text: 整行}。空行跳过。
// 每行需非空 text。
function parseDebugScript(raw: string): { lines: DebugScriptLine[]; error: string | null } {
  const trimmed = raw.trim()
  if (!trimmed) return { lines: [], error: "剧本为空" }

  // 先试 JSON（数组 或 {lines:[...]}）。失败则当纯文本。
  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    let data: unknown = null
    try {
      data = JSON.parse(trimmed)
    } catch {
      // 解析失败 → data 保持 null，退回纯文本路径。
    }
    if (data) {
      const arr = Array.isArray(data)
        ? data
        : typeof data === "object" && Array.isArray((data as { lines?: unknown }).lines)
          ? (data as { lines: unknown[] }).lines
          : null
      if (arr) {
        const lines: DebugScriptLine[] = []
        for (const item of arr) {
          if (!item || typeof item !== "object") continue
          const o = item as Record<string, unknown>
          if (typeof o.text !== "string" || !o.text.trim()) continue
          lines.push({
            character: typeof o.character === "string" ? o.character : null,
            text: o.text.trim(),
          })
        }
        if (lines.length === 0) return { lines: [], error: "JSON 里没有带 text 的有效行" }
        return { lines, error: null }
      }
      // 是 JSON 但形状不对（既非数组也非 {lines:[]}）→ 报错，不静默当纯文本。
      return { lines: [], error: "JSON 需为数组或 {lines:[...]}" }
    }
  }

  // 纯文本：每行按首个 ：/ : 切分。
  const lines: DebugScriptLine[] = []
  for (const row of trimmed.split(/\r?\n/)) {
    const line = row.trim()
    if (!line) continue
    const m = /[：:]/.exec(line)
    if (m) {
      const character = line.slice(0, m.index).trim()
      const text = line.slice(m.index + 1).trim()
      if (!text) continue
      lines.push({ character: character || null, text })
    } else {
      lines.push({ character: null, text: line })
    }
  }
  if (lines.length === 0) return { lines: [], error: "没有有效台词行" }
  return { lines, error: null }
}

// ---- 数据模型 ----

interface SettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

// ---- 组件 ----

export default function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  // 服务器连接：admin token（localStorage 持久化 + 同步 store 触发重连）
  const storeToken = useSessionStore((s) => s.token)
  const connection = useSessionStore((s) => s.connection)
  const setToken = useSessionStore((s) => s.setToken)
  const [tokenInput, setTokenInput] = useState<string>(storeToken ?? "")
  // API 地址可编辑：初值=当前生效的 API_BASE（模块期常量，不是空串）。
  const [apiBaseInput, setApiBaseInput] = useState<string>(API_BASE)
  const queryClient = useQueryClient()

  // 保存 API 地址：trim → 去尾斜杠 → 等于默认/空则 removeItem 否则写 LS_API_BASE_KEY → 整页 reload
  //（API_BASE 是模块加载期 const，热换不掉，必须 reload 让新 base 在所有 fetch/WS 生效）。
  const handleSaveApiBase = () => {
    const v = apiBaseInput.trim().replace(/\/$/, "")
    if (!v || v === ENV_DEFAULT_API_BASE) {
      localStorage.removeItem(LS_API_BASE_KEY)
    } else {
      localStorage.setItem(LS_API_BASE_KEY, v)
    }
    location.reload()
  }

  const handleSaveToken = () => {
    const v = tokenInput.trim()
    if (v) {
      localStorage.setItem(LS_TOKEN_KEY, v)
    } else {
      localStorage.removeItem(LS_TOKEN_KEY)
    }
    // 写 localStorage 不会通知 useLiveConnection；更新 store.token 才会翻转连接态并触发重连。
    setToken(v || null)
    // 首次填 token 时 scenes/takes 此前因 401 settle 在 error，key 没变不会自动 refetch；
    // 显式 invalidate 让它们带新 token 重取（否则 REC 一直停在「无活跃场次」直到硬刷新）。
    if (v) {
      queryClient.invalidateQueries({ queryKey: ["scenes"] })
      queryClient.invalidateQueries({ queryKey: ["takes"] })
    }
  }

  // ---- dev 测试面板：paste ASR JSON → 一键跑完整 take ----
  const { data: scenes } = useScenes()
  const activeScene = pickActiveScene(scenes)
  const resetSegments = useSessionStore((s) => s.resetSegments)
  const [asrJson, setAsrJson] = useState(DEV_ASR_SAMPLE)
  const [running, setRunning] = useState(false)
  const [runStatus, setRunStatus] = useState<{ kind: "info" | "error" | "done"; msg: string } | null>(null)
  const [scriptText, setScriptText] = useState(DEV_SCRIPT_SAMPLE)
  const [scriptStatus, setScriptStatus] = useState<{ kind: "info" | "error" | "done"; msg: string } | null>(null)
  // 一键清空数据库：二次确认弹窗开关 + 状态 pill（沿用 scriptStatus 的展示风格）。
  const [confirmResetOpen, setConfirmResetOpen] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetStatus, setResetStatus] = useState<{ kind: "info" | "error" | "done"; msg: string } | null>(null)
  // slugline heading（随剧本注入写到场次）。预填默认场景头。
  const [heading, setHeading] = useState({ int_ext: "室外", time_of_day: "日", location: "街道" })

  const handleInjectScript = async () => {
    if (running) return
    const { lines, error } = parseDebugScript(scriptText)
    if (error) {
      setScriptStatus({ kind: "error", msg: error })
      return
    }
    if (!activeScene) {
      setScriptStatus({ kind: "error", msg: "无活跃场次，无法注入" })
      return
    }
    setRunning(true)
    try {
      // sceneId 省略 → 后端用活跃场次；这里显式传 activeScene 与 UI 显示一致。
      // heading 空串由 injectDebugScript 内部过滤（不清掉已有 heading）。
      const res = await injectDebugScript(lines, activeScene.scene_id, heading)
      setScriptStatus({
        kind: "done",
        msg: `注入 ${res.line_count} 行剧本到 Scene ${res.scene_id}`,
      })
      // 让剧本面板立刻看到新剧本 + heading。
      queryClient.invalidateQueries({ queryKey: ["scenes"] })
      queryClient.invalidateQueries({ queryKey: ["scene-script"] })
    } catch (err) {
      console.error("inject script failed", err)
      setScriptStatus({ kind: "error", msg: "请求失败（看 console / 是否 SOUNDSPEED_DEV=1）" })
    } finally {
      setRunning(false)
    }
  }

  const handleResetDb = async () => {
    if (resetting) return
    setResetting(true)
    setResetStatus({ kind: "info", msg: "清空中…" })
    try {
      await resetDb()
      // 成功 → 整页 reload，从空/新库重新派生 UI（不必手动同步各处缓存状态）。
      location.reload()
    } catch (err) {
      console.error("reset db failed", err)
      setResetStatus({ kind: "error", msg: "清空失败（看 console / 是否 SOUNDSPEED_DEV=1 / token）" })
      setResetting(false)
      setConfirmResetOpen(false)
    }
  }

  const handleRunFullTake = async () => {
    if (running) return
    const { segs, error } = parseDebugAsr(asrJson)
    if (error) {
      setRunStatus({ kind: "error", msg: error })
      return
    }
    if (!activeScene) {
      setRunStatus({ kind: "error", msg: "无活跃场次，无法开始" })
      return
    }
    setRunning(true)
    // 清 segments，避免上一次注入残留。currentTakeId 由 applyTakeChanged 兜底顶到新 take（单调最大 id），
    // applyAsr 跨-take 守卫随之对齐；新 take 的编号经 take.changed + refetch 显示。
    resetSegments()
    try {
      await startTake(activeScene.scene_id, null)
      setRunStatus({ kind: "info", msg: `注入 ${segs.length} 段…` })
      for (const seg of segs) {
        await injectDebugAsr(seg)
        // stagger，让 transcript 可见地滚动（partial 替换 / final 落定）。
        await sleep(150)
      }
      await endTake()
      setRunStatus({ kind: "done", msg: "完成 — 看 History / LLM 反馈 tab" })
      queryClient.invalidateQueries({ queryKey: ["takes"] })
    } catch (err) {
      console.error("run full take failed", err)
      setRunStatus({ kind: "error", msg: "请求失败（看 console / 是否 SOUNDSPEED_DEV=1）" })
    } finally {
      setRunning(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>设置</DialogTitle>
          <DialogDescription>
            配置音频输入、演员与说话人绑定，开发者选项含服务器连接与测试工具
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="general" className="py-2">
          <TabsList className="w-full flex-shrink-0">
            <TabsTrigger value="general">常规</TabsTrigger>
            <TabsTrigger value="dev">开发者</TabsTrigger>
          </TabsList>

          {/* ============ 常规 tab ============ */}
          <TabsContent value="general" className="grid gap-5 max-h-[70vh] overflow-y-auto pr-1">
            {/* ========== 音频输入 ========== */}
            <div className="grid gap-2">
              <span className="text-sm font-medium">音频输入设备</span>
              <AudioInputSelect />
            </div>

            <div className="grid gap-2">
              <span className="text-sm font-medium">转录语言（ASR）</span>
              <AsrLanguageSelect />
            </div>

            <Separator />

            {/* ========== 演员（声纹台账，接 /api/v1/speakers）========== */}
            {/* merge 注：1.x 把演员/说话人管理重构成独立组件 ActorManagementPanel（接真实
                /api/v1/speakers 后端），取代 2.x 内联的本地 state 版双栏 UI。 */}
            <ActorManagementPanel />

            <Separator />

            {/* ========== 界面语言 ========== */}
            <div className="grid gap-2">
              <span className="text-sm font-medium">界面语言</span>
              <Select defaultValue="zh">
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="选择语言" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="zh">简体中文</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <Separator />

            {/* ========== 文件名显示格式（场镜次 → 录音机文件名风格）========== */}
            <FileNameFormatSettings />
          </TabsContent>

          {/* ============ 开发者 tab ============ */}
          <TabsContent value="dev" className="grid gap-5 max-h-[70vh] overflow-y-auto pr-1">
            {/* ========== 服务器连接 ========== */}
            <div className="grid gap-2">
              <div className="flex items-center gap-2">
                <Server className="size-4 text-primary" />
                <span className="text-sm font-medium">服务器连接</span>
                <span
                  className={`ml-auto ${miniPill(
                    connection === "open" ? "primary" : "neutral",
                    "text-[10px]"
                  )}`}
                >
                  {connection === "open"
                    ? "已连接"
                    : connection === "connecting"
                      ? "连接中…"
                      : connection === "no-token"
                        ? "未鉴权"
                        : "已断开"}
                </span>
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">后端 IP 地址</span>
                <div className="flex gap-2">
                  <Input
                    type="text"
                    placeholder="http://localhost:8000"
                    value={apiBaseInput}
                    onChange={(e) => setApiBaseInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveApiBase()
                    }}
                    className="flex-1 font-mono text-xs"
                  />
                  <Button variant="secondary" size="sm" onClick={handleSaveApiBase}>
                    保存
                  </Button>
                </div>
                <span className="text-[11px] text-muted-foreground/70">
                  改地址后整页刷新生效（影响所有请求与 WebSocket）。
                </span>
              </div>
              <div className="grid gap-1">
                <span className="text-xs text-muted-foreground">Admin Token</span>
                <div className="flex gap-2">
                  <Input
                    type="password"
                    placeholder="粘贴后端启动时打印的 admin token"
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    onBlur={handleSaveToken}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveToken()
                    }}
                    className="flex-1"
                  />
                  <Button variant="secondary" size="sm" onClick={handleSaveToken}>
                    保存
                  </Button>
                </div>
                {connection === "no-token" && (
                  <span className="text-xs text-destructive">
                    未填写 admin token，连接未鉴权。
                  </span>
                )}
              </div>
            </div>

            {/* ========== 开发 / 测试 ========== */}
            <Separator />

            <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <FlaskConical className="size-4 text-primary" />
                  <span className="text-sm font-medium">开发 / 测试</span>
                </div>

                {/* ---- tool-call 实时日志框（Agent 工具调用轨迹） ---- */}
                <ToolCallLog />

                <Separator className="my-1" />

                {/* ---- 剧本注入（先做，持久化） ---- */}
                <span className="text-xs font-medium text-foreground">
                  剧本（可选，注入后 L2 才能产出真实 diff）
                </span>
                {/* slugline heading：随剧本写到场次，剧本面板头部显示 */}
                <div className="grid grid-cols-3 gap-2">
                  {HEADING_FIELDS.map(({ key, label, placeholder }) => (
                    <div key={key} className="grid gap-1">
                      <span className="text-[10px] text-muted-foreground">{label}</span>
                      <Input
                        value={heading[key]}
                        onChange={(e) => setHeading((h) => ({ ...h, [key]: e.target.value }))}
                        placeholder={placeholder}
                        className="h-8 text-xs"
                        disabled={running}
                      />
                    </div>
                  ))}
                </div>
                <Textarea
                  value={scriptText}
                  onChange={(e) => setScriptText(e.target.value)}
                  placeholder={DEBUG_SCRIPT_PLACEHOLDER}
                  rows={5}
                  className="font-mono text-xs"
                  disabled={running}
                />
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="gap-1.5"
                    disabled={running || !activeScene || !scriptText.trim()}
                    onClick={handleInjectScript}
                  >
                    注入剧本到当前场次
                  </Button>
                  {scriptStatus && (
                    <span className={statusTextClass(scriptStatus.kind)}>
                      {scriptStatus.msg}
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-muted-foreground/70">
                  先注入剧本，再「一键跑完整 take」，L2 就会按剧本逐行比对（改词/漏词/加词）。
                  剧本会持久化，注入一次可跑多条 take。
                </span>

                <Separator className="my-1" />

                {/* ---- ASR 注入 + 一键跑完整 take ---- */}
                <span className="text-xs text-muted-foreground">
                  粘贴 ASR JSON，一键跑完整 take（start → 逐段注入 → end → L2）。
                </span>
                <Textarea
                  value={asrJson}
                  onChange={(e) => setAsrJson(e.target.value)}
                  placeholder={DEBUG_ASR_PLACEHOLDER}
                  rows={6}
                  className="font-mono text-xs"
                  disabled={running}
                />
                <div className="flex items-center gap-2">
                  <Button
                    variant="default"
                    size="sm"
                    className="gap-1.5"
                    disabled={running || !activeScene || !asrJson.trim()}
                    onClick={handleRunFullTake}
                  >
                    <FlaskConical className="size-4" />
                    {running ? "运行中…" : "一键跑完整 take"}
                  </Button>
                  {runStatus && (
                    <span className={statusTextClass(runStatus.kind)}>
                      {runStatus.msg}
                    </span>
                  )}
                </div>
                <span className="text-[10px] text-muted-foreground/70">
                  L2 摘要需 Gemma 权重，否则降级（script_diff 为空）。
                </span>
              </div>

              <Separator />

              {/* ---- 危险区：一键清空数据库内容 ---- */}
              <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <Trash2 className="size-4 text-destructive" />
                  <span className="text-sm font-medium text-destructive">危险操作</span>
                </div>
                <span className="text-xs text-muted-foreground">
                  清空全部业务数据（场次 / take / 剧本 / 转写），不可恢复。仅 dev 测试用。
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="destructive"
                    size="sm"
                    className="gap-1.5"
                    disabled={resetting}
                    onClick={() => {
                      setResetStatus(null)
                      setConfirmResetOpen(true)
                    }}
                  >
                    <Trash2 className="size-4" />
                    {resetting ? "清空中…" : "清空数据库"}
                  </Button>
                  {resetStatus && (
                    <span className={statusTextClass(resetStatus.kind)}>
                      {resetStatus.msg}
                    </span>
                  )}
                </div>
              </div>
          </TabsContent>
        </Tabs>
      </DialogContent>

      {/* 一键清空数据库 — 二次确认（无 AlertDialog 组件，用 Dialog 搭等效确认） */}
      <Dialog
          open={confirmResetOpen}
          onOpenChange={(o) => {
            // 清空进行中不允许关弹窗（避免误触；成功会 reload，失败由 handler 关闭）。
            if (resetting) return
            setConfirmResetOpen(o)
          }}
        >
          <DialogContent className="sm:max-w-sm">
            <DialogHeader>
              <DialogTitle>清空数据库内容</DialogTitle>
              <DialogDescription>
                确定清空全部数据库内容？此操作不可恢复。
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                size="sm"
                disabled={resetting}
                onClick={() => setConfirmResetOpen(false)}
              >
                取消
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={resetting}
                onClick={handleResetDb}
              >
                {resetting ? "清空中…" : "确定清空"}
              </Button>
            </DialogFooter>
          </DialogContent>
      </Dialog>
    </Dialog>
  )
}
