import crypto from 'node:crypto'
import cors from 'cors'
import dotenv from 'dotenv'
import express from 'express'
import { loadProviderConfig, publicProviderConfig, saveProviderConfig } from './providerStore.js'
import { buildBulkRnaseqPlan } from './planner.js'
import { runBulkRnaseqDemo } from './bulkRnaseqPipeline.js'
import { runSingleCellDemo } from './singleCellPipeline.js'
import { runProteomicsDemo } from './proteomicsPipeline.js'
import { requestModelPlan, requestModelSummary, testModelConnection } from './llmClient.js'
import { appendReviewAgentResultSummary, persistReviewAgentArtifacts, requestReviewAgentPlan } from './reviewAgentRuntime.js'
import { routeConversation } from './conversationRouter.js'
import { workflowCatalog, type WorkflowKey } from './workflowCatalog.js'
import type { ConversationRouteContext, ModelPlan, PlannedStep, TaskRecord, TimelineEventInput } from './types.js'

dotenv.config()

const app = express()
const port = Number(process.env.API_PORT || 3101)
const tasks = new Map<string, TaskRecord>()

let timelineSequence = 0

function getTaskOrThrow(id: string): TaskRecord {
  const task = tasks.get(id)
  if (!task) {
    throw new Error(`Task not found: ${id}`)
  }
  return task
}

function updateTask(id: string, patch: Partial<TaskRecord>): TaskRecord {
  const current = getTaskOrThrow(id)
  const next = {
    ...current,
    ...patch,
    updatedAt: new Date().toISOString(),
  }
  tasks.set(id, next)
  return next
}

function appendTimeline(taskId: string, event: TimelineEventInput): TaskRecord {
  const current = getTaskOrThrow(taskId)
  const timestamp = event.timestamp || new Date().toISOString()
  const nextEvent = {
    ...event,
    id: event.id || `${Date.now()}-${timelineSequence++}`,
    timestamp,
  }
  const existingIndex = current.timeline.findIndex((item) => item.id === nextEvent.id)
  const timeline = [...current.timeline]
  if (existingIndex >= 0) {
    timeline[existingIndex] = {
      ...timeline[existingIndex],
      ...nextEvent,
    }
  } else {
    timeline.push(nextEvent)
  }
  const next = {
    ...current,
    updatedAt: timestamp,
    timeline,
  }
  tasks.set(taskId, next)
  return next
}

function completePlan(modelPlan: ModelPlan, prompt: string): PlannedStep[] {
  return modelPlan.steps.length ? modelPlan.steps : buildBulkRnaseqPlan(prompt)
}

async function runSelectedWorkflow(
  id: string,
  prompt: string,
  provider: Awaited<ReturnType<typeof loadProviderConfig>>,
  modelPlan: ModelPlan,
  emitEvent: (event: TimelineEventInput) => void,
) {
  if (modelPlan.source === 'failed' || !modelPlan.workflowKey) {
    throw new Error(modelPlan.sourceMessage || 'Model planning failed before a workflow could be selected.')
  }

  const workflowKey = modelPlan.workflowKey as WorkflowKey
  if (workflowKey === 'bulk_rna_seq') {
    return runBulkRnaseqDemo(id, prompt, provider, modelPlan, emitEvent)
  }
  if (workflowKey === 'single_cell_rna_seq') {
    return runSingleCellDemo(id, provider, modelPlan, emitEvent)
  }
  if (workflowKey === 'proteomics_lfq') {
    return runProteomicsDemo(id, provider, modelPlan, emitEvent)
  }
  throw new Error(`Unsupported workflow: ${modelPlan.workflowKey}`)
}

app.use(cors())
app.use(express.json({ limit: '2mb' }))

app.get('/api/health', (_req, res) => {
  res.json({ ok: true, service: 'gemma-bioinformatics-demo-api' })
})

