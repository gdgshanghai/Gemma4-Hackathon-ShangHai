import fs from 'node:fs/promises'
import path from 'node:path'
import { requestModelChatWithTools, requestModelPlan, type ChatToolCall } from './llmClient.js'
import { reviewDataRoot } from './paths.js'
import {
  plannedStepsFromValidatedToolPlan,
  publicBioToolCatalogForTrace,
  publicWorkflowContractForModel,
  toolPlanPromptLines,
  validateToolLevelPlan,
  type ValidatedToolLevelPlan,
} from './publicBioToolPlanning.js'
import { publicToolDefinitions, type PublicToolDefinition, type PublicToolName } from './publicToolManifest.js'
import {
  assertPublicToolName,
  publicWorkflowOrThrow,
  sanitizePublicText,
  workflowSummaryForPublicTrace,
} from './reviewAgentGuards.js'
import {
  controlledRecoveryToolCall,
  schemaFallbackExampleForTool,
  workflowCatalogForPlanner,
} from './reviewAgentRecovery.js'
import type {
  ModelPlan,
  PlannedStep,
  ProviderConfig,
  ReviewAgentMemory,
  ReviewAgentRun,
  ReviewAgentTraceEntry,
  ReviewToolCall,
} from './types.js'
import type { WorkflowKey } from './workflowCatalog.js'

export type ReviewAgentModelCaller = typeof requestModelChatWithTools

type ExecutedPublicTool = {
  call: ReviewToolCall
  result: Record<string, unknown>
  native: boolean
}

type GuidedToolStep = {
  name: PublicToolName
  messages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }>
  workflowKey?: WorkflowKey
  maxTokens?: number
  timeoutSeconds?: number
}

function now() {
  return new Date().toISOString()
}

function traceEntry(
  id: string,
  stage: ReviewAgentTraceEntry['stage'],
  status: ReviewAgentTraceEntry['status'],
  title: string,
  detail?: string,
): ReviewAgentTraceEntry {
  return {
    id,
    stage,
    status,
    title,
    detail: detail ? sanitizePublicText(detail) : undefined,
    timestamp: now(),
  }
}

function initializeMemory(prompt: string, provider: ProviderConfig): ReviewAgentMemory {
  // 中文：任务级 Memory 只记录公开可审计状态，包括模型、输入、选择的 workflow、观察到的公开样例文件和工具调用 ID。
  // EN: Task-level memory stores only public auditable state: model, prompt, selected workflow, observed public sample files, and tool-call IDs.
  return {
    prompt: sanitizePublicText(prompt),
    model: provider.model,
    publicSafetyRules: [
      'Use only public toy data included in this review repository.',
      'Use only public workflow contracts and public container images listed by the demo.',
      'Do not use private XR platform internals, private data, private images, or production credentials.',
      'Ground all visible execution steps against the public workflow catalog before execution.',
    ],
    observedToyData: [],
    toolCallIds: [],
  }
}

function parseToolArguments(raw: string | Record<string, unknown> | undefined): Record<string, unknown> {
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  if (!raw.trim()) return {}
  const parsed = JSON.parse(raw)
  return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {}
}

function extractJsonObject(text: string): Record<string, unknown> {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i)
  const candidate = fenced?.[1] ?? text
  const start = candidate.indexOf('{')
  const end = candidate.lastIndexOf('}')
  if (start < 0 || end <= start) {
    throw new Error('No JSON object found in guided tool response.')
  }
  const parsed = JSON.parse(candidate.slice(start, end + 1))
  return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {}
}

function normalizeToolCall(toolCall: ChatToolCall, index: number): ReviewToolCall {
  const name = String(toolCall.function?.name || '')
  assertPublicToolName(name)
  return {
    id: toolCall.id || `tool-call-${index + 1}`,
    name,
    origin: 'model_native',
    arguments: parseToolArguments(toolCall.function?.arguments),
    status: 'requested',
    timestamp: now(),
  }
}

function toolDefinition(name: PublicToolName): PublicToolDefinition {
  const definition = publicToolDefinitions.find((tool) => tool.function.name === name)
  if (!definition) throw new Error(`Public tool definition not found: ${name}`)
  return definition
}

function compactSteps(steps: PlannedStep[]) {
  return steps.map((step) => ({
    id: step.id,
    title: step.title,
    toolName: step.toolName || 'not specified',
    toolImage: step.toolImage || 'not specified',
  }))
}

