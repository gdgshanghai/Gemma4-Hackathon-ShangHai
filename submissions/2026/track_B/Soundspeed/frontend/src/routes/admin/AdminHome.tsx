import { useEffect, useMemo, useRef, useState, type TouchEvent } from "react"
import { useQueryClient } from "@tanstack/react-query"
import {
  CalendarDays,
  Eye,
  Layers,
  Settings,
  Upload,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import BottomControlBar from "@/components/admin/BottomControlBar"
import InlineFeedbackQueue from "@/components/admin/InlineFeedbackQueue"
import { LLMArchiveSheet } from "@/components/admin/LLMArchiveSheet"
import GemmaIcon from "@/components/icons/GemmaIcon"
import { MARK_ORDER } from "@/lib/constants"
import { cn, formatTakeLabel } from "@/lib/utils"
import { formatFileName } from "@/lib/filename-format"
import { useFileNameFormat } from "@/store/filename"
import type { Status } from "@/types/take"
import type { LlmState, TakeStatus, TakeDTO } from "@/types/api"
import {
  exportTakesCsv,
  todayRange,
  pickActiveScene,
  takesQueryKey,
  useActivateScene,
  useCreateScene,
  useDeleteTake,
  useEndTake,
  usePatchTake,
  useRestoreTake,
  useScenes,
  useStartTake,
  useTakes,
} from "@/lib/api"
import { ApiError } from "@/lib/api"
import { useLiveConnection } from "@/hooks/useLiveConnection"
import { useSessionStore } from "@/store/session"
import { StatusChip } from "./components/StatusChip"
import { InputLevelChip } from "./components/InputLevelChip"
import { LiveTranscript } from "./components/LiveTranscript"
import { ScriptPanel } from "./components/ScriptPanel"
import { HistoryTakes } from "./components/HistoryTakes"
import SettingsDialog from "@/components/admin/SettingsDialog"
import CreateSceneDialog from "@/components/admin/CreateSceneDialog"

const MOBILE_TABS = ["live", "script", "history"] as const

// 底部「工作槽」（spec §16）：一个待录描述符 {scene_id, shot, take_number}，独立于 History 已存的
// take 行，不绑定任何 take_id。底部 Scene/Shot/Take 三个 badge 读它；REC/Next 在它的 (scene_id, shot)
// 下调 start_take。录制指示器仍读 currentTakeRecord（实际在录的那条），两者解耦。
interface WorkSlot {
  scene_id: number
  shot: string
  take_number: number
}

// shot 归一：null/undefined/'' 都当 ''（空 shot 边角场景与 NULL 等价，spec §16 决策 1）。
const normShot = (shot: string | null | undefined): string => shot ?? ""

// 从一组 take 里找 (scene_id, shot) 组的最新 live take：scene 匹配、shot 归一后匹配、
// deleted_at==null、take_number 最大那条（spec §16「最新 live take」定义）。
function latestLiveTakeInGroup(
  takes: Iterable<TakeDTO>,
  sceneId: number,
  shot: string,
): TakeDTO | undefined {
  let best: TakeDTO | undefined
  for (const t of takes) {
    if (t.scene_id !== sceneId) continue
    if (normShot(t.shot) !== shot) continue
    if (t.deleted_at != null) continue
    if (!best || t.take_number > best.take_number) best = t
  }
  return best
}

// 某场内全局最新 live take：scene 匹配、未软删、take_id 最大那条（跨 shot，呈现该场最近录的）。
function latestLiveTakeInScene(
  takes: Iterable<TakeDTO>,
  sceneId: number,
): TakeDTO | undefined {
  let best: TakeDTO | undefined
  for (const t of takes) {
    if (t.scene_id !== sceneId) continue
    if (t.deleted_at != null) continue
    if (!best || t.take_id > best.take_id) best = t
  }
  return best
}

// 全局最新 live take：所有 live take 里 take_id 最大那条（启动初始化用）。
function latestLiveTakeGlobal(takes: Iterable<TakeDTO>): TakeDTO | undefined {
  let best: TakeDTO | undefined
  for (const t of takes) {
    if (t.deleted_at != null) continue
    if (!best || t.take_id > best.take_id) best = t
  }
  return best
}

// llm.status → header LLM chip 展示（spec §3.5）。running 的 detail 由 task_type 覆盖（见 llmDetail）。
const LLM_CHIP: Record<LlmState, { tone: "ok" | "warn"; detail: string }> = {
  idle: { tone: "ok", detail: "Idle" },
  loading: { tone: "warn", detail: "Loading…" },
  running: { tone: "warn", detail: "Running" },
  downloading: { tone: "warn", detail: "Downloading…" },
}

// running 时 chip 显示在跑哪个 LLM pipeline（task_type → 简称）。后端目前只发这两类；未知值兜底显示原文，
// 不再像旧版把 running 硬编码成「L2」（NP 任务被误显示成 L2 就是这么来的）。
const LLM_TASK_LABEL: Record<string, string> = {
  l2_take: "L2",
  note_struct: "NP",
}

export default function AdminHome() {
  const [mobileTab, setMobileTab] = useState("live")
  const [sideTab, setSideTab] = useState("script")
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  // 本 take 在场演员（按 Rec 时传 startTake；录制中锁定不可改）
  const [takeSpeakerIds, setTakeSpeakerIds] = useState<number[]>([])

  // ---- WS 连接（admin-scoped，挂一次）----
  useLiveConnection()

  // ---- scene / take / llm（来自后端 / store）----
  const { data: scenes } = useScenes()
  const activeScene = pickActiveScene(scenes)

  // header Input 电平芯片（设备名 + ch1 实时电平）已下沉到 InputLevelChip 叶子组件：
  // 把高频更新的麦克风电平状态关在那里，避免它每帧拖着整棵 AdminHome 重渲。

  // P5：LLM 反馈档案未读数 + 标记已读（打开 Sheet 时清）。
  const archiveUnread = useSessionStore((s) => s.archiveUnread)
  const markArchiveRead = useSessionStore((s) => s.markArchiveRead)
  const fileFormat = useFileNameFormat((s) => s.format)

  // 顶栏导出 Sound Report：下拉两项——今天 / 全部（不弹 modal）。
  // FileName 列按当前命名格式渲染，与 UI 一致；"今天" 按 take 开录时间落在本地今天过滤。
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const handleExport = async (scope: "today" | "all") => {
    if (exporting) return
    setExporting(true)
    setExportError(null)
    try {
      const range = scope === "today" ? todayRange() : undefined
      await exportTakesCsv(fileFormat, scope, range)
    } catch (err) {
      // 不能只 console：顶栏图标下拉无内联错误位，失败会完全不可见（401/CORS 是已知坑）。
      console.error("导出 CSV 失败", err)
      setExportError(`导出失败：${err instanceof Error ? err.message : "未知错误"}`)
    } finally {
      setExporting(false)
    }
  }

  // takes 列表 + seedTakes 桥接挂在 AdminHome（始终挂载），不在 HistoryTakes（桌面端条件挂载）。
  // 否则未打开 History 时 LLMFeedback 读空 Map，且重连时无活跃 observer → invalidate 不 refetch，
  // §3.3 恢复链断开。react-query v5 无 onSuccess，用 effect 桥接。
  const { data: takesData } = useTakes()
  const seedTakes = useSessionStore((s) => s.seedTakes)
  useEffect(() => {
    if (takesData) seedTakes(takesData)
  }, [takesData, seedTakes])

  const takesMap = useSessionStore((s) => s.takes)
  const setCurrentTakeId = useSessionStore((s) => s.setCurrentTakeId)
  const resetSegments = useSessionStore((s) => s.resetSegments)
  const llmState = useSessionStore((s) => s.llm.state)
  const llmTask = useSessionStore((s) => s.llm.taskType)
  // running 时 chip 显示具体 pipeline（NP/L2，按 task_type）；其余态用通用文案。
  const llmDetail =
    llmState === "running"
      ? llmTask
        ? LLM_TASK_LABEL[llmTask] ?? llmTask
        : "Running"
      : LLM_CHIP[llmState].detail

  // REC 开关：纯前端，与「建 take」解耦。store 单一来源，LiveTranscript 等共享读。
  const isRecording = useSessionStore((s) => s.isRecording)
  const setRecording = useSessionStore((s) => s.setRecording)

  // device.warning：持久化设备被拔走 / 不在场（后端已回落 fallback）提示，可手动 dismiss。
  const deviceWarning = useSessionStore((s) => s.deviceWarning)
  const setDeviceWarning = useSessionStore((s) => s.setDeviceWarning)
  const viewerCount = useSessionStore((s) => s.viewerCount)

  const queryClient = useQueryClient()

  // ---- scene / take mutations（2.C / 2.D）----
  const activateScene = useActivateScene()
  const createScene = useCreateScene()
  const patchTake = usePatchTake()
  const deleteTake = useDeleteTake()
  const restoreTake = useRestoreTake()
  const startTakeMut = useStartTake()
  const endTakeMut = useEndTake()
  const [createSceneOpen, setCreateSceneOpen] = useState(false)

  // 当前 take 派生：活跃场内、未软删、take_id 最大（autoincrement 单调，take_number 会被复用故不可作排序键）
  // 的那条。REC/建 take 解耦后这是「控件作用的当前 take」唯一来源——跟着 Next Take 建的空块、REC 建的块、
  // 切场后的最新块走，与 isRecording 无关。
  const currentTakeRecord = useMemo<TakeDTO | undefined>(
    () =>
      activeScene
        ? latestLiveTakeInScene(takesMap.values(), activeScene.scene_id)
        : undefined,
    [takesMap, activeScene],
  )
  const currentTakeId = currentTakeRecord?.take_id ?? null

  // 派生的 currentTakeId 同步进 store，供 applyAsr 的跨-take 守卫读（单一来源，不与 store 内部兜底分叉）。
  useEffect(() => {
    setCurrentTakeId(currentTakeId)
  }, [currentTakeId, setCurrentTakeId])

  // 「当前 take 是否已结束」：以 refetch 后的 end_ts 为准（take.changed 不带 end_ts，见 useStartTake 注释）。
  const currentTakeEnded = currentTakeRecord
    ? currentTakeRecord.end_ts !== null
    : true

  // ---- 工作槽 workSlot（spec §16）----
  // 待录描述符，与 currentTakeRecord 解耦。底部 Scene/Shot/Take badge 读它；录制指示器读 currentTakeRecord。
  //
  // 两段结构（不用 effect 播种，避免 setState-in-effect + 被 refetch 误触发重播）：
  //   - derivedInitialSlot：pristine-load 派生值。仅在用户尚未交互时生效。启动规则——全局最新 live take
  //     的 {scene_id, shot, take_number}；其不在活跃场或无 live take → 活跃场最新 live take，再退默认
  //     {shot:"1", take_number:1}。scene_id 始终 pin 到 activeScene（后端 start_take 校验 scene==active，
  //     播种到非活跃场会 REC 409）。
  //   - workSlotOverride：用户一旦交互（任一 handler）即写它，此后永久压住 derived——refetch 抹不掉
  //     用户的切场/换镜/REC 结果（advisor 陷阱 1）。
  // workSlot = override ?? derived。8 个事件全部 commit override（REC-reuse 分支靠下方 freeze 补上）。
  const [workSlotOverride, setWorkSlotOverride] = useState<WorkSlot | null>(null)
  const derivedInitialSlot = useMemo<WorkSlot | null>(() => {
    if (!activeScene) return null
    const g = latestLiveTakeGlobal(takesMap.values())
    if (g && g.scene_id === activeScene.scene_id) {
      return { scene_id: g.scene_id, shot: normShot(g.shot), take_number: g.take_number }
    }
    const s = latestLiveTakeInScene(takesMap.values(), activeScene.scene_id)
    return s
      ? { scene_id: activeScene.scene_id, shot: normShot(s.shot), take_number: s.take_number }
      : { scene_id: activeScene.scene_id, shot: "1", take_number: 1 }
  }, [activeScene, takesMap])
  const workSlot = workSlotOverride ?? derivedInitialSlot
  const setWorkSlot = setWorkSlotOverride

  // 用户在底部 Take 弹窗手动指定的「待录号」。workSlot.take_number 平时显示的是组内最新已录号
  //（REC 时后端 MAX+1 推进），不能直接当显式号回传——否则正常 REC 会拿最新号撞 live 落后缀。
  // 故单独记录手动号：仅下一次 REC 消费并作为显式号传后端；任何其它槽操作（切场/换镜/Next Take/删）
  // 都清空它，避免把旧语境的号串到新槽。null → REC 走后端自动 MAX+1（默认）。
  const [manualTakeNumber, setManualTakeNumber] = useState<number | null>(null)

  // workSlot 组（scene_id, shot）的最新 live take：删（事件 7）的作用对象。底部展示的是 workSlot，
  // 删必须删 workSlot 组里那条，而非 currentTakeRecord（活跃场跨 shot 的 max-take_id）——换镜后两者
  // 指向不同 take，删 currentTakeRecord 会删掉用户看不到、没指向的那条（advisor 指出的 §16 事件 7 偏差）。
  const slotLatestTake = useMemo<TakeDTO | undefined>(
    () =>
      workSlot
        ? latestLiveTakeInGroup(takesMap.values(), workSlot.scene_id, workSlot.shot)
        : undefined,
    [takesMap, workSlot],
  )

  // ---- recording 计时 / 错误态 ----
  const [elapsed, setElapsed] = useState(0)
  const [recError, setRecError] = useState<string | null>(null)
  const elapsedRef = useRef(elapsed)

  // start/end take inflight。useStartTake/useEndTake 的 onSuccess 返回 invalidateQueries 的 promise，
  // react-query v5 会等它 resolve 才退出 pending（useTakes 始终挂载，invalidate 必触发真实 refetch），
  // 故 isPending 覆盖到 ["takes"] refetch 落定。覆盖此窗口禁 REC/Next Take，避免 end_ts 尚未刷新时
  // 误判「未结束块可复用」（快速点击竞态）。
  const takeBlockBusy = startTakeMut.isPending || endTakeMut.isPending

  // Mark 显示当前 take 的 status（权威来自后端，经 take.changed / refetch 回灌）。无 take → 占位 ng。
  const mark: Status = currentTakeRecord?.status ?? "ng"

  useEffect(() => {
    elapsedRef.current = elapsed
  }, [elapsed])

  useEffect(() => {
    if (!isRecording) return
    const start = Date.now() - elapsedRef.current * 1000
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000))
    }, 250)
    return () => clearInterval(id)
  }, [isRecording])

  // refetch 后从 query cache（非 store——seedTakes 由 effect 在后续 render 异步播种，await 后读不到）
  // 取某 (scene, shot) 组的最新 live take，更新 workSlot。useTakes() 无参，cache key = ["takes", null]。
  const syncWorkSlotFromCacheToGroup = (sceneId: number, shot: string) => {
    const fresh = queryClient.getQueryData<TakeDTO[]>(takesQueryKey())
    const latest = fresh ? latestLiveTakeInGroup(fresh, sceneId, shot) : undefined
    if (latest) {
      setWorkSlot({ scene_id: sceneId, shot, take_number: latest.take_number })
    } else {
      // 兜底：refetch 还没落定就用待录首条，REC 实际建的号以后端为准。
      setWorkSlot({ scene_id: sceneId, shot, take_number: 1 })
    }
  }

  // ---- REC 按钮（事件 2 / 事件 3，独立开关，与建 take 解耦）----
  // OFF→ON：在 (workSlot.scene_id, workSlot.shot) 调 start_take（前端传 scene+shot，不传 number，
  //         后端按 (scene,shot) 算 MAX+1）。沿用 REC/take 解耦：若 currentTakeRecord 未结束且其
  //         (scene, shot) 与 workSlot 一致 → 复用该空块，不新建；否则建新块。新块经 refetch 回来后
  //         workSlot 更新为该组最新 live take 的 {scene_id, shot, take_number}。
  // ON→OFF：endTake，workSlot 不变。
  const handleToggleRecording = async () => {
    if (isRecording) {
      setRecording(false)
      try {
        await endTakeMut.mutateAsync()
      } catch (err) {
        console.error("endTake failed", err)
        // 后端 take 已起，前端不回滚 recording=false（已停录）；仅记日志。
      }
      return
    }

    if (!activeScene || !workSlot) {
      setRecError("无活跃场次")
      return
    }
    setRecError(null)

    // Freeze：录制一旦开始即把当前 workSlot 提交进 override，压住 derivedInitialSlot。否则在「pristine
    // load → REC(复用未结束块) → Stop → Delete」序列里 override 仍为 null，derived 会随 takesMap 退回上
    // 一条，违反 §16 事件 7「删后维持被删的号，不回退」。create 分支下方还会再按 cache 刷一次（无害）。
    setWorkSlot(workSlot)

    // workSlot.scene_id 始终 pin 到 activeScene（handleSelectScene 同步两者），故用 activeScene.scene_id
    // 调 start_take 满足后端 scene_not_active 校验。
    const sceneId = activeScene.scene_id
    const shot = workSlot.shot

    // 复用条件收紧（advisor 陷阱 3）：未结束块的 (scene, shot) 必须与 workSlot 一致才复用，
    // 否则换镜后（事件 6 只改 workSlot 不发 API）会把音频录进旧 shot 的空块。
    // 手动指定了待录号（manualTakeNumber）时也不复用：用户要的是带显式号的新 take，不是复用旧空块。
    const reuseUnended =
      manualTakeNumber == null &&
      currentTakeRecord != null &&
      !currentTakeEnded &&
      currentTakeRecord.scene_id === sceneId &&
      normShot(currentTakeRecord.shot) === shot

    setElapsed(0)
    resetSegments()
    setRecording(true)

    if (reuseUnended) {
      // 复用未结束的空块（同 scene+shot 的 Next Take 块）：不新建，直接录。workSlot 已指向它。
      return
    }
    // 否则建新块。manualTakeNumber 非 null → 作为显式号传后端（撞 live 落后缀）；null → 后端自动取号。
    // 失败回滚 recording。
    try {
      await startTakeMut.mutateAsync({
        sceneId,
        shot: shot === "" ? null : shot,
        speakerIds: takeSpeakerIds,
        takeNumber: manualTakeNumber,
      })
      setManualTakeNumber(null) // 显式号已被这次 REC 消费
      // refetch 已落定（mutateAsync await 含 onSuccess 的 invalidate→refetch）：把 workSlot 推到新块。
      syncWorkSlotFromCacheToGroup(sceneId, shot)
    } catch (err) {
      console.error("startTake failed", err)
      setRecording(false)
      setRecError("开始录制失败")
    }
  }

  // Mark：循环 MARK_ORDER → PATCH 当前 take 的 status。无 take 则 no-op（按钮也已禁用）。
  const handleCycleMark = () => {
    if (currentTakeId == null) return
    const current = (currentTakeRecord?.status ?? "ng") as Status
    const next = MARK_ORDER[
      (MARK_ORDER.indexOf(current) + 1) % MARK_ORDER.length
    ] as TakeStatus
    patchTake.mutate({ takeId: currentTakeId, body: { status: next } })
  }

  // ---- scene 切换 / 新建（2.C，bootstrap：选场即 activate，使其成为活跃场再起拍）----
  // 事件 5（改 Scene 到 S）：不 PATCH 任何 take，不动 History。activate 成功后按决策 2 重置 workSlot：
  //   S 有 live take → workSlot = S 内全局最新 live take 的 {shot, take_number}（呈现已录的那条）；
  //   S 空 → {scene_id: S, shot: "1", take_number: 1}。
  // workSlot 在 onSuccess 里改（避免切场 409 时误改），从 store takesMap 本地算（takes 全场已加载）。
  const handleSelectScene = (sceneId: number) => {
    setRecError(null)
    activateScene.mutate(sceneId, {
      onSuccess: () => {
        setManualTakeNumber(null) // 切场 = 新语境，手动号失效
        const latest = latestLiveTakeInScene(takesMap.values(), sceneId)
        setWorkSlot(
          latest
            ? { scene_id: sceneId, shot: normShot(latest.shot), take_number: latest.take_number }
            : { scene_id: sceneId, shot: "1", take_number: 1 },
        )
      },
      onError: (err) => {
        // 录制中切场后端必 409；前端已 disable，这里兜底提示。
        if (err instanceof ApiError && err.status === 409) {
          setRecError("录制中不可切场")
        } else {
          setRecError("切场失败")
        }
      },
    })
  }

  // 新建场：创建后随即 activate（与「选场即活跃」一致），关闭弹窗。
  // 复用已存在场也返回 scene_id；走 handleSelectScene 统一 activate + 按决策 2 重置 workSlot
  //（新建空场 → {shot:"1", take_number:1}；复用已有场 → 该场最新 live take）。
  const handleCreateScene = (sceneCode: string) => {
    createScene.mutate(
      { scene_code: sceneCode },
      {
        onSuccess: (res) => {
          setCreateSceneOpen(false)
          handleSelectScene(res.scene_id)
        },
      },
    )
  }

  // ---- 改 Shot（事件 6，同场 free-text 输入）----
  // 语义修正：改 shot = 换镜，不是改历史。只更新 workSlot，不 PATCH 任何已存 take、不动 History。
  //   (scene, H) 有 live take → workSlot.shot=H、take_number=该组最新 live take 的号（恢复，决策 2）；
  //   (scene, H) 无 live take → workSlot.shot=H、take_number=1（待录首条）。
  // 换镜前若还没录，只改待录槽，不产生孤儿 take。
  const handleChangeShot = (shotInput: string | null) => {
    if (!workSlot) return
    setManualTakeNumber(null) // 换镜 = 新语境，手动号失效，新镜按其最新号 / 1 显示
    const shot = normShot(shotInput)
    const latest = latestLiveTakeInGroup(takesMap.values(), workSlot.scene_id, shot)
    setWorkSlot({
      scene_id: workSlot.scene_id,
      shot,
      take_number: latest ? latest.take_number : 1,
    })
  }

  // ---- 改 Take（底部 Take 弹窗，与 Shot 对称）：手动指定待录号，只改 workSlot 显示 + 记下手动号，
  // 不发 API。下一次 REC 把它当显式号传后端（号空闲/软删占 → 干净落号；被 live 占 → 后端落后缀）。
  // 录制中禁改（呼应底部 disabled）。
  const handleChangeTake = (n: number) => {
    if (!workSlot || isRecording) return
    setManualTakeNumber(n)
    setWorkSlot({ ...workSlot, take_number: n })
  }

  // ---- Next take：只把待录 take 号 +1（场记过空条/跳号用），不建实际 take 块、----
  // 不调 start/end take API。下一次 REC 会用这个号（经 handleChangeTake 写入 manualTakeNumber）。
  // 录制中禁用。
  const handleNextTake = () => {
    if (!workSlot || isRecording) return
    handleChangeTake((workSlot.take_number ?? 0) + 1)
  }

  // ---- Delete（事件 7）：删 workSlot 组最新一条 take（软删，二次确认在 BottomControlBar 内）。----
  // 作用对象 = slotLatestTake（workSlot 组的最新 live take），不是 currentTakeId——换镜后两者可能指向
  // 不同 take，必须删用户底部看到的那条。workSlot 维持不变（不回退到上一条）：删后 REC（事件 8）后端
  // vacate 让软删行加 + 让位，新 live take 拿干净同号位（前端正常走事件 2）。故这里刻意不动 workSlot。
  const handleDeleteTake = () => {
    if (!slotLatestTake) return
    setManualTakeNumber(null) // 删后维持显示号但清手动号，删后 REC 走后端 vacate 复用同号（事件 8）
    const takeId = slotLatestTake.take_id
    deleteTake.mutate(takeId, {
      onSuccess: () => pushUndo(takeId),
      onError: (err) => {
        if (err instanceof ApiError && err.status === 409) {
          setRecError("录制中不可删除")
        } else {
          setRecError("删除失败")
        }
      },
    })
  }

  // ---- 删除撤销栈（深度 8）：记最近删除的 take_id，撤销按钮弹栈顶 → restoreTake。----
  const UNDO_DEPTH = 8
  const [undoStack, setUndoStack] = useState<number[]>([])
  const pushUndo = (takeId: number) =>
    setUndoStack((prev) => [...prev, takeId].slice(-UNDO_DEPTH))

  const handleUndoDelete = () => {
    if (undoStack.length === 0 || restoreTake.isPending) return
    const takeId = undoStack[undoStack.length - 1]
    restoreTake.mutate(takeId, {
      onSuccess: () => {
        setRecError(null)
        setUndoStack((prev) => prev.slice(0, -1))
      },
      onError: (err) => {
        // 编号已被复用 → 后端三元 UNIQUE 报 500（或其他错误）。优雅处理：提示 + 移出栈，不白屏。
        console.error("restoreTake failed", err)
        setRecError("该 take 的编号已被占用，无法撤销")
        setUndoStack((prev) => prev.slice(0, -1))
      },
    })
  }

  // ---- mobile swipe ----
  const touchStart = useRef<{ x: number; y: number } | null>(null)
  const handleTouchStart = (e: TouchEvent<HTMLDivElement>) => {
    const t = e.touches[0]
    touchStart.current = { x: t.clientX, y: t.clientY }
  }
  const handleTouchEnd = (e: TouchEvent<HTMLDivElement>) => {
    if (!touchStart.current) return
    const start = touchStart.current
    touchStart.current = null
    const t = e.changedTouches[0]
    const dx = start.x - t.clientX
    const dy = start.y - t.clientY
    const minSwipe = 56
    if (Math.abs(dx) < minSwipe || Math.abs(dy) > Math.abs(dx)) return

    const idx = MOBILE_TABS.indexOf(mobileTab as typeof MOBILE_TABS[number])
    if (dx > 0 && idx < MOBILE_TABS.length - 1) {
      setMobileTab(MOBILE_TABS[idx + 1])
    } else if (dx < 0 && idx > 0) {
      setMobileTab(MOBILE_TABS[idx - 1])
    }
  }

  const mobileIdx = MOBILE_TABS.indexOf(mobileTab as typeof MOBILE_TABS[number])

  return (
    <div className="h-dvh w-screen flex flex-col bg-muted/50 text-foreground overflow-hidden">
      {/* ============ Header ============ */}
      <header className="flex-shrink-0 bg-background">
        <div className="px-4 h-11 flex items-center justify-between gap-2 border-b">
          <div className="flex items-center gap-2 min-w-0">
            <InputLevelChip />
            <StatusChip
              label="Gemma 4"
              icon={<GemmaIcon className="size-5 text-[#4285F4]" />}
              tone={LLM_CHIP[llmState].tone}
              detail={llmDetail}
              className="flex-shrink-0"
            />
            {/* ---- 状态栏：当前场次 / take / 录制态（真实数据）---- */}
            <div className="hidden sm:flex items-center gap-1.5 h-9 px-3 rounded-full bg-muted/70 flex-shrink-0 font-mono text-[10px] text-muted-foreground">
              <span
                className={cn(
                  "size-1.5 rounded-full flex-shrink-0",
                  isRecording ? "bg-destructive animate-pulse" : "bg-muted-foreground/40"
                )}
              />
              {/* 按用户配置的文件名格式显示当前条（scene=活跃场，shot/take=最近录的 take；统一 formatFileName）。 */}
              <span className="text-foreground">
                {formatFileName(
                  {
                    scene_code: activeScene?.scene_code,
                    shot: currentTakeRecord?.shot,
                    take_number: currentTakeRecord?.take_number,
                  },
                  fileFormat,
                ) || "—"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground">
              <Eye />
              <span className="font-mono text-xs">{viewerCount}</span>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild disabled={exporting}>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="rounded-full text-muted-foreground"
                  title="导出 Sound Report"
                >
                  <Upload className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>导出 Sound Report</DropdownMenuLabel>
                <DropdownMenuItem onClick={() => void handleExport("today")}>
                  <CalendarDays className="size-3.5" />
                  导出今天的内容
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => void handleExport("all")}>
                  <Layers className="size-3.5" />
                  导出全部内容
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              variant="ghost"
              size="icon-sm"
              className="rounded-full text-muted-foreground"
              title={settingsOpen ? "关闭设置" : "打开设置"}
              onClick={() => setSettingsOpen((prev) => !prev)}
            >
              {settingsOpen ? <X className="size-4" /> : <Settings className="size-4" />}
            </Button>
          </div>
        </div>
        {/* device.warning：持久化设备拔走 / 不在场（后端已回落 fallback）。amber 提示，可手动 dismiss。
            风格与 SettingsDialog 里 selected_available===false 那条一致。 */}
        {deviceWarning && (
          <div className="px-4 py-1 flex items-center gap-1.5 border-b bg-amber-50/60">
            <span className="text-xs text-amber-600 min-w-0 truncate">{deviceWarning}</span>
            <button
              type="button"
              className="ml-auto flex-shrink-0 text-amber-600/70 hover:text-amber-600"
              title="忽略提示"
              onClick={() => setDeviceWarning(null)}
            >
              <X className="size-3.5" />
            </button>
          </div>
        )}
        {/* 导出失败可见反馈：顶栏图标下拉本身无内联错误位，否则失败完全静默。可手动 dismiss。 */}
        {exportError && (
          <div className="px-4 py-1 flex items-center gap-1.5 border-b bg-destructive/10">
            <span className="text-xs text-destructive min-w-0 truncate">{exportError}</span>
            <button
              type="button"
              className="ml-auto flex-shrink-0 text-destructive/70 hover:text-destructive"
              title="忽略提示"
              onClick={() => setExportError(null)}
            >
              <X className="size-3.5" />
            </button>
          </div>
        )}
      </header>

      {/* ============ Main ============ */}
      <main className="flex-1 min-h-0 p-4 flex flex-col md:flex-row gap-3">
        {/* ---- Mobile：单 Card 内 Tabs 切换 ---- */}
        <Card size="sm" className="md:hidden flex-1 min-h-0 p-0 gap-0 overflow-hidden">
          <Tabs value={mobileTab} onValueChange={setMobileTab} className="flex-1 min-h-0 flex flex-col p-3 pb-0 gap-3">
            <TabsList className="w-full flex-shrink-0">
              <TabsTrigger value="live">Live</TabsTrigger>
              <TabsTrigger value="script">剧本</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>
            <div
              className="flex-1 min-h-0 overflow-hidden touch-pan-y"
              onTouchStart={handleTouchStart}
              onTouchEnd={handleTouchEnd}
            >
              <div
                className="flex h-full transition-transform duration-300 ease-out will-change-transform"
                style={{ transform: `translateX(-${mobileIdx * 100}%)` }}
              >
                <div className="w-full h-full flex-shrink-0 overflow-y-auto px-3 pb-3">
                  <LiveTranscript />
                </div>
                <div className="w-full h-full flex-shrink-0 overflow-y-auto px-3 pb-3">
                  <ScriptPanel />
                </div>
                <div className="w-full h-full flex-shrink-0 overflow-y-auto px-3 pb-3">
                  <HistoryTakes />
                </div>
              </div>
            </div>
          </Tabs>
        </Card>

        {/* ---- Desktop：左 transcript Card ---- */}
        <Card size="sm" className="hidden md:flex flex-[2] min-h-0 p-0 gap-0 overflow-hidden flex-col">
          <div className="flex-shrink-0 p-3 pb-0">
            <Tabs value="live" className="items-center">
              <TabsList>
                <TabsTrigger value="live" className="min-w-[9rem]">Live</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto">
            <LiveTranscript />
          </div>
        </Card>

        {/* ---- Desktop：右 tabs Card ---- */}
        <Card size="sm" className="hidden md:flex flex-[3] flex-col p-0 gap-0 overflow-hidden">
          <Tabs value={sideTab} onValueChange={setSideTab} className="flex-1 min-h-0 flex flex-col p-3 pb-0 gap-3">
            <TabsList className="w-full flex-shrink-0">
              <TabsTrigger value="script">剧本</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>
            <div className="flex-1 min-h-0 overflow-y-auto -mx-3 px-3 pb-3">
              {sideTab === "script" && <ScriptPanel />}
              {sideTab === "history" && <HistoryTakes />}
            </div>
          </Tabs>
        </Card>
      </main>

      {/* ============ Bottom ============ */}
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />

      <CreateSceneDialog
        open={createSceneOpen}
        onOpenChange={setCreateSceneOpen}
        onCreate={handleCreateScene}
        pending={createScene.isPending || activateScene.isPending}
      />

      {/* ============ 底部 dock：note 队列浮层 + 控制栏 ============ */}
      <div className="relative flex-shrink-0">
        {/* Note 队列浮层：从底栏 MemoInput 顶部向上延伸，半透明盖在 main 上，上圆角下直角。
            bottom-[calc(100%-26px)]：浮层底边藏进 pill 顶下 17px（26 = 9 缝隙 + 17 藏量），由 pill(z-30)
            盖住，形成从输入框背后弹出。该距离恒定，不随控制行/REC 高度变。队列为空时 InlineFeedbackQueue 返回 null。
            pointer-events-none 让浮层 padding 区穿透到 main；InlineFeedbackQueue 的 Card 自带 pointer-events-auto 可滚。 */}
        <div className="pointer-events-none absolute inset-x-0 bottom-[calc(100%-26px)] z-20 px-4">
          <InlineFeedbackQueue />
        </div>

        {/* LLM 反馈档案浮层：从输入框上沿向上展开（挂 dock relative 容器内，absolute 相对它定位）。 */}
        <LLMArchiveSheet open={archiveOpen} onOpenChange={setArchiveOpen} />

        <BottomControlBar
        isRecording={isRecording}
        onToggleRecording={handleToggleRecording}
        mark={mark}
        onCycleMark={handleCycleMark}
        elapsed={elapsed}
        // bootstrap：切场期间 activeScene 还没刷成新场，此时禁 REC 避免 start 用旧活跃场 → 409
        // scene_not_active。建 take inflight（含 refetch）期间也禁，避免 end_ts 未刷新时误判复用（竞态）。
        // 录制中不受 takeBlockBusy 限（要能停录）。
        recDisabled={
          (!activeScene || activateScene.isPending || takeBlockBusy) && !isRecording
        }
        recHint={
          recError ??
          (activateScene.isPending && !isRecording
            ? "切场中…"
            : !activeScene
              ? "无活跃场次"
              : null)
        }
        scenes={scenes ?? []}
        activeScene={activeScene}
        // ── 底部 Scene/Shot/Take badge 读 workSlot（待录描述符）──
        // workSlot 的 shot 内部用 '' 表示空，显示成 "—"；take_number 直接拼成 label（无 suffix，
        // workSlot 不带 suffix，formatTakeLabel 默认 suffix=''）。
        slotShot={workSlot ? (workSlot.shot === "" ? null : workSlot.shot) : null}
        slotTakeLabel={
          workSlot ? formatTakeLabel({ take_number: workSlot.take_number }) : "—"
        }
        slotTakeNumber={workSlot?.take_number ?? null}
        // ── Mark 的作用对象：currentTakeRecord（活跃场 max-take_id），与 workSlot 解耦 ──
        currentTakeId={currentTakeId}
        // ── Delete 的作用对象：workSlot 组最新 live take。空组 → 无可删 → 禁用删除（事件 7）──
        canDeleteSlot={slotLatestTake != null}
        onSelectScene={handleSelectScene}
        onCreateScene={() => setCreateSceneOpen(true)}
        onChangeShot={handleChangeShot}
        onChangeTake={handleChangeTake}
        onNextTake={handleNextTake}
        nextTakeBusy={false}
        onDeleteTake={handleDeleteTake}
        canUndo={undoStack.length > 0}
        onUndoDelete={handleUndoDelete}
        undoBusy={restoreTake.isPending}
        sceneBusy={activateScene.isPending}
        takeBusy={patchTake.isPending || deleteTake.isPending}
        // ── 1.x：本 take 在场演员选择（diarization 回填匹配范围）──
        speakerIds={takeSpeakerIds}
        onSpeakerIdsChange={setTakeSpeakerIds}
        // P5：LLM 反馈一级入口 —— 打开档案 Sheet 并清未读。
        onOpenArchive={() => {
          setArchiveOpen(true)
          markArchiveRead()
        }}
        archiveUnread={archiveUnread}
        llmState={llmState}
        />
      </div>
    </div>
  )
}
