import { useEffect, useState } from "react"
import { Loader2, ChevronDown, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { feedBlock } from "@/lib/styles"
import { useSessionStore } from "@/store/session"
import { postNote, postVoiceNote } from "@/lib/api"
import { runQuery, runNote } from "@/lib/feed-actions"
import type { PendingNote, FeedReceipt, QaItem } from "@/types/api"

// note.failed reason → 场记可读文案（4.I），沿用旧 NoteList 映射。
const FAIL_REASON_TEXT: Record<string, string> = {
  take_not_found: "找不到对应素材",
  parse_error: "理解失败",
  timeout: "处理超时",
  asr_unclear: "没听清",
  model_unavailable: "模型未就绪",
  upload_failed: "提交失败",
}

// note 回执：done 态，挂载即排 3s 自走（query 项 P3 lingers，不在此）。轻视觉，无框纯文字。
// 「↩ 其实是提问」= query→note 误判兜底（最危险：问题被当日志记了），琥珀暖色动词，点击改走 query。
function ReceiptRow({
  r,
  onDismiss,
  onReclassify,
}: {
  r: FeedReceipt
  onDismiss: (id: string) => void
  onReclassify: (rawText: string) => void
}) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(r.client_id), 3000)
    return () => clearTimeout(t)
  }, [r.client_id, onDismiss])
  return (
    <div className={cn(feedBlock.note, "flex items-center gap-2 px-2.5 py-1.5 text-xs")}>
      <span className="text-muted-foreground">已记录</span>
      <span className="font-medium text-foreground">{r.category}</span>
      <span className="flex-1 min-w-0 truncate text-foreground/70">{r.content}</span>
      <button
        onClick={() => onReclassify(r.rawText)}
        className="text-primary font-medium hover:underline flex-shrink-0"
      >
        其实是提问
      </button>
    </div>
  )
}

// pending note：处理中（转圈 + 当条内容）/ 失败（alert 块 + 当条内容 + 原因 + 重试 + 放弃）。
// 始终显示当条内容（原文优先，语音无原文则占位 content），让多条并存时能区分是哪条。
function PendingRow({
  pn,
  onRetry,
  onDismiss,
}: {
  pn: PendingNote
  onRetry: (pn: PendingNote) => void
  onDismiss: (clientId: string) => void
}) {
  const failed = pn.failedReason != null
  const label = pn.rawText || pn.content
  if (!failed) {
    return (
      <div className="flex items-center gap-2 px-2.5 py-1.5 text-sm text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin opacity-60 flex-shrink-0" />
        <span className="flex-1 min-w-0 truncate text-foreground/80">{label}</span>
        <span className="text-xs text-muted-foreground/60 flex-shrink-0">处理中</span>
      </div>
    )
  }
  // 失败 = alert 块（更重主题色底 + ring），与处理中轻行、答案淡主题色块拉开档差。
  // 重试（同 client_id 重投）+ 放弃（× 移除这条，不再处理）。
  return (
    <div className={cn(feedBlock.alert, "flex items-center gap-2 px-2.5 py-1.5 text-sm")}>
      <span className="flex-1 min-w-0 truncate text-foreground">{label}</span>
      <span className="text-xs text-muted-foreground flex-shrink-0">
        {FAIL_REASON_TEXT[pn.failedReason!] ?? "处理失败"}
      </span>
      <button onClick={() => onRetry(pn)} className="text-primary font-medium hover:underline flex-shrink-0">
        重试
      </button>
      <button
        onClick={() => onDismiss(pn.client_id)}
        className="flex-shrink-0 text-muted-foreground/70 hover:text-foreground"
        title="放弃这条"
      >
        <X className="size-3.5" />
      </button>
    </div>
  )
}

