/// <reference lib="webworker" />
import { AutoProcessor, env, Gemma4ForConditionalGeneration, RawImage, TextStreamer } from '@huggingface/transformers'
import type { ModelState } from '../services/localAI'
import { MOBILE_MODEL_ID, WEB_MODEL_ID, BUNDLED_MODEL_FOLDER, MODEL_SOURCE } from '../config/model'

env.allowLocalModels = MODEL_SOURCE === 'bundled'
env.allowRemoteModels = MODEL_SOURCE === 'remote'
env.localModelPath = '/models/'
env.useBrowserCache = true

// Resolved once at worker startup; avoids repeated UA parsing on each generate call
const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)
const EFFECTIVE_MODEL_ID = (import.meta.env.VITE_GEMMA_MODEL_ID as string | undefined)
  || (MODEL_SOURCE === 'bundled' ? BUNDLED_MODEL_FOLDER : isMobile ? MOBILE_MODEL_ID : WEB_MODEL_ID)

let model: InstanceType<typeof Gemma4ForConditionalGeneration> | null = null
let processor: Awaited<ReturnType<typeof AutoProcessor.from_pretrained>> | null = null
let initializing: Promise<boolean> | null = null
let cancelled = false

function post(type: string, payload: Record<string, unknown> = {}) {
  self.postMessage({ type, ...payload })
}

function setState(state: ModelState) {
  post('STATE', { state })
}

async function initialize() {
  if (model && processor) return true
  if (initializing) return initializing
  initializing = (async () => {
    if (!('gpu' in navigator)) {
      setState({ status: 'unsupported', progress: 0, detail: '当前浏览器不支持 WebGPU' })
      return false
    }
    try {
      setState({ status: 'checking', progress: 0 })
      const gpu = (navigator as Navigator & { gpu: { requestAdapter(): Promise<unknown> } }).gpu
      if (!await gpu.requestAdapter()) throw new Error('未找到可用 GPU')
      const modelLabel = MODEL_SOURCE === 'bundled' ? '随包模型' : isMobile ? '移动端优化模型' : '桌面端模型'
      const progressByFile = new Map<string, number>()
      const progress_callback = (info: { status?: string; file?: string; progress?: number }) => {
        if (info.file && info.status === 'progress') {
          progressByFile.set(info.file, info.progress ?? 0)
          const values = [...progressByFile.values()]
          const progress = Math.round(values.reduce((sum, value) => sum + value, 0) / Math.max(1, values.length))
          setState({ status: 'downloading', progress: Math.min(progress, 95), detail: modelLabel })
        }
      }
      const loaded = await Promise.all([
        Gemma4ForConditionalGeneration.from_pretrained(EFFECTIVE_MODEL_ID, { dtype: 'q4f16', device: 'webgpu', progress_callback }),
        AutoProcessor.from_pretrained(EFFECTIVE_MODEL_ID, { progress_callback }),
      ])
      model = loaded[0] as InstanceType<typeof Gemma4ForConditionalGeneration>
      processor = loaded[1]
      setState({ status: 'ready', progress: 100 })
      return true
    } catch (error) {
      setState({ status: 'error', progress: 0, detail: error instanceof Error ? error.message : String(error) })
      initializing = null
      return false
    }
  })()
  return initializing
}

async function analyzeImage(buffer: ArrayBuffer, mimeType: string, prompt: string): Promise<string> {
  if (!model || !processor) throw new Error('模型尚未下载或初始化')
  const blob = new Blob([buffer], { type: mimeType })
  const image = await RawImage.fromBlob(blob)
  const messages = [
    {
      role: 'user',
      content: [
        { type: 'image' },
        { type: 'text', text: prompt },
      ],
    },
  ]
  const tokenizer = processor.tokenizer!
  const text = (tokenizer as unknown as { apply_chat_template(m: unknown, o: unknown): string }).apply_chat_template(messages, {
    tokenize: false,
    add_generation_prompt: true,
  })
  // processor(text, images) produces multimodal inputs including pixel_values
  const inputs = await (processor as unknown as (t: string, imgs: RawImage[], o: unknown) => Promise<Record<string, unknown>>)(
    text,
    [image],
    { return_tensors: 'pt' },
  )
  try {
    const outputIds = await model.generate({
      ...inputs,
      max_new_tokens: 512,
      do_sample: false,
    } as never) as unknown as { dims: number[]; tolist(): number[][] }
    const inputLen = (inputs.input_ids as { dims: number[] }).dims[1]
    const newTokenIds = outputIds.tolist()[0].slice(inputLen)
    return (tokenizer as unknown as { decode(ids: number[], o: unknown): string })
      .decode(newTokenIds, { skip_special_tokens: true })
      .trim()
  } finally {
    Object.values(inputs).forEach((v) => (v as { dispose?: () => void })?.dispose?.())
  }
}

async function generate(id: string, messages: Array<{ role: string; content: string }>, maxTokens: number) {
  if (!model || !processor) throw new Error('模型尚未下载或初始化')
  cancelled = false
  const tokenizer = processor.tokenizer!
  const prompt = (tokenizer as unknown as { apply_chat_template(messages: unknown, options: unknown): string }).apply_chat_template(messages, {
    tokenize: false,
    add_generation_prompt: true,
  })
  const inputs = tokenizer(prompt, { add_special_tokens: false, return_tensor: 'pt' } as never)
  let result = ''
  const streamer = new TextStreamer(tokenizer, {
    skip_prompt: true,
    skip_special_tokens: true,
    callback_function: (text: string) => {
      if (cancelled) return
      result += text
      post('CHUNK', { id, text })
    },
  })
  try {
    if (cancelled) throw new Error('任务已取消')
    await model.generate({ ...inputs, max_new_tokens: maxTokens, do_sample: false, streamer } as never)
  } finally {
    Object.values(inputs).forEach((value) => (value as { dispose?: () => void })?.dispose?.())
  }
  if (cancelled) throw new Error('任务已取消')
  return result
}

self.onmessage = async (event: MessageEvent) => {
  const data = event.data as {
    type: string
    id?: string
    messages?: Array<{ role: string; content: string }>
    maxTokens?: number
    buffer?: ArrayBuffer
    mimeType?: string
    prompt?: string
  }
  if (data.type === 'CANCEL') {
    cancelled = true
    return
  }
  if (!data.id) return
  try {
    if (data.type === 'INIT') {
      post('DONE', { id: data.id, ok: await initialize() })
      return
    }
    if (data.type === 'GENERATE') {
      const result = await generate(data.id, data.messages ?? [], data.maxTokens ?? 640)
      post('DONE', { id: data.id, result })
      return
    }
    if (data.type === 'ANALYZE_IMAGE') {
      if (!data.buffer || !data.mimeType || !data.prompt) throw new Error('ANALYZE_IMAGE 缺少必要参数')
      const result = await analyzeImage(data.buffer, data.mimeType, data.prompt)
      post('DONE', { id: data.id, result })
      return
    }
  } catch (error) {
    post('ERROR', { id: data.id, error: error instanceof Error ? error.message : String(error) })
  }
}

export {}
