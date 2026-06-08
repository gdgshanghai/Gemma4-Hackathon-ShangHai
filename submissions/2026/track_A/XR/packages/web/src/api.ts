export type ProviderView = {
  provider: 'local_openai_compatible'
  baseUrl: string
  model: string
  hasApiKey: boolean
}

export type PlannedStep = {
  id: string
  title: string
  description: string
  toolName?: string
  toolImage?: string
}

export type PlanningTraceEntry = {
  id: string
  status: 'running' | 'completed' | 'failed'
  title: string
  detail?: string
  timestamp: string
}

export type ReviewToolCall = {
  id: string
  name: string
  origin: 'model_native' | 'model_schema' | 'system_grounding' | 'json_fallback'
  arguments: Record<string, unknown>
  status: 'requested' | 'completed' | 'failed'
  resultSummary?: string
  timestamp: string
}

export type ReviewAgentMemory = {
  prompt: string
  model: string
  selectedWorkflowKey?: string
  selectedWorkflowName?: string
  comparison?: string
  publicSafetyRules: string[]
  observedToyData: string[]
  toolCallIds: string[]
}

export type ReviewAgentTraceEntry = {
  id: string
  stage: 'understand' | 'plan' | 'ground' | 'execute' | 'reflect'
  status: 'running' | 'completed' | 'failed'
  title: string
  detail?: string
  timestamp: string
}

export type ReviewAgentRun = {
  mode: 'native_guided_tool_calling' | 'guided_tool_calling' | 'native_tool_calling' | 'json_fallback'
  model: string
  memory: ReviewAgentMemory
  toolCalls: ReviewToolCall[]
  trace: ReviewAgentTraceEntry[]
  artifactPaths?: {
    memory?: string
    toolCalls?: string
    trace?: string
  }
}

export type ConversationDecision = {
  action: 'answer' | 'clarify' | 'status' | 'run_analysis'
  message: string
  confidence: number
  source: 'fast_rule' | 'model' | 'fallback'
  reason?: string
  workflowKey?: string
  analysisPrompt?: string
}

export type ConversationRouteContext = {
  hasActiveTask?: boolean
  latestTaskStatus?: string
  previousAction?: ConversationDecision['action']
  previousWorkflowKey?: string
  previousAnalysisPrompt?: string
  previousMessage?: string
}

export type ModelPlan = {
  intent: string
  comparison: string
  steps: PlannedStep[]
  model: string
  rawResponse: string
  source: 'model' | 'fallback' | 'failed'
  sourceMessage?: string
  trace?: PlanningTraceEntry[]
  workflowKey?: string
  workflowName?: string
  executionMode?: 'executable'
  executionNote?: string
  sampleData?: {
    status: 'included' | 'reference_only'
    label: string
    description: string
    files: string[]
  }
  agentRun?: ReviewAgentRun
}

export type WorkflowView = {
  key: string
  name: string
  description: string
  executionMode: 'executable'
  executionNote: string
  sampleData: NonNullable<ModelPlan['sampleData']>
}

export type ToolRunRecord = {
  id: string
  name: string
  image: string
  command: string[]
  status: 'completed' | 'failed'
  startedAt: string
  finishedAt: string
  durationMs: number
  stdoutPath: string
  stderrPath: string
  outputFiles: string[]
}

export type TimelineEvent = {
  id: string
  phase: 'request' | 'planning' | 'execution' | 'model' | 'result'
  status: 'running' | 'completed' | 'failed'
  title: string
  detail?: string
  timestamp: string
  toolName?: string
  image?: string
  durationMs?: number
  outputFiles?: string[]
}

export type TaskRecord = {
  id: string
  prompt: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  createdAt: string
  updatedAt: string
  plan?: PlannedStep[]
  modelPlan?: ModelPlan
  agentRun?: ReviewAgentRun
  timeline: TimelineEvent[]
  error?: string
  result?: {
    workflowKey: string
    plan: PlannedStep[]
    qc?: Array<{
      sampleId: string
      condition: string
      reads: number
      averageLength: number
      gcPercent: number
    }>
    counts?: Record<string, Record<string, number>>
    differential?: Array<{
      gene: string
      controlMean: number
      treatmentMean: number
      log2FoldChange: number
      score: number
      direction: 'up' | 'down' | 'stable'
    }>
    tables: Array<{
      title: string
      columns: string[]
      rows: Array<Record<string, string | number>>
    }>
    modelPlan: ModelPlan
    agentRun?: ReviewAgentRun
    toolRuns: ToolRunRecord[]
    outputDir: string
    reportMarkdown: string
    summary: string
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.error || `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

export const api = {
  getProvider: () => request<ProviderView>('/api/provider'),
  getWorkflows: () => request<{ workflows: WorkflowView[] }>('/api/workflows'),
  saveProvider: (payload: Partial<ProviderView> & { apiKey?: string }) =>
    request<ProviderView>('/api/provider', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  testProvider: () => request<{ ok: boolean; message: string }>('/api/provider/test', { method: 'POST' }),
  plan: (prompt: string) =>
    request<{ plan: PlannedStep[]; modelPlan: ModelPlan }>('/api/plan', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    }),
  routeConversation: (message: string, context?: ConversationRouteContext) =>
    request<ConversationDecision>('/api/conversation/route', {
      method: 'POST',
      body: JSON.stringify({ message, context }),
    }),
  createTask: (prompt: string) =>
    request<TaskRecord>('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    }),
  getTask: (id: string) => request<TaskRecord>(`/api/tasks/${id}`),
  getTaskAgent: (id: string) => request<ReviewAgentRun>(`/api/tasks/${id}/agent`),
}