function executePublicTool(name: PublicToolName, args: Record<string, unknown>) {
  if (name === 'inspect_available_bio_tools') {
    return {
      tools: publicBioToolCatalogForTrace(),
      boundary: 'Gemma 4 may plan with these public tools, but API execution remains contract-grounded.',
    }
  }

  if (name === 'inspect_available_workflows') {
    return {
      workflows: workflowSummaryForPublicTrace(),
    }
  }

  if (name === 'inspect_workflow_contract') {
    const workflow = publicWorkflowOrThrow(args.workflowKey)
    return publicWorkflowContractForModel(workflow)
  }

  if (name === 'inspect_sample_data') {
    const workflow = publicWorkflowOrThrow(args.workflowKey)
    return {
      workflowKey: workflow.key,
      label: workflow.sampleData.label,
      description: workflow.sampleData.description,
      files: workflow.sampleData.files,
      compliance: 'Synthetic public-style toy data included for review reproduction.',
    }
  }

  if (name === 'select_workflow') {
    const workflow = publicWorkflowOrThrow(args.workflowKey)
    return {
      workflowKey: workflow.key,
      workflowName: workflow.name,
      reason: sanitizePublicText(args.reason),
      comparison: sanitizePublicText(args.comparison || 'condition comparison'),
    }
  }

  if (name === 'draft_tool_level_plan') {
    return validateToolLevelPlan(args)
  }

  if (name === 'draft_execution_plan') {
    const workflow = publicWorkflowOrThrow(args.workflowKey)
    return {
      workflowKey: workflow.key,
      intent: sanitizePublicText(args.intent || workflow.description),
      comparison: sanitizePublicText(args.comparison || 'condition comparison'),
      steps: compactSteps(workflow.steps),
      caveat: 'Execution is restricted to the public review workflow contract.',
    }
  }

  if (name === 'summarize_results') {
    const workflow = publicWorkflowOrThrow(args.workflowKey)
    return {
      workflowKey: workflow.key,
      summary: sanitizePublicText(args.compactResult || `Public ${workflow.name} result is ready for review.`),
      caveat: 'Interpretation is based on public toy data, not clinical or production data.',
    }
  }

  throw new Error(`Unsupported public review tool: ${name}`)
}

function updateMemoryFromTool(memory: ReviewAgentMemory, tool: ExecutedPublicTool) {
  // 中文：每个工具执行结果都会回写 Memory，让评审能追踪 tool call 如何改变 Agent 状态。
  // EN: Every executed tool writes back into memory, making tool-call state changes traceable for reviewers.
  memory.toolCallIds.push(tool.call.id)

  if (tool.call.name === 'inspect_sample_data' && Array.isArray(tool.result.files)) {
    memory.observedToyData = Array.from(new Set([
      ...memory.observedToyData,
      ...tool.result.files.map((file) => String(file)),
    ]))
  }

  if (tool.call.name === 'select_workflow') {
    memory.selectedWorkflowKey = String(tool.result.workflowKey || '')
    memory.selectedWorkflowName = String(tool.result.workflowName || '')
    memory.comparison = String(tool.result.comparison || '')
  }

  if (tool.call.name === 'draft_execution_plan') {
    memory.selectedWorkflowKey = String(tool.result.workflowKey || memory.selectedWorkflowKey || '')
    memory.comparison = String(tool.result.comparison || memory.comparison || '')
  }

  if (tool.call.name === 'draft_tool_level_plan') {
    memory.selectedWorkflowKey = String(tool.result.workflowKey || memory.selectedWorkflowKey || '')
    memory.selectedWorkflowName = String(tool.result.workflowName || memory.selectedWorkflowName || '')
    memory.comparison = String(tool.result.comparison || memory.comparison || '')
  }
}

function executeModelToolCall(
  toolCall: ChatToolCall,
  index: number,
  origin: ReviewToolCall['origin'] = 'model_native',
): ExecutedPublicTool {
  const call = normalizeToolCall(toolCall, index)
  const result = executePublicTool(call.name as PublicToolName, call.arguments)
  return {
    call: {
      ...call,
      origin,
      status: 'completed',
      resultSummary: sanitizePublicText(JSON.stringify(result).slice(0, 500)),
    },
    result,
    native: origin === 'model_native',
  }
}

function schemaToolCallFromContent(
  content: string,
  allowedNames: PublicToolName[],
  index: number,
  forcedName?: PublicToolName,
): ChatToolCall {
  const parsed = extractJsonObject(content)
  const nestedFunction = parsed.function && typeof parsed.function === 'object'
    ? parsed.function as Record<string, unknown>
    : {}
  const detectedName = String(parsed.toolName || parsed.name || nestedFunction.name || '')
  const name = forcedName || detectedName || (allowedNames.length === 1 ? allowedNames[0] : '')
  if (!allowedNames.includes(name as PublicToolName)) {
    throw new Error(`Schema fallback selected unsupported next tool: ${name || 'empty'}.`)
  }
  const rawArgs = parsed.arguments || parsed.args || parsed.parameters || nestedFunction.arguments
  const args = rawArgs && typeof rawArgs === 'object'
    ? rawArgs as Record<string, unknown>
    : forcedName || !detectedName
      ? parsed
      : {}

  return {
    id: `schema-${name}-${index + 1}`,
    type: 'function',
    function: {
      name,
      arguments: JSON.stringify(args),
    },
  }
}

