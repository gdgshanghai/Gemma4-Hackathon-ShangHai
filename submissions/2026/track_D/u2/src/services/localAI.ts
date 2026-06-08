export type ModelStatus = 'idle' | 'checking' | 'downloading' | 'initializing' | 'ready' | 'unsupported' | 'error'

export interface ModelState {
  status: ModelStatus
  progress: number
  detail?: string
}

export interface GenerateOptions {
  messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>
  maxTokens?: number
  onChunk?: (text: string) => void
}

export interface LocalAIEngine {
  initialize(): Promise<boolean>
  generate(options: GenerateOptions): Promise<string>
  analyzeImage(file: File, prompt: string): Promise<string>
  cancel(): void
  subscribe(listener: (state: ModelState) => void): () => void
  clearCache(): Promise<void>
  state(): ModelState
}

type Pending = {
  resolve: (value: string | boolean) => void
  reject: (reason: Error) => void
  onChunk?: (text: string) => void
}

class BrowserLocalAI implements LocalAIEngine {
  private worker: Worker | null = null
  private current: ModelState = { status: 'idle', progress: 0 }
  private listeners = new Set<(state: ModelState) => void>()
  private pending = new Map<string, Pending>()

  private ensureWorker() {
    if (this.worker) return this.worker
    this.worker = new Worker(new URL('../workers/gemma.worker.ts', import.meta.url), { type: 'module' })
    this.worker.onmessage = (event) => {
      const data = event.data as { type: string; id?: string; state?: ModelState; text?: string; result?: string; error?: string; ok?: boolean }
      if (data.type === 'STATE' && data.state) {
        this.current = data.state
        this.listeners.forEach((listener) => listener(this.current))
        return
      }
      if (!data.id) return
      const task = this.pending.get(data.id)
      if (!task) return
      if (data.type === 'CHUNK' && data.text) task.onChunk?.(data.text)
      if (data.type === 'DONE') {
        this.pending.delete(data.id)
        task.resolve(data.result ?? data.ok ?? true)
      }
      if (data.type === 'ERROR') {
        this.pending.delete(data.id)
        task.reject(new Error(data.error || '本地模型任务失败'))
      }
    }
    return this.worker
  }

  private request<T extends string | boolean>(type: string, payload: Record<string, unknown> = {}, onChunk?: (text: string) => void) {
    const id = crypto.randomUUID()
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as Pending['resolve'], reject, onChunk })
      this.ensureWorker().postMessage({ type, id, ...payload })
    })
  }

  initialize() {
    return this.request<boolean>('INIT')
  }

  generate(options: GenerateOptions) {
    return this.request<string>('GENERATE', { messages: options.messages, maxTokens: options.maxTokens ?? 640 }, options.onChunk)
  }

  async analyzeImage(file: File, prompt: string) {
    const buffer = await file.arrayBuffer()
    return this.request<string>('ANALYZE_IMAGE', { buffer, mimeType: file.type, prompt })
  }

  cancel() {
    this.worker?.postMessage({ type: 'CANCEL' })
  }

  subscribe(listener: (state: ModelState) => void) {
    this.listeners.add(listener)
    listener(this.current)
    return () => this.listeners.delete(listener)
  }

  async clearCache() {
    this.cancel()
    this.worker?.terminate()
    this.worker = null
    this.current = { status: 'idle', progress: 0 }
    if ('caches' in window) {
      for (const name of await caches.keys()) {
        if (name.includes('transformers') || name.includes('u2-model')) await caches.delete(name)
      }
    }
    this.listeners.forEach((listener) => listener(this.current))
  }

  state() {
    return this.current
  }
}

export const localAI: LocalAIEngine = new BrowserLocalAI()
