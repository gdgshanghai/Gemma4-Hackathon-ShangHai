import { WS_BASE } from "@/lib/config"

// 纯传输层，不依赖 React / store。回调由 useLiveConnection 注入，避免循环依赖。

export interface LiveSocketHandlers {
  onMessage: (topic: string, payload: unknown) => void
  onOpen: () => void
  onClose: () => void
  // 断线后重连成功时回调（首连不触发），用于 refetch getTakes 对齐错过的 take.changed。
  onReconnect: () => void
}

const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 30_000

export class LiveSocket {
  private ws: WebSocket | null = null
  private token: string
  private handlers: LiveSocketHandlers
  private attempt = 0
  private hadOpened = false
  private manualClose = false
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null

  constructor(token: string, handlers: LiveSocketHandlers) {
    this.token = token
    this.handlers = handlers
  }

  connect(): void {
    this.manualClose = false
    this.open()
  }

  private open(): void {
    const url = `${WS_BASE}/ws?token=${encodeURIComponent(this.token)}`
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      const wasReconnect = this.hadOpened
      this.hadOpened = true
      this.attempt = 0
      this.handlers.onOpen()
      if (wasReconnect) this.handlers.onReconnect()
    }

    ws.onmessage = (ev) => {
      try {
        const env = JSON.parse(ev.data as string) as { topic?: string; payload?: unknown }
        if (typeof env.topic === "string") {
          this.handlers.onMessage(env.topic, env.payload)
        }
      } catch {
        // 非 JSON / 畸形信封：忽略，不影响连接。
      }
    }

    ws.onclose = () => {
      this.handlers.onClose()
      if (!this.manualClose) this.scheduleReconnect()
    }

    ws.onerror = () => {
      // onclose 会随后触发并处理重连；这里不重复调度。
      ws.close()
    }
  }

  private scheduleReconnect(): void {
    const delay = Math.min(BASE_DELAY_MS * 2 ** this.attempt, MAX_DELAY_MS)
    this.attempt += 1
    this.reconnectTimer = setTimeout(() => this.open(), delay)
  }

  close(): void {
    this.manualClose = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onclose = null
      this.ws.onerror = null
      this.ws.close()
      this.ws = null
    }
  }
}