app.get('/api/workflows', (_req, res) => {
  res.json({
    workflows: workflowCatalog.map((workflow) => ({
      key: workflow.key,
      name: workflow.name,
      description: workflow.description,
      executionMode: workflow.executionMode,
      executionNote: workflow.executionNote,
      sampleData: workflow.sampleData,
    })),
  })
})

app.get('/api/provider', async (_req, res, next) => {
  try {
    res.json(publicProviderConfig(await loadProviderConfig()))
  } catch (error) {
    next(error)
  }
})

app.post('/api/provider', async (req, res, next) => {
  try {
    const config = await saveProviderConfig({
      baseUrl: req.body.baseUrl,
      apiKey: req.body.apiKey,
      model: req.body.model,
    })
    res.json(publicProviderConfig(config))
  } catch (error) {
    next(error)
  }
})

app.post('/api/provider/test', async (_req, res, next) => {
  try {
    const result = await testModelConnection(await loadProviderConfig())
    res.json(result)
  } catch (error) {
    next(error)
  }
})

app.get('/api/conversation/model', async (_req, res, next) => {
  try {
    const provider = await loadProviderConfig()
    res.json({ provider: provider.provider, model: provider.model })
  } catch (error) {
    next(error)
  }
})

app.post('/api/conversation/model', async (req, res, next) => {
  try {
    const provider = await saveProviderConfig({ model: req.body.model })
    res.json({ provider: provider.provider, model: provider.model })
  } catch (error) {
    next(error)
  }
})

app.post('/api/plan', async (req, res, next) => {
  try {
    const prompt = String(req.body.prompt || '')
    const provider = await loadProviderConfig()
    const modelPlan = await requestReviewAgentPlan(provider, prompt)
    res.json({ plan: modelPlan.steps, modelPlan })
  } catch (error) {
    next(error)
  }
})

app.post('/api/chat', async (req, res, next) => {
  try {
    const prompt = String(req.body.message || '')
    const provider = await loadProviderConfig()
    const modelPlan = await requestModelPlan(provider, prompt)
    const plan = modelPlan.steps.length ? modelPlan.steps : buildBulkRnaseqPlan(prompt)
    const response = await requestModelSummary(provider, [
      {
        role: 'system',
        content: 'You are a concise assistant for a public Gemma 4 bulk RNA-seq demo.',
      },
      {
        role: 'user',
        content: `User request: ${prompt}\nPlanned steps: ${plan.map((step) => step.title).join(' -> ')}`,
      },
    ])
    res.json({ message: response, plan })
  } catch (error) {
    next(error)
  }
})

app.post('/api/conversation/route', async (req, res, next) => {
  try {
    const message = String(req.body.message || '').trim()
    if (!message) {
      res.status(400).json({ error: 'message is required' })
      return
    }
    const latestTask = Array.from(tasks.values()).sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0]
    const context = req.body.context && typeof req.body.context === 'object'
      ? req.body.context as ConversationRouteContext
      : {}
    const decision = await routeConversation(await loadProviderConfig(), message, {
      hasActiveTask: Boolean(context.hasActiveTask ?? latestTask?.status === 'running'),
      latestTaskStatus: context.latestTaskStatus || latestTask?.status,
      previousAction: context.previousAction,
      previousWorkflowKey: context.previousWorkflowKey,
      previousAnalysisPrompt: context.previousAnalysisPrompt,
      previousMessage: context.previousMessage,
    })
    res.json(decision)
  } catch (error) {
    next(error)
  }
})

