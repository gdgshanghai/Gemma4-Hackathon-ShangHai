import { create } from "zustand"
import { LS_TOKEN_KEY } from "@/lib/config"
import type {
  AsrMsg,
  LlmState,
  TakeChangedMsg,
  TakeDTO,
  TakeProcessingMsg,
  TakeProcessingPhase,
  TranscriptSegmentDTO,
} from "@/types/api"

import type {
  FeedReceipt,
  NoteFailedMsg,
  NoteProcessedMsg,
  PendingNote,
  QaItem,
} from "@/types/api"

export type ConnectionState = "connecting" | "open" | "closed" | "no-token"

// tool.call 全局 WS 事件：后端 agent 的工具调用轨迹（开发者 tab 实时日志框消费）。
// 冻结契约 v2：topic === "tool.call"，payload 即此形状（ts 是 epoch 秒 float，
// arguments 是原样 JSON 字符串、前端负责美化，nullable 字段后端可能给 null）。
export interface ToolCallEntry {
  task_type: string
  tool_id: string | null
  tool_type: string | null
  tool_name: string
  arguments: string
  finish_reason: string | null
  model: string | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  available_tools: string[]
  tool_choice: string | null
  ts: number
}

// tool-call 实时日志有界缓冲：只留最近 N 条，超出从头丢（避免长跑 session 无限堆积）。
const TOOL_CALLS_MAX = 150

// 当前录制 take 的实时转录条目（按声道维护）。
export interface LiveSeg {
  text: string
  speaker: string | null
  start_frame: number
  end_frame: number
  isPartial: boolean
}

// QP 答案到达：把命中 client_id 的 qaItem 置 done + answer（其余不动）。resolveQa 与
// qpAnswerArrived 的命中分支共用同一 transition；archiveUnread+1 的 bump 仍留在各自 set()。
function resolveQaItems(items: QaItem[], clientId: string, answer: string): QaItem[] {
  return items.map((q) =>
    q.client_id === clientId ? { ...q, status: "done", answer } : q,
  )
}

function readToken(): string | null {
  const stored =
    typeof localStorage !== "undefined" ? localStorage.getItem(LS_TOKEN_KEY) : null
  if (stored && stored.trim()) return stored
  // dev 自动填：localhost 无需手填 token。后端 DEV 用固定 "devtoken"，故默认 VITE_ADMIN_TOKEN ?? "devtoken"。
  // 生产构建（import.meta.env.DEV=false）不自动填，仍需手填 token——不是鉴权绕过，只是已知 dev 默认。
  if (import.meta.env.DEV) {
    return (import.meta.env.VITE_ADMIN_TOKEN as string | undefined) ?? "devtoken"
  }
  return null
}

interface SessionState {
  // 鉴权（API base 取自 config.ts 的 API_BASE，不可编辑，故不入 store）
  token: string | null
  connection: ConnectionState

  // 当前录制 take 的实时转录（按 ch）。partial 替换该声道最后一条 partial，final 落定。
  segments: { ch1: LiveSeg[]; ch2: LiveSeg[] }

  // 当前 take 的 take_id。REC/建 take 解耦后，「当前 take」由 AdminHome 从 takes Map + 活跃场派生
  // （最近一条 take），再经 setCurrentTakeId 同步进来。这里只留 id，供 applyAsr 的跨-take 守卫读，
  // 不再持 take_number / shot（这些由 AdminHome 从派生 take 读）。
  currentTakeId: number | null

  // REC 开关（纯前端，与「建 take」解耦）。AdminHome 是唯一 writer；LiveTranscript 等读它显示录制态。
  isRecording: boolean

  // take 列表：Map<take_id, TakeDTO>。getTakes 全量覆盖（权威），take.changed patch-merge 5 字段。
  takes: Map<number, TakeDTO>

  llm: { state: LlmState; taskType: string | null }

  // pending notes: 已提交、等待 NP Pipeline 归置
  pendingNotes: PendingNote[]

  // 就地队列的 note 回执（done 态，note.processed 派生，3s 由组件 dismissReceipt 自走）
  feedReceipts: FeedReceipt[]

  // QP 问答项：就地队列渲染（processing/done/failed）+ 留存供档案（P5）。
  // inlineDismissed 后只在档案显示，不在就地层。query 答案经 qp.answer.{CONN_ID} WS 按 client_id resolveQa。
  qaItems: QaItem[]