function schemaFallbackMessages(
  messages: GuidedToolStep['messages'],
  allowedNames: PublicToolName[],
  forcedName?: PublicToolName,
  workflowKey?: WorkflowKey,
  prompt?: string,
): GuidedToolStep['messages'] {
  const exampleTool = forcedName || allowedNames[0]
  const schema = exampleTool
    ? schemaFallbackExampleForTool(exampleTool, Boolean(forcedName), workflowKey, prompt)
    : '{}'
  return [
    ...messages,
    {
      role: 'system',
      content: [
        'Native tool calls were unavailable for this stage.',
        `Return one compact JSON object only. Allowed tool names: ${allowedNames.join(', ')}.`,
        forcedName
          ? `Use the ${forcedName} parameters directly as the JSON object.`
          : 'Use {"toolName":"...","arguments":{...}} and choose exactly one allowed tool.',
        'For draft_tool_level_plan, fill every selected workflow step exactly from the public workflow contract in the previous message.',
        `Example shape: ${schema}`,
      ].join('\n'),
    },
  ]
}

async function callPublicToolWithFallback(
  provider: ProviderConfig,
  modelCaller: ReviewAgentModelCaller,
  options: {
    allowedNames: PublicToolName[]
    messages: GuidedToolStep['messages']
    index: number
    forcedName?: PublicToolName
    workflowKey?: WorkflowKey
    prompt?: string
    maxTokens?: number
    timeoutSeconds?: number
  },
): Promise<ExecutedPublicTool> {
  const toolDefinitions = options.allowedNames.map(toolDefinition)
  const toolChoice = options.forcedName
    ? { type: 'function', function: { name: options.forcedName } }
    : 'auto'
  const nativeResponse = await modelCaller(
    provider,
    options.messages,
    toolDefinitions,
    toolChoice,
    'none',
    options.timeoutSeconds,
    options.maxTokens,
  )

  const nativeCall = nativeResponse.toolCalls.find((toolCall) => {
    const name = String(toolCall.function?.name || '')
    return options.allowedNames.includes(name as PublicToolName)
  })
  if (nativeCall) {
    return executeModelToolCall(nativeCall, options.index)
  }

  const nativeContent = nativeResponse.content.trim()
  if (nativeContent) {
    try {
      const schemaCall = schemaToolCallFromContent(nativeContent, options.allowedNames, options.index, options.forcedName)
      return executeModelToolCall(schemaCall, options.index, 'model_schema')
    } catch {
      // 中文：继续执行显式 schema fallback 请求，避免兼容端点的半结构化文本直接导致整体 JSON fallback。
      // EN: Continue with an explicit schema fallback request so semi-structured text does not force whole-agent JSON fallback.
    }
  }

  const schemaResponse = await modelCaller(
    provider,
    schemaFallbackMessages(options.messages, options.allowedNames, options.forcedName, options.workflowKey, options.prompt),
    [],
    undefined,
    'none',
    options.timeoutSeconds,
    options.maxTokens,
    'json_object',
  )
  if (schemaResponse.error) {
    const nativeError = nativeResponse.error ? `${nativeResponse.error}; ` : ''
    throw new Error(`${nativeError}${schemaResponse.error}`)
  }
  if (!schemaResponse.content.trim()) {
    const recoveredCall = controlledRecoveryToolCall(options.allowedNames, options.index, options.workflowKey, options.prompt)
    if (recoveredCall) {
      return executeModelToolCall(recoveredCall, options.index, 'system_grounding')
    }
    const nativeError = nativeResponse.error ? ` ${nativeResponse.error}` : ''
    throw new Error(`No native tool call or schema JSON returned.${nativeError}`)
  }

  try {
    const schemaCall = schemaToolCallFromContent(schemaResponse.content, options.allowedNames, options.index, options.forcedName)
    return executeModelToolCall(schemaCall, options.index, 'model_schema')
  } catch (error) {
    const recoveredCall = controlledRecoveryToolCall(options.allowedNames, options.index, options.workflowKey, options.prompt)
    if (recoveredCall) {
      return executeModelToolCall(recoveredCall, options.index, 'system_grounding')
    }
    throw error
  }
}