// QP 问答行（B2 单行）：查询中转圈 / 失败琥珀实心块 / 完成单行；长答案截断点开就地展开。
// query 项不像 note 回执 3s 自走——lingers 供场记看完，由档案/收起手动清。
// 「✎ 记为备注」= note→query 误判兜底（较轻），淡链接，把这条问题改当 note 记。
function QaRow({
  q,
  onAsNote,
  onDismiss,
}: {
  q: QaItem
  onAsNote: (question: string) => void
  onDismiss: (clientId: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  if (q.status === "processing") {
    return (
      <div className="flex items-center gap-2 px-2.5 py-1.5 text-sm text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin opacity-60 flex-shrink-0" />
        <span className="flex-1 min-w-0 truncate text-foreground/80">{q.question}</span>
        <span className="text-xs text-muted-foreground/60 flex-shrink-0">查询中</span>
      </div>
    )
  }
  // 警告/失败 = alert 块（更重主题色底 + ring）。显示当条问题 + 失败原因以区分 + 放弃。
  if (q.status === "failed") {
    return (
      <div className={cn(feedBlock.alert, "flex items-center gap-2 px-2.5 py-1.5 text-sm")}>
        <span className="flex-1 min-w-0 truncate text-foreground">{q.question}</span>
        <span className="text-xs text-muted-foreground flex-shrink-0">{q.failedReason ?? "查询失败"}</span>
        <button
          onClick={() => onDismiss(q.client_id)}
          className="flex-shrink-0 text-muted-foreground/70 hover:text-foreground"
          title="放弃这条"
        >
          <X className="size-3.5" />
        </button>
      </div>
    )
  }
  const text = q.answer ?? ""
  const isLong = text.includes("\n") || text.length > 36
  const head = isLong ? text.split("\n")[0].slice(0, 36) + "…" : text
  // 正常答案 = answer 块（淡主题色底，标识 LLM 反馈）；note 回执用中性灰底以色相区分。
  // 外层 div 容纳两个平级按钮（展开 / 记为备注）——button 不能嵌 button。
  return (
    <div className={cn(feedBlock.answer, "flex items-start gap-2 px-2.5 py-1.5 text-sm")}>
      <button
        onClick={() => isLong && setExpanded((e) => !e)}
        className="flex-1 min-w-0 flex items-start gap-2 text-left text-foreground"
      >
        <span className="flex-1 min-w-0">
          {expanded ? (
            <span className="leading-relaxed whitespace-pre-line">{text}</span>
          ) : (
            <span className="truncate block">{head}</span>
          )}
        </span>
        {isLong && (
          <ChevronDown
            className={
              "size-4 flex-shrink-0 mt-0.5 text-muted-foreground/60 transition-transform " +
              (expanded ? "rotate-180" : "")
            }
          />
        )}
      </button>
      <button
        onClick={() => onAsNote(q.question)}
        className="text-xs text-muted-foreground hover:text-foreground flex-shrink-0 mt-0.5"
        title="把这条改当备注记"
      >
        记为备注
      </button>
    </div>
  )
}

// 就地反馈队列：替代旧常驻 NoteList。短暂、就地、自清理。
// note（pending + 回执）+ query（QaRow）按 ts 混排，最新贴底。
export default function InlineFeedbackQueue() {
  const pendingNotes = useSessionStore((s) => s.pendingNotes)
  const feedReceipts = useSessionStore((s) => s.feedReceipts)
  const qaItems = useSessionStore((s) => s.qaItems)
  const dismissReceipt = useSessionStore((s) => s.dismissReceipt)
  const dismissQaInline = useSessionStore((s) => s.dismissQaInline)
  const dismissPending = useSessionStore((s) => s.dismissPending)
  const retryPending = useSessionStore((s) => s.retryPending)
  const noteFailed = useSessionStore((s) => s.noteFailed)

  // 失败重试：乐观打回处理中，用同 client_id 重投（语音重传 WAV，文本重投原文）。
  const handleRetry = (pn: PendingNote) => {
    retryPending(pn.client_id)
    const resubmit = pn.voiceBlob
      ? postVoiceNote(pn.voiceBlob, pn.client_id, pn.ts)
      : postNote(pn.rawText, undefined, pn.client_id)
    resubmit.catch(() => noteFailed({ reason: "upload_failed", ts: pn.ts, client_id: pn.client_id }))
  }

  // query→note 误判：拿原文重发 query，撤掉这条 note 回执（改判后它不再是 note）。
  const handleReclassify = (rawText: string, receiptId: string) => {
    runQuery(rawText)
    dismissReceipt(receiptId)
  }

  // note→query 误判：把问题当 note 记，撤掉这条 query（postNote 失败才提示，乐观立即收起）。
  const handleAsNote = (question: string, qaId: string) => {
    runNote(question).catch((e) => alert(e instanceof Error ? e.message : "记为备注失败"))
    dismissQaInline(qaId)
  }

  // 合并按 ts，最新贴底（输入框侧）。
  const rows = [
    ...pendingNotes.map((pn) => ({
      ts: pn.ts,
      node: (
        <PendingRow
          key={`p-${pn.client_id}`}
          pn={pn}
          onRetry={handleRetry}
          onDismiss={dismissPending}
        />
      ),
    })),
    ...feedReceipts.map((r) => ({
      ts: r.ts,
      node: (
        <ReceiptRow
          key={`r-${r.client_id}`}
          r={r}
          onDismiss={dismissReceipt}
          onReclassify={(rawText) => handleReclassify(rawText, r.client_id)}
        />
      ),
    })),
    ...qaItems
      .filter((q) => !q.inlineDismissed)
      .map((q) => ({
        ts: q.ts,
        node: (
          <QaRow
            key={`q-${q.client_id}`}
            q={q}
            onAsNote={(question) => handleAsNote(question, q.client_id)}
            onDismiss={dismissQaInline}
          />
        ),
      })),
  ].sort((a, b) => a.ts - b.ts)

  if (rows.length === 0) return null
  return (
    // pb-[32px]：浮层底边下沉 26px 藏进输入框 pill（AdminHome bottom-[calc(100%-26px)]），
    // 留足底距让最后一行浮在 pill 之上不被挡（沿用旧 NoteList 的补偿思路）。
    <div className="pb-[32px] space-y-1 max-h-[40vh] overflow-y-auto pointer-events-auto rounded-t-2xl bg-background/95 backdrop-blur-sm px-3 pt-2 shadow-[0_-12px_28px_-20px_rgba(0,0,0,0.18)]">
      {rows.length > 1 && (
        <div className="px-1 pb-0.5 text-[10px] text-muted-foreground/50">{rows.length} 条</div>
      )}
      {rows.map((r) => r.node)}
    </div>
  )
}