app.post('/api/tasks', async (req, res) => {
  const prompt = String(req.body.prompt || '').trim()
  if (!prompt) {
    res.status(400).json({ error: 'prompt is required' })
    return
  }

  const id = crypto.randomUUID()
  const now = new Date().toISOString()
  const task: TaskRecord = {
    id,
    prompt,
    status: 'running',
    createdAt: now,
    updatedAt: now,
    timeline: [
      {
        id: `${Date.now()}-${timelineSequence++}`,
        phase: 'request',
        status: 'completed',
        title: 'Analysis request received',
        detail: 'The prompt has been accepted and the configured model provider will be used for planning.',
        timestamp: now,
      },
    ],
  }
  tasks.set(id, task)
  res.status(202).json(task)

  void (async () => {
    try {
      appendTimeline(id, {
        id: 'planning-model-intent',
        phase: 'planning',
        status: 'running',
        title: 'Asking model to interpret the request',
        detail: 'The local OpenAI-compatible provider is asked to extract the analysis intent before the workflow is assembled.',
      })
      const provider = await loadProviderConfig()
      const modelPlan = await requestReviewAgentPlan(provider, prompt)
      if (modelPlan.source === 'failed') {
        throw new Error(modelPlan.sourceMessage || 'Model planning failed before a workflow could be selected.')
      }
      const plan = completePlan(modelPlan, prompt)
      updateTask(id, { modelPlan, plan, agentRun: modelPlan.agentRun })
      appendTimeline(id, {
        id: 'planning-model-intent',
        phase: 'planning',
        status: 'completed',
        title: 'Model planning response captured',
        detail: `${modelPlan.model}: ${modelPlan.intent}`,
      })
      appendTimeline(id, {
        id: 'planning-workflow-assembled',
        phase: 'planning',
        status: 'completed',
        title: 'Reviewer workflow assembled',
        detail: `${plan.length} visible steps are ready for execution.`,
      })
      const result = await runSelectedWorkflow(id, prompt, provider, { ...modelPlan, steps: plan }, (event) => {
        appendTimeline(id, event)
      })
      const reflectedAgentRun = await appendReviewAgentResultSummary(
        provider,
        result.agentRun || result.modelPlan.agentRun,
        result.workflowKey,
        result.summary,
      )
      const persistedAgentRun = await persistReviewAgentArtifacts(id, reflectedAgentRun || result.agentRun || result.modelPlan.agentRun)
      const resultWithAgent = {
        ...result,
        agentRun: persistedAgentRun,
        modelPlan: {
          ...result.modelPlan,
          agentRun: persistedAgentRun,
        },
      }
      appendTimeline(id, {
        phase: 'result',
        status: 'completed',
        title: 'Task completed with public review trace',
        detail: `Report and output files were written to ${result.outputDir}.`,
      })
      updateTask(id, {
        status: 'completed',
        plan: resultWithAgent.plan,
        modelPlan: resultWithAgent.modelPlan,
        agentRun: persistedAgentRun,
        result: resultWithAgent,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Task failed'
      appendTimeline(id, {
        phase: 'result',
        status: 'failed',
        title: 'Task failed',
        detail: message,
      })
      updateTask(id, {
        status: 'failed',
        error: message,
      })
      console.error(error)
    }
  })()
})

app.get('/api/tasks', (_req, res) => {
  res.json({ tasks: Array.from(tasks.values()).sort((a, b) => b.createdAt.localeCompare(a.createdAt)) })
})

app.get('/api/tasks/:id', (req, res) => {
  const task = tasks.get(req.params.id)
  if (!task) {
    res.status(404).json({ error: 'task not found' })
    return
  }
  res.json(task)
})

app.get('/api/tasks/:id/agent', (req, res) => {
  const task = tasks.get(req.params.id)
  if (!task) {
    res.status(404).json({ error: 'task not found' })
    return
  }
  const agentRun = task.agentRun || task.modelPlan?.agentRun || task.result?.agentRun
  if (!agentRun) {
    res.status(404).json({ error: 'agent trace not found' })
    return
  }
  res.json(agentRun)
})

app.use((error: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  const message = error instanceof Error ? error.message : 'Internal server error'
  res.status(500).json({ error: message })
})

app.listen(port, () => {
  console.log(`Gemma bulk RNA-seq demo API listening on http://127.0.0.1:${port}`)
})
