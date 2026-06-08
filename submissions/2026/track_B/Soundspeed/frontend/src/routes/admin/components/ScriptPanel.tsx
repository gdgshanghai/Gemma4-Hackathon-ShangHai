import { useState, useRef, useEffect, useMemo } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { miniPill, mutedCard } from "@/lib/styles"
import { cn } from "@/lib/utils"
import {
  ApiError,
  pickActiveScene,
  scenesQueryKey,
  scriptUploadsQueryKey,
  useParseUpload,
  useSceneScript,
  useScenes,
  useScriptUploads,
  useUploadScript,
} from "@/lib/api"
import type { SceneDTO } from "@/types/api"
import SceneUpdateDialog from "@/components/admin/SceneUpdateDialog"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Camera,
  RotateCcw,
  Check,
  Loader2,
  X,
} from "lucide-react"

// ---- OCR 本地 mock（决策点 2：不接后端，仍走本地预览）----

type OcrLine =
  | { type: "action"; text: string }
  | { type: "dialogue"; speaker: string; text: string }

interface OcrScene {
  location: string
  time: string
  setting: string
  lines: OcrLine[]
}

const MOCK_OCR: OcrScene = {
  location: "室内",
  time: "夜",
  setting: "拍摄现场",
  lines: [
    { type: "action", text: "【OCR 识别结果，请核对】" },
    { type: "dialogue", speaker: "角色A", text: "这是从照片识别出的台词。" },
    { type: "dialogue", speaker: "角色B", text: "需要人工校对后确认。" },
  ],
}

// 归一化台词行（真库行与 OCR 行共用一种渲染样式）。speaker=null → 动作描述。
interface NormLine {
  speaker: string | null
  text: string
}

// ---- 组件 ----