async function callGuidedTool(
  provider: ProviderConfig,
  modelCaller: ReviewAgentModelCaller,
  step: GuidedToolStep,
  index: number,
): Promise<ExecutedPublicTool> {
  // 中文：强制单个公开工具时也做阶段级 schema fallback，避免端点不支持原生 tool calls 时整条 Agent 链路降级。
  // EN: Single-tool stages also use stage-level schema fallback so unsupported native calls do not downgrade the whole agent chain.
  try {
    return await callPublicToolWithFallback(provider, modelCaller, {
      allowedNames: [step.name],
      forcedName: step.name,
      workflowKey: step.workflowKey,
      messages: step.messages,
      index,
      maxTokens: step.maxTokens,
      timeoutSeconds: step.timeoutSeconds,
    })
  } catch (error) {
    throw new Error(`${step.name} failed: ${error instanceof Error ? error.message : 'tool call failed'}`)
  }
}

function buildPlanFromToolResults(
  provider: ProviderConfig,
  prompt: string,
  toolResults: ExecutedPublicTool[],
  agentRun: ReviewAgentRun,
  rawResponse: string,
): ModelPlan {
  // 中文：最终执行计划不直接信任模型文本，而是由已执行的公开工具结果和 workflow contract 组装。
  // EN: The final execution plan is assembled from executed public tool results and workflow contracts, not from free-form model text.
  const selected = toolResults.find((tool) => tool.call.name === 'select_workflow')
  const toolLevelDraft = toolResults.find((tool) => tool.call.name === 'draft_tool_level_plan')
  const drafted = toolResults.find((tool) => tool.call.name === 'draft_execution_plan')
  const workflowKey = String(selected?.result.workflowKey || toolLevelDraft?.result.workflowKey || drafted?.result.workflowKey || '')
  const workflow = publicWorkflowOrThrow(workflowKey)
  const intent = sanitizePublicText(toolLevelDraft?.result.intent || drafted?.result.intent || selected?.call.arguments.reason || workflow.description)
  const comparison = sanitizePublicText(selected?.result.comparison || toolLevelDraft?.result.comparison || drafted?.result.comparison || 'condition comparison')
  const validatedToolPlan = toolLevelDraft?.result as ValidatedToolLevelPlan | undefined
  const steps = validatedToolPlan?.steps ? plannedStepsFromValidatedToolPlan(validatedToolPlan) : workflow.steps
  const usedControlledRecovery = agentRun.toolCalls.some((toolCall) => toolCall.origin === 'system_grounding')

  return {
    intent: intent || workflow.description,
    comparison: comparison || (workflow.key === 'bulk_rna_seq' ? 'treatment vs control' : 'condition comparison'),
    model: provider.model,
    rawResponse,
    source: 'model',
    sourceMessage: agentRun.mode === 'native_guided_tool_calling'
      ? 'Gemma 4 used a controlled public planner loop with native tool calling to choose next tools and draft a concrete bioinformatics tool-level plan; executable steps were validated against public workflow contracts.'
      : agentRun.mode === 'guided_tool_calling' && usedControlledRecovery
        ? 'Gemma 4 used a controlled public planner loop for available planning stages; empty model responses were recovered by API-controlled public tool grounding, and executable steps were validated against public workflow contracts.'
      : agentRun.mode === 'guided_tool_calling'
        ? 'Gemma 4 used a controlled public planner loop with tool-schema JSON fallback to choose next tools and draft a concrete bioinformatics tool-level plan; executable steps were validated against public workflow contracts.'
        : 'Gemma 4 used public review tool calling; executable steps were validated against public workflow contracts.',
    trace: [
      {
        id: 'review-agent-tool-calling',
        status: 'completed',
        title: agentRun.mode === 'native_guided_tool_calling' ? 'Controlled native planner loop captured' : 'Controlled planner loop captured',
        detail: `${agentRun.toolCalls.length} public review tool calls were recorded, including model-selected next tools and concrete tool-level planning.`,
        timestamp: now(),
      },
    ],
    workflowKey: workflow.key,
    workflowName: workflow.name,
    executionMode: workflow.executionMode,
    executionNote: workflow.executionNote,
    sampleData: workflow.sampleData,
    steps,
    agentRun,
  }
}

