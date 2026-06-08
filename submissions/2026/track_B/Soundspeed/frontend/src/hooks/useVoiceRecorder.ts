import { useEffect, useRef, useState } from "react"
import { blobToWav16kMono } from "@/lib/wav"

// 按住说话录音器（4.L）：getUserMedia + MediaRecorder → blobToWav16kMono（复用 enroll 同款编码：
// 任意录音格式经 decodeAudioData 归一成 16k 单声道 WAV，绕过 iOS Safari MediaRecorder 吐 mp4/aac 的
// 格式差异）。start/stop/cancel 三态，供 MemoInput 的对讲机式交互调用。
//
// 注：录音机制与 EnrollRecorderDialog 同源（MediaRecorder + blobToWav16kMono），未来可把那边也收进本 hook。

export interface VoiceRecorder {
  recording: boolean
  start: () => Promise<void>
  // 返回 16k 单声道 WAV Blob；时长 < minDurationMs（误触）→ null，调用方静默丢弃。
  stop: () => Promise<Blob | null>
  cancel: () => void
}

export function useVoiceRecorder(minDurationMs = 500): VoiceRecorder {
  const [recording, setRecording] = useState(false)
  const recRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startedAtRef = useRef(0)

  const release = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    recRef.current = null
    chunksRef.current = []
  }

  // 卸载时释放麦克风：按住录音中途组件卸载（未走 stop/cancel）→ 停轨，不留热麦。
  useEffect(
    () => () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
    },
    [],
  )

  const start = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    streamRef.current = stream
    const rec = new MediaRecorder(stream)
    chunksRef.current = []
    rec.ondataavailable = (e) => {
      if (e.data.size) chunksRef.current.push(e.data)
    }
    rec.start()
    recRef.current = rec
    startedAtRef.current = Date.now()
    setRecording(true)
  }

  const stop = async (): Promise<Blob | null> => {
    const rec = recRef.current
    setRecording(false)
    if (!rec) return null
    const durationMs = Date.now() - startedAtRef.current
    // 等 onstop（在最后一次 ondataavailable 之后）拿齐所有块再合成。
    const raw = await new Promise<Blob>((resolve) => {
      rec.onstop = () =>
        resolve(new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" }))
      rec.stop()
    })
    release()
    if (durationMs < minDurationMs) return null // 误触，丢弃
    return blobToWav16kMono(raw)
  }

  const cancel = () => {
    const rec = recRef.current
    setRecording(false)
    if (rec && rec.state !== "inactive") {
      rec.onstop = () => {} // 取消：不合成
      try {
        rec.stop()
      } catch {
        /* 已停 */
      }
    }
    release()
  }

  return { recording, start, stop, cancel }
}
