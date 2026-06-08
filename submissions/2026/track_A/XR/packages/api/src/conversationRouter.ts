import type { ConversationDecision, ConversationRouteContext, ProviderConfig } from './types.js'
import { workflowCatalog, type WorkflowKey } from './workflowCatalog.js'
import { requestModelChatWithTools, type ChatToolCall } from './llmClient.js'
import { sanitizePublicText } from './reviewAgentGuards.js'

const llmEngineUrl = process.env.LLM_ENGINE_URL || 'http://127.0.0.1:8011'
const conversationIntentToolName = 'classify_conversation_intent'

const workflowAliases: Array<{ key: WorkflowKey; patterns: RegExp[] }> = [
  {
    key: 'single_cell_rna_seq',
    patterns: [
      /single[-\s]?cell/i,
      /\bscRNA\b/i,
      /单细胞/i,
    ],
  },
  {
    key: 'proteomics_lfq',
    patterns: [
      /proteomics/i,
      /label[-\s]?free/i,
      /\blfq\b/i,
      /蛋白组|非标记/i,
    ],
  },
  {
    key: 'bulk_rna_seq',
    patterns: [
      /\bbulk\b/i,
      /\brna[-\s]?seq\b/i,
      /转录组|bulk\s*RNA|RNA测序/i,
    ],
  },
]

const directExecutePatterns = [
  /\b(run|start|execute|process|perform|launch)\b/i,
  /开始|运行|执行|启动|跑一下|做一下/,
]

const planningExecutePatterns = [
  /\b(analy[sz]e|plan)\b/i,
  /分析|规划|处理|生成计划/,
]

const imperativeExecutePatterns = [
  /\bplease\s+(run|start|execute|process|perform|launch|analy[sz]e|plan)\b/i,
  /请(开始|运行|执行|启动|分析|规划|处理)|现在(开始|运行|执行|启动|分析|规划|处理)|直接(开始|运行|执行|启动|分析|规划|处理)/,
]

const statusPatterns = [
  /\b(status|progress|result|timeline|finished|done|running)\b/i,
  /状态|进度|结果|完成了吗|跑完|运行中|当前任务/,
]

const questionPatterns = [
  /\?|？/,
  /\b(what|why|how|can you|could you|explain|tell me|support|available)\b/i,
  /什么|为什么|如何|怎么|能否|可以吗|支持|解释|介绍|区别|有哪些/,
]

function detectWorkflowKey(message: string): WorkflowKey | undefined {
  return workflowAliases.find((workflow) => workflow.patterns.some((pattern) => pattern.test(message)))?.key
}

function workflowName(key?: WorkflowKey) {
  return workflowCatalog.find((workflow) => workflow.key === key)?.name
}

function validWorkflowKey(value?: string): WorkflowKey | undefined {
  return workflowCatalog.some((workflow) => workflow.key === value) ? value as WorkflowKey : undefined
}

function supportedWorkflowText() {
  return workflowCatalog.map((workflow) => workflow.name).join(', ')
}

function defaultAnalysisPrompt(workflowKey: WorkflowKey) {
  const workflow = workflowCatalog.find((item) => item.key === workflowKey)
  return `Plan and run ${workflow?.name || workflowKey} using the included public toy data.`
}

function normalizePrompt(message: string, workflowKey?: WorkflowKey) {
  const trimmed = message.trim()
  if (!workflowKey) return trimmed
  const workflow = workflowCatalog.find((item) => item.key === workflowKey)
  if (!workflow) return trimmed
  return trimmed || `Plan and run ${workflow.name} using the included public toy data.`
}

function explicitExecutionIntent(message: string) {
  const asksQuestion = questionPatterns.some((pattern) => pattern.test(message))
  const asksDirectExecution = directExecutePatterns.some((pattern) => pattern.test(message))
  const asksPlanningExecution = planningExecutePatterns.some((pattern) => pattern.test(message))
  const asksImperativeExecution = imperativeExecutePatterns.some((pattern) => pattern.test(message))
  return asksImperativeExecution || (!asksQuestion && (asksDirectExecution || asksPlanningExecution))
}

