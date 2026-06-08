import { useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { miniPill } from "@/lib/styles"
import {
  createSpeaker,
  deleteSpeaker,
  enrollSpeaker,
  speakersQueryKey,
  useCharacters,
  useSpeakers,
} from "@/lib/api"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { CheckCircle2, ChevronDown, Loader2, Mic, Plus, Trash2, Upload, User } from "lucide-react"
import EnrollRecorderDialog from "@/components/admin/EnrollRecorderDialog"
import type { SpeakerDTO } from "@/types/api"

type Msg = { kind: "error" | "done" | "info"; text: string }

// 已注册演员(speaker)管理：维护全局声纹台账。加演员（名字）→ 上传一段 sample 录声纹。
// take 创建时从这里选"在场演员"，diarization 回填只在所选演员里匹配。
export default function ActorManagementPanel() {
  const { data: speakers, isLoading, error } = useSpeakers()
  const { data: characters } = useCharacters() // 整部戏角色全集，"选角色"下拉用
  const qc = useQueryClient()
  const [newName, setNewName] = useState("")
  const [busy, setBusy] = useState<number | "add" | null>(null)
  const [msg, setMsg] = useState<Msg | null>(null)
  const [recordingFor, setRecordingFor] = useState<SpeakerDTO | null>(null)
  const fileInputs = useRef<Record<number, HTMLInputElement | null>>({})

  const invalidate = () => qc.invalidateQueries({ queryKey: speakersQueryKey() })

  const handleAdd = async () => {
    const name = newName.trim()
    if (!name || busy) return
    setBusy("add")
    setMsg(null)
    try {
      await createSpeaker(name)
      setNewName("")
      invalidate()
    } catch (e) {
      console.error("createSpeaker failed", e)
      setMsg({ kind: "error", text: "新增演员失败（看 console / 是否已连接）" })
    } finally {
      setBusy(null)
    }
  }

  const handleEnroll = async (id: number, file: File | undefined) => {
    if (!file || busy) return
    setBusy(id)
    setMsg(null)
    try {
      await enrollSpeaker(id, file)
      setMsg({ kind: "done", text: "声纹已录入" })
      invalidate()
    } catch (e) {
      const text = e instanceof Error ? e.message : "声纹录入失败"
      setMsg({ kind: "error", text })
    } finally {
      setBusy(null)
    }
  }

  const handleDelete = async (id: number) => {
    if (busy) return
    setBusy(id)
    try {
      await deleteSpeaker(id)
      invalidate()
    } catch (e) {
      console.error("deleteSpeaker failed", e)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="grid gap-3 content-start">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">演员（声纹台账）</span>
        <span className="text-xs text-muted-foreground">加演员后上传一段 sample 录声纹</span>
      </div>

      {isLoading && <div className="text-xs text-muted-foreground">加载演员…</div>}
      {error && <div className="text-xs text-destructive">加载失败（检查连接 / token）</div>}

      <div className="grid gap-2">
        {(speakers ?? []).map((s) => {
          const rowBusy = busy === s.speaker_id
          return (
            <div
              key={s.speaker_id}
              className="flex items-center gap-2 rounded-2xl bg-muted/50 px-3 py-2"
            >
              <User className="size-4 text-primary flex-shrink-0" />
              <span className="text-sm font-medium flex-1 truncate">{s.display_name}</span>
              {s.has_enrollment ? (
                <span className={miniPill("primary", "text-[10px] flex-shrink-0 gap-1")}>
                  <CheckCircle2 className="size-3" />已录声纹
                </span>
              ) : (
                <span className={miniPill("neutral", "text-[10px] flex-shrink-0")}>未录声纹</span>
              )}

              {/* 隐藏 file input + 触发按钮（上传 sample → enroll） */}
              <input
                ref={(el) => { fileInputs.current[s.speaker_id] = el }}
                type="file"
                accept="audio/*,.wav"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  handleEnroll(s.speaker_id, f)
                  e.target.value = "" // 允许重复选同一文件
                }}
              />
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground hover:text-primary flex-shrink-0"
                disabled={rowBusy}
                title={s.has_enrollment ? "重新上传 sample 文件" : "上传 sample 文件录声纹"}
                onClick={() => fileInputs.current[s.speaker_id]?.click()}
              >
                {rowBusy ? <Loader2 className="size-3.5 animate-spin" /> : <Upload className="size-3.5" />}
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground hover:text-primary flex-shrink-0"
                disabled={rowBusy}
                title={s.has_enrollment ? "重新录制声纹（覆盖）" : "录制声纹"}
                onClick={() => setRecordingFor(s)}
              >
                <Mic className="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground hover:text-destructive flex-shrink-0 -mr-1"
                disabled={rowBusy}
                onClick={() => handleDelete(s.speaker_id)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          )
        })}
        {!isLoading && (speakers ?? []).length === 0 && (
          <div className="text-xs text-muted-foreground">还没有演员，下面添加。</div>
        )}
      </div>

      {/* 添加演员：可从剧本角色下拉选（填名），也可自由输入；名字即角色名，diarization
          命中声纹后转录段 speaker 直接显示这个名。已注册的角色名置灰提示。 */}
      <div className="flex gap-2">
        <Input
          placeholder="角色名 / 演员名"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleAdd()
          }}
          className="flex-1"
          disabled={busy === "add"}
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="secondary"
              size="icon-sm"
              disabled={busy === "add"}
              title="从剧本角色里选（填入名字，可再改）"
            >
              <ChevronDown className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 max-h-72 overflow-y-auto">
            <DropdownMenuLabel>剧本角色</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {(characters ?? []).length === 0 && (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">
                无剧本角色（先导入并解析剧本）
              </div>
            )}
            {(characters ?? []).map((c) => {
              const taken = (speakers ?? []).some((s) => s.display_name === c)
              return (
                <DropdownMenuItem
                  key={c}
                  onSelect={() => setNewName(c)}
                  className="gap-2"
                >
                  <span className="truncate">{c}</span>
                  {taken && (
                    <span className="ml-auto text-[10px] text-muted-foreground flex-shrink-0">
                      已注册
                    </span>
                  )}
                </DropdownMenuItem>
              )
            })}
          </DropdownMenuContent>
        </DropdownMenu>
        <Button variant="secondary" size="icon-sm" onClick={handleAdd} disabled={busy === "add"}>
          {busy === "add" ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
        </Button>
      </div>

      {msg && (
        <span
          className={
            msg.kind === "error"
              ? "text-xs text-destructive"
              : msg.kind === "done"
                ? "text-xs text-green-600"
                : "text-xs text-muted-foreground"
          }
        >
          {msg.text}
        </span>
      )}
      <span className="text-[10px] text-muted-foreground/70">
        声纹可「上传 sample 文件」或「录制」（两者等价，每人只留一份，重录覆盖）。建议 ≥15s 干净独白。
        声纹用 community-1 抽取，与录制时 diarization 同一套，才能在 take 里匹配上。
      </span>

      <EnrollRecorderDialog
        key={recordingFor?.speaker_id ?? "closed"}
        open={recordingFor !== null}
        onOpenChange={(o) => {
          if (!o) setRecordingFor(null)
        }}
        speaker={recordingFor}
        onEnrolled={invalidate}
      />
    </div>
  )
}