function fallbackAgentRun(provider: ProviderConfig, prompt: string, reason: string, modelPlan: ModelPlan): ReviewAgentRun {
  // 中文：fallback 是显式审计路径，保留 json-fallback-plan 记录，避免把非原生调用伪装成 native tool calling。
  // EN: Fallback is an explicit audit path with a json-fallback-plan record, so non-native planning is not presented as native tool calling.
  const memory = initializeMemory(prompt, provider)
  if (modelPlan.workflowKey) {
    memory.selectedWorkflowKey = modelPlan.workflowKey
    memory.selectedWorkflowName = modelPlan.workflowName
  }
  memory.comparison = modelPlan.comparison
  memory.observedToyData = modelPlan.sampleData?.files || []
  const fallbackToolCall: ReviewToolCall = {
    id: 'json-fallback-plan',
    name: 'json_fallback_plan',
    origin: 'json_fallback',
    arguments: {
      workflowKey: modelPlan.workflowKey || 'unknown',
      comparison: modelPlan.comparison,
      reason: sanitizePublicText(reason),
    },
    status: 'completed',
    resultSummary: sanitizePublicText(modelPlan.sourceMessage || 'Fallback public workflow plan selected.'),
    timestamp: now(),
  }
  memory.toolCallIds = [fallbackToolCall.id]
  return {
    mode: 'json_fallback',
    model: provider.model,
    memory,
    toolCalls: [fallbackToolCall],
    trace: [
      traceEntry('fallback-start', 'understand', 'completed', 'Use JSON fallback planner', reason),
      traceEntry('fallback-ground', 'ground', 'completed', 'Ground fallback plan to public workflow contract', modelPlan.workflowName || modelPlan.workflowKey || 'default workflow'),
    ],
  }
}

function deterministicFallbackPlan(provider: ProviderConfig, prompt: string, reason: string): ModelPlan {
  const lower = prompt.toLowerCase()
  const workflow = lower.includes('single-cell') || lower.includes('single cell') || lower.includes('scanpy')
    ? publicWorkflowOrThrow('single_cell_rna_seq')
    : lower.includes('proteomics') || lower.includes('protein') || lower.includes('lfq')
      ? publicWorkflowOrThrow('proteomics_lfq')
      : publicWorkflowOrThrow('bulk_rna_seq')
  const comparison = workflow.key === 'bulk_rna_seq' || lower.includes('treatment')
    ? 'treatment vs control'
    : 'condition comparison'
  const basePlan: ModelPlan = {
    intent: workflow.description,
    comparison,
    model: provider.model,
    rawResponse: '',
    source: 'fallback',
    sourceMessage: `Deterministic public workflow fallback was used after model planning failed: ${sanitizePublicText(reason)}`,
    workflowKey: workflow.key,
    workflowName: workflow.name,
    executionMode: workflow.executionMode,
    executionNote: workflow.executionNote,
    sampleData: workflow.sampleData,
    steps: workflow.steps,
  }
  const agentRun = fallbackAgentRun(provider, prompt, reason, basePlan)
  return { ...basePlan, agentRun }
}

function wasToolExecuted(tools: ExecutedPublicTool[], name: PublicToolName): boolean {
  return tools.some((tool) => tool.call.name === name)
}

function allowedPlannerTools(tools: ExecutedPublicTool[], memory: ReviewAgentMemory): PublicToolName[] {
  const inspectedBioTools = wasToolExecuted(tools, 'inspect_available_bio_tools')
  const inspectedWorkflows = wasToolExecuted(tools, 'inspect_available_workflows')
  const selectedWorkflow = Boolean(memory.selectedWorkflowKey)
  const inspectedContract = wasToolExecuted(tools, 'inspect_workflow_contract')
  const inspectedSampleData = wasToolExecuted(tools, 'inspect_sample_data')
  const draftedToolPlan = wasToolExecuted(tools, 'draft_tool_level_plan')

  if (draftedToolPlan) return []
  if (!inspectedBioTools) {
    return inspectedWorkflows
      ? ['inspect_available_bio_tools']
      : ['inspect_available_bio_tools', 'inspect_available_workflows']
  }
  if (!selectedWorkflow) {
    return inspectedWorkflows ? ['select_workflow'] : ['select_workflow', 'inspect_available_workflows']
  }
  if (!inspectedContract && !inspectedSampleData) return ['inspect_workflow_contract', 'inspect_sample_data']
  if (!inspectedContract) return ['inspect_workflow_contract']
  if (!inspectedSampleData) return ['inspect_sample_data']
  return ['draft_tool_level_plan']
}

function plannerStageForTool(name: PublicToolName): ReviewAgentTraceEntry['stage'] {
  if (name === 'inspect_workflow_contract' || name === 'inspect_sample_data') return 'ground'
  return 'plan'
}

