import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface CreateSceneDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  // 提交 scene_code（后端 POST /scenes，建/复用都 200，由父组件随即 activate）。
  onCreate: (sceneCode: string) => void
  pending?: boolean
}

// 新建场次：只收 scene_code（必填）。其余 slugline 元数据走 dev 面板的剧本注入，这里不暴露。
export default function CreateSceneDialog({
  open,
  onOpenChange,
  onCreate,
  pending = false,
}: CreateSceneDialogProps) {
  const [sceneCode, setSceneCode] = useState("")

  const canSubmit = sceneCode.trim().length > 0 && !pending

  const submit = () => {
    if (!canSubmit) return
    onCreate(sceneCode.trim())
  }

  // 关闭时清空输入（避免在 effect 里 setState 触发的级联渲染告警）。
  const handleOpenChange = (next: boolean) => {
    if (!next) setSceneCode("")
    onOpenChange(next)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent showCloseButton={false} className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>新建场次</DialogTitle>
          <DialogDescription>
            输入场次编号。已存在的编号会复用，不会重复创建。
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
          className="grid gap-2"
        >
          <span className="text-xs text-muted-foreground">场次编号</span>
          <Input
            autoFocus
            value={sceneCode}
            onChange={(e) => setSceneCode(e.target.value)}
            placeholder="例：3 / 12A / EXT-街道"
          />
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={pending}>
            取消
          </Button>
          <Button onClick={submit} disabled={!canSubmit}>
            {pending ? "创建中…" : "创建并切换"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
