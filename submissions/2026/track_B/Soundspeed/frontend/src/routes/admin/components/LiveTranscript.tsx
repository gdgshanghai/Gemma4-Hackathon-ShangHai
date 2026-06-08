import { useMemo } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { AlertCircle, Loader2 } from "lucide-react"
import { speakerColor } from "@/lib/constants"
import { cn } from "@/lib/utils"
import { formatFileName } from "@/lib/filename-format"
import { useFileNameFormat } from "@/store/filename"
import { useSessionStore, type LiveSeg } from "@/store/session"
import { correctSegmentSpeaker, takeQueryKey, useScenes, useSpeakers, useTake } from "@/lib/api"
import { SpeakerLabel } from "./SpeakerLabel"
import { TakeDivider } from "./TakeDivider"

// take.end 后处理状态条：分离说话人 / 生成摘要(Gemma) / 出错。
function ProcessingBanner() {
  const processing = useSessionStore((s) => s.processing)
  if (!processing) return null

  if (processing.phase === "error") {
    return (
      <div className="flex items-start gap-2 rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertCircle className="size-4 mt-0.5 flex-shrink-0" />
        <span>{processing.detail ?? "后处理出错"}</span>
      </div>
    )
  }

  const label =
    processing.phase === "diarizing"
      ? "正在分离说话人…"
      : "正在生成场记摘要（Gemma）…"
  return (
    <div className="flex items-center gap-2 rounded-xl bg-muted/70 px-3 py-2 text-sm text-muted-foreground">
      <Loader2 className="size-4 flex-shrink-0 animate-spin" />
      <span>{label}</span>
    </div>
  )
}

// 统一渲染行：实时流（store，无 segment_id）与权威数据（useTake，含 segment_id）共用一个形状。
// segmentId 存在 → ch1 人名可点纠正；不存在（实时流）→ 纯文本。
interface Row {
  key: string
  ch: 1 | 2
  speaker: string | null
  text: string
  isPartial: boolean
  segmentId?: number
}

export function LiveTranscript() {
  const segments = useSessionStore((s) => s.segments)
  const currentTakeId = useSessionStore((s) => s.currentTakeId)
  const isRecording = useSessionStore((s) => s.isRecording)
  const currentTake = useSessionStore((s) =>
    currentTakeId != null ? s.takes.get(currentTakeId) : undefined,
  )
  const { data: scenes } = useScenes()
  const fileFormat = useFileNameFormat((s) => s.format)
  const queryClient = useQueryClient()

  // 分隔条按用户配置的文件名格式显示当前条场镜次（统一 formatFileName，与 History/底栏/titlebar 一致）。
  const dividerLabel = useMemo(() => {
    if (!currentTake || currentTake.take_number == null) return ""
    const sceneCode = scenes?.find((s) => s.scene_id === currentTake.scene_id)?.scene_code ?? null
    return formatFileName(
      { scene_code: sceneCode, shot: currentTake.shot, take_number: currentTake.take_number },
      fileFormat,
    )
  }, [currentTake, scenes, fileFormat])

  // take 结束后拉权威 segment（带 segment_id + speaker），与 History 同源 → 编辑天然同步。
  // 录制中不拉：用 store 实时流低延迟显示，避免和实时帧打架。
  const showFinal = !isRecording && currentTakeId != null
  const { data: takeDetail } = useTake(currentTakeId ?? -1, showFinal)
  const finalSegs = showFinal ? takeDetail?.segments : undefined

  // 候选演员（同 History）：全部注册演员 ∪ 本 take 现有标签 ∪ 未知。
  const { data: registeredSpeakers } = useSpeakers()
  const candidates = useMemo<(string | null)[]>(() => {
    const names = new Set<string>()
    for (const s of registeredSpeakers ?? []) names.add(s.display_name)
    for (const seg of finalSegs ?? []) if (seg.speaker) names.add(seg.speaker)
    return [...names, null]
  }, [registeredSpeakers, finalSegs])

  async function handleCorrect(
    segmentId: number,
    currentSpeaker: string | null,
    next: string | null,
  ) {
    if (next === currentSpeaker || currentTakeId == null) return
    try {
      await correctSegmentSpeaker(currentTakeId, segmentId, next)
      // 失效该 take query：本框 + History 同读 useTake，一起刷新（单一数据源同步）。
      await queryClient.invalidateQueries({ queryKey: takeQueryKey(currentTakeId) })
    } catch (err) {
      console.error("纠正说话人失败", err)
    }
  }

  // 渲染源：take 结束且权威数据已到 → 用它（可编辑）；否则用 store 实时流（纯文本，兜底防闪空）。
  const useFinal = finalSegs != null && finalSegs.length > 0
  const rows: Row[] = useFinal
    ? [...finalSegs]
        .sort((a, b) => a.start_frame - b.start_frame)
        .map((s) => ({
          key: `seg-${s.segment_id}`,
          ch: s.ch as 1 | 2,
          speaker: s.speaker,
          text: s.text,
          isPartial: false,
          segmentId: s.segment_id,
        }))
    : [
        ...segments.ch1.map((s: LiveSeg, i: number) => ({ ...s, ch: 1 as const, idx: i })),
        ...segments.ch2.map((s: LiveSeg, i: number) => ({ ...s, ch: 2 as const, idx: i })),
      ]
        .sort((a, b) => a.start_frame - b.start_frame)
        .map((s) => ({
          key: `${s.ch}-${s.idx}`,
          ch: s.ch,
          speaker: s.speaker,
          text: s.text,
          isPartial: s.isPartial,
        }))

  const hasContent = rows.length > 0

  return (
    <div className="px-4 py-4 space-y-4">
      {currentTake?.take_number != null && <TakeDivider label={dividerLabel} />}

      {hasContent ? (
        <div className="space-y-1.5 leading-relaxed">
          {rows.map((r) => (
            <p
              key={r.key}
              className={cn(
                "text-sm",
                r.isPartial ? "text-muted-foreground italic" : "text-foreground",
              )}
            >
              {r.segmentId != null && r.ch === 1 ? (
                // 权威 ch1 段：人名可点，从全部注册演员里改（落库 + 同步 History）。
                <SpeakerLabel
                  key={String(r.speaker)}
                  speaker={r.speaker}
                  options={candidates}
                  onChange={(next) => handleCorrect(r.segmentId!, r.speaker, next)}
                />
              ) : (
                r.speaker && (
                  <span className={cn("font-medium mr-1", speakerColor(r.speaker))}>
                    {r.speaker}：
                  </span>
                )
              )}{" "}
              {r.text}
              {r.isPartial && (
                <span className="inline-block w-0.5 h-4 bg-muted-foreground ml-0.5 align-middle animate-pulse" />
              )}
            </p>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground/60 text-center py-8">
          {isRecording ? "等待转录…" : "未在录制"}
        </p>
      )}

      {/* take.end 后处理状态条：放在对白下方，跟随文本末尾显示 */}
      <ProcessingBanner />
    </div>
  )
}
