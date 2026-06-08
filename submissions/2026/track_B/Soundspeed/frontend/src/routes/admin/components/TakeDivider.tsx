import { Separator } from "@/components/ui/separator"

// Live transcript 顶部的 take 分隔条。label 为完整场镜次（如 "Scene_1 · Shot 1 · Take 10"）。
// time 可选（实时录制无时间戳）。
export function TakeDivider({ label, time }: { label: string; time?: string }) {
  return (
    <div className="flex items-center gap-3">
      <Separator className="flex-1" />
      <span className="text-[10px] font-mono tracking-wider text-muted-foreground">
        {label}{time ? ` · ${time}` : ""}
      </span>
      <Separator className="flex-1" />
    </div>
  )
}