function plannerCompletedTitle(name: PublicToolName): string {
  if (name === 'inspect_available_bio_tools') return 'Gemma 4 inspected public bioinformatics tools'
  if (name === 'inspect_available_workflows') return 'Gemma 4 inspected public workflows'
  if (name === 'select_workflow') return 'Gemma 4 selected a public workflow'
  if (name === 'inspect_workflow_contract') return 'Gemma 4 inspected the selected workflow contract'
  if (name === 'inspect_sample_data') return 'Gemma 4 inspected selected public toy data'
  if (name === 'draft_tool_level_plan') return 'Gemma 4 drafted a validated public tool-level plan'
  return `Gemma 4 used ${name}`
}

function plannerCompletedTitleForTool(tool: ExecutedPublicTool): string {
  if (tool.call.origin !== 'system_grounding') {
    return plannerCompletedTitle(tool.call.name as PublicToolName)
  }
  if (tool.call.name === 'select_workflow') return 'API recovered a public workflow selection'
  if (tool.call.name === 'draft_tool_level_plan') return 'API recovered a contract-grounded tool-level plan'
  return `API recovered ${tool.call.name} within the public planner contract`
}

function executedToolContext(tools: ExecutedPublicTool[]) {
  return tools.map((tool) => ({
    name: tool.call.name,
    origin: tool.call.origin,
    workflowKey: tool.result.workflowKey || tool.call.arguments.workflowKey,
    comparison: tool.result.comparison,
    status: tool.call.status,
  }))
}

function selectedWorkflowContext(memory: ReviewAgentMemory, tools: ExecutedPublicTool[]) {
  if (!memory.selectedWorkflowKey) return {}
  const workflow = publicWorkflowOrThrow(memory.selectedWorkflowKey)
  const inspectedContract = tools.some((tool) => tool.call.name === 'inspect_workflow_contract')
    ? {
        expectedStepOrder: workflow.steps.map((step) => step.id),
        steps: compactSteps(workflow.steps),
      }
    : undefined
  const inspectedSampleData = tools.some((tool) => tool.call.name === 'inspect_sample_data')
    ? {
        label: workflow.sampleData.label,
        files: workflow.sampleData.files,
      }
    : undefined
  return {
    selectedWorkflow: {
      workflowKey: workflow.key,
      workflowName: workflow.name,
      comparison: memory.comparison || 'condition comparison',
    },
    inspectedContract,
    inspectedSampleData,
    exactToolPlanOrder: wasToolExecuted(tools, 'inspect_workflow_contract') && wasToolExecuted(tools, 'inspect_sample_data')
      ? toolPlanPromptLines(workflow.key)
      : undefined,
  }
}

function plannerMessages(
  prompt: string,
  memory: ReviewAgentMemory,
  tools: ExecutedPublicTool[],
  allowedNames: PublicToolName[],
): GuidedToolStep['messages'] {
  return [
    {
      role: 'system',
      content: [
        'You are Gemma 4 acting as a controlled public bioinformatics planner.',
        'Choose exactly one next public tool from the allowed next tools using native tool calling.',
        'The API controls allowed tools, validates every tool argument, and executes only public workflow contracts.',
        'Do not choose tools outside the allowed list. Do not generate Docker commands, private paths, new images, or extra steps.',
        'Planning is complete only after draft_tool_level_plan is called and validated.',
      ].join('\n'),
    },
    {
      role: 'user',
      content: [
        `User request: ${prompt}`,
        `Allowed next tools: ${allowedNames.join(', ')}`,
        'Current public planner state:',
        JSON.stringify({
          selectedWorkflowKey: memory.selectedWorkflowKey || null,
          selectedWorkflowName: memory.selectedWorkflowName || null,
          comparison: memory.comparison || null,
          observedToyData: memory.observedToyData,
          completedTools: executedToolContext(tools),
          publicWorkflowCatalog: memory.selectedWorkflowKey ? undefined : workflowCatalogForPlanner(),
          ...selectedWorkflowContext(memory, tools),
        }),
        'Select exactly one allowed next tool and provide valid arguments for that tool.',
      ].join('\n'),
    },
  ]
}

function validatePlannerTransition(
  tool: ExecutedPublicTool,
  allowedNames: PublicToolName[],
  memory: ReviewAgentMemory,
) {
  if (!allowedNames.includes(tool.call.name as PublicToolName)) {
    throw new Error(`Planner selected ${tool.call.name}, but allowed next tools were: ${allowedNames.join(', ')}.`)
  }

  if (
    (tool.call.name === 'inspect_workflow_contract'
      || tool.call.name === 'inspect_sample_data'
      || tool.call.name === 'draft_tool_level_plan')
    && memory.selectedWorkflowKey
  ) {
    const workflowKey = String(tool.call.arguments.workflowKey || tool.result.workflowKey || '')
    if (workflowKey !== memory.selectedWorkflowKey) {
      throw new Error(`Planner used workflowKey=${workflowKey || 'empty'} after selecting ${memory.selectedWorkflowKey}.`)
    }
  }
}