function confirmsPreviousWorkflow(message: string) {
  const text = message.trim().toLowerCase()
  return [
    /^(yes|y|ok|okay|sure|please do|go ahead|start it|run it|do it|continue|proceed|confirm)([.!。！]*)$/,
    /^(yes|ok|sure|please),?\s+(start|run|do|continue|proceed|execute|launch)\b/,
    /^(是|是的|对|可以|好的|好|确认|继续|开始|开始吧|运行|运行吧|执行|执行吧|就这个|按这个|没问题)([。.!！]*)$/,
  ].some((pattern) => pattern.test(text))
}

function previousMessageAsksToStart(context: ConversationRouteContext) {
  if (!context.previousMessage || context.previousAction === 'status') return false
  const text = context.previousMessage.toLowerCase()
  return [
    /(would you like|do you want|shall i|should i).*(start|run|execute|plan|process|launch|analysis|workflow)/,
    /(start|run|execute|plan|process|launch).*(now|\?)/,
    /是否|要不要|需要我|是否现在|开始吗|运行吗|执行吗|规划吗|继续吗/,
  ].some((pattern) => pattern.test(text))
}

function canConfirmPreviousWorkflow(message: string, context: ConversationRouteContext) {
  return confirmsPreviousWorkflow(message) && previousMessageAsksToStart(context)
}

function startingDecision(
  workflowKey: WorkflowKey,
  analysisPrompt: string,
  source: ConversationDecision['source'],
  reason: string,
): ConversationDecision {
  return {
    action: 'run_analysis',
    confidence: 0.9,
    source,
    message: `Starting ${workflowName(workflowKey)} with the public review workflow.`,
    workflowKey,
    analysisPrompt,
    reason,
  }
}

export function routeConversationByRules(
  message: string,
  context: ConversationRouteContext = {},
): ConversationDecision | undefined {
  const text = message.trim()
  if (!text) {
    return {
      action: 'clarify',
      confidence: 1,
      source: 'fast_rule',
      message: 'Please describe the analysis question or ask what this demo can do.',
      reason: 'empty message',
    }
  }

  if (statusPatterns.some((pattern) => pattern.test(text))) {
    const statusText = context.latestTaskStatus
      ? `The latest task is ${context.latestTaskStatus}.`
      : 'No task has been started in this browser session yet.'
    return {
      action: 'status',
      confidence: 0.92,
      source: 'fast_rule',
      message: statusText,
      reason: 'status request',
    }
  }

  const workflowKey = detectWorkflowKey(text)
  const asksQuestion = questionPatterns.some((pattern) => pattern.test(text))
  const asksExecution = explicitExecutionIntent(text)
  const previousWorkflowKey = validWorkflowKey(context.previousWorkflowKey)

  if (canConfirmPreviousWorkflow(text, context) && previousWorkflowKey) {
    if (context.hasActiveTask) {
      return {
        action: 'status',
        confidence: 0.9,
        source: 'fast_rule',
        message: 'A task is already running. Wait for it to finish before starting another workflow.',
        reason: 'active task prevents confirmed workflow execution',
      }
    }
    return startingDecision(
      previousWorkflowKey,
      context.previousAnalysisPrompt || defaultAnalysisPrompt(previousWorkflowKey),
      'fast_rule',
      'user confirmed previous workflow context',
    )
  }

  if (asksExecution && context.hasActiveTask) {
    return {
      action: 'status',
      confidence: 0.9,
      source: 'fast_rule',
      message: 'A task is already running. Wait for it to finish before starting another workflow.',
      reason: 'active task prevents new execution',
    }
  }

  if (asksExecution && workflowKey && !context.hasActiveTask) {
    return {
      action: 'run_analysis',
      confidence: 0.9,
      source: 'fast_rule',
      message: `Starting ${workflowName(workflowKey)} with the public review workflow.`,
      workflowKey,
      analysisPrompt: normalizePrompt(text, workflowKey),
      reason: 'explicit workflow execution request',
    }
  }

  if (asksExecution && !workflowKey) {
    return {
      action: 'clarify',
      confidence: 0.86,
      source: 'fast_rule',
      message: `Which public workflow should I use: ${supportedWorkflowText()}?`,
      reason: 'execution requested without workflow',
    }
  }

  if (asksQuestion) {
    return {
      action: 'answer',
      confidence: 0.78,
      source: 'fast_rule',
      message: workflowKey
        ? `${workflowName(workflowKey)} is available in this public demo. I will only start execution after you explicitly ask me to run it.`
        : `This demo can discuss and run three public workflows: ${supportedWorkflowText()}. Ask me to run one when you want execution to start.`,
      workflowKey,
      reason: 'general question',
    }
  }

  if (workflowKey && !asksExecution) {
    return {
      action: 'clarify',
      confidence: 0.82,
      source: 'fast_rule',
      message: `I recognized ${workflowName(workflowKey)}. Tell me to run or analyze it when you want me to start the workflow.`,
      workflowKey,
      reason: 'workflow mentioned without execution intent',
    }
  }

  return undefined
}

