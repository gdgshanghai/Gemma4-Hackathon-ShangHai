import { useEffect, useState } from "react"
import { useDevices } from "@/lib/api"
import { useSessionStore } from "@/store/session"
import { useMicLevel } from "@/hooks/useMicLevel"
import { StatusChip, LiveLevelMeter } from "./StatusChip"

// header 的 Input 电平芯片，独立成叶子组件。
// 关键：useMicLevel 是一个会高频更新的状态源（按档位去抖后仍会随声音变动而重渲）。把它连同
// backendLevel 混合逻辑一起关在这个叶子里，AdminHome 就不再因为电平变化而整棵树重渲——只有这
// 十几个节点的小子树跟着动。配合 useMicLevel 的档位去抖，待机时几乎不重渲。
export function InputLevelChip() {
  // 头部 Input 芯片显示真实会采集的设备名：selected 是后端权威 index（持久化设备不在场时已是
  // fallback 设备的 index），直接按它查名。
  const { data: devicesData } = useDevices()
  const deviceName = (() => {
    const ds = devicesData?.devices ?? []
    const selected = devicesData?.selected
    return ds.find((d) => d.index === selected)?.name ?? "—"
  })()

  // header 实时麦克风电平（ch1 监看）：绑定到设置里选定的输入设备；"—"（无权威设备）时走默认。
  const micLevel = useMicLevel(true, deviceName !== "—" ? deviceName : undefined)

  // 后端实际采集那路的真实 RMS（仅录制时 ~5Hz 推），用于电平条混合（见下）。
  const backendLevel = useSessionStore((s) => s.backendLevel)
  const backendLevelTs = useSessionStore((s) => s.backendLevelTs)

  // 混合电平判新鲜度需要「现在」，但 Date.now() 是非纯函数不能在 render 调（react-hooks/purity）。
  // 故用 nowTick 状态：收到后端帧后起一个 100ms 轮询 effect 在回调里推进 nowTick，确认陈旧（超阈值）
  // 即自停。停录后后端不再推，轮询把 nowTick 推过阈值后电平条自动回落浏览器电平。
  const [nowTick, setNowTick] = useState(0)
  useEffect(() => {
    if (!backendLevelTs) return
    const id = setInterval(() => {
      const t = Date.now()
      setNowTick(t)
      if (t - backendLevelTs >= 600) clearInterval(id) // 已陈旧，停轮询
    }, 100)
    return () => clearInterval(id)
  }, [backendLevelTs])

  // 混合电平：后端数据新鲜（600ms 内有新帧）就用后端真实 RMS，否则回落浏览器常驻 micLevel。
  // 用 max(nowTick, backendLevelTs) 当「现在」：刚到的新帧 ts 可能 > 上一次轮询的 nowTick，取大者
  // 保证新帧立刻判新鲜。视觉尺度对齐：浏览器电平已是 min(1, rms*3)，后端 rms 同乘 3 取 min(1,…)。
  const backendFresh =
    backendLevelTs > 0 && Math.max(nowTick, backendLevelTs) - backendLevelTs < 600
  const displayLevel = backendFresh ? Math.min(1, backendLevel * 3) : micLevel

  return (
    <StatusChip label="Input" tone="ok" detail={deviceName} className="min-w-0">
      {/* ch1 实时电平：录制时用后端真实采集 RMS，平时用浏览器常驻电平（见 displayLevel） */}
      <LiveLevelMeter level={displayLevel} count={7} color="bg-green-500" className="ml-0.5" />
    </StatusChip>
  )
}