async function callPlannerNextTool(
  provider: ProviderConfig,
  prompt: string,
  memory: ReviewAgentMemory,
  executedTools: ExecutedPublicTool[],
  allowedNames: PublicToolName[],
  modelCaller: ReviewAgentModelCaller,
): Promise<ExecutedPublicTool> {
  return callPublicToolWithFallback(provider, modelCaller, {
    allowedNames,
    messages: plannerMessages(prompt, memory, executedTools, allowedNames),
    index: executedTools.length,
    workflowKey: memory.selectedWorkflowKey as WorkflowKey | undefined,
    prompt,
    maxTokens: allowedNames.includes('draft_tool_level_plan') ? 1536 : 768,
    timeoutSeconds: allowedNames.includes('draft_tool_level_plan') ? 75 : 45,
  })
}

export async function requestReviewAgentPlan(
  provider: ProviderConfig,
  prompt: string,
  modelCaller: ReviewAgentModelCaller = requestModelChatWithTools,
): Promise<ModelPlan> {
  if (process.env.DEMO_SKIP_REVIEW_AGENT === '1') {
    const fallbackPlan = await requestModelPlan(provider, prompt)
    const agentRun = fallbackAgentRun(provider, prompt, 'Review agent was skipped by DEMO_SKIP_REVIEW_AGENT.', fallbackPlan)
    return { ...fallbackPlan, agentRun }
  }

  const memory = initializeMemory(prompt, provider)
  const trace: ReviewAgentTraceEntry[] = [
    traceEntry('understand-request', 'understand', 'completed', 'Read public analysis request', `Prompt length: ${prompt.trim().length} characters.`),
    traceEntry('controlled-planner-start', 'plan', 'completed', 'Start controlled public planner loop', 'Gemma 4 chooses the next public tool each round; the API constrains allowed transitions.'),
  ]

  try {
    // 中文：受控 loop 让 Gemma 4 每轮选择下一步公开工具；API 只暴露 allowed next tools 并校验状态转移。
    // EN: The controlled loop lets Gemma 4 choose the next public tool each round while the API exposes only allowed transitions.
    const executedTools: ExecutedPublicTool[] = []
    const maxPlannerSteps = 8
    for (let round = 0; round < maxPlannerSteps; round += 1) {
      const allowedNames = allowedPlannerTools(executedTools, memory)
      if (!allowedNames.length) break
      trace.push(traceEntry(
        `planner-round-${round + 1}`,
        'plan',
        'running',
        'Ask Gemma 4 to choose the next public planning tool',
        `Allowed next tools: ${allowedNames.join(', ')}`,
      ))
      const nextTool = await callPlannerNextTool(provider, prompt, memory, executedTools, allowedNames, modelCaller)
      validatePlannerTransition(nextTool, allowedNames, memory)
      executedTools.push(nextTool)
      updateMemoryFromTool(memory, nextTool)
      trace.push(traceEntry(
        `planner-tool-${round + 1}-${nextTool.call.name}`,
        plannerStageForTool(nextTool.call.name as PublicToolName),
        'completed',
        plannerCompletedTitleForTool(nextTool),
        nextTool.call.resultSummary,
      ))
      if (nextTool.call.name === 'draft_tool_level_plan') break
    }

    if (!wasToolExecuted(executedTools, 'draft_tool_level_plan')) {
      throw new Error('Controlled planner loop ended before draft_tool_level_plan.')
    }

    const failedTool = executedTools.find((tool) => tool.call.status === 'failed')
    if (failedTool) {
      throw new Error(failedTool.call.resultSummary || 'Guided native tool call failed.')
    }

    trace.push(traceEntry('ground-tools', 'ground', 'completed', 'Validate Gemma 4 tool-level plan against public workflow contracts', memory.selectedWorkflowName || memory.selectedWorkflowKey || 'workflow selected'))
    trace.push(traceEntry('execute-ready', 'execute', 'completed', 'Public workflow ready for controlled execution', 'Execution will be performed by the API against public Docker workflows.'))
    trace.push(traceEntry('reflect-pending', 'reflect', 'completed', 'Result reflection will run after tool execution', 'The model will summarize computed public results after Docker execution.'))

    const agentRun: ReviewAgentRun = {
      mode: executedTools.every((tool) => tool.native) ? 'native_guided_tool_calling' : 'guided_tool_calling',
      model: provider.model,
      memory,
      toolCalls: executedTools.map((tool) => tool.call),
      trace,
    }

    return buildPlanFromToolResults(provider, prompt, executedTools, agentRun, [
      ...executedTools.map((tool) => JSON.stringify(tool.call.arguments)),
    ].join('\n'))
  } catch (error) {
    trace.push(traceEntry(
      'guided-native-failed',
      'plan',
      'failed',
      'Guided native tool calling failed',
      error instanceof Error ? error.message : 'Guided native tool calling failed.',
    ))
    const reason = error instanceof Error ? error.message : 'Guided native tool calling failed.'
    const fallbackPlan = await requestModelPlan(provider, prompt)
    if (fallbackPlan.source === 'failed') {
      return deterministicFallbackPlan(provider, prompt, fallbackPlan.sourceMessage || reason)
    }
    const agentRun = fallbackAgentRun(provider, prompt, reason, fallbackPlan)
    agentRun.trace = [...trace, ...agentRun.trace]
    return { ...fallbackPlan, agentRun }
  }
}

