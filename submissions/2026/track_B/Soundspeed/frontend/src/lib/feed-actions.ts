import { postNote, postQuery } from "@/lib/api"
import { randomId } from "@/lib/uuid"
import { useSessionStore } from "@/store/session"

// client_id 全局唯一去重键（与 MemoInput 同源 randomId；局域网 HTTP 无 crypto 时回退，见 uuid.ts）。
export function newClientId(): string {
  return randomId("nid")
}

// 跑一条 QP 查询（显式强制查询，绕过 /notes 自动分类器）：乐观插 processing → 同步返回填 done /
// 异常填 failed。回执「↩ 其实是提问」误判兜底共用——异常自吞成 failed 态（有专门渲染），调用方不必 try/catch。
export async function runQuery(text: string): Promise<void> {
  const clientId = newClientId()
  const ts = Date.now() / 1000
  useSessionStore.getState().addQa({ client_id: clientId, question: text, status: "processing", ts })
  try {
    const r = await postQuery(text)
    useSessionStore.getState().resolveQa(clientId, r.answer)
  } catch (e) {
    useSessionStore.getState().failQa(clientId, e instanceof Error ? e.message : "查询失败")
  }
}

// 跑一条文本 note（显式强制备注，不带 conn_id → 后端跳过分类恒走 NP）：乐观优先插 pending（占位
// 类别 note / 正文原文），真类别/正文经 note.processed WS 回灌转成回执。QaRow「✎ 记为备注」误判兜底用。
export async function runNote(text: string): Promise<void> {
  const clientId = newClientId()
  const ts = Date.now() / 1000
  useSessionStore.getState().addPendingNote({
    client_id: clientId,
    kind: "text",
    ts,
    category: "note",
    content: text,
    rawText: text,
  })
  try {
    await postNote(text, undefined, clientId) // 无 conn_id = 强制 note，不触发块③分类
  } catch {
    useSessionStore.getState().noteFailed({ reason: "upload_failed", ts, client_id: clientId })
  }
}
