import { Minus, Plus, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

// Shot / Take 共用的步进器输入：[−] [文本框] [+] ✓。
// −/+ 把当前值解析成整数后 ±1（下限 1）写回；当前值非纯数字（如 "2A"）时 −/+ 自动禁用。
// 中间框接受任意文本。提交（✓ 或回车）由外层 <form onSubmit> 处理。
export default function StepperField({
  value,
  onValueChange,
  placeholder,
}: {
  value: string
  onValueChange: (v: string) => void
  placeholder?: string
}) {
  const trimmed = value.trim()
  const n = Number.parseInt(trimmed, 10)
  const isNumeric = Number.isFinite(n) && String(n) === trimmed
  const step = (delta: number) => {
    if (isNumeric) onValueChange(String(Math.max(1, n + delta)))
  }
  return (
    <div className="flex items-center gap-1.5 px-1">
      <Button type="button" size="icon-sm" variant="ghost" disabled={!isNumeric} onClick={() => step(-1)} className="rounded-full border border-border/60 shrink-0" title="减 1">
        <Minus className="size-3.5" />
      </Button>
      <Input autoFocus value={value} onChange={(e) => onValueChange(e.target.value)} placeholder={placeholder} className="h-8 text-sm text-center" />
      <Button type="button" size="icon-sm" variant="ghost" disabled={!isNumeric} onClick={() => step(1)} className="rounded-full border border-border/60 shrink-0" title="加 1">
        <Plus className="size-3.5" />
      </Button>
      <Button type="submit" size="icon-sm" className="rounded-full shrink-0" title="确认">
        <Check className="size-3.5" />
      </Button>
    </div>
  )
}
