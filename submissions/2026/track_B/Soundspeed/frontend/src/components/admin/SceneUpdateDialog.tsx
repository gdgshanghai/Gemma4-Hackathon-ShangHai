import { useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  ApiError,
  charactersQueryKey,
  diffSceneScript,
  parseScenesFromImages,
  parseSingleScene,
  scenesQueryKey,
  sceneScriptQueryKey,
  updateSceneScript,
} from "@/lib/api"
import type { ParseSingleResult, ScriptDiffResult, ScriptDiffRow, ScriptLineInput } from "@/types/api"
import { cn } from "@/lib/utils"
import { Image as ImageIcon, Loader2 } from "lucide-react"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  sceneId: number | null
  sceneCode: string | null
  onUpdated?: () => void
}

type Phase = "edit" | "parsing" | "preview" | "committing"

// 增量对照各状态的标签 + 角标样式（单一来源：行内角标与顶部摘要都读它）。
// cls 缺省（equal）→ 行内不显角标，仅用 label 进摘要。
const DIFF_BADGE: Record<ScriptDiffRow["status"], { label: string; cls?: string }> = {
  equal: { label: "未变" },
  changed: { label: "改", cls: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
  added: { label: "新增", cls: "bg-primary/15 text-primary" },
  kept: { label: "保留", cls: "bg-muted text-muted-foreground" },
}

// 一行剧本投影：「角色：台词」；舞台指示（无角色）或被替换/保留的旧文本走 muted。
function LineText({
  line,
  muted,
  strike,
}: {
  line: ScriptLineInput
  muted?: boolean
  strike?: boolean
}) {
  return (
    <span className={cn("text-sm leading-relaxed", strike && "line-through", muted && "text-muted-foreground")}>
      {line.character ? (
        <span className={cn("font-medium", muted ? "" : "text-primary")}>{line.character}：</span>
      ) : null}
      {line.text}
    </span>
  )
}

// 选中场更新：粘贴这一场的剧本文本 → 原生 FC 解析预览 → 确认 → 给该场追加新版本。
// 只动选中的那一场（versioned，不删旧版）。照片/OCR 走同一确认流（后续接 OCR 时复用）。
export default function SceneUpdateDialog({
  open,
  onOpenChange,
  sceneId,
  sceneCode,
  onUpdated,
}: Props) {
  const qc = useQueryClient()
  const [text, setText] = useState("")
  const [phase, setPhase] = useState<Phase>("edit")
  const [preview, setPreview] = useState<ParseSingleResult | null>(null)
  // 增量对照：解析后与该场最新版逐行对齐，确认时提交 diff.merged（非整段覆盖）。
  const [diff, setDiff] = useState<ScriptDiffResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [skippedMsg, setSkippedMsg] = useState<string | null>(null)
  // 照片入口：选了图就优先走视觉 OCR（忽略文本框）；空则走文本。
  const [images, setImages] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const reset = () => {
    setText("")
    setPhase("edit")
    setPreview(null)
    setDiff(null)
    setError(null)
    setSkippedMsg(null)
    setImages([])
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  const handleParse = async () => {
    const useImages = images.length > 0
    const src = text.trim()
    if (!useImages && !src) return
    setError(null)
    setPhase("parsing")
    try {
      const result = useImages
        ? await parseScenesFromImages(images, sceneCode)
        : await parseSingleScene(src)
      setPreview(result)
      // 增量对照：与该场最新版逐行对齐（旧有新无→保留旧，防 OCR 漏）。无 sceneId 则按全新处理。
      const d: ScriptDiffResult =
        sceneId != null
          ? await diffSceneScript(sceneId, result.lines)
          : { has_old: false, rows: [], merged: result.lines, merged_raw_text: result.raw_text }
      setDiff(d)
      setPhase("preview")
    } catch (err) {
      const fallback = useImages ? "照片识别失败，请重试" : "解析失败，请重试"
      setError(err instanceof ApiError ? err.message : fallback)
      setPhase("edit")
    }
  }

  const handleCommit = async () => {
    if (sceneId == null || !preview || !diff) return
    setError(null)
    setPhase("committing")
    try {
      // 落库行用增量合并结果 diff.merged（非整段覆盖：未变留旧、改动取新、新增加入、旧有新无保留旧）；
      // raw_text 用 merged 重建的 merged_raw_text（保证 raw_text↔lines 一致，不混入被 kept 掉的旧文本来源）。
      const res = await updateSceneScript(sceneId, diff.merged_raw_text, diff.merged)
      qc.invalidateQueries({ queryKey: sceneScriptQueryKey(sceneId) })
      qc.invalidateQueries({ queryKey: scenesQueryKey() })
      qc.invalidateQueries({ queryKey: charactersQueryKey() })
      if (res.skipped) {
        // 内容与最新版相同：不当成功收尾，提示用户
        setSkippedMsg("内容与当前版本相同，未新建版本。")
        setPhase("preview")
        return
      }
      onUpdated?.()
      reset()
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "更新失败，请重试")
      setPhase("preview")
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset()
        onOpenChange(o)
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>更新本场（SCENE {sceneCode ?? "—"}）</DialogTitle>
          <DialogDescription>
            粘贴本场剧本文本，或上传照片（视觉识别）。已有剧本时按差异增量合并（未变留旧、改动取新、新增加入、旧有新无默认保留），核对后确认；只更新这一场，追加为新版本（旧版本保留）。
          </DialogDescription>
        </DialogHeader>

        {phase === "edit" || phase === "parsing" ? (
          <div className="space-y-3">
            {/* 照片入口：选图后优先走视觉 OCR（忽略文本框）。 */}
            <div className="space-y-1.5">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                disabled={phase === "parsing"}
                onChange={(e) => {
                  setImages(Array.from(e.target.files ?? []))
                  setError(null)
                }}
              />
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={phase === "parsing"}
                >
                  <ImageIcon className="size-3.5" /> 选择照片
                </Button>
                {images.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    已选 {images.length} 张
                    <button
                      type="button"
                      className="ml-2 text-muted-foreground/70 hover:text-foreground"
                      onClick={() => {
                        setImages([])
                        if (fileInputRef.current) fileInputRef.current.value = ""
                      }}
                    >
                      清除
                    </button>
                  </span>
                )}
              </div>
              {images.length > 0 && (
                <p className="text-[11px] text-muted-foreground/70">
                  将用视觉识别这些照片更新本场（忽略下方文本框）。
                </p>
              )}
            </div>

            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="粘贴本场剧本文本（可含场头行，如「场3 内 咖啡馆 日」）…"
              className="min-h-40 text-sm"
              disabled={phase === "parsing" || images.length > 0}
            />
            {error && <p className="text-xs text-destructive">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
                取消
              </Button>
              <Button
                size="sm"
                onClick={handleParse}
                disabled={(!text.trim() && images.length === 0) || phase === "parsing"}
              >
                {phase === "parsing" ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />{" "}
                    {images.length > 0 ? "识别中…" : "解析中…"}
                  </>
                ) : images.length > 0 ? (
                  "识别照片"
                ) : (
                  "解析预览"
                )}
              </Button>
            </div>
          </div>
        ) : (
          // preview / committing
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-1.5 text-xs font-mono text-muted-foreground">
              <span>SCENE {preview?.scene_code ?? sceneCode ?? "—"}</span>
              {[preview?.int_ext, preview?.time_of_day, preview?.location]
                .filter((v): v is string => !!v)
                .map((v) => (
                  <span key={v} className="text-primary">
                    · {v}
                  </span>
                ))}
            </div>
            {/* 增量对照摘要（有旧版时）：改 / 新增 / 保留 / 未变 各几行 */}
            {diff?.has_old && (
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
                {(["changed", "added", "kept", "equal"] as const).map((s) => {
                  const n = diff.rows.filter((r) => r.status === s).length
                  if (!n) return null
                  return (
                    <span key={s}>
                      {DIFF_BADGE[s].label} {n}
                    </span>
                  )
                })}
              </div>
            )}
            <div className="max-h-64 overflow-y-auto space-y-2 rounded-lg bg-muted/50 p-3">
              {(diff?.merged ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">未解析出任何台词行。</p>
              ) : diff?.has_old ? (
                // 有旧版：逐行色标对照（未变/改/新增/保留旧）
                diff.rows.map((r, i) => {
                  const badge = DIFF_BADGE[r.status]
                  return (
                    <div key={i} className="flex items-start gap-2">
                      {badge.cls ? (
                        <span
                          className={cn(
                            "mt-0.5 shrink-0 rounded px-1 text-[10px] leading-4",
                            badge.cls,
                          )}
                        >
                          {badge.label}
                        </span>
                      ) : (
                        <span className="mt-0.5 w-6 shrink-0" />
                      )}
                      <div className="min-w-0 flex-1">
                        {r.status === "kept"
                          ? r.old && <LineText line={r.old} muted />
                          : (
                            <>
                              {r.new && <LineText line={r.new} />}
                              {r.status === "changed" && r.old && (
                                <div className={cn(r.new && "mt-0.5")}>
                                  <LineText line={r.old} muted strike />
                                </div>
                              )}
                            </>
                          )}
                      </div>
                    </div>
                  )
                })
              ) : (
                // 无旧版：直接列新解析行
                diff?.merged.map((l, i) => (
                  <p key={i}>
                    <LineText line={l} muted={!l.character} />
                  </p>
                ))
              )}
            </div>
            {skippedMsg && <p className="text-xs text-muted-foreground">{skippedMsg}</p>}
            {error && <p className="text-xs text-destructive">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setPhase("edit")
                  setSkippedMsg(null)
                }}
                disabled={phase === "committing"}
              >
                重新编辑
              </Button>
              <Button
                size="sm"
                onClick={handleCommit}
                disabled={phase === "committing" || (diff?.merged ?? []).length === 0}
              >
                {phase === "committing" ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" /> 更新中…
                  </>
                ) : (
                  "确认更新本场"
                )}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