  // LLM 反馈档案未读数：L2 推送实时到达（take.changed 带 script_diff null→非 null）/ QP 新答案落定
  // 时 +1；打开档案 Sheet 时 markArchiveRead 清 0。seedTakes（历史加载/refetch）不 bump——非新事件。
  archiveUnread: number

  // note 队列版本号：note.processed 落库后递增，据此 refetch resolved notes（History/take 详情）。
  // 提交时不 bump——那时 note 未落库，refetch 拿不到，pending 已由 store 直接显示。
  notesVersion: number

  // take.end 后处理状态条（diarization + Gemma）；done 清空，error 保留到下次录制。null=不显示。
  processing: { phase: TakeProcessingPhase; detail: string | null } | null

  // device.warning：持久化设备被拔走 / 不在场（后端已回落 fallback）的提示文案。null=不显示。
  deviceWarning: string | null

  // audio.level：后端实际采集那路音频的归一化 RMS [0,1]，仅录制时 ~5Hz 推送。
  // backendLevelTs 记最近一帧到达的本地时间戳（Date.now()）用于判断新鲜度——停录后后端不再推，
  // 过阈值即视为陈旧，电平条回落到浏览器常驻 micLevel。
  backendLevel: number
  backendLevelTs: number

  // viewer.count：当前连着 /ws 的客户端总数（含自己）。后端在连接建立 / 断开时广播。
  // 连接断开（onClose）归 0，避免显示陈旧值；重连后服务端首帧重填。
  viewerCount: number

  // tool.call：后端 agent 工具调用轨迹（有界缓冲，最近 150 条）。设置页开发者 tab 日志框消费。
  toolCalls: ToolCallEntry[]

  // ── actions ──
  setToken: (t: string | null) => void
  setConnection: (c: ConnectionState) => void
  applyAsr: (ch: 1 | 2, isFinal: boolean, p: AsrMsg) => void
  applyBackfilledSegments: (takeId: number, segments: TranscriptSegmentDTO[]) => void
  applyTakeChanged: (m: TakeChangedMsg) => void
  seedTakes: (list: TakeDTO[]) => void
  removeTake: (takeId: number) => void
  setLlm: (state: LlmState, taskType: string | null) => void
  setTakeProcessing: (m: TakeProcessingMsg) => void
  setCurrentTakeId: (id: number | null) => void
  setRecording: (recording: boolean) => void
  setDeviceWarning: (message: string | null) => void
  setBackendLevel: (rms: number) => void
  setViewerCount: (count: number) => void
  appendToolCall: (entry: ToolCallEntry) => void
  resetSegments: () => void
  addPendingNote: (n: PendingNote) => void
  removePending: (clientId: string) => void
  noteProcessed: (m: NoteProcessedMsg) => void
  noteFailed: (m: NoteFailedMsg) => void
  retryPending: (clientId: string) => void
  dismissPending: (clientId: string) => void
  dismissReceipt: (clientId: string) => void
  addQa: (q: QaItem) => void
  resolveQa: (clientId: string, answer: string) => void
  qpAnswerArrived: (clientId: string, answerText: string) => void
  failQa: (clientId: string, reason: string) => void
  dismissQaInline: (clientId: string) => void
  markArchiveRead: () => void
}

