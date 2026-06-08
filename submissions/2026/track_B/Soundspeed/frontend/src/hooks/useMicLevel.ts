import { useEffect, useRef, useState } from "react"
import { levelBucket } from "@/lib/level"

// 实时麦克风电平 [0,1]。浏览器 getUserMedia + AnalyserNode 取时域 RMS，rAF 刷新。
// 与后端采集是各自独立的流（Windows 共享模式可同时打开同一麦克风），仅用于 header 监看
// “麦克风是否在收声”——常驻实时，打开页面即跳动，不依赖 REC。
//
// deviceName：设置里选的输入设备名（后端 selected 设备的 name）。传入后会枚举
// audioinput，按 label 匹配出 deviceId，用 ideal 软约束重取流绑定到该设备。匹配不到 /
// 设备被拔走也只回落到默认设备继续出电平，绝不黑掉。deviceName 变化时重建流。
// 无权限/无设备时静默返回 0。
export function useMicLevel(enabled = true, deviceName?: string): number {
  const [level, setLevel] = useState(0)
  const rafRef = useRef<number | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  // 上一次 setState 的电平档位。rAF 每帧都跑（读 analyser 很便宜），但只有跨档才 setState，
  // 避免 60fps 无脑重渲。-1 = 还没出过值，首帧必出。
  const lastBucketRef = useRef(-1)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false

    // 按 deviceName 在 audioinput 里找匹配的 deviceId（先精确 label，再包含匹配）。
    // 拿不到 / 匹配不到返回 null，调用方回落到默认设备。
    const resolveDeviceId = async (): Promise<string | null> => {
      if (!deviceName) return null
      try {
        const devices = await navigator.mediaDevices.enumerateDevices()
        const inputs = devices.filter((d) => d.kind === "audioinput" && d.deviceId)
        const exact = inputs.find((d) => d.label === deviceName)
        if (exact) return exact.deviceId
        const partial = inputs.find(
          (d) => d.label && (d.label.includes(deviceName) || deviceName.includes(d.label)),
        )
        return partial?.deviceId ?? null
      } catch {
        return null
      }
    }

    const start = async () => {
      try {
        lastBucketRef.current = -1 // (重)建流：首帧必出一次值
        // 先用默认约束拿权限：首次 enumerateDevices 的 label 在授权前可能为空。
        let stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }

        // 授权后枚举找选定设备的 deviceId；命中且与当前不同则用 ideal 软约束重取流。
        // ideal 而非 exact：匹配不到 / 设备拔了时浏览器回落到默认设备，电平不中断。
        const deviceId = await resolveDeviceId()
        if (deviceId) {
          const curId = stream.getAudioTracks()[0]?.getSettings().deviceId
          if (curId !== deviceId) {
            try {
              const next = await navigator.mediaDevices.getUserMedia({
                audio: { deviceId: { ideal: deviceId } },
              })
              if (cancelled) {
                next.getTracks().forEach((t) => t.stop())
                stream.getTracks().forEach((t) => t.stop())
                return
              }
              // 切到新流前停掉旧默认流。
              stream.getTracks().forEach((t) => t.stop())
              stream = next
            } catch {
              // 重取失败：保留默认流继续出电平。
            }
          }
        }

        streamRef.current = stream
        const ctx = new AudioContext()
        ctxRef.current = ctx
        const src = ctx.createMediaStreamSource(stream)
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 512
        src.connect(analyser)
        const buf = new Uint8Array(analyser.fftSize)

        const tick = () => {
          analyser.getByteTimeDomainData(buf)
          let sum = 0
          for (let i = 0; i < buf.length; i++) {
            const v = (buf[i] - 128) / 128
            sum += v * v
          }
          const rms = Math.sqrt(sum / buf.length)
          const next = Math.min(1, rms * 3) // 放大便于观察
          // 去抖：只有跨过量化档位才 setState 触发重渲。静音时 rms 近恒定 → 档位不变 → 不重渲，
          // 待机不再 60fps 拖整棵树（dev 下也不再灌 PerformanceMeasure）。
          const b = levelBucket(next)
          if (b !== lastBucketRef.current) {
            lastBucketRef.current = b
            setLevel(next)
          }
          rafRef.current = requestAnimationFrame(tick)
        }
        rafRef.current = requestAnimationFrame(tick)
      } catch {
        // 无麦克风权限/设备：保持 0，不报错
      }
    }
    void start()

    return () => {
      cancelled = true
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current)
      ctxRef.current?.close()
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [enabled, deviceName])

  return level
}
