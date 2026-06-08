import { useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { getTake, takeQueryKey } from "@/lib/api"
import { CONN_ID } from "@/lib/connId"
import { LiveSocket } from "@/lib/ws"
import { useSessionStore } from "@/store/session"
import type { ToolCallEntry } from "@/store/session"
import type {
  AsrMsg,
  DeviceWarningMsg,
  LlmStatusMsg,
  NoteFailedMsg,
  NoteProcessedMsg,
  QpAnswerMsg,
  SceneChangedMsg,
  TakeChangedMsg,
  TakeDeletedMsg,
  TakeProcessingMsg,
  TakeSegmentsUpdatedMsg,
  ViewerCountMsg,
} from "@/types/api"

// ch 编码在 topic 后缀（asr.partial.ch1 / asr.final.ch2），不在 payload 里。
function parseAsrTopic(topic: string): { ch: 1 | 2; isFinal: boolean } | null {
  const m = /^asr\.(partial|final)\.ch([12])$/.exec(topic)
  if (!m) return null
  return { isFinal: m[1] === "final", ch: Number(m[2]) as 1 | 2 }
}

// 单 WS 连接，按 topic 分发进 store；token 变化（SettingsDialog 保存）时重连。
export function useLiveConnection(): void {
  const token = useSessionStore((s) => s.token)
  const queryClient = useQueryClient()

  useEffect(() => {
    const store = useSessionStore.getState()

    if (!token) {
      store.setConnection("no-token")
      return
    }

    store.setConnection("connecting")

    const socket = new LiveSocket(token, {
      onOpen: () => useSessionStore.getState().setConnection("open"),
      onClose: () => {
        const s = useSessionStore.getState()
        s.setConnection("closed")
        // 断开后在线数已失真，归 0 避免显示陈旧值；重连后服务端首帧 viewer.count 重填。
        s.setViewerCount(0)
      },
      onReconnect: () => {
        // 断线期间错过的 take.changed（尤其 L2 那条）靠重取 getTakes 对齐（spec §3.3）。
        queryClient.invalidateQueries({ queryKey: ["takes"] })
      },
      onMessage: (topic, payload) => {
        const s = useSessionStore.getState()
        const asr = parseAsrTopic(topic)
        if (asr) {
          s.applyAsr(asr.ch, asr.isFinal, payload as AsrMsg)
          return
        }
        if (topic === "take.changed") {
          s.applyTakeChanged(payload as TakeChangedMsg)
          return
        }
        if (topic === "take.segments.updated") {
          // diarization 回填完成：refetch 带 speaker 的 segments，替换 Live 框纯 ASR 文本。
          const m = payload as TakeSegmentsUpdatedMsg
          getTake(m.take_id)
            .then((detail) =>
              useSessionStore
                .getState()
                .applyBackfilledSegments(m.take_id, detail.segments),
            )
            .catch(() => {
              /* 网络/鉴权失败：忽略，下次 invalidate 重取 */
            })
          // take 详情 / 列表 query 失效（HistoryTakes 等据此重渲染结构化转录）。
          queryClient.invalidateQueries({ queryKey: takeQueryKey(m.take_id) })
          queryClient.invalidateQueries({ queryKey: ["takes"] })
          return
        }
        if (topic === "take.processing") {
          // take.end 后处理进度（分离说话人 / 生成摘要 / 完成 / 出错）→ Live 框状态条
          s.setTakeProcessing(payload as TakeProcessingMsg)
          return
        }
        if (topic === "take.deleted") {
          // 删除条目 store 只增不删（seedTakes 加性），故既显式 removeTake 又 invalidate 重取对齐。
          const { take_id } = payload as TakeDeletedMsg
          s.removeTake(take_id)
          queryClient.invalidateQueries({ queryKey: ["takes"] })
          return
        }
        if (topic === "scene.changed") {
          // 建/切场：场次列表 + 活跃场（pickActiveScene 读 is_active）靠重取 scenes 刷新。
          // payload 形状见 SceneChangedMsg；这里不读字段，权威以重取为准。
          void (payload as SceneChangedMsg)
          queryClient.invalidateQueries({ queryKey: ["scenes"] })
          return
        }
        if (topic === "llm.status") {
          const m = payload as LlmStatusMsg
          s.setLlm(m.state, m.task_type)
          return
        }
        if (topic === "note.processed") {
          const m = payload as NoteProcessedMsg
          s.noteProcessed(m)
          // 刷新受影响的 take：takes 列表（折叠态 take.notes）+ 该 take 详情（展开态 data.notes）。
          queryClient.invalidateQueries({ queryKey: ["takes"] })
          queryClient.invalidateQueries({ queryKey: takeQueryKey(m.take_id) })
          return
        }
        if (topic === "note.failed") {
          // 4.I：NP 失败 → 对应 pending 转失败态（红 + reason + 重试），不再永久卡处理中
          const m = payload as NoteFailedMsg
          s.noteFailed(m)
          return
        }
        if (topic === `qp.answer.${CONN_ID}`) {
          // 入口调度器查询答案：广播 send-to-all，按 CONN_ID 后缀认领本 tab，其余 tab 过滤掉。
          // 队列模型 promote：按 client_id 调 qpAnswerArrived。文本 query 命中预建的 processing
          // qaItem（/notes 分支已 addQa）→ 置 done + answer；语音 query 此刻才知是 query，命中
          // 那条语音 pending → 撤 pending 并新建一条 done qaItem 进队列/档案。缺 client_id 的旧广播
          // 无对应项 → no-op。「其实是提问」强制查询走同步 postQuery 不经此路。
          const m = payload as QpAnswerMsg
          if (m.client_id) s.qpAnswerArrived(m.client_id, m.answer_text)
          return
        }
        if (topic === "device.warning") {
          // 持久化设备被拔走 / 不在场，后端已回落 fallback；存进 store 供头部 amber 提示。
          s.setDeviceWarning((payload as DeviceWarningMsg).message)
          return
        }
        if (topic === "audio.level") {
          // 后端实际采集那路音频的归一化 RMS，仅录制时 ~5Hz 推。存值 + 时间戳，电平条按新鲜度
          // 决定用后端 rms 还是浏览器常驻 micLevel。
          s.setBackendLevel((payload as { rms: number }).rms)
          return
        }
        if (topic === "tool.call") {
          // 后端 agent 工具调用轨迹（全局事件，不带 conn_id 后缀）。push 进有界缓冲，
          // 设置页开发者 tab 的实时日志框消费。冻结契约见 ToolCallEntry。
          s.appendToolCall(payload as ToolCallEntry)
          return
        }
        if (topic === "viewer.count") {
          // 在线观看数：连接建立 / 断开时后端广播，驱动 header 眼睛计数。
          s.setViewerCount((payload as ViewerCountMsg).count)
          return
        }
      },
    })

    socket.connect()
    return () => socket.close()
  }, [token, queryClient])
}
