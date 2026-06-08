import { useRef, useState } from "react"
import { Mic, ArrowUp } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { postNote, postVoiceNote } from "@/lib/api"
import { CONN_ID } from "@/lib/connId"
import { newClientId } from "@/lib/feed-actions"
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder"
import { useSessionStore } from "@/store/session"

// 底部栏的打字 memo 输入（场记真实输入口）。接 POST /notes 并带 CONN_ID：后端块③调度器自动判
// note / query（用户发送时不打前缀，回溯地按 kind 渲染）。普通备注 → 乐观 pending → note.processed
// 落定转就地回执；判为 query → 撤掉乐观 note、转一条就地 qaItem「正在查询…」，答案经
// qp.answer.{CONN_ID} WS 到达时由 qpAnswerArrived 按 client_id 落到对应那条。类别走 @语法
//（@ 开头后端跳过分类强制 note）。麦克风按住录音（4.L）→ 16k WAV → POST /notes/voice →
// Gemma 原生音频归置；语音判为 query 时无同步 kind，答案到达才 promote 进队列（见 uploadVoice）。
export default function MemoInput() {
  const [text, setText] = useState("")
  const addPendingNote = useSessionStore((s) => s.addPendingNote)
  const recorder = useVoiceRecorder()
  // 当前手势是否在录音（守卫 start 的 async 间隙 + 避免 up/leave 重复触发）。
  const gestureRef = useRef(false)

  // 文本提交：乐观 pending 提前到 await 之前（提交即显「处理中」，藏掉后端 classify 串行延迟），
  // 提交转后台不阻塞输入。后端判这条其实是查询（kind=query）→ 撤掉刚插的 note pending、转一条
  // 就地 qaItem 占位，答案靠 qp.answer WS 回灌；普通备注照旧等 note.processed 落定转回执。
  const handleSubmit = () => {
    const trimmed = text.trim()
    if (!trimmed || recorder.recording) return
    const clientId = newClientId()
    const ts = Date.now() / 1000
    addPendingNote({
      client_id: clientId,
      kind: "text",
      ts,
      category: "note", // 占位；note.processed 回灌时按 client_id 转成真类别（query 命中则撤掉）
      content: trimmed,
      rawText: trimmed, // 失败重试据此重投同文本
    })
    setText("")
    postNote(trimmed, undefined, clientId, CONN_ID)
      .then((resp) => {
        if (resp.kind === "query") {
          // 实为查询：撤掉乐观插的 note pending（它不落库、无 note.processed 回灌），转一条就地
          // qaItem 占位「正在查询…」，答案经 qp.answer.{CONN_ID} 按 client_id resolveQa 落到这条。
          const s = useSessionStore.getState()
          s.removePending(clientId)
          s.addQa({ client_id: clientId, question: trimmed, status: "processing", ts })
        }
      })
      .catch(() => {
        // 网络/上传层失败 → 标失败态（用 client_id 精确定位），不卡处理中。
        useSessionStore.getState().noteFailed({ reason: "upload_failed", ts, client_id: clientId })
      })
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // ── 语音 note：按住麦克风录音（对讲机式）──

  const uploadVoice = async (wav: Blob) => {
    const clientId = newClientId()
    const ts = Date.now() / 1000
    // 乐观 pending：语音的类别/正文 202 时未知（由模型从音频判）。kind=voice → 渲染只显「语音备注」
    // 不显 @category（避免伪造类别）；voiceBlob 供失败重试重传。
    addPendingNote({
      client_id: clientId,
      kind: "voice",
      ts,
      category: "note",
      content: "语音备注",
      rawText: "",
      voiceBlob: wav,
    })
    try {
      // 带 CONN_ID（对齐文本 postNote）：后端 voice dispatch 判这条是 note 还是 query。
      // 这里不 addQa——202 只回 kind="dispatching"，此刻还不知 note/query，只挂一条 kind="voice"
      // 的 pending。query 分支的答案不在 202 里返回，等 qp.answer.{CONN_ID} 到达时由
      // useLiveConnection 调 qpAnswerArrived：撤掉这条语音 pending，promote 成一条 done qaItem
      // 进就地队列/档案（避免永久卡处理中）。
      await postVoiceNote(wav, clientId, ts, CONN_ID)
    } catch {
      // 网络层失败 → 标失败态（用 client_id 精确定位），不卡处理中。upload_failed 区别于后端 NP timeout。
      useSessionStore.getState().noteFailed({ reason: "upload_failed", ts, client_id: clientId })
    }
  }

  const handleMicDown = async (e: React.PointerEvent) => {
    e.preventDefault()
    if (gestureRef.current) return
    gestureRef.current = true
    try {
      await recorder.start()
    } catch {
      gestureRef.current = false
      alert("无法访问麦克风（检查浏览器权限 / 局域网需 HTTPS）")
    }
  }

  const handleMicUp = async () => {
    if (!gestureRef.current) return
    gestureRef.current = false
    const wav = await recorder.stop() // null=太短（误触），静默丢弃
    if (wav) await uploadVoice(wav)
  }

  const handleMicCancel = () => {
    if (!gestureRef.current) return // 上滑离开按钮 / pointercancel → 取消不提交
    gestureRef.current = false
    recorder.cancel()
  }

  return (
    <div className="flex items-center gap-2 h-11 px-4 rounded-4xl bg-muted">
      <Input
        placeholder={
          recorder.recording
            ? "录音中…松开发送，上滑取消"
            : "Typing memo / 提问 · 第三条结尾好（@keep）｜ 第三场 NG 几条？"
        }
        className="flex-1 bg-transparent border-0 ring-0 rounded-none text-sm focus:outline-none placeholder:text-muted-foreground/70 focus-visible:ring-0"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={recorder.recording}
      />
      <Button
        variant="ghost"
        size="icon-sm"
        className="rounded-full text-muted-foreground hover:text-foreground disabled:opacity-40"
        onClick={handleSubmit}
        disabled={recorder.recording || !text.trim()}
        title="提交备注"
      >
        <ArrowUp className="size-4" />
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        className={
          "rounded-full select-none touch-none " +
          (recorder.recording
            ? "text-destructive bg-destructive/10"
            : "text-muted-foreground hover:text-foreground")
        }
        onPointerDown={handleMicDown}
        onPointerUp={handleMicUp}
        onPointerLeave={handleMicCancel}
        onPointerCancel={handleMicCancel}
        title="按住说话（松开发送，上滑取消）"
      >
        <Mic className={"size-4" + (recorder.recording ? " animate-pulse" : "")} />
      </Button>
    </div>
  )
}
