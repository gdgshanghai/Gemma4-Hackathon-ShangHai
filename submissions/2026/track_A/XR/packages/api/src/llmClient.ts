import type { ModelPlan, PlanningTraceEntry, ProviderConfig } from './types.js'
import { defaultWorkflow, findWorkflow, workflowCatalog, type WorkflowContract } from './workflowCatalog.js'

const llmEngineUrl = process.env.LLM_ENGINE_URL || 'http://127.0.0.1:8011'

export type ChatToolCall = {
  id?: string
  type?: string
  function?: {
    name?: string
    arguments?: string | Record<string, unknown>
  }
}

export type ChatWithToolsResponse = {
  content: string
  toolCalls: ChatToolCall[]
  error?: string
}

export type ModelResponseFormat = 'text' | 'json_object'

function traceEntry(
  id: string,
  status: PlanningTraceEntry['status'],
  title: string,
  detail?: string,
): PlanningTraceEntry {
  return {
    id,
    status,
    title,
    detail,
    timestamp: new Date().toISOString(),
  }
}

export async function requestModelSummary(
  provider: ProviderConfig,
  messages: Array<{ role: 'system' | 'user'; content: string }>,
  fallback = 'Model interpretation unavailable; inspect the generated tool outputs for the computed results.',
): Promise<string> {
  if (process.env.DEMO_SKIP_MODEL_SUMMARY === '1') {
    return fallback
  }

  try {
    const response = await fetch(`${llmEngineUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider,
        messages,
        temperature: 0.2,
        maxTokens: 100,
        timeoutSeconds: 90,
      }),
    })

    if (!response.ok) {
      return fallback
    }

    const payload = await response.json() as { content?: string }
    return cleanModelSummary(payload.content || '') || fallback
  } catch {
    return fallback
  }
}

export async function requestModelChatWithTools(
  provider: ProviderConfig,
  messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>,
  tools: Array<Record<string, unknown>>,
  toolChoice: 'auto' | 'none' | Record<string, unknown> | undefined = 'auto',
  reasoningEffort = 'none',
  timeoutSeconds = 45,
  maxTokens = 256,
  responseFormat: ModelResponseFormat = 'text',
): Promise<ChatWithToolsResponse> {
  // 中文：API 层通过本地 LLM adapter 发送 OpenAI-compatible tools/tool_choice，保留 Gemma 4 原生 tool_calls。
  // EN: The API sends OpenAI-compatible tools/tool_choice through the local LLM adapter and preserves Gemma 4 native tool_calls.
  const body: Record<string, unknown> = {
    provider,
    messages,
    reasoningEffort,
    temperature: 0,
    maxTokens,
    timeoutSeconds,
    responseFormat,
  }
  if (tools.length) {
    body.tools = tools
    if (toolChoice !== undefined) {
      body.toolChoice = toolChoice
    }
  }

  const response = await fetch(`${llmEngineUrl}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    return {
      content: '',
      toolCalls: [],
      error: `Tool calling HTTP ${response.status}.`,
    }
  }

  const payload = await response.json() as { content?: string; tool_calls?: ChatToolCall[]; error?: string }
  return {
    content: payload.content || '',
    toolCalls: Array.isArray(payload.tool_calls) ? payload.tool_calls : [],
    error: payload.error,
  }
}

function cleanModelSummary(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return ''
  const finalAnswerMatch = trimmed.match(/final answer\s*:?\s*([\s\S]*)$/i)
  const candidate = (finalAnswerMatch?.[1] || trimmed)
    .replace(/^(thinking process|reasoning)\s*:?\s*/i, '')
    .trim()
  const lines = candidate
    .split(/\r?\n/)
    .map((line) => line.replace(/^[-*\d.)\s]+/, '').trim())
    .filter(Boolean)
    .filter((line) => !/^(analy[sz]e|the user wants|based on|toy rna-seq result)/i.test(line))
  const sentence = lines.find((line) => /gene|upregulated|downregulated|stable|treatment|control/i.test(line)) || lines[0]
  return sentence ? sentence.slice(0, 320) : ''
}

