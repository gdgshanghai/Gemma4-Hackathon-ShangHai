import { useEffect, useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function StatusChip({
  label,
  tone,
  detail,
  className,
  onClick,
  icon,
  children,
}: {
  label: string
  tone: "ok" | "warn" | "err"
  detail?: string
  className?: string
  onClick?: () => void
  icon?: ReactNode
  children?: ReactNode
}) {
  const dotColor =
    tone === "ok" ? "bg-green-500" : tone === "warn" ? "bg-primary" : "bg-destructive"
  const cls = cn(
    "flex items-center gap-1.5 h-9 px-4 rounded-full bg-muted/70 min-w-0 sm:min-w-[5.5rem]",
    onClick && "cursor-pointer active:scale-95 transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    className
  )
  const content = (
    <>
      {/* warn 态（如 LLM 处理中）点呼吸，与 LLM 历史入口左点的处理态脉冲一致。 */}
      <span
        className={cn(
          "size-1.5 rounded-full flex-shrink-0",
          dotColor,
          tone === "warn" && "animate-pulse",
        )}
      />
      {icon && <span className="flex items-center flex-shrink-0">{icon}</span>}
      <span className="hidden sm:inline text-xs font-medium text-foreground flex-shrink-0">{label}</span>
      {detail && (
        <span className="text-[10px] font-mono text-muted-foreground truncate min-w-0">{detail}</span>
      )}
      {children}
    </>
  )

  if (onClick) {
    return (
      <Button variant="ghost" className={cls} onClick={onClick} aria-label={`${label} ${detail ?? ""}`.trim()}>
        {content}
      </Button>
    )
  }
  return <div className={cls}>{content}</div>
}

// 真实电平表：由 [0,1] 的 level 驱动，亮起的 bar 数 = level×count（升序高度）。
// 替代 LevelMeter 的假随机动画，用于 header 实时麦克风监看。
export function LiveLevelMeter({
  level,
  count = 7,
  color = "bg-green-500",
  className,
}: {
  level: number
  count?: number
  color?: string
  className?: string
}) {
  // 线性 RMS 在人声区间（~0.05–0.3）亮格太少、不明显 → 转 dB（对数感知）刻度放大小信号：
  // 20·log10(level) 落在 [FLOOR_DB, 0] dB，归一化到 [0,1]。静音（level→0）落到 floor 以下 → 0 格。
  const FLOOR_DB = -60
  const safe = Math.min(1, Math.max(0, level))
  const db = 20 * Math.log10(Math.max(safe, 1e-5))
  const norm = Math.max(0, (db - FLOOR_DB) / -FLOOR_DB)
  const lit = Math.round(Math.min(1, norm) * count)
  return (
    <div className={cn("flex items-center gap-[1.5px] h-4 flex-shrink-0", className)}>
      {Array.from({ length: count }, (_, i) => (
        <span
          key={i}
          className={cn(
            "w-[2px] rounded-full transition-all duration-75",
            i < lit ? color : "bg-muted-foreground/20"
          )}
          style={{ height: `${3 + (i / Math.max(1, count - 1)) * 11}px` }}
        />
      ))}
    </div>
  )
}

export function LevelMeter({
  count = 5,
  color = "bg-green-500",
  className,
}: {
  count?: number
  color?: string
  className?: string
}) {
  const [heights, setHeights] = useState<number[]>(() =>
    Array.from({ length: count }, () => Math.random())
  )

  useEffect(() => {
    const id = setInterval(() => {
      setHeights(Array.from({ length: count }, () => Math.random()))
    }, 80)
    return () => clearInterval(id)
  }, [count])

  return (
    <div className={cn("flex items-center gap-[1.5px] h-4 flex-shrink-0", className)}>
      {heights.map((h, i) => (
        <span
          key={i}
          className={cn("w-[2px] rounded-full transition-all duration-75", color)}
          style={{ height: `${3 + h * 10}px` }}
        />
      ))}
    </div>
  )
}