export function ScriptPanel() {
  const { data: scenes } = useScenes()

  // viewIndex=null 表示「跟随当前场」（活跃场次随后端变化时自动跟）。
  const [viewIndex, setViewIndex] = useState<number | null>(null)
  const [jumpInput, setJumpInput] = useState(false)
  const [jumpValue, setJumpValue] = useState("")
  const jumpRef = useRef<HTMLInputElement>(null)
  const [ocrScene, setOcrScene] = useState<OcrScene | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [updateOpen, setUpdateOpen] = useState(false) // 选中场更新对话框
  const [confirmUpdateAll, setConfirmUpdateAll] = useState(false) // 整本重传「更新全本」确认

  // 剧本上传/解析（两段式 + 异步进度，全部从服务器状态派生 → 切 tab 不丢）。
  const upload = useUploadScript()
  const parse = useParseUpload()
  const queryClient = useQueryClient()
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [dismissedId, setDismissedId] = useState<number | null>(null)

  // 常驻轮询上传记录；最新一条驱动 UI（上传/解析中/完成）。组件重新挂载会重新拉，
  // 故切走再回来能自动恢复进度——后台解析本就不受前端影响。
  const { data: uploads } = useScriptUploads()
  const latestUpload = uploads?.[0]

  const isOcr = ocrScene !== null

  // 剧本面板只翻「有剧本的场」：跳过 dev 种子 Scene_1 这类无剧本空场，不显示空占位。
  // has_script 由后端 list_scenes 带（EXISTS 子查询）。
  const scriptScenes = useMemo<SceneDTO[]>(
    () => (scenes ?? []).filter((s) => s.has_script),
    [scenes],
  )

  // 当前场 = is_active 那条（若它有剧本则定位到它，否则默认第一场有剧本的）。
  const active = pickActiveScene(scenes)
  const activeIdx = active
    ? scriptScenes.findIndex((s) => s.scene_id === active.scene_id)
    : -1
  const currentIndex = activeIdx >= 0 ? activeIdx : 0
  // 有效查看索引：null → 当前场；并夹在有效范围内（场数变化时防越界）。
  const rawView = viewIndex ?? currentIndex
  const view = Math.min(Math.max(0, rawView), Math.max(0, scriptScenes.length - 1))
  const viewScene: SceneDTO | undefined = scriptScenes[view]
  const hasScriptScenes = scriptScenes.length > 0

  // OCR 模式不拉剧本（OCR 自带行）；真库模式按 scene_id 拉，hook 内部用 enabled 门控。
  const scriptSceneId = isOcr ? null : viewScene?.scene_id ?? null
  const {
    data: script,
    isLoading: scriptLoading,
    isError: scriptError,
  } = useSceneScript(scriptSceneId)

  // ---- 导航（都在 scriptScenes 范围内，避免异步 stale）----
  const goPrev = () => {
    setViewIndex(Math.max(0, view - 1))
  }
  const goNext = () => {
    setViewIndex(Math.min(scriptScenes.length - 1, view + 1))
  }
  const goCurrent = () => {
    setOcrScene(null)
    setViewIndex(null) // 回到「跟随当前场」
  }

  const startJump = () => {
    setJumpValue(viewScene?.scene_code ?? "")
    setJumpInput(true)
  }

  const commitJump = () => {
    const target = jumpValue.trim()
    if (!target) {
      setJumpInput(false)
      return
    }
    const idx = scriptScenes.findIndex((s) => s.scene_code === target)
    if (idx >= 0) {
      setViewIndex(idx)
      setOcrScene(null)
    }
    setJumpInput(false)
  }

  // ---- 阶段 1：上传（只入库，不碰 Gemma，秒回）----
  const triggerUpload = () => fileInputRef.current?.click()

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = "" // 允许重复选同一文件
    if (!file) return
    setUploadError(null)
    setOcrScene(null)
    try {
      await upload.mutateAsync({ file })
      setDismissedId(null)
      queryClient.invalidateQueries({ queryKey: scriptUploadsQueryKey() })
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "上传失败，请重试")
    }
  }

  // ---- 阶段 2：解析分场（启动后台任务；进度由 latestUpload 轮询派生）----
  const doParse = async (onConflict: "skip" | "version") => {
    if (!latestUpload) return
    setUploadError(null)
    setDismissedId(null)
    try {
      await parse.mutateAsync({
        uploadId: latestUpload.upload_id,
        target: "multi_scene",
        onConflict,
      })
      queryClient.invalidateQueries({ queryKey: scriptUploadsQueryKey() })
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "解析启动失败，请重试")
    }
  }

  const handleParse = () => {
    if (!latestUpload) return
    // 已有剧本 → 再次解析视为「更新全本」，先确认；首次导入直接解析（全新场）。
    if (scriptScenes.length > 0) {
      setConfirmUpdateAll(true)
      return
    }
    void doParse("skip")
  }

  // 解析进行中/刚完成 → 刷新场次/剧本，让已入库的场「逐个冒出来」（updated_at 每场变一次）。
  const latestStatus = latestUpload?.status
  const latestUpdatedAt = latestUpload?.updated_at
  useEffect(() => {
    if (latestStatus === "parsing" || latestStatus === "parsed") {
      queryClient.invalidateQueries({ queryKey: scenesQueryKey() })
      queryClient.invalidateQueries({ queryKey: ["scene-script"] })
    }
  }, [latestStatus, latestUpdatedAt, queryClient])

  // ---- 渲染台词（归一化行）----
  const renderLines = (lines: NormLine[]) => (
    <div className="space-y-3">
      {lines.map((line, i) =>
        line.speaker == null ? (
          <p key={i} className="text-sm leading-relaxed text-foreground">
            {line.text}
          </p>
        ) : (
          <p key={i} className="text-sm leading-relaxed">
            <span className="text-primary font-medium">{line.speaker}：</span>
            {line.text}
          </p>
        )
      )}
    </div>
  )

  // 真库剧本 → 归一化行（后端已按 line_no 升序）。
  const scriptLines: NormLine[] =
    script?.lines.map((l) => ({ speaker: l.character, text: l.text })) ?? []
  // OCR mock → 归一化行。
  const ocrLines: NormLine[] =
    ocrScene?.lines.map((l) =>
      l.type === "dialogue" ? { speaker: l.speaker, text: l.text } : { speaker: null, text: l.text }
    ) ?? []

  const headerCode = viewScene?.scene_code

  return (
    <div className="py-4 space-y-3 h-full flex flex-col">
      {/* ========== 工具栏 ========== */}
      <div className="flex items-center justify-end gap-2">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            title="上传剧本文件（txt / md / docx / pdf）"
            onClick={triggerUpload}
            disabled={upload.isPending}
          >
            {upload.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <FileText className="size-4" />
            )}
          </Button>
        </div>
      </div>

      <SceneUpdateDialog
        open={updateOpen}
        onOpenChange={setUpdateOpen}
        sceneId={viewScene?.scene_id ?? null}
        sceneCode={viewScene?.scene_code ?? null}
      />

      {/* 整本重传「更新全本」确认（已有剧本时） */}
      <Dialog open={confirmUpdateAll} onOpenChange={setConfirmUpdateAll}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>更新全本？</DialogTitle>
            <DialogDescription>
              已解析过剧本。继续将按场号逐场对照：命中的场各追加一个新版本（旧版本保留、已录
              take 的对照不受影响），新场号则新增。内容无变化的场会自动跳过。
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setConfirmUpdateAll(false)}>
              取消
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setConfirmUpdateAll(false)
                void doParse("version")
              }}
            >
              更新全本
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* 隐藏的文件输入 */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.md,.markdown,.docx,.pdf"
        className="hidden"
        onChange={handleFileUpload}
      />

      {/* 阶段 1：上传中（秒回）*/}
      {upload.isPending && (
        <div className="flex items-center gap-2 rounded-lg bg-muted/70 px-3 py-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin flex-shrink-0" />
          <span>正在上传剧本…</span>
        </div>
      )}

      {/* 已保存：显示文件信息 + 独立「解析分场」按钮 */}
      {latestUpload?.status === "uploaded" && (
        <div className="rounded-lg bg-muted/70 px-3 py-2 text-xs space-y-2">
          <span className="text-foreground">
            已保存：<span className="font-medium">{latestUpload.filename}</span>
            <span className="text-muted-foreground">（{latestUpload.char_count} 字）</span>
          </span>
          <Button
            size="sm"
            className="h-7 w-full text-xs gap-1.5"
            onClick={handleParse}
            disabled={parse.isPending}
          >
            {parse.isPending ? (
              <>
                <Loader2 className="size-3.5 animate-spin" />
                启动中…
              </>
            ) : (
              "解析分场"
            )}
          </Button>
        </div>
      )}

      {/* 解析进度（后台逐场，轮询 detail：解析中 i/N 场…）切 tab 回来自动恢复 */}
      {latestUpload?.status === "parsing" && (
        <div className="flex items-center gap-2 rounded-lg bg-muted/70 px-3 py-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin flex-shrink-0" />
          <span>{latestUpload.detail ?? "正在解析…"}</span>
        </div>
      )}

      {uploadError && (
        <div className="flex items-start gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <X className="size-3.5 mt-0.5 flex-shrink-0" />
          <span className="flex-1">{uploadError}</span>
          <button onClick={() => setUploadError(null)} className="opacity-60 hover:opacity-100">
            <X className="size-3.5" />
          </button>
        </div>
      )}

      {/* 解析完成结果（parsed 成功 / error 失败）；dismiss 后不再显示同一条 */}
      {latestUpload &&
        (latestUpload.status === "parsed" || latestUpload.status === "error") &&
        dismissedId !== latestUpload.upload_id && (
          <div
            className={cn(
              "flex items-start gap-2 rounded-lg px-3 py-2 text-xs",
              latestUpload.status === "parsed"
                ? "bg-primary/10 text-foreground"
                : "bg-destructive/10 text-destructive",
            )}
          >
            <span className="flex-1">
              {latestUpload.status === "parsed" ? "✅ " : "✗ "}
              {latestUpload.detail ??
                (latestUpload.status === "parsed" ? "解析完成" : "解析失败")}
            </span>
            {latestUpload.status === "error" && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs gap-1 flex-shrink-0"
                onClick={handleParse}
                disabled={parse.isPending}
              >
                {parse.isPending ? <Loader2 className="size-3 animate-spin" /> : <RotateCcw className="size-3" />}
                重新解析
              </Button>
            )}
            <button
              onClick={() => setDismissedId(latestUpload.upload_id)}
              className="opacity-60 hover:opacity-100"
            >
              <X className="size-3.5" />
            </button>
          </div>
        )}

      {/* ========== 场次导航（仅当有「带剧本的场」时显示）========== */}
      {!isOcr && hasScriptScenes && (
        <div className="flex items-center justify-between">
          <Button variant="ghost" size="icon-sm" onClick={goPrev} disabled={view === 0}>
            <ChevronLeft className="size-4" />
          </Button>
          <div className="flex items-center gap-1.5 sm:gap-2">
            {jumpInput ? (
              <div className="flex items-center gap-1.5">
                <Input
                  ref={jumpRef}
                  value={jumpValue}
                  onChange={(e) => setJumpValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitJump()
                    if (e.key === "Escape") setJumpInput(false)
                  }}
                  className="h-6 w-20 text-center text-xs font-mono px-1 py-0"
                  autoFocus
                />
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="size-6 rounded-full bg-primary/10 hover:bg-primary/20 text-primary p-0"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={commitJump}
                >
                  <Check className="size-3.5" />
                </Button>
              </div>
            ) : (
              <span
                className="text-xs font-mono text-muted-foreground cursor-pointer select-none"
                onDoubleClick={startJump}
                title="双击输入场次号跳转"
              >
                SCENE {headerCode ?? "—"}
              </span>
            )}
            {view !== currentIndex && (
              <Button
                variant="ghost"
                size="icon-sm"
                className="size-6 rounded-full sm:h-6 sm:w-auto sm:px-2 sm:text-xs sm:gap-1"
                onClick={goCurrent}
                title="返回当前场"
              >
                <RotateCcw className="size-3" />
                <span className="hidden sm:inline">返回当前场</span>
              </Button>
            )}
            {view === currentIndex && (
              <span className={miniPill("primary", "text-[10px]")}>
                当前场
              </span>
            )}
            {/* 更新本场：跟场号切换同处一行（场级操作，关联更紧） */}
            {viewScene && (
              <Button
                variant="ghost"
                size="icon-sm"
                className="size-6 rounded-full"
                title={`更新本场（SCENE ${viewScene.scene_code ?? "—"}）`}
                onClick={() => setUpdateOpen(true)}
              >
                <Camera className="size-3.5" />
              </Button>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={goNext}
            disabled={view >= scriptScenes.length - 1}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}

      {/* OCR 场次头 */}
      {isOcr && (
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono text-muted-foreground">OCR 识别</span>
          <Button variant="ghost" size="sm" className="h-6 text-xs gap-1" onClick={goCurrent}>
            <RotateCcw className="size-3" />
            返回剧本
          </Button>
        </div>
      )}

      {/* ========== 剧本内容 ========== */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <Card className={mutedCard}>
          <CardContent className="p-4 space-y-4">
            {isOcr && ocrScene ? (
              <>
                {/* OCR 场次头 */}
                <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
                  <span className={miniPill("neutral")}>OCR</span>
                  <span>{ocrScene.location}</span>
                  <span>·</span>
                  <span>{ocrScene.time}</span>
                  <span>·</span>
                  <span>{ocrScene.setting}</span>
                </div>
                {renderLines(ocrLines)}
              </>
            ) : !hasScriptScenes ? (
              <p className="text-sm text-muted-foreground/70 text-center py-8">
                {scenes ? "还没有剧本。点右上角上传剧本文件并「解析分场」。" : "加载中…"}
              </p>
            ) : (
              <>
                {/* 真库场次头 */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex flex-wrap items-center gap-1.5 text-xs font-mono text-muted-foreground">
                    <span className={miniPill("neutral")}>
                      SCENE {headerCode ?? "—"}
                    </span>
                    {[viewScene?.int_ext, viewScene?.time_of_day, viewScene?.location]
                      .map((v) => v?.trim())
                      .filter((v): v is string => !!v)
                      .map((v) => (
                        <span key={v} className={miniPill("primary")}>{v}</span>
                      ))}
                  </div>
                  {viewScene?.description && (
                    <p className="text-xs text-muted-foreground">{viewScene.description}</p>
                  )}
                </div>

                {/* 台词 / 加载 / 空 / 错误态 */}
                {!viewScene ? (
                  <p className="text-sm text-muted-foreground">
                    {scenes ? "无场次" : "加载中…"}
                  </p>
                ) : scriptLoading ? (
                  <p className="text-sm text-muted-foreground">加载中…</p>
                ) : scriptError ? (
                  <p className="text-sm text-destructive">剧本加载失败，请重试。</p>
                ) : scriptLines.length === 0 ? (
                  <p className="text-sm text-muted-foreground">该场暂无剧本</p>
                ) : (
                  renderLines(scriptLines)
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