function defaultPlan(
  model: string,
  rawResponse = '',
  sourceMessage = 'Fallback workflow template was used.',
  trace: PlanningTraceEntry[] = [],
  workflow: WorkflowContract = defaultWorkflow(),
): ModelPlan {
  return {
    intent: workflow.description,
    comparison: workflow.key === 'bulk_rna_seq' ? 'treatment vs control' : 'condition comparison',
    model,
    rawResponse,
    source: 'fallback',
    sourceMessage,
    trace,
    workflowKey: workflow.key,
    workflowName: workflow.name,
    executionMode: workflow.executionMode,
    executionNote: workflow.executionNote,
    sampleData: workflow.sampleData,
    steps: workflow.steps,
  }
}

function failedPlan(
  model: string,
  rawResponse: string,
  sourceMessage: string,
  trace: PlanningTraceEntry[],
): ModelPlan {
  return {
    intent: 'Planning failed before a workflow could be selected.',
    comparison: 'not available',
    model,
    rawResponse,
    source: 'failed',
    sourceMessage,
    trace,
    steps: [],
  }
}

function extractJsonObject(text: string): unknown {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  const candidate = fenced?.[1] ?? text
  const start = candidate.indexOf('{')
  const end = candidate.lastIndexOf('}')
  if (start < 0 || end <= start) {
    throw new Error('No JSON object found in model response.')
  }
  return JSON.parse(candidate.slice(start, end + 1))
}

function extractWorkflowKeyFromText(text: string): string {
  const normalized = text.toLowerCase()
  const matches = workflowCatalog
    .map((workflow) => workflow.key)
    .filter((key) => normalized.includes(key.toLowerCase()))

  if (matches.length === 1) return matches[0]
  if (matches.length > 1) {
    const last = matches
      .map((key) => ({ key, index: normalized.lastIndexOf(key.toLowerCase()) }))
      .sort((a, b) => b.index - a.index)[0]
    return last.key
  }

  throw new Error('No workflowKey found in model response.')
}

function planFromWorkflowSelection(
  payload: unknown,
  provider: ProviderConfig,
  rawResponse: string,
  trace: PlanningTraceEntry[],
): ModelPlan {
  const record = payload && typeof payload === 'object' ? payload as Record<string, unknown> : {}
  const workflowKey = String(record.workflowKey || extractWorkflowKeyFromText(rawResponse))
  const workflow = findWorkflow(workflowKey)
  return {
    intent: String(record.intent || workflow.description),
    comparison: String(record.comparison || (workflow.key === 'bulk_rna_seq' ? 'treatment vs control' : 'condition comparison')),
    model: provider.model,
    rawResponse,
    source: 'model',
    sourceMessage: 'Gemma 4 selected the workflow; executable steps and runtimes were grounded against the public demo workflow contract.',
    trace,
    workflowKey: workflow.key,
    workflowName: workflow.name,
    executionMode: workflow.executionMode,
    executionNote: workflow.executionNote,
    sampleData: workflow.sampleData,
    steps: workflow.steps,
  }
}

