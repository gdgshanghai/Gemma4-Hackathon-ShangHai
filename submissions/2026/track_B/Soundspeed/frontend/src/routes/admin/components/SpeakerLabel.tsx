import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { speakerColor, speakerDot } from "@/lib/constants"
import { STAGE_POP_STYLE } from "@/lib/styles"
import { cn } from "@/lib/utils"

const UNKNOWN_LABEL = "未知"

// 可切换说话人 label。speaker=null 显示「未知」；options 含 null 代表「未知」候选。
// disabled（ch2）→ 渲染为不可点纯文本。配色统一走 speakerColor/speakerDot 哈希。
export function SpeakerLabel({
  speaker,
  options,
  onChange,
  disabled = false,
}: {
  speaker: string | null
  options: (string | null)[]
  onChange: (speaker: string | null) => void
  disabled?: boolean
}) {
  const label = speaker ?? UNKNOWN_LABEL
  const textColor = speakerColor(speaker)
  const dotColor = speakerDot(speaker)

  if (disabled) {
    return (
      <span className={cn("inline-flex items-center gap-1 font-medium select-none", textColor)}>
        <span className={cn("size-1.5 rounded-full flex-shrink-0", dotColor)} />
        {label}：
      </span>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <span
          className={cn(
            "inline-flex items-center gap-1 font-medium cursor-pointer select-none rounded-md px-1 -ml-1 transition-colors hover:bg-muted",
            textColor,
          )}
        >
          <span className={cn("size-1.5 rounded-full flex-shrink-0", dotColor)} />
          {label}：
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" style={STAGE_POP_STYLE}>
        <DropdownMenuLabel>切换说话人</DropdownMenuLabel>
        {options.map((opt) => (
          <DropdownMenuItem
            key={opt ?? "__unknown__"}
            className={cn(opt === speaker && "bg-accent")}
            onClick={() => onChange(opt)}
          >
            <span className={cn("size-1.5 rounded-full mr-2", speakerDot(opt))} />
            {opt ?? UNKNOWN_LABEL}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
