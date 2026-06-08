import { useEffect, useRef, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { enrollStart, enrollStop, enrollCancel } from "@/lib/api"
import type { SpeakerDTO } from "@/types/api"
import { Loader2, Mic, Square } from "lucide-react"

type Phase = "idle" | "starting" | "recording" | "saving" | "done" | "error"

// 录声纹时照着念的样例对白（内容中性，约 15–25 秒，音素覆盖均衡）。
const SAMPLE_SCRIPT =
  "大家好，我现在正在录制我的声音样本。这段话没有特别的含义，" +
  "只是为了让系统记住我说话的声音和语调。我会用平时聊天的语气，" +
  "自然地把这几句话念完。今天天气不错，适合出门走走，" +
  "也适合安静地待在房间里看书。好，就到这里，谢谢。"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  speaker: SpeakerDTO | null
  onEnrolled: () => void
}

// 录制声纹：后端现场麦录音（与 Capture 同设备）→ stop 提声纹存库（覆盖该演员旧声纹）。
// 浏览器麦只用于 take note，不在此使用。
export default function EnrollRecorderDialog({ open, onOpenChange, speaker, onEnrolled }: Props) {
  const [phase, setPhase] = useState<Phase>("idle")
  const [elapsed, setElapsed] = useState(0)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const recordingRef = useRef(false) // 卸载时判断是否需要 cancel 释放后端设备
  const mountedRef = useRef(true)
  const speakerRef = useRef<SpeakerDTO | null>(speaker)
  speakerRef.current = speaker

  const clearTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  // 卸载时若仍在录音，cancel 释放后端设备。父组件用 key 在每次打开时重挂，状态从 idle 复位。
  // setup 里显式置 true：StrictMode（dev）会 mount→unmount→remount，cleanup 先把 ref 置 false，
  // 若 remount 不重置，ref 会永久 false，导致 startRecording 误判组件已卸载而卡在 starting。
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      clearTimer()
      if (recordingRef.current && speakerRef.current) {
        void enrollCancel(speakerRef.current.speaker_id)
      }
    }
  }, [])

  const startRecording = async () => {
    if (!speaker) return
    setErrorMsg(null)
    setPhase("starting") // 同步切走 idle：按钮立即消失，防重复点击
    try {
      await enrollStart(speaker.speaker_id)
      recordingRef.current = true
      if (!mountedRef.current) {
        // 启动期间弹窗已关：后端已开录，显式 cancel 释放设备
        void enrollCancel(speaker.speaker_id)
        return
      }
      setPhase("recording")
      setElapsed(0)
      timerRef.current = setInterval(() => setElapsed((e) => e + 0.2), 200)
    } catch (e) {
      if (!mountedRef.current) return
      setPhase("error")
      setErrorMsg(e instanceof Error ? e.message : "无法启动现场麦录音")
    }
  }

  const stopRecording = async () => {
    clearTimer()
    if (!speaker) return
    recordingRef.current = false
    setPhase("saving")
    try {
      await enrollStop(speaker.speaker_id)
      setPhase("done")
      onEnrolled()
    } catch (e) {
      setPhase("error")
      setErrorMsg(e instanceof Error ? e.message : "声纹录入失败")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>录制声纹{speaker ? ` · ${speaker.display_name}` : ""}</DialogTitle>
          <DialogDescription>
            对着<b>现场麦克风</b>念下面这段话，自然语气即可（建议 15–30 秒，<b>请勿超过 30 秒</b>）。
            停止后自动保存，覆盖该演员旧声纹。
          </DialogDescription>
        </DialogHeader>

        {(phase === "idle" || phase === "recording") && (
          <div className="rounded-xl bg-muted/60 px-4 py-3 text-sm leading-relaxed text-foreground max-h-40 overflow-y-auto">
            {SAMPLE_SCRIPT}
          </div>
        )}

        <div className="flex flex-col items-center gap-4 py-4">
          {phase === "recording" ? (
            <>
              <div
                className={
                  "flex items-center gap-2 " +
                  (elapsed > 30 ? "text-amber-600" : "text-destructive")
                }
              >
                <span
                  className={
                    "size-2.5 rounded-full animate-pulse " +
                    (elapsed > 30 ? "bg-amber-500" : "bg-destructive")
                  }
                />
                <span className="font-mono text-2xl tabular-nums">{elapsed.toFixed(1)}s</span>
              </div>
              <span className="text-xs text-muted-foreground">正在通过现场麦录音…</span>
              {elapsed > 30 && (
                <span className="text-xs text-amber-600">已超过 30 秒，建议停止</span>
              )}
              <Button variant="destructive" size="lg" className="gap-2 rounded-full" onClick={() => void stopRecording()}>
                <Square className="size-4" />停止并保存
              </Button>
            </>
          ) : phase === "starting" ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />正在启动现场麦…
            </div>
          ) : phase === "saving" ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />正在提取声纹…
            </div>
          ) : phase === "done" ? (
            <>
              <div className="text-sm text-green-600">声纹已录入 ✓</div>
              <Button variant="secondary" onClick={() => onOpenChange(false)}>完成</Button>
            </>
          ) : (
            <>
              <Button variant="default" size="lg" className="gap-2 rounded-full" onClick={() => void startRecording()}>
                <Mic className="size-5" />开始录制
              </Button>
              {errorMsg && <div className="text-xs text-destructive text-center">{errorMsg}</div>}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