export async function requestModelPlan(provider: ProviderConfig, prompt: string): Promise<ModelPlan> {
  const trace: PlanningTraceEntry[] = [
    traceEntry('planning-input', 'completed', 'Read analysis request', `Prompt length: ${prompt.trim().length} characters.`),
  ]

  if (process.env.DEMO_SKIP_MODEL_PLANNING === '1') {
    trace.push(traceEntry('planning-model', 'completed', 'Use fallback planning path', 'Model planning was skipped by DEMO_SKIP_MODEL_PLANNING.'))
    trace.push(traceEntry('planning-contracts', 'completed', 'Attach public workflow contracts', 'Bulk RNA-seq, single-cell RNA-seq, and proteomics planning contracts are available.'))
    return defaultPlan(provider.model, '', 'Model planning was skipped by DEMO_SKIP_MODEL_PLANNING.', trace)
  }

  try {
    // 中文：这是非 tool-calling 的 JSON 规划兜底路径，只在 Review Agent 原生函数调用失败或被跳过时使用。
    // EN: This is the non-tool-calling JSON planning fallback, used only when the Review Agent native function-calling path fails or is skipped.
    trace.push(traceEntry('planning-model', 'running', 'Request workflow selection from model', `Sending a compact workflow-selection prompt to ${provider.model}.`))
    const response = await fetch(`${llmEngineUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider,
        temperature: 0,
        maxTokens: 768,
        timeoutSeconds: 90,
        responseFormat: 'json_object',
        messages: [
          {
            role: 'system',
            content: [
              'Choose one workflow key only: bulk_rna_seq, single_cell_rna_seq, proteomics_lfq.',
              'Output one compact JSON object only. No markdown. No explanation.',
              '{"workflowKey":"...","intent":"...","comparison":"..."}',
              'bulk_rna_seq = bulk RNA-seq from FASTQ reads.',
              'single_cell_rna_seq = 10x-style single-cell RNA-seq clustering and marker genes.',
              'proteomics_lfq = label-free proteomics differential abundance.',
            ].join('\n'),
          },
          {
            role: 'user',
            content: prompt,
          },
        ],
      }),
    })

    if (!response.ok) {
      trace.push(traceEntry('planning-model', 'failed', 'Model planning request failed', `Planner HTTP ${response.status}.`))
      return failedPlan(provider.model, `Planner HTTP ${response.status}`, `Planner HTTP ${response.status}.`, trace)
    }

    const payload = await response.json() as { content?: string; error?: string }
    if (payload.error) {
      trace.push(traceEntry('planning-model', 'failed', 'Model returned an error', payload.error))
      return failedPlan(provider.model, payload.error, payload.error, trace)
    }
    const rawResponse = payload.content?.trim() || ''
      trace.push(traceEntry('planning-model', 'completed', 'Model response received', rawResponse ? `Received ${rawResponse.length} characters of workflow-selection text.` : 'The model returned an empty message.'))
    try {
      const parsed = extractJsonObject(rawResponse)
      const workflow = findWorkflow((parsed as Record<string, unknown>).workflowKey)
      trace.push(traceEntry('planning-parse', 'completed', 'Parse workflow selection JSON', 'The response was parsed into workflow choice, intent, and comparison.'))
      trace.push(traceEntry('planning-contracts', 'completed', 'Ground workflow tools', `Selected ${workflow.name}. Executable steps and runtimes were grounded against public demo workflow contracts.`))
      return planFromWorkflowSelection(parsed, provider, rawResponse, trace)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Planner JSON parsing failed'
      try {
        const workflowKey = extractWorkflowKeyFromText(rawResponse)
        const workflow = findWorkflow(workflowKey)
        trace.push(traceEntry('planning-parse', 'completed', 'Parse workflowKey from model text', `The model text explicitly selected ${workflowKey}.`))
        trace.push(traceEntry('planning-contracts', 'completed', 'Ground workflow tools', `Selected ${workflow.name}. Executable steps and runtimes were grounded against public demo workflow contracts.`))
        return planFromWorkflowSelection({ workflowKey }, provider, rawResponse, trace)
      } catch (textError) {
        const textMessage = textError instanceof Error ? textError.message : 'Workflow selection parsing failed'
        trace.push(traceEntry('planning-parse', 'failed', 'Parse workflowKey from model text', textMessage))
        return failedPlan(provider.model, rawResponse, `${message}; ${textMessage}`, trace)
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Planner request failed'
    trace.push(traceEntry('planning-model', 'failed', 'Model planning request failed', message))
    return failedPlan(provider.model, message, message, trace)
  }
}

export async function testModelConnection(provider: ProviderConfig): Promise<{ ok: boolean; message: string }> {
  try {
    const response = await fetch(`${llmEngineUrl}/test-provider`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider }),
    })
    const payload = await response.json() as { ok?: boolean; message?: string }
    return {
      ok: Boolean(payload.ok),
      message: payload.message || (response.ok ? 'Endpoint responded.' : 'Endpoint check failed.'),
    }
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : 'Endpoint check failed.',
    }
  }
}
