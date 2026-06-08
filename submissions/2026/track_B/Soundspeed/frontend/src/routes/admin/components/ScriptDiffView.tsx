import type { JuxtaLine, LineMatch, ScriptDiff } from "@/types/api"

const DIFF_LABEL: Record<LineMatch["diff_type"], string> = {
  match: "匹配",
  missing: "漏词",
  substitution: "改词",
  insertion: "加词",
}

const DIFF_ORDER: LineMatch["diff_type"][] = [
  "match",
  "substitution",
  "missing",
  "insertion",
]

// 并置文档（缺口③）：剧本台词 ‖ 实际说的，逐行对照。这是 take 的最终输出文档主体。
// 以剧本行为骨架；漏说 → 实际侧「（未说）」；insertion（line_no<0）→ 剧本侧「（剧本无）」。
// 只显示「对白行」（有角色，或确实有人说了话/insertion）的左右对比；非对白（动作/场景描述：
// 无角色且无人对白）不在此呈现——剧本页已完整展示剧本，History 里无需重复表演/描述文本。
// 注：line_no 仍按原始剧本编号（含非对白），故对白行的 L 号可能有跳号；将 L 收敛为仅对白
// 编号属 line_no 语义变更（跨人契约边界），留待与境熙拉通后单独做。
function JuxtapositionView({ rows }: { rows: JuxtaLine[] }) {
  // 只保留对白行：有角色（剧本台词）或确实有人说了话（含 insertion：剧本无、实际有）。
  const dialogue = rows.filter((row) => row.character != null || row.spoken_text != null)
  if (dialogue.length === 0) return null
  return (
    <div className="space-y-1.5">
      <div className="grid grid-cols-2 gap-3 text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wide">
        <span>剧本台词</span>
        <span>实际说的</span>
      </div>
      {dialogue.map((row, i) => {
        const isInsertion = row.line_no < 0
        const lineLabel = isInsertion ? "—" : `L${row.line_no}`
        const missing = row.spoken_text == null
        return (
          <div
            key={i}
            className="grid grid-cols-2 gap-3 text-sm border-t border-border/30 pt-1.5"
          >
            {/* 剧本侧：行号 + 角色 + 台词 */}
            <div className="flex gap-1.5 min-w-0">
              <span className="text-[10px] font-mono text-muted-foreground/50 mt-1 w-7 flex-shrink-0 text-right">
                {lineLabel}
              </span>
              <div className="min-w-0">
                {row.character && (
                  <span className="text-xs text-primary/80 mr-1.5">{row.character}</span>
                )}
                {isInsertion ? (
                  <span className="text-muted-foreground/40 italic">（剧本无）</span>
                ) : (
                  <span className="text-foreground">{row.script_text}</span>
                )}
              </div>
            </div>
            {/* 实际侧：说话人 + 实际台词 */}
            <div className="min-w-0">
              {row.speaker && (
                <span className="text-xs text-muted-foreground mr-1.5">{row.speaker}</span>
              )}
              {missing ? (
                <span className="text-muted-foreground/40 italic">（未说）</span>
              ) : (
                <span className="text-foreground">{row.spoken_text}</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// L2 script_diff 显示。主体是 juxtaposition 两列对照（剧本 ‖ 实际）；summary 置顶一句话概览，
// corrected_segments（原→改 ASR 纠错）放下方。老库/无剧本无 juxtaposition 时回退到旧的
// line_matches 计数视图。降级：无 diff →「L2 未完成 / 无剧本」；全空 →「无偏差」。
// hideJuxtaposition：History 详情用 MergedTranscriptView（实录可改）渲染并置时，这里只出
// summary + corrected（避免重复渲染只读的 juxtaposition）。
export function ScriptDiffView({
  diff,
  hideJuxtaposition = false,
}: {
  diff: ScriptDiff | null
  hideJuxtaposition?: boolean
}) {
  if (!diff) {
    return <p className="text-sm text-muted-foreground/60">L2 未完成 / 无剧本</p>
  }

  // ?? [] 兜底：v3 老库 / 降级路径可能缺字段，.filter / .map 才不会抛、白屏。
  const corrected = diff.corrected_segments ?? []
  const matches = diff.line_matches ?? []
  const juxta = diff.juxtaposition ?? []
  const detailMatches = matches.filter((m) => m.detail)

  // summary、corrected、matches、juxta 全空才算无偏差。
  if (
    !diff.script_diff_summary &&
    corrected.length === 0 &&
    matches.length === 0 &&
    juxta.length === 0
  ) {
    return <p className="text-sm text-muted-foreground/60">无偏差</p>
  }

  // line_matches 按 diff_type 计数（仅 juxta 缺省时的回退视图用）。
  const counts = matches.reduce<Record<string, number>>((acc, m) => {
    acc[m.diff_type] = (acc[m.diff_type] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-3">
      {/* script_diff_summary —— 模型 prose，一句话概览置顶 */}
      {diff.script_diff_summary && (
        <p className="text-sm text-foreground leading-relaxed">
          {diff.script_diff_summary}
        </p>
      )}

      {/* 主体：并置文档（剧本 ‖ 实际）。有 juxtaposition 就以它为准；hideJuxtaposition 时跳过
          （History 详情改用 MergedTranscriptView 渲染可编辑实录侧）。 */}
      {!hideJuxtaposition && juxta.length > 0 && <JuxtapositionView rows={juxta} />}

      {/* a. corrected_segments —— 辅助信息：原 → 改 */}
      {corrected.length > 0 && (
        <div className="space-y-2">
          {corrected.map((seg) => (
            <div key={seg.idx} className="space-y-0.5">
              <p className="flex gap-1.5 text-sm">
                <span className="text-[10px] font-mono text-muted-foreground/70 mt-0.5 flex-shrink-0">
                  原
                </span>
                <span className="text-muted-foreground line-through decoration-muted-foreground/40">
                  {seg.original}
                </span>
              </p>
              <p className="flex gap-1.5 text-sm">
                <span className="text-[10px] font-mono text-primary mt-0.5 flex-shrink-0">
                  改
                </span>
                <span className="text-foreground">{seg.corrected}</span>
              </p>
            </div>
          ))}
        </div>
      )}

      {/* b. line_matches —— 一行计数摘要（仅老库/无 juxtaposition 时回退展示） */}
      {juxta.length === 0 && matches.length > 0 && (
        <p className="text-xs text-muted-foreground">
          剧本比对 {matches.length} 行
          {DIFF_ORDER.map((d) => ` · ${DIFF_LABEL[d]} ${counts[d] ?? 0}`).join("")}
        </p>
      )}

      {/* 若有非空 detail 的 line_match，补充展示（同样仅 juxtaposition 缺省时） */}
      {juxta.length === 0 && detailMatches.length > 0 && (
        <div className="space-y-1">
          {detailMatches.map((lm, i) => (
            <div key={i} className="flex items-baseline gap-2 text-xs">
              <span className="font-mono text-muted-foreground w-10 flex-shrink-0">
                {lm.line_no >= 0 ? `L${lm.line_no}` : "—"}
              </span>
              <span className="text-muted-foreground flex-shrink-0">
                {DIFF_LABEL[lm.diff_type]}
              </span>
              <span className="text-foreground">{lm.detail}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