function parseDecision(raw: string): Partial<ConversationDecision> {
  const start = raw.indexOf('{')
  const end = raw.lastIndexOf('}')
  if (start < 0 || end <= start) return {}
  try {
    return JSON.parse(raw.slice(start, end + 1)) as Partial<ConversationDecision>
  } catch {
    return {}
  }
}

function parseToolArguments(raw: string | Record<string, unknown> | undefined): Record<string, unknown> {
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  const trimmed = raw.trim()
  if (!trimmed) return {}
  const parsed = JSON.parse(trimmed)
  return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {}
}

function normalizeDecision(candidate: Partial<ConversationDecision>, message: string): ConversationDecision {
  const allowedActions = new Set<ConversationDecision['action']>(['answer', 'clarify', 'status', 'run_analysis'])
  const action = allowedActions.has(candidate.action as ConversationDecision['action'])
    ? candidate.action as ConversationDecision['action']
    : 'clarify'
  const workflowKey = candidate.workflowKey && workflowCatalog.some((workflow) => workflow.key === candidate.workflowKey)
    ? candidate.workflowKey as WorkflowKey
    : detectWorkflowKey(message)

  return {
    action,
    confidence: Math.max(0, Math.min(1, Number(candidate.confidence ?? 0.55))),
    source: 'model',
    message: sanitizePublicText(candidate.message || 'I can help discuss the request, or start a public workflow after you explicitly ask me to run it.'),
    reason: typeof candidate.reason === 'string' ? sanitizePublicText(candidate.reason) : undefined,
    workflowKey,
    analysisPrompt: action === 'run_analysis'
      ? normalizePrompt(sanitizePublicText(candidate.analysisPrompt || message), workflowKey)
      : undefined,
  }
}

function conversationIntentToolDefinition() {
  return {
    type: 'function',
    function: {
      name: conversationIntentToolName,
      description: 'Classify a public bioinformatics demo conversation turn and decide whether execution should start.',
      parameters: {
        type: 'object',
        properties: {
          action: {
            type: 'string',
            enum: ['answer', 'clarify', 'status', 'run_analysis'],
            description: 'Conversation action for this turn.',
          },
          message: {
            type: 'string',
            description: 'Brief assistant reply visible to the reviewer.',
          },
          confidence: {
            type: 'number',
            description: 'Confidence from 0 to 1.',
          },
          workflowKey: {
            type: 'string',
            enum: ['bulk_rna_seq', 'single_cell_rna_seq', 'proteomics_lfq'],
            description: 'Public workflow key, only when one is clearly selected.',
          },
          analysisPrompt: {
            type: 'string',
            description: 'Executable analysis prompt to pass into the planner when action is run_analysis.',
          },
          reason: {
            type: 'string',
            description: 'Short public reason for the routing decision.',
          },
        },
        required: ['action', 'message', 'confidence'],
        additionalProperties: false,
      },
    },
  }
}