function modeAfterAdditionalTool(agentRun: ReviewAgentRun, tool: ExecutedPublicTool): ReviewAgentRun['mode'] {
  if (agentRun.mode === 'json_fallback') {
    return 'json_fallback'
  }
  if (agentRun.mode === 'native_guided_tool_calling' && tool.native) {
    return 'native_guided_tool_calling'
  }
  return 'guided_tool_calling'
}

export async function appendReviewAgentResultSummary(
  provider: ProviderConfig,
  agentRun: ReviewAgentRun | undefined,
  workflowKey: string,
  compactResult: string,
  modelCaller: ReviewAgentModelCaller = requestModelChatWithTools,
): Promise<ReviewAgentRun | undefined> {
  if (!agentRun) return undefined
  const memory: ReviewAgentMemory = {
    ...agentRun.memory,
    observedToyData: [...agentRun.memory.observedToyData],
    toolCallIds: [...agentRun.memory.toolCallIds],
  }
  try {
    const summaryTool = await callGuidedTool(provider, modelCaller, {
      name: 'summarize_results',
      maxTokens: 384,
      timeoutSeconds: 45,
      messages: [
        {
          role: 'system',
          content: [
            'Use the required summarize_results tool. Return only the function call.',
            'Summarize only the public computed result provided by the API.',
            'Do not mention private data, clinical use, production systems, or unpublished architecture.',
          ].join('\n'),
        },
        {
          role: 'assistant',
          content: `Workflow selected during planning: ${workflowKey}`,
        },
        {
          role: 'user',
          content: `Summarize this compact public demo result for workflowKey=${workflowKey}: ${sanitizePublicText(compactResult)}`,
        },
      ],
    }, agentRun.toolCalls.length)
    updateMemoryFromTool(memory, summaryTool)
    return {
      ...agentRun,
      mode: modeAfterAdditionalTool(agentRun, summaryTool),
      memory,
      toolCalls: [...agentRun.toolCalls, summaryTool.call],
      trace: [
        ...agentRun.trace,
        traceEntry('summarize-results', 'reflect', 'completed', 'Gemma 4 summarized public computed results', summaryTool.call.resultSummary),
      ],
    }
  } catch (error) {
    return {
      ...agentRun,
      trace: [
        ...agentRun.trace,
        traceEntry('summarize-results', 'reflect', 'failed', 'Gemma 4 result summary tool call was unavailable', error instanceof Error ? error.message : 'summarize_results failed.'),
      ],
    }
  }
}

export async function persistReviewAgentArtifacts(jobId: string, agentRun?: ReviewAgentRun): Promise<ReviewAgentRun | undefined> {
  if (!agentRun) return undefined
  // 中文：持久化 Memory、Tool Calls 和 Trace，便于评审截图或直接打开 JSON artifact 复核。
  // EN: Memory, tool calls, and trace are persisted so reviewers can screenshot or inspect JSON artifacts directly.
  const outputDir = path.join(reviewDataRoot, 'jobs', jobId)
  await fs.mkdir(outputDir, { recursive: true })
  const artifactPaths = {
    memory: path.join(outputDir, 'agent-memory.json'),
    toolCalls: path.join(outputDir, 'tool-calls.json'),
    trace: path.join(outputDir, 'agent-trace.json'),
  }
  await fs.writeFile(artifactPaths.memory, JSON.stringify(agentRun.memory, null, 2))
  await fs.writeFile(artifactPaths.toolCalls, JSON.stringify(agentRun.toolCalls, null, 2))
  await fs.writeFile(artifactPaths.trace, JSON.stringify(agentRun.trace, null, 2))
  return {
    ...agentRun,
    artifactPaths,
  }
}
