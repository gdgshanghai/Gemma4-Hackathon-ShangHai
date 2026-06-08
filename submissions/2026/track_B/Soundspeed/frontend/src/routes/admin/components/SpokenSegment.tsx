import type { TranscriptSegmentDTO } from "@/types/api"
import { SpeakerLabel } from "./SpeakerLabel"

// 一条实录段：说话人可点纠正 + 文本。纠正即时落库+刷新，说话人天然同步到读它的视图。
// key 绑 speaker（由 caller 传 key）：强制 SpeakerLabel 重挂载，绕过 Radix asChild trigger
// 复用 DOM、重渲染却不重绘文本的问题（数据/重渲染本身正常，见排查记录）。
// History 详情的合并并置视图（MergedTranscriptView）与无剧本回退分支共用此组件。
export function SpokenSegment({
  seg,
  candidates,
  onCorrect,
  failedSegId,
}: {
  seg: TranscriptSegmentDTO
  candidates: (string | null)[]
  onCorrect: (seg: TranscriptSegmentDTO, next: string | null) => void
  failedSegId: number | null
}) {
  return (
    <div>
      <p className="text-sm">
        <SpeakerLabel
          key={String(seg.speaker)}
          speaker={seg.speaker}
          options={candidates}
          onChange={(next) => onCorrect(seg, next)}
        />{" "}
        {seg.text}
      </p>
      {failedSegId === seg.segment_id && (
        <p className="text-xs text-destructive">说话人纠正失败，请重试</p>
      )}
    </div>
  )
}
