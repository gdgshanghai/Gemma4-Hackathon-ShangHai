import { beforeEach, describe, expect, it } from "vitest"

import { useSessionStore } from "@/store/session"
import type { PendingNote, QaItem } from "@/types/api"

// qpAnswerArrived：QP 答案到达时把答案落进队列。store 是模块级单例，每个用例前重置相关切片。
describe("qpAnswerArrived", () => {
  beforeEach(() => {
    useSessionStore.setState({ qaItems: [], pendingNotes: [], archiveUnread: 0 })
  })

  it("命中预建的 processing qaItem（文本 query 路径）→ 置 done + answer", () => {
    const qa: QaItem = {
      client_id: "c-text",
      question: "第三场 NG 几条？",
      status: "processing",
      ts: 100,
    }
    useSessionStore.setState({ qaItems: [qa] })

    useSessionStore.getState().qpAnswerArrived("c-text", "NG 共 3 条。")

    const items = useSessionStore.getState().qaItems
    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({
      client_id: "c-text",
      question: "第三场 NG 几条？",
      status: "done",
      answer: "NG 共 3 条。",
    })
    expect(useSessionStore.getState().archiveUnread).toBe(1)
  })

  it("无 qaItem 但有匹配的语音 pending → 撤 pending + 新增 done qaItem（fallback 问题文案）", () => {
    const pending: PendingNote = {
      client_id: "c-voice",
      kind: "voice",
      ts: 200,
      category: "note",
      content: "语音备注",
      rawText: "",
    }
    useSessionStore.setState({ pendingNotes: [pending] })

    useSessionStore.getState().qpAnswerArrived("c-voice", "这是语音查询的答案。")

    const state = useSessionStore.getState()
    // 语音 pending 被移除
    expect(state.pendingNotes.find((p) => p.client_id === "c-voice")).toBeUndefined()
    // 新增一条 done qaItem，问题用通用占位（语音 query 无问题原文）
    expect(state.qaItems).toHaveLength(1)
    expect(state.qaItems[0]).toMatchObject({
      client_id: "c-voice",
      question: "🎤 语音提问",
      status: "done",
      answer: "这是语音查询的答案。",
      ts: 200,
    })
    expect(state.archiveUnread).toBe(1)
  })

  it("既无 qaItem 也无 pending（陈旧/旧广播）→ no-op", () => {
    useSessionStore.getState().qpAnswerArrived("c-unknown", "孤儿答案")

    const state = useSessionStore.getState()
    expect(state.qaItems).toHaveLength(0)
    expect(state.pendingNotes).toHaveLength(0)
    expect(state.archiveUnread).toBe(0)
  })
})
