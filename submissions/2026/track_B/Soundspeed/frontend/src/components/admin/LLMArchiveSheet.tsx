import { useEffect, type ReactNode } from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import { feedBlock } from "@/lib/styles"
import { Button } from "@/components/ui/button"
import { useSessionStore } from "@/store/session"
import { ScriptDiffView } from "@/routes/admin/components/ScriptDiffView"
import GemmaIcon from "@/components/icons/GemmaIcon"

// 时间线一项：QP 问答 = answer 块（淡主题色底）；L2 推送 = note 块（中性灰底）。
// 与就地层同一套 feedBlock 语言，靠背景色相区分 LLM 答案 / L2 记录，无装饰图标。
function FeedItem({
  source,
  time,
  children,
}: {
  source: "QP" | "L2"
  time: string
  children: ReactNode
}) {
  const isQP = source === "QP"
  return (
    <div className={cn(isQP ? feedBlock.answer : feedBlock.note, "px-3 py-2.5")}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className={cn("text-xs font-medium", isQP ? "text-primary" : "text-muted-foreground")}>
          {isQP ? "问答" : "L2 推送"}
        </span>
        <span className="text-[10px] font-mono text-muted-foreground/60">{time}</span>
      </div>
      {children}
    </div>
  )
}

const fmtTime = (ts: number) =>
  ts > 0 ? new Date(ts * 1000).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : ""

// 留存层：QP 问答 + L2 推送的全历史时间线。
// 呈现为从底栏输入框上沿向上展开的浮层（不是贴屏底的 Sheet）——底边对齐 dock 顶（输入框上方），
// 向上 max-h-[70vh]，下方输入框/控制栏保持可见可用。需挂在 dock 的 relative 容器内（absolute 相对它定位）。
export function LLMArchiveSheet({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const takesMap = useSessionStore((s) => s.takes)
  const qaItems = useSessionStore((s) => s.qaItems)

  // Esc 收起（radix Sheet 自带，自定义浮层手动补）。
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onOpenChange])

  // 关闭态（其常态）渲染恒为 null：提前 return，省掉下方纯派生计算在每次 store 更新时白跑。
  // 必须落在最后一个 hook（上面的 useEffect）之后，确保不违反 rules-of-hooks。
  if (!open) return null

  // L2：带 script_diff 的 take（按开拍时序）。start_ts/created_at 为 0 = 实时 L2 刚到、getTakes
  // 尚未回填真实时间 → 视为最新（排最底），refetch 后落到真实位置。
  const l2 = Array.from(takesMap.values())
    .filter((t) => t.script_diff != null)
    .map((t) => ({ kind: "L2" as const, sortTs: t.start_ts || t.created_at || Number.MAX_SAFE_INTEGER, t }))
  // QP：已落定的问答（processing/failed 不入档案）。
  const qa = qaItems
    .filter((q) => q.status === "done")
    .map((q) => ({ kind: "QP" as const, sortTs: q.ts, q }))
  const items = [...l2, ...qa].sort((a, b) => a.sortTs - b.sortTs)

  return (
    <>
      {/* 遮罩：盖输入框上方的业务区（从 dock 顶向上铺满），点击收起。不盖底栏。 */}
      <div
        className="absolute inset-x-0 bottom-full h-screen z-30 bg-foreground/10"
        onClick={() => onOpenChange(false)}
      />
      {/* 浮层面板：左右铺满 viewport，底边贴 dock 顶（输入框上沿）无缝相连，向上展开。
          只上圆角 + 顶/左右边框（无底边框），向上阴影——底边与底栏直接相接、不浮起。 */}
      <div className="pointer-events-none absolute inset-x-0 bottom-full z-40">
        <div className="pointer-events-auto flex max-h-[70vh] flex-col overflow-hidden rounded-t-2xl border-t border-x bg-background shadow-[0_-12px_28px_-20px_rgba(0,0,0,0.25)]">
          <header className="flex flex-shrink-0 items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 text-base font-semibold text-foreground">
                <GemmaIcon className="size-6 text-[#4285F4]" />
                Gemma 4
                <span className="font-normal text-muted-foreground">· 反馈</span>
              </span>
              <span className="text-xs text-muted-foreground">QP 问答 · L2 推送 · 全历史</span>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              className="rounded-full"
              onClick={() => onOpenChange(false)}
              title="收起"
            >
              <X className="size-4" />
            </Button>
          </header>
          <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3">
            {items.length === 0 && (
              <p className="text-xs text-muted-foreground text-center pt-4">还没有问答或 L2 推送</p>
            )}
            {items.map((it) =>
              it.kind === "L2" ? (
                <FeedItem key={`l2-${it.t.take_id}`} source="L2" time={`Take ${it.t.take_number}`}>
                  <ScriptDiffView diff={it.t.script_diff} />
                </FeedItem>
              ) : (
                <FeedItem key={`qa-${it.q.client_id}`} source="QP" time={fmtTime(it.q.ts)}>
                  <div className="text-sm font-medium text-foreground mb-1">{it.q.question}</div>
                  <div className="text-sm leading-relaxed text-foreground/80 whitespace-pre-line">
                    {it.q.answer}
                  </div>
                </FeedItem>
              ),
            )}
          </div>
        </div>
      </div>
    </>
  )
}
