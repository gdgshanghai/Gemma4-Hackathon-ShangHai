import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useSpeakers } from "@/lib/api"
import { STAGE_POP_STYLE } from "@/lib/styles"
import { ChevronDown, Users } from "lucide-react"

interface Props {
  value: number[]
  onChange: (ids: number[]) => void
  disabled?: boolean
}

// 本 take「在场演员」多选：从已注册演员里勾选，按 Rec 时随 startTake 传 speaker_ids。
// diarization 回填只在这些演员里匹配；未勾选/无演员 → 全匿名说话人N。
// 未录声纹的演员不能用于匹配，禁选。
export default function TakeSpeakerSelect({ value, onChange, disabled }: Props) {
  const { data: speakers } = useSpeakers()
  const list = speakers ?? []

  const toggle = (id: number, checked: boolean) => {
    onChange(checked ? [...value, id] : value.filter((x) => x !== id))
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="default"
          disabled={disabled}
          title="本 take 在场演员（diarization 身份识别匹配范围）"
          className="flex-none gap-1.5 h-9 px-3 rounded-full bg-muted/60 border border-border/60 active:scale-95 transition-transform"
        >
          <Users className="size-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">
            演员{value.length > 0 ? ` ${value.length}` : ""}
          </span>
          <ChevronDown className="size-3 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56" style={STAGE_POP_STYLE}>
        <DropdownMenuLabel>在场演员</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {list.length === 0 && (
          <div className="px-2 py-1.5 text-xs text-muted-foreground">
            未注册演员（去设置 → 演员 添加）
          </div>
        )}
        {list.map((s) => (
          <DropdownMenuCheckboxItem
            key={s.speaker_id}
            checked={value.includes(s.speaker_id)}
            onCheckedChange={(c) => toggle(s.speaker_id, Boolean(c))}
            onSelect={(e) => e.preventDefault()} // 多选：勾选后保持菜单打开
          >
            {s.display_name}
            {!s.has_enrollment && (
              <span className="ml-1 text-[10px] text-muted-foreground">· 未录声纹</span>
            )}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
