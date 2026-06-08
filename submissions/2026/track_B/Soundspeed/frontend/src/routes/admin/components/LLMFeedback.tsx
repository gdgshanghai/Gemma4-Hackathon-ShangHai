import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { mutedCard } from "@/lib/styles"
import type { TakeDTO } from "@/types/api"
import { useSessionStore } from "@/store/session"
import { ScriptDiffView } from "./ScriptDiffView"

export function LLMFeedback() {
  const takesMap = useSessionStore((s) => s.takes)

  // 最新一条有 script_diff 的 take：按 take_id 降序。take_id 单调（autoincrement，最高 = 最新），
  // 且 WS take.changed 与 getTakes 两条路径都带它；updated_at 不在 WS Pick 上（WS-only take 会是
  // undefined→排到所有 seeded take 之下，反而选错），故不用它。
  const latest: TakeDTO | undefined = Array.from(takesMap.values())
    .filter((t) => t.script_diff != null)
    .sort((a, b) => b.take_id - a.take_id)[0]

  if (!latest || !latest.script_diff) {
    return (
      <div className="py-4">
        <p className="text-xs text-muted-foreground text-center pt-2">
          take 结束后由 L2 推送
        </p>
      </div>
    )
  }

  const diff = latest.script_diff

  return (
    <div className="py-4 space-y-3">
      <Card className={mutedCard}>
        <CardContent className="p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="font-mono uppercase">
              diff
            </Badge>
            <span className="font-mono text-[10px] text-muted-foreground">
              Scene {latest.scene_id} · Take {latest.take_number}
            </span>
          </div>
          <ScriptDiffView diff={diff} />
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground text-center pt-2">
        每次 take 结束后由 L2 推送
      </p>
    </div>
  )
}
