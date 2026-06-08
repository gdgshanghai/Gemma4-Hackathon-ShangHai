export type ProviderConfig = {
  provider: 'local_openai_compatible'
  baseUrl: string
  apiKey: string
  model: string
}

export type PlannedStep = {
  id: string
  title: string
  description: string
  toolName?: string
  toolImage?: string
}

export type WorkflowExecutionMode = 'executable'

export type SampleDataInfo = {
  status: 'included' | 'reference_only'
  label: string
  description: string
  files: string[]
}

export type PlanningTraceEntry = {
  id: string
  status: 'running' | 'completed' | 'failed'
  title: string
  detail?: string
  timestamp: string
}

export type ReviewAgentMode = 'native_guided_tool_calling' | 'guided_tool_calling' | 'native_tool_calling' | 'json_fallback'
export type ReviewToolCallOrigin = 'model_native' | 'model_schema' | 'system_grounding' | 'json_fallback'

export type ReviewToolCall = {
  id: string
  name: string
  origin: ReviewToolCallOrigin
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
  mode: ReviewAgentMode
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

export type ConversationAction = 'answer' | 'clarify' | 'status' | 'run_analysis'

export type ConversationRouteContext = {
  hasActiveTask?: boolean
  latestTaskStatus?: 'queued' | 'running' | 'completed' | 'failed'
  previousAction?: ConversationAction
  previousWorkflowKey?: string
  previousAnalysisPrompt?: string
  previousMessage?: string
}

export type ConversationDecision = {
  action: ConversationAction
  message: string
  confidence: number
  source: 'fast_rule' | 'model' | 'fallback'
  reason?: string
  workflowKey?: string
  analysisPrompt?: string
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
  executionMode?: WorkflowExecutionMode
  executionNote?: string
  sampleData?: SampleDataInfo
  agentRun?: ReviewAgentRun
}

export type SampleMetadata = {
  sampleId: string
  condition: 'control' | 'treatment'
  fastq: string
}

export type SampleQc = {
  sampleId: string
  condition: string
  reads: number
  averageLength: number
  gcPercent: number
}

export type CountMatrix = Record<string, Record<string, number>>

export type DifferentialGene = {
  gene: string
  controlMean: number
  treatmentMean: number
  log2FoldChange: number
  score: number
  direction: 'up' | 'down' | 'stable'
}

export type ResultTable = {
  title: string
  columns: string[]
  rows: Array<Record<string, string | number>>
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

export type TimelineEventInput = Omit<TimelineEvent, 'id' | 'timestamp'> & {
  id?: string
  timestamp?: string
}

export type PipelineResult = {
  jobId: string
  workflowKey: string
  plan: PlannedStep[]
  modelPlan: ModelPlan
  agentRun?: ReviewAgentRun
  toolRuns: ToolRunRecord[]
  qc?: SampleQc[]
  counts?: CountMatrix
  differential?: DifferentialGene[]
  tables: ResultTable[]
  outputDir: string
  reportMarkdown: string
  summary: string
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
  result?: PipelineResult
  error?: string
}