function conversationMessages(
  message: string,
  context: ConversationRouteContext,
) {
  return [
    {
      role: 'system' as const,
      content: [
        'You are Gemma 4 routing a public bioinformatics demo conversation.',
        'Classify the user message with the classify_conversation_intent tool.',
        'Allowed actions: answer, clarify, status, run_analysis.',
        'Use run_analysis only when the user clearly asks to run, execute, analyze, process, start, or plan a workflow now.',
        'If the user only mentions a data type, asks a question, greets, or gives vague context, use answer or clarify.',
        'Allowed workflowKey values: bulk_rna_seq, single_cell_rna_seq, proteomics_lfq.',
        'Do not claim access to private systems, private data, arbitrary tools, or production endpoints.',
      ].join('\n'),
    },
    {
      role: 'user' as const,
      content: [
        `Active task: ${context.hasActiveTask ? 'yes' : 'no'}`,
        `Latest task status: ${context.latestTaskStatus || 'none'}`,
        `Previous assistant action: ${context.previousAction || 'none'}`,
        `Previous workflow key: ${validWorkflowKey(context.previousWorkflowKey) || 'none'}`,
        `Previous analysis prompt: ${context.previousAnalysisPrompt ? sanitizePublicText(context.previousAnalysisPrompt) : 'none'}`,
        `Previous assistant message: ${context.previousMessage ? sanitizePublicText(context.previousMessage) : 'none'}`,
        `Supported public workflows: ${supportedWorkflowText()}`,
        `Message: ${message}`,
        'If the user confirms the previous workflow and no task is active, classify as run_analysis using the previous workflow and analysis prompt.',
      ].join('\n'),
    },
  ]
}

function normalizeToolDecision(toolCall: ChatToolCall | undefined, message: string): ConversationDecision | undefined {
  if (!toolCall || toolCall.function?.name !== conversationIntentToolName) return undefined
  return normalizeDecision(parseToolArguments(toolCall.function.arguments), message)
}

async function requestModelDecisionWithTool(
  provider: ProviderConfig,
  message: string,
  context: ConversationRouteContext,
  modelCaller: typeof requestModelChatWithTools,
): Promise<ConversationDecision | undefined> {
  const response = await modelCaller(
    provider,
    conversationMessages(message, context),
    [conversationIntentToolDefinition()],
    { type: 'function', function: { name: conversationIntentToolName } },
    'none',
    45,
    384,
  )
  const toolDecision = normalizeToolDecision(response.toolCalls[0], message)
  if (toolDecision) return toolDecision
  if (response.content.trim()) {
    return normalizeDecision(parseDecision(response.content), message)
  }
  if (response.error) {
    throw new Error(response.error)
  }
  return undefined
}