export const useSessionStore = create<SessionState>((set) => ({
  token: readToken(),
  connection: readToken() ? "connecting" : "no-token",

  segments: { ch1: [], ch2: [] },
  currentTakeId: null,
  isRecording: false,
  takes: new Map(),
  llm: { state: "idle", taskType: null },
  pendingNotes: [],
  feedReceipts: [],
  qaItems: [],
  archiveUnread: 0,
  notesVersion: 0,
  processing: null,
  deviceWarning: null,
  backendLevel: 0,
  backendLevelTs: 0,
  viewerCount: 0,
  toolCalls: [],

  setToken: (t) =>
    set(() => ({
      token: t && t.trim() ? t : null,
      connection: t && t.trim() ? "connecting" : "no-token",
    })),

  setConnection: (c) => set(() => ({ connection: c })),

  applyAsr: (ch, isFinal, p) =>
    set((state) => {
      // 丢弃来自其他 take 的迟到帧（跨 take 泄漏）。两侧 != null 守卫：dev 注入器（take_id=null）
      // 与 currentTakeId 绑定前的窗口仍正常工作。
      if (
        p.take_id != null &&
        state.currentTakeId != null &&
        p.take_id !== state.currentTakeId
      ) {
        return {}
      }
      const key = ch === 1 ? "ch1" : "ch2"
      const list = state.segments[key]
      const seg: LiveSeg = {
        text: p.text,
        speaker: p.speaker,
        start_frame: p.start_frame,
        end_frame: p.end_frame,
        isPartial: !isFinal,
      }
      const last = list[list.length - 1]
      // partial 替换该声道最后一条 partial；final 也优先落定最后一条 partial，否则 push。
      const next =
        last && last.isPartial
          ? [...list.slice(0, -1), seg]
          : [...list, seg]
      return { segments: { ...state.segments, [key]: next } }
    }),

  // diarization 回填完成：用权威 segments（带 speaker）替换 Live 框里只有 ASR 文本的内容。
  // 守卫：仅当回填的 take 仍是当前/最后绑定的 take 时替换；若已开新 take（take_id 不同且
  // 在录），跳过以免覆盖新 take 的实时转录。
  applyBackfilledSegments: (takeId, segments) =>
    set((state) => {
      const cur = state.currentTakeId
      if (cur != null && cur !== takeId && state.isRecording) {
        return {}
      }
      const toSeg = (d: TranscriptSegmentDTO): LiveSeg => ({
        text: d.text,
        speaker: d.speaker,
        start_frame: d.start_frame,
        end_frame: d.end_frame,
        isPartial: false,
      })
      return {
        segments: {
          ch1: segments.filter((s) => s.ch === 1).map(toSeg),
          ch2: segments.filter((s) => s.ch === 2).map(toSeg),
        },
      }
    }),

  applyTakeChanged: (m) =>
    set((state) => {
      const takes = new Map(state.takes)
      const existing = takes.get(m.take_id)
      // L2 推送实时到达：script_diff 从无到有（新 take 直接带 diff，或已存在 take 补上 diff）→ 档案未读 +1。
      const l2Arrived = m.script_diff != null && existing?.script_diff == null
      if (existing) {
        // patch-merge：只覆盖 take.changed 的 5 字段，保留 shot/start_ts/end_ts/notes 等。
        // script_diff 同 seedTakes：不向下降级到 null（与 P1-1 对称的纵深防御）。单条有序 WS 上
        // 发布序为 start(null)→end(null)→L2(non-null)，本不会产生 null-after-non-null，但对齐
        // 防御形状，杜绝该类隐患。
        takes.set(m.take_id, {
          ...existing,
          ...m,
          script_diff: m.script_diff ?? existing.script_diff ?? null,
        })
      } else {
        // 新 take：插入部分条目，其余字段等 getTakes/getTake 补齐。
        // ⚠ end_ts 此处先填 null，但 take.changed（5 字段 Pick）永不更新 end_ts——只有 getTakes
        // refetch 能把真实 end_ts 填进来。判断「take 是否已结束」必须以 refetch 后的快照为准。
        takes.set(m.take_id, {
          take_id: m.take_id,
          scene_id: m.scene_id,
          take_number: m.take_number,
          take_suffix: "",
          status: m.status,
          script_diff: m.script_diff,
          shot: null,
          start_ts: 0,
          end_ts: null,
          notes: null,
          deleted_at: null,
          created_at: 0,
          updated_at: 0,
        })
      }

      // currentTakeId 兜底绑定（单调）。REC/建 take 解耦后权威派生在 AdminHome（按活跃场 + 最大
      // take_id），但 WS 帧往往早于 refetch + 派生 effect 到达；这里先把 currentTakeId 顶到最新
      // take_id，让 applyAsr 的跨-take 守卫立刻对齐新块。低 id 帧抢先到也会被后续更高 id 帧纠正。
      // 不分 recording：建空块（Next Take，不录）同样要让 id 跟上。
      const currentTakeId =
        state.currentTakeId === null || m.take_id > state.currentTakeId
          ? m.take_id
          : state.currentTakeId

      return {
        takes,
        currentTakeId,
        archiveUnread: l2Arrived ? state.archiveUnread + 1 : state.archiveUnread,
      }
    }),

  // getTakes 全量覆盖每个 take_id 条目（getTakes 权威）。例外：script_diff 不向下降级到 null——
  // getTakes 快照读可能早于某条 L2 DB 写，而那条的 WS 帧已把 store 的 script_diff 填好；若 seed
  // 直接覆盖会把刚到的 L2 摘要抹回 null。故 script_diff 取 incoming ?? existing ?? null。
  seedTakes: (list) =>
    set((state) => {
      const takes = new Map(state.takes)
      for (const t of list) {
        const existing = takes.get(t.take_id)
        takes.set(t.take_id, {
          ...t,
          script_diff: t.script_diff ?? existing?.script_diff ?? null,
        })
      }
      return { takes }
    }),

  // 删某条 take（DELETE 成功 / take.deleted WS）。seedTakes 只增不删，故删除必须走这条显式抹掉，
  // 否则 invalidate→refetch 后该条仍残留在 Map 里。若删的是当前 take，顺手解绑 currentTakeId
  //（AdminHome 的派生 effect 随后会重指到下一条最近 take）。
  removeTake: (takeId) =>
    set((state) => {
      const unbind = state.currentTakeId === takeId
      if (!state.takes.has(takeId)) {
        return unbind ? { currentTakeId: null } : {}
      }
      const takes = new Map(state.takes)
      takes.delete(takeId)
      return unbind ? { takes, currentTakeId: null } : { takes }
    }),

  setLlm: (state, taskType) => set(() => ({ llm: { state, taskType } })),

  // take.end 后处理状态条：done 清空；diarizing/summarizing/error 显示。
  setTakeProcessing: (m) =>
    set(() => ({
      processing: m.phase === "done" ? null : { phase: m.phase, detail: m.detail },
    })),

  // AdminHome 派生「当前 take」后同步进来，作为 applyAsr 跨-take 守卫的权威。
  setCurrentTakeId: (id) =>
    set((state) => (state.currentTakeId === id ? {} : { currentTakeId: id })),

  addPendingNote: (n) =>
    set((s) => ({ pendingNotes: [...s.pendingNotes, n] })),

  // 按 client_id 精确移除一条 pending（无 version bump，区别于 noteProcessed）。
  // 入口调度器判这条 memo 其实是查询（kind=query）时，乐观插的 note pending 要撤掉——
  // 它不是备注、不会落库、无 note.processed 回灌，留着会永久卡「处理中」。
  removePending: (clientId) =>
    set((s) => ({
      pendingNotes: s.pendingNotes.filter((p) => p.client_id !== clientId),
    })),

  // client_id 精确移除对应 pending（content 被 LLM 改写、ts 前后端不同源，旧的三元匹配必失败 → 永久卡
  // 「处理中」）。client_id 缺失（异常/旧后端）时不误删，仅 bump version。notesVersion 递增触发 refetch。
  noteProcessed: (m) =>
    set((s) => {
      // 移除前先取对应 pending 的原文，供回执「↩ 其实是提问」改判重发（content 被 LLM 改写，故用 rawText）。
      const matched = m.client_id
        ? s.pendingNotes.find((p) => p.client_id === m.client_id)
        : undefined
      return {
        pendingNotes: m.client_id
          ? s.pendingNotes.filter((p) => p.client_id !== m.client_id)
          : s.pendingNotes,
        notesVersion: s.notesVersion + 1,
        // 就地队列：落定时推一条 note 回执（done 态，组件 3s 后 dismissReceipt 自走）。
        feedReceipts: m.client_id
          ? [
              ...s.feedReceipts,
              {
                client_id: m.client_id,
                category: m.category,
                content: m.content,
                rawText: matched?.rawText ?? m.content,
                ts: m.ts,
              },
            ]
          : s.feedReceipts,
      }
    }),

  // 4.I：NP 失败 → 按 client_id 把对应 pending 标失败态（保留在列表，渲染红 + reason + 重试），
  // 而非移除或永久卡「处理中」。client_id 缺失（异常/旧链路）时不误标，仅原样返回。
  noteFailed: (m) =>
    set((s) => ({
      pendingNotes: m.client_id
        ? s.pendingNotes.map((p) =>
            p.client_id === m.client_id ? { ...p, failedReason: m.reason } : p,
          )
        : s.pendingNotes,
    })),

  // 重试：把失败 pending 乐观打回「处理中」（清 failedReason），调用方随后用同 client_id 重投。
  retryPending: (clientId) =>
    set((s) => ({
      pendingNotes: s.pendingNotes.map((p) =>
        p.client_id === clientId ? { ...p, failedReason: undefined } : p,
      ),
    })),

  setRecording: (recording) =>
    set((state) => (state.isRecording === recording ? {} : { isRecording: recording })),

  // device.warning：设备拔走提示；null=清空（手动 dismiss）。
  setDeviceWarning: (message) =>
    set((state) => (state.deviceWarning === message ? {} : { deviceWarning: message })),

  // audio.level：每帧同时写 rms 值和到达时间戳，供电平条判断新鲜度后混合。
  setBackendLevel: (rms) => set(() => ({ backendLevel: rms, backendLevelTs: Date.now() })),

  // viewer.count：后端广播的在线观看数；onClose 调 setViewerCount(0) 清陈旧值。
  setViewerCount: (count) => set(() => ({ viewerCount: count })),

  // tool.call：追加一条工具调用轨迹，有界保留最近 TOOL_CALLS_MAX 条（超出从头丢）。
  appendToolCall: (entry) =>
    set((s) => {
      const next = [...s.toolCalls, entry]
      return { toolCalls: next.length > TOOL_CALLS_MAX ? next.slice(-TOOL_CALLS_MAX) : next }
    }),

  // 放弃失败 pending：用户主动关掉这条失败行，不再重试，直接移除。
  dismissPending: (clientId) =>
    set((s) => ({ pendingNotes: s.pendingNotes.filter((p) => p.client_id !== clientId) })),

  // 就地回执 3s 后由组件调用，按 client_id 移除（让回执飘走，不长期占席）。
  dismissReceipt: (clientId) =>
    set((s) => ({ feedReceipts: s.feedReceipts.filter((r) => r.client_id !== clientId) })),

  // QP 问答：提交即乐观插 processing；qp.answer WS（按 client_id resolveQa）填 done；异常填 failed。
  // query 项就地 lingers（不像 note 回执 3s 自走），点开看长答案，由 dismissQaInline 手动收进档案。
  addQa: (q) => set((s) => ({ qaItems: [...s.qaItems, q] })),
  resolveQa: (clientId, answer) =>
    set((s) => ({
      qaItems: resolveQaItems(s.qaItems, clientId, answer),
      // QP 新答案进档案 → 未读 +1（打开档案清 0）。
      archiveUnread: s.archiveUnread + 1,
    })),

  // QP 答案到达时把答案落进队列。两种 client_id 来源：
  //  1. 文本 query：提交时已 addQa 一条 processing qaItem（MemoInput 的 postNote.then 分支）。
  //     命中它 → 等价 resolveQa（置 done + answer + archiveUnread+1）。
  //  2. 语音 query：提交 202 只回 kind="dispatching"，那刻不知 note/query，故只插了一条
  //     kind="voice" 的 pending、没 addQa。答案到达此刻才确定是 query → 撤掉那条语音 pending，
  //     新建一条 done qaItem 进队列/档案。MVP 局限：qp.answer 只带 answer_text/client_id 不带
  //     问题原文，语音 pending 的 rawText 为空，故问题文案只能用占位「🎤 语音提问」。
  //  3. 既无 qaItem 也无 pending（陈旧/旧广播）→ no-op。
  qpAnswerArrived: (clientId, answerText) =>
    set((s) => {
      if (s.qaItems.some((q) => q.client_id === clientId)) {
        return {
          qaItems: resolveQaItems(s.qaItems, clientId, answerText),
          archiveUnread: s.archiveUnread + 1,
        }
      }
      const pending = s.pendingNotes.find(
        (p) => p.client_id === clientId && p.kind === "voice",
      )
      if (pending) {
        return {
          pendingNotes: s.pendingNotes.filter((p) => p.client_id !== clientId),
          qaItems: [
            ...s.qaItems,
            {
              client_id: clientId,
              // 语音 query 无问题原文（rawText 空），用通用占位。content 是「语音备注」的乐观
              // 文案，对 query 而言是错标，故不用它。
              question: pending.rawText || "🎤 语音提问",
              status: "done",
              answer: answerText,
              ts: pending.ts,
            },
          ],
          archiveUnread: s.archiveUnread + 1,
        }
      }
      return {}
    }),
  failQa: (clientId, reason) =>
    set((s) => ({
      qaItems: s.qaItems.map((q) =>
        q.client_id === clientId ? { ...q, status: "failed", failedReason: reason } : q,
      ),
    })),
  dismissQaInline: (clientId) =>
    set((s) => ({
      qaItems: s.qaItems.map((q) =>
        q.client_id === clientId ? { ...q, inlineDismissed: true } : q,
      ),
    })),

  // 打开档案 Sheet 时清未读（看过即已读）。
  markArchiveRead: () => set((s) => (s.archiveUnread === 0 ? {} : { archiveUnread: 0 })),

  // 清实时转录（REC 开始 / dev 注入开始时调，避免上一条 take 的转录残留）。
  resetSegments: () => set(() => ({ segments: { ch1: [], ch2: [] } })),
}))
