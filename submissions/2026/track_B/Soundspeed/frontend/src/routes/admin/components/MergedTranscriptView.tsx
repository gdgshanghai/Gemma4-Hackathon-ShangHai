import type { JuxtaLine, TranscriptSegmentDTO } from "@/types/api"
import { SpokenSegment } from "./SpokenSegment"

interface Props {
  rows: JuxtaLine[]
  ch1Segs: TranscriptSegmentDTO[]
  candidates: (string | null)[]
  onCorrect: (seg: TranscriptSegmentDTO, next: string | null) => void
  failedSegId: number | null
}

// 剧本侧（右列）：行号 + 角色 + 台词。无剧本行（实录独有 / insertion）显示「（剧本无）」。
function ScriptCell({ line }: { line: JuxtaLine | null }) {
  return (
    <div className="flex gap-1.5 min-w-0">
      <span className="text-[10px] font-mono text-muted-foreground/50 mt-1 w-7 flex-shrink-0 text-right">
        {line && line.line_no >= 0 ? `L${line.line_no}` : "—"}
      </span>
      {line && line.line_no >= 0 ? (
        <div className="min-w-0">
          {line.character && (
            <span className="text-xs text-primary/80 mr-1.5">{line.character}</span>
          )}
          <span className="text-foreground">{line.script_text}</span>
        </div>
      ) : (
        <span className="text-muted-foreground/40 italic">（剧本无）</span>
      )}
    </div>
  )
}

// 合并后的一行：matched=实录段↔剧本行对上；spoken=实录独有（剧本无）；missing=漏说（剧本有、没说）。
// matched/spoken 都用 segs 数组，左列渲染统一；missing 无实录段。
type MergedRow =
  | { kind: "matched"; line: JuxtaLine; segs: TranscriptSegmentDTO[] }
  | { kind: "spoken"; segs: TranscriptSegmentDTO[] }
  | { kind: "missing"; line: JuxtaLine }

// 序列对齐（merge-diff）：以实录时间顺序为主线，剧本去匹配；两边对不上的就地穿插。
// - 主线 = ch1Segs（start_frame 升序，真实录制顺序）。
// - segById→剧本行：segment_id 命中某行 segment_ids → 该段属于这条剧本行（matched）；否则实录独有（spoken）。
// - 漏说行（剧本有、没说：line_no≥0、对白、无 segment_ids）按 line_no 在「下一个匹配行之前」flush 进去，
//   落到它在序列里该出现的位置（不堆末尾）。同 gap 内：实录独有按时间先出，漏说行紧贴下一个匹配点。
function buildMergedRows(rows: JuxtaLine[], ch1Segs: TranscriptSegmentDTO[]): MergedRow[] {
  // segment_id → 它所属的剧本行（取首个命中行）。
  const rowBySeg = new Map<number, JuxtaLine>()
  for (const r of rows) {
    for (const id of r.segment_ids ?? []) {
      if (!rowBySeg.has(id)) rowBySeg.set(id, r)
    }
  }

  // 漏说的对白行（剧本有、没人说：对白行 + 无对齐段），按 line_no 升序供穿插。
  // 无 segment_ids ⟺ 未说（skeleton 行 spoken_text 也必为 None），故无需再判 spoken_text。
  const missing = rows
    .filter((r) => r.line_no >= 0 && r.character != null && (r.segment_ids?.length ?? 0) === 0)
    .sort((a, b) => a.line_no - b.line_no)

  const out: MergedRow[] = []
  const consumed = new Set<number>()
  let mi = 0 // missing 指针

  for (const seg of ch1Segs) {
    if (consumed.has(seg.segment_id)) continue
    const row = rowBySeg.get(seg.segment_id)
    const isMatched = row != null && row.line_no >= 0 && row.character != null
    if (isMatched) {
      // 先 flush 所有 line_no 更小、还没出的漏说行（它们排在这个匹配点之前）。
      while (mi < missing.length && missing[mi].line_no < row.line_no) {
        out.push({ kind: "missing", line: missing[mi] })
        mi++
      }
      // 该剧本行对到的全部实录段聚成一行（保持各段按 ch1Segs 的时间序）。
      const ids = new Set(row.segment_ids ?? [])
      const segs = ch1Segs.filter((s) => ids.has(s.segment_id))
      for (const s of segs) consumed.add(s.segment_id)
      out.push({ kind: "matched", line: row, segs })
    } else {
      // 实录独有（insertion / 孤儿 / 对到非对白行）：右侧「剧本无」，落在时间线本位。
      out.push({ kind: "spoken", segs: [seg] })
    }
  }
  // 剩下的漏说行（在最后一个匹配点之后才出现的）补在末尾。
  while (mi < missing.length) {
    out.push({ kind: "missing", line: missing[mi] })
    mi++
  }
  return out
}

// 合并并置视图：左「实录(实际说的)」‖ 右「台词(剧本)」，以实录时间顺序为主线、剧本穿插匹配。
// 实录侧用真实转录段（按 segment_ids 重接）——说话人纠正即时同步，不读 L2 烤死的 speaker。
// 非对白（动作/场景描述）不显示——剧本页已完整展示剧本（任务二决策）。
// 老库行无 segment_ids → 整体回退到「剧本骨架 + 烤死 spoken_text/speaker」的只读视图。
export function MergedTranscriptView({
  rows,
  ch1Segs,
  candidates,
  onCorrect,
  failedSegId,
}: Props) {
  const hasSegmentIds = rows.some((r) => (r.segment_ids?.length ?? 0) > 0)

  const header = (
    <div className="grid grid-cols-2 gap-3 text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wide">
      <span>实录（实际说的）</span>
      <span>台词（剧本）</span>
    </div>
  )

  // 老库回退：无 segment_ids 无法重建实录顺序，按剧本骨架 + 烤死值（只读）逐行并置。
  if (!hasSegmentIds) {
    const dialogue = rows.filter((r) => r.character != null || r.spoken_text != null)
    return (
      <div className="space-y-1.5">
        {header}
        {dialogue.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-2 gap-3 text-sm border-t border-border/30 pt-1.5"
          >
            <div className="min-w-0">
              {row.spoken_text == null ? (
                <span className="text-muted-foreground/40 italic">（未说）</span>
              ) : (
                <span>
                  {row.speaker && (
                    <span className="text-xs text-muted-foreground mr-1.5">{row.speaker}</span>
                  )}
                  <span className="text-foreground">{row.spoken_text}</span>
                </span>
              )}
            </div>
            <ScriptCell line={row.line_no >= 0 ? row : null} />
          </div>
        ))}
      </div>
    )
  }

  const merged = buildMergedRows(rows, ch1Segs)

  return (
    <div className="space-y-1.5">
      {header}
      {merged.map((row, i) => (
        <div
          key={i}
          className="grid grid-cols-2 gap-3 text-sm border-t border-border/30 pt-1.5"
        >
          {/* 左：实录（matched/spoken 渲染各自的段；missing 标「未说」） */}
          <div className="min-w-0 space-y-0.5">
            {row.kind === "missing" ? (
              <span className="text-muted-foreground/40 italic">（未说）</span>
            ) : (
              row.segs.map((seg) => (
                <SpokenSegment
                  key={seg.segment_id}
                  seg={seg}
                  candidates={candidates}
                  onCorrect={onCorrect}
                  failedSegId={failedSegId}
                />
              ))
            )}
          </div>
          {/* 右：台词（剧本）—— matched/missing 显示剧本行；spoken（实录独有）显示「剧本无」 */}
          <ScriptCell line={row.kind === "spoken" ? null : row.line} />
        </div>
      ))}
    </div>
  )
}