async function requestModelDecisionWithJson(
  provider: ProviderConfig,
  message: string,
  context: ConversationRouteContext,
): Promise<ConversationDecision | undefined> {
  const response = await fetch(`${llmEngineUrl}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      provider,
      temperature: 0,
      maxTokens: 384,
      timeoutSeconds: 45,
      responseFormat: 'json_object',
      messages: [
        ...conversationMessages(message, context),
        {
          role: 'system',
          content: [
            'Native tool calls were unavailable.',
            'Return one compact JSON object only.',
            '{"action":"answer|clarify|status|run_analysis","message":"...","confidence":0.0,"workflowKey":"...","analysisPrompt":"...","reason":"..."}',
          ].join('\n'),
        },
      ],
    }),
  })
  if (!response.ok) {
    throw new Error(`Conversation router HTTP ${response.status}`)
  }
  const payload = await response.json() as { content?: string; error?: string }
  if (payload.error) {
    throw new Error(payload.error)
  }
  return normalizeDecision(parseDecision(payload.content || ''), message)
}

function applyConversationGuards(
  decision: ConversationDecision,
  message: string,
  context: ConversationRouteContext,
): ConversationDecision {
  const text = message.trim()
  const previousWorkflowKey = validWorkflowKey(context.previousWorkflowKey)
  const currentWorkflowKey = validWorkflowKey(decision.workflowKey) || detectWorkflowKey(text)

  if (canConfirmPreviousWorkflow(text, context) && previousWorkflowKey) {
    if (context.hasActiveTask) {
      return {
        action: 'status',
        confidence: 0.88,
        source: 'fast_rule',
        message: 'A task is already running. Wait for it to finish before starting another workflow.',
        reason: 'active task prevents confirmed workflow execution',
      }
    }
    return startingDecision(
      previousWorkflowKey,
      context.previousAnalysisPrompt || defaultAnalysisPrompt(previousWorkflowKey),
      'fast_rule',
      'user confirmed previous workflow context',
    )
  }

  if (decision.action !== 'run_analysis' && explicitExecutionIntent(text) && currentWorkflowKey) {
    if (context.hasActiveTask) {
      return {
        action: 'status',
        confidence: 0.88,
        source: 'fast_rule',
        message: 'A task is already running. Wait for it to finish before starting another workflow.',
        reason: 'active task prevents explicit workflow execution',
      }
    }
    return startingDecision(
      currentWorkflowKey,
      normalizePrompt(text, currentWorkflowKey),
      'fast_rule',
      'explicit execution intent corrected model routing',
    )
  }

  if (decision.action === 'run_analysis' && context.hasActiveTask) {
    return {
      action: 'status',
      confidence: 0.88,
      source: 'fast_rule',
      message: 'A task is already running. Wait for it to finish before starting another workflow.',
      reason: 'active task prevents new execution',
    }
  }

  if (decision.action === 'run_analysis' && (!currentWorkflowKey || decision.confidence < 0.45)) {
    return {
      action: 'clarify',
      confidence: 0.82,
      source: 'fast_rule',
      message: `Which public workflow should I use: ${supportedWorkflowText()}?`,
      reason: currentWorkflowKey ? 'model confidence too low for execution' : 'model requested execution without workflow',
    }
  }

  if (decision.action === 'run_analysis' && currentWorkflowKey) {
    return startingDecision(
      currentWorkflowKey,
      decision.analysisPrompt || context.previousAnalysisPrompt || normalizePrompt(text, currentWorkflowKey),
      decision.source,
      decision.reason || 'model requested workflow execution',
    )
  }

  if (decision.action !== 'run_analysis' && !decision.workflowKey) {
    const detectedWorkflowKey = detectWorkflowKey(text)
    if (detectedWorkflowKey) {
      return { ...decision, workflowKey: detectedWorkflowKey }
    }
  }

  return decision
}

export async function routeConversation(
  provider: ProviderConfig,
  message: string,
  context: ConversationRouteContext = {},
  modelCaller: typeof requestModelChatWithTools = requestModelChatWithTools,
): Promise<ConversationDecision> {
  if (!message.trim()) {
    return routeConversationByRules(message, context) as ConversationDecision
  }

  if (process.env.DEMO_SKIP_CONVERSATION_ROUTER === '1') {
    return routeConversationByRules(message, context) || {
      action: 'clarify',
      confidence: 0.6,
      source: 'fallback',
      message: `I can discuss the request first. To start execution, explicitly ask me to run one of: ${supportedWorkflowText()}.`,
      reason: 'conversation router skipped',
    }
  }

  try {
    const toolDecision = await requestModelDecisionWithTool(provider, message, context, modelCaller)
    if (toolDecision) return applyConversationGuards(toolDecision, message, context)
    const jsonDecision = await requestModelDecisionWithJson(provider, message, context)
    if (jsonDecision) return applyConversationGuards(jsonDecision, message, context)
    throw new Error('model returned no conversation decision')
  } catch (error) {
    return routeConversationByRules(message, context) || {
      action: 'clarify',
      confidence: 0.5,
      source: 'fallback',
      message: `I can discuss the request first. To start execution, explicitly ask me to run one of: ${supportedWorkflowText()}.`,
      reason: error instanceof Error ? error.message : 'conversation router failed',
    }
  }
}
