import { describe, expect, it, vi } from 'vitest'
import { validateToolLevelPlan } from '../publicBioToolPlanning.js'
import { publicToolDefinitions, publicToolNames } from '../publicToolManifest.js'
import { assertPublicSampleFiles, assertPublicToolName, publicWorkflowOrThrow, sanitizePublicText } from '../reviewAgentGuards.js'
import {
  appendReviewAgentResultSummary,
  persistReviewAgentArtifacts,
  requestReviewAgentPlan,
  type ReviewAgentModelCaller,
} from '../reviewAgentRuntime.js'
import { routeConversation, routeConversationByRules } from '../conversationRouter.js'
import { requestModelChatWithTools } from '../llmClient.js'
import type { ProviderConfig } from '../types.js'
import type { WorkflowKey } from '../workflowCatalog.js'

const provider: ProviderConfig = {
  provider: 'local_openai_compatible',
  baseUrl: 'http://127.0.0.1:11434/v1',
  apiKey: 'local-placeholder-token',
  model: 'gemma4:latest',
}

function toolLevelPlanArguments(workflowKey: WorkflowKey) {
  const workflow = publicWorkflowOrThrow(workflowKey)
  return {
    workflowKey,
    intent: workflow.description,
    comparison: 'treatment vs control',
    steps: workflow.steps.map((step, index) => ({
      stepId: step.id,
      toolName: step.toolName,
      toolImage: step.toolImage,
      purpose: step.description,
      inputs: index === 0 ? workflow.sampleData.files.slice(0, 2) : [`artifact from ${workflow.steps[index - 1].id}`],
      outputs: [`public artifact from ${step.id}`],
      dependsOn: index === 0 ? [] : [workflow.steps[index - 1].id],
    })),
  }
}

function allowedToolNames(tools: Array<Record<string, unknown>>) {
  return tools
    .map((tool) => {
      const fn = tool.function && typeof tool.function === 'object'
        ? tool.function as { name?: string }
        : {}
      return String(fn.name || '')
    })
    .filter(Boolean)
}

function nextPlannerTool(allowedNames: string[]): string {
  for (const name of [
    'inspect_available_bio_tools',
    'select_workflow',
    'inspect_workflow_contract',
    'inspect_sample_data',
    'draft_tool_level_plan',
    'summarize_results',
  ]) {
    if (allowedNames.includes(name)) return name
  }
  return allowedNames[0] || ''
}

function toolArguments(name: string, workflowKey: WorkflowKey) {
  if (name === 'inspect_available_bio_tools') return {}
  if (name === 'select_workflow') {
    return {
      workflowKey,
      reason: `Public ${workflowKey} request.`,
      comparison: 'treatment vs control',
    }
  }
  if (name === 'inspect_workflow_contract' || name === 'inspect_sample_data') return { workflowKey }
  if (name === 'draft_tool_level_plan') return toolLevelPlanArguments(workflowKey)
  if (name === 'summarize_results') {
    return {
      workflowKey,
      compactResult: 'Public demo result summarized.',
    }
  }
  return {}
}

function toolResponse(id: string, name: string, args: Record<string, unknown>, native: boolean, forced = false) {
  if (!native) {
    return {
      content: JSON.stringify(forced ? args : { toolName: name, arguments: args }),
      toolCalls: [],
    }
  }
  return {
    content: '',
    toolCalls: [
      {
        id,
        function: {
          name,
          arguments: JSON.stringify(args),
        },
      },
    ],
  }
}

function sequentialModelCaller(workflowKey: WorkflowKey, native = true): ReviewAgentModelCaller {
  return vi.fn<ReviewAgentModelCaller>(async (_provider, _messages, tools, toolChoice) => {
    const forcedName = typeof toolChoice === 'object' ? toolChoice.function?.name : undefined
    const name = forcedName || nextPlannerTool(allowedToolNames(tools))
    if (!name) return { content: '', toolCalls: [], error: 'no allowed tool names' }
    return toolResponse(`call-${name}`, name, toolArguments(name, workflowKey), native, Boolean(forcedName))
  })
}

describe('public review agent manifest and guards', () => {
  it('exposes the required public tool names', () => {
    expect(publicToolNames()).toEqual([
      'inspect_available_bio_tools',
      'inspect_available_workflows',
      'inspect_workflow_contract',
      'inspect_sample_data',
      'select_workflow',
      'draft_tool_level_plan',
      'draft_execution_plan',
      'summarize_results',
    ])
  })

  it('defines strict object schemas for all public tools', () => {
    expect(publicToolDefinitions.every((definition) => definition.type === 'function')).toBe(true)
    expect(publicToolDefinitions.every((definition) => definition.function.parameters.additionalProperties === false)).toBe(true)
  })

  it('accepts only public workflow keys', () => {
    expect(publicWorkflowOrThrow('bulk_rna_seq').name).toContain('Bulk RNA-seq')
    expect(() => publicWorkflowOrThrow('private_workflow')).toThrow(/unknown workflowKey/)
  })

  it('accepts only public sample files from the selected workflow', () => {
    expect(() => assertPublicSampleFiles('bulk_rna_seq', ['demo-data/bulk_rnaseq/metadata.csv'])).not.toThrow()
    expect(() => assertPublicSampleFiles('bulk_rna_seq', ['private/customer.fastq'])).toThrow(/Unsupported public sample file/)
  })

  it('accepts only public review tool names', () => {
    expect(() => assertPublicToolName('select_workflow')).not.toThrow()
    expect(() => assertPublicToolName('unsupported_scheduler')).toThrow(/Unsupported public review tool/)
  })

  it('validates tool-level plans for all public workflows', () => {
    for (const workflowKey of ['bulk_rna_seq', 'single_cell_rna_seq', 'proteomics_lfq'] as WorkflowKey[]) {
      const validated = validateToolLevelPlan(toolLevelPlanArguments(workflowKey))
      expect(validated.workflowKey).toBe(workflowKey)
      expect(validated.steps.map((step) => step.stepId)).toEqual(publicWorkflowOrThrow(workflowKey).steps.map((step) => step.id))
      expect(validated.validation).toMatch(/public workflow contract/)
    }
  })

  it('rejects model plans that change public tool images', () => {
    const invalid = toolLevelPlanArguments('bulk_rna_seq')
    invalid.steps[0].toolImage = 'private.registry/internal-fastqc:latest'
    expect(() => validateToolLevelPlan(invalid)).toThrow(/must use public image/)
  })

  it('redacts private paths and secret-like values from trace text', () => {
    const privatePath = `/Users/example/Workspaces/Services/cross_reaction/${'cross_reaction_' + 'client'}/apps ${'api_key=' + 'abc123'}`
    const cleaned = sanitizePublicText(privatePath)
    expect(cleaned).toContain('[private-project-path]')
    expect(cleaned).toContain('api_key=[redacted]')
    expect(cleaned).not.toContain('abc123')
  })

  it('builds a model plan from guided native public tool calls', async () => {
    const modelCaller = sequentialModelCaller('bulk_rna_seq')

    const plan = await requestReviewAgentPlan(provider, 'Run a bulk RNA-seq treatment vs control analysis.', modelCaller)
    expect(plan.workflowKey).toBe('bulk_rna_seq')
    expect(plan.model).toBe('gemma4:latest')
    expect(plan.agentRun?.mode).toBe('native_guided_tool_calling')
    expect(plan.agentRun?.model).toBe('gemma4:latest')
    expect(plan.agentRun?.toolCalls.map((toolCall) => toolCall.name)).toEqual([
      'inspect_available_bio_tools',
      'select_workflow',
      'inspect_workflow_contract',
      'inspect_sample_data',
      'draft_tool_level_plan',
    ])
    expect(plan.agentRun?.toolCalls.every((toolCall) => toolCall.origin === 'model_native')).toBe(true)
    expect(plan.agentRun?.memory.toolCallIds).toEqual([
      'call-inspect_available_bio_tools',
      'call-select_workflow',
      'call-inspect_workflow_contract',
      'call-inspect_sample_data',
      'call-draft_tool_level_plan',
    ])
    expect(modelCaller).toHaveBeenCalledTimes(5)
    expect(vi.mocked(modelCaller).mock.calls.every((call) => call[3] === 'auto')).toBe(true)
    expect(plan.agentRun?.memory.observedToyData).toContain('demo-data/bulk_rnaseq/metadata.csv')
    expect(plan.steps.map((step) => step.id)).toEqual(publicWorkflowOrThrow('bulk_rna_seq').steps.map((step) => step.id))
    expect(plan.sourceMessage).toMatch(/controlled public planner loop/i)
  })

  it('builds tool-level plans for single-cell and proteomics workflows', async () => {
    for (const workflowKey of ['single_cell_rna_seq', 'proteomics_lfq'] as WorkflowKey[]) {
      const plan = await requestReviewAgentPlan(provider, `Run ${workflowKey} treatment vs control analysis.`, sequentialModelCaller(workflowKey))
      expect(plan.workflowKey).toBe(workflowKey)
      expect(plan.agentRun?.toolCalls.map((toolCall) => toolCall.name)).toContain('draft_tool_level_plan')
      expect(plan.steps.map((step) => step.id)).toEqual(publicWorkflowOrThrow(workflowKey).steps.map((step) => step.id))
      expect(plan.sourceMessage).toMatch(/tool-level plan/)
    }
  })

  it('disables reasoning for OpenAI-compatible native tool calls', async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body || '{}'))
      expect(body.reasoningEffort).toBe('none')
      expect(body.toolChoice).toBe('auto')
      expect(body.timeoutSeconds).toBe(45)
      expect(body.maxTokens).toBe(256)
      expect(body.tools).toHaveLength(1)
      return new Response(JSON.stringify({
        content: '',
        tool_calls: [
          {
            id: 'call-weather',
            type: 'function',
            function: {
              name: 'get_current_weather',
              arguments: '{"location":"Seoul"}',
            },
          },
        ],
      }), { status: 200 })
    })
    const originalFetch = globalThis.fetch
    globalThis.fetch = fetchMock as typeof fetch
    try {
      const response = await requestModelChatWithTools(provider, [
        { role: 'user', content: 'Use the weather tool for Seoul.' },
      ], [
        {
          type: 'function',
          function: {
            name: 'get_current_weather',
            parameters: { type: 'object', properties: { location: { type: 'string' } }, required: ['location'] },
          },
        },
      ])
      expect(response.toolCalls).toHaveLength(1)
      expect(response.toolCalls[0].function?.name).toBe('get_current_weather')
    } finally {
      globalThis.fetch = originalFetch
    }
  })

  it('captures guided tool-schema planning when native tool calls are absent', async () => {
    const modelCaller = sequentialModelCaller('bulk_rna_seq', false)

    const plan = await requestReviewAgentPlan(provider, 'Run a bulk RNA-seq treatment vs control analysis.', modelCaller)
    expect(plan.workflowKey).toBe('bulk_rna_seq')
    expect(plan.agentRun?.mode).toBe('guided_tool_calling')
    expect(plan.agentRun?.toolCalls.map((toolCall) => toolCall.name)).toEqual([
      'inspect_available_bio_tools',
      'select_workflow',
      'inspect_workflow_contract',
      'inspect_sample_data',
      'draft_tool_level_plan',
    ])
    expect(plan.agentRun?.toolCalls.every((toolCall) => toolCall.origin === 'model_schema')).toBe(true)
  })

  it('accepts object-shaped tool arguments from Gemma-compatible parsers', async () => {
    const workflowKey: WorkflowKey = 'bulk_rna_seq'
    const modelCaller = vi.fn<ReviewAgentModelCaller>(async (_provider, _messages, tools, toolChoice) => {
      const forcedName = typeof toolChoice === 'object' ? toolChoice.function?.name : undefined
      const name = forcedName || nextPlannerTool(allowedToolNames(tools))
      if (name === 'inspect_available_bio_tools') {
        return { content: '', toolCalls: [{ id: 'call-bio-tools-object', function: { name, arguments: {} } }] }
      }
      if (name === 'select_workflow') {
        return {
          content: '',
          toolCalls: [{
            id: 'call-select-object-args',
            function: {
              name,
              arguments: {
                workflowKey,
                reason: 'Object-shaped Gemma parser arguments.',
                comparison: 'treatment vs control',
              },
            },
          }],
        }
      }
      if (name === 'inspect_workflow_contract' || name === 'inspect_sample_data') {
        return { content: '', toolCalls: [{ id: `call-${name}-object`, function: { name, arguments: { workflowKey } } }] }
      }
      if (name === 'draft_tool_level_plan') {
        return { content: '', toolCalls: [{ id: 'call-tool-plan-object', function: { name, arguments: toolLevelPlanArguments(workflowKey) } }] }
      }
      return { content: '', toolCalls: [], error: 'unexpected tool choice' }
    })

    const plan = await requestReviewAgentPlan(provider, 'Run a bulk RNA-seq treatment vs control analysis.', modelCaller)
    expect(plan.agentRun?.mode).toBe('native_guided_tool_calling')
    expect(plan.agentRun?.toolCalls.find((toolCall) => toolCall.name === 'select_workflow')?.arguments.workflowKey).toBe('bulk_rna_seq')
    expect(plan.agentRun?.toolCalls.every((toolCall) => toolCall.origin === 'model_native')).toBe(true)
  })

  it('retries the current planner stage with schema JSON before using JSON fallback', async () => {
    const workflowKey: WorkflowKey = 'bulk_rna_seq'
    let pendingSchemaTool = ''
    let schemaFallbackRequests = 0
    const modelCaller = vi.fn<ReviewAgentModelCaller>(async (_provider, messages, tools, toolChoice, _reasoningEffort, _timeoutSeconds, _maxTokens, responseFormat) => {
      const forcedName = typeof toolChoice === 'object' ? toolChoice.function?.name : undefined
      const allowedNames = allowedToolNames(tools)
      if (allowedNames.length) {
        expect(responseFormat || 'text').toBe('text')
        expect(toolChoice).toBe('auto')
        pendingSchemaTool = forcedName || nextPlannerTool(allowedNames)
        return { content: '', toolCalls: [], error: 'native tool calls unavailable' }
      }
      schemaFallbackRequests += 1
      expect(toolChoice).toBeUndefined()
      expect(responseFormat).toBe('json_object')
      expect(messages.at(-1)?.content).toContain(`Allowed tool names:`)
      expect(messages.at(-1)?.content).toContain(pendingSchemaTool)
      const name = forcedName || pendingSchemaTool
      return {
        content: JSON.stringify({
          toolName: name,
          arguments: toolArguments(name, workflowKey),
        }),
        toolCalls: [],
      }
    })

    const plan = await requestReviewAgentPlan(provider, 'Run a bulk RNA-seq treatment vs control analysis.', modelCaller)
    expect(plan.workflowKey).toBe('bulk_rna_seq')
    expect(plan.agentRun?.mode).toBe('guided_tool_calling')
    expect(plan.agentRun?.toolCalls.every((toolCall) => toolCall.origin === 'model_schema')).toBe(true)
    expect(plan.agentRun?.toolCalls.map((toolCall) => toolCall.name)).toContain('draft_tool_level_plan')
    expect(plan.agentRun?.mode).not.toBe('json_fallback')
    expect(modelCaller).toHaveBeenCalledTimes(10)
    expect(schemaFallbackRequests).toBe(5)
  })

  it('recovers empty model responses within the controlled public planner contract', async () => {
    const workflowKey: WorkflowKey = 'bulk_rna_seq'
    const modelCaller = vi.fn<ReviewAgentModelCaller>(async (_provider, messages, tools, _toolChoice, _reasoningEffort, _timeoutSeconds, _maxTokens, responseFormat) => {
      const allowedNames = allowedToolNames(tools)
      const completedTools = messages.at(-1)?.content || ''
      expect(completedTools).not.toContain('resultSummary')
      if (allowedNames.includes('inspect_available_workflows')) {
        return toolResponse('call-inspect-workflows', 'inspect_available_workflows', {}, true)
      }
      if (allowedNames.includes('inspect_available_bio_tools')) {
        return toolResponse('call-inspect-bio-tools', 'inspect_available_bio_tools', {}, true)
      }
      if (allowedNames.length) {
        return { content: '', toolCalls: [], error: '' }
      }
      expect(responseFormat).toBe('json_object')
      return { content: '', toolCalls: [], error: '' }
    })

    const plan = await requestReviewAgentPlan(provider, 'Plan bulk RNA-seq treatment vs control analysis with QC, counting, differential summary, and report.', modelCaller)
    const toolCalls = plan.agentRun?.toolCalls || []

    expect(plan.workflowKey).toBe('bulk_rna_seq')
    expect(plan.agentRun?.mode).toBe('guided_tool_calling')
    expect(plan.agentRun?.mode).not.toBe('json_fallback')
    expect(toolCalls.map((toolCall) => toolCall.name)).toEqual([
      'inspect_available_workflows',
      'inspect_available_bio_tools',
      'select_workflow',
      'inspect_workflow_contract',
      'inspect_sample_data',
      'draft_tool_level_plan',
    ])
    expect(toolCalls.slice(2).every((toolCall) => toolCall.origin === 'system_grounding')).toBe(true)
    expect(toolCalls).not.toContainEqual(expect.objectContaining({ name: 'json_fallback_plan' }))
    expect(plan.sourceMessage).toMatch(/controlled recovery|recovered/i)
    expect(modelCaller).toHaveBeenCalledTimes(10)
  })

  it('falls back when native tool calls are unavailable', async () => {
    process.env.DEMO_SKIP_MODEL_PLANNING = '1'
    const modelCaller: ReviewAgentModelCaller = async () => ({
      content: '',
      toolCalls: [],
      error: 'tool calling unavailable',
    })

    const plan = await requestReviewAgentPlan(provider, 'Run a bulk RNA-seq treatment vs control analysis.', modelCaller)
    delete process.env.DEMO_SKIP_MODEL_PLANNING

    expect(plan.agentRun?.mode).toBe('json_fallback')
    expect(plan.workflowKey).toBe('bulk_rna_seq')
    expect(plan.agentRun?.toolCalls).toEqual([
      expect.objectContaining({
        id: 'json-fallback-plan',
        name: 'json_fallback_plan',
        origin: 'json_fallback',
        status: 'completed',
      }),
    ])
    expect(plan.agentRun?.memory.toolCallIds).toEqual(['json-fallback-plan'])
  })

  it('persists public review agent artifacts', async () => {
    process.env.DEMO_SKIP_MODEL_PLANNING = '1'
    const plan = await requestReviewAgentPlan(provider, 'Run a bulk RNA-seq treatment vs control analysis.', async () => ({
      content: '',
      toolCalls: [],
      error: 'force fallback',
    }))
    delete process.env.DEMO_SKIP_MODEL_PLANNING
    const persisted = await persistReviewAgentArtifacts('test-review-agent-artifacts', plan.agentRun)
    expect(persisted?.artifactPaths?.memory).toContain('agent-memory.json')
    expect(persisted?.artifactPaths?.toolCalls).toContain('tool-calls.json')
    expect(persisted?.artifactPaths?.trace).toContain('agent-trace.json')
  })

  it('appends result reflection as a guided summarize_results tool call', async () => {
    const modelCaller = sequentialModelCaller('bulk_rna_seq')
    const plan = await requestReviewAgentPlan(provider, 'Run a bulk RNA-seq treatment vs control analysis.', modelCaller)
    const reflected = await appendReviewAgentResultSummary(
      provider,
      plan.agentRun,
      'bulk_rna_seq',
      'GENE_A up, GENE_B down in public toy data.',
      modelCaller,
    )

    expect(reflected?.toolCalls.at(-1)).toEqual(expect.objectContaining({
      name: 'summarize_results',
      origin: 'model_native',
      status: 'completed',
    }))
    expect(reflected?.memory.toolCallIds).toContain('call-summarize_results')
  })
})

describe('conversation intent routing', () => {
  function conversationToolCaller(args: Record<string, unknown>) {
    return vi.fn<typeof requestModelChatWithTools>(async () => ({
      content: '',
      toolCalls: [
        {
          id: 'call-conversation-intent',
          function: {
            name: 'classify_conversation_intent',
            arguments: JSON.stringify(args),
          },
        },
      ],
    }))
  }

  it('does not start analysis when the user only mentions a workflow area', () => {
    const decision = routeConversationByRules('bulk RNA-seq', {})
    expect(decision?.action).toBe('clarify')
    expect(decision?.workflowKey).toBe('bulk_rna_seq')
  })

  it('starts analysis only for explicit execution intent', () => {
    const decision = routeConversationByRules('Please run bulk RNA-seq treatment vs control analysis now.', {})
    expect(decision?.action).toBe('run_analysis')
    expect(decision?.workflowKey).toBe('bulk_rna_seq')
    expect(decision?.analysisPrompt).toContain('bulk RNA-seq')
  })

  it('answers workflow questions without execution', () => {
    const decision = routeConversationByRules('Can you explain single-cell RNA-seq first?', {})
    expect(decision?.action).toBe('answer')
    expect(decision?.workflowKey).toBe('single_cell_rna_seq')
  })

  it('reports status instead of starting another active task', () => {
    const decision = routeConversationByRules('run proteomics analysis', {
      hasActiveTask: true,
      latestTaskStatus: 'running',
    })
    expect(decision?.action).toBe('status')
    expect(decision?.message).toMatch(/already running/i)
  })

  it('uses Gemma 4 model routing before fast-rule canned answers', async () => {
    const modelCaller = conversationToolCaller({
      action: 'answer',
      message: 'Bulk RNA-seq is available; execution starts only when you ask me to run it.',
      confidence: 0.91,
      workflowKey: 'bulk_rna_seq',
      reason: 'model classified a workflow question',
    })

    const decision = await routeConversation(provider, 'Can you explain bulk RNA-seq first?', {}, modelCaller)
    expect(decision.source).toBe('model')
    expect(decision.action).toBe('answer')
    expect(decision.workflowKey).toBe('bulk_rna_seq')
    expect(decision.message).toContain('Bulk RNA-seq is available')
    expect(modelCaller).toHaveBeenCalledTimes(1)
  })

  it('lets Gemma 4 start a public workflow when execution intent is clear', async () => {
    const modelCaller = conversationToolCaller({
      action: 'run_analysis',
      message: 'Starting the public label-free proteomics workflow.',
      confidence: 0.94,
      workflowKey: 'proteomics_lfq',
      analysisPrompt: 'Run label-free proteomics treatment vs control differential abundance analysis.',
      reason: 'explicit execution intent',
    })

    const decision = await routeConversation(provider, 'Please run proteomics analysis now.', {}, modelCaller)
    expect(decision.source).toBe('model')
    expect(decision.action).toBe('run_analysis')
    expect(decision.workflowKey).toBe('proteomics_lfq')
    expect(decision.analysisPrompt).toContain('proteomics')
  })

  it('corrects model confirmation prompts when the user already gave explicit execution intent', async () => {
    const modelCaller = conversationToolCaller({
      action: 'answer',
      message: 'I can plan that workflow for you. Would you like me to start the planning process now?',
      confidence: 0.86,
      workflowKey: 'bulk_rna_seq',
      reason: 'model asked for extra confirmation',
    })

    const decision = await routeConversation(
      provider,
      'Please plan bulk RNA-seq treatment vs control analysis now.',
      {},
      modelCaller,
    )

    expect(decision.source).toBe('fast_rule')
    expect(decision.action).toBe('run_analysis')
    expect(decision.workflowKey).toBe('bulk_rna_seq')
    expect(decision.message).toMatch(/Starting Bulk RNA-seq/i)
    expect(decision.analysisPrompt).toContain('bulk RNA-seq')
  })

  it('continues from previous workflow context when the user confirms the prior router response', async () => {
    const previousPrompt = 'I have a 10x-style single-cell RNA-seq dataset and want clusters and marker genes.'
    const modelCaller = vi.fn<typeof requestModelChatWithTools>(async (_provider, messages) => {
      expect(messages.at(-1)?.content).toContain('Previous workflow key: single_cell_rna_seq')
      expect(messages.at(-1)?.content).toContain(previousPrompt)
      return {
        content: '',
        toolCalls: [
          {
            id: 'call-conversation-intent',
            function: {
              name: 'classify_conversation_intent',
              arguments: JSON.stringify({
                action: 'answer',
                message: 'Confirmed.',
                confidence: 0.8,
                reason: 'model saw a short confirmation',
              }),
            },
          },
        ],
      }
    })

    const decision = await routeConversation(provider, 'yes', {
      previousAction: 'answer',
      previousWorkflowKey: 'single_cell_rna_seq',
      previousAnalysisPrompt: previousPrompt,
      previousMessage: 'I can plan that workflow for you. Would you like me to start the planning process now?',
    }, modelCaller)

    expect(decision.source).toBe('fast_rule')
    expect(decision.action).toBe('run_analysis')
    expect(decision.workflowKey).toBe('single_cell_rna_seq')
    expect(decision.analysisPrompt).toBe(previousPrompt)
  })

  it('keeps confirmation replies from starting a second workflow during an active task', async () => {
    const modelCaller = conversationToolCaller({
      action: 'run_analysis',
      message: 'Starting the previous workflow.',
      confidence: 0.93,
      workflowKey: 'proteomics_lfq',
      analysisPrompt: 'Run label-free proteomics analysis.',
      reason: 'model saw a confirmation',
    })

    const decision = await routeConversation(provider, 'go ahead', {
      hasActiveTask: true,
      latestTaskStatus: 'running',
      previousAction: 'answer',
      previousWorkflowKey: 'proteomics_lfq',
      previousAnalysisPrompt: 'Run label-free proteomics analysis.',
    }, modelCaller)

    expect(decision.source).toBe('fast_rule')
    expect(decision.action).toBe('status')
    expect(decision.message).toMatch(/already running/i)
  })

  it('does not treat yes as execution unless the previous response asked to start', async () => {
    const modelCaller = conversationToolCaller({
      action: 'answer',
      message: 'Bulk RNA-seq compares expression between conditions in the public demo.',
      confidence: 0.82,
      workflowKey: 'bulk_rna_seq',
      reason: 'model answered a general follow-up',
    })

    const decision = await routeConversation(provider, 'yes', {
      previousAction: 'answer',
      previousWorkflowKey: 'bulk_rna_seq',
      previousAnalysisPrompt: 'Can you explain bulk RNA-seq first?',
      previousMessage: 'Bulk RNA-seq is available in this public demo.',
    }, modelCaller)

    expect(decision.source).toBe('model')
    expect(decision.action).toBe('answer')
    expect(decision.workflowKey).toBe('bulk_rna_seq')
  })

  it('keeps backend safety guards when model asks to run during an active task', async () => {
    const modelCaller = conversationToolCaller({
      action: 'run_analysis',
      message: 'Starting another workflow.',
      confidence: 0.96,
      workflowKey: 'single_cell_rna_seq',
      analysisPrompt: 'Run single-cell RNA-seq analysis.',
      reason: 'model saw execution intent',
    })

    const decision = await routeConversation(provider, 'Run single-cell RNA-seq now.', {
      hasActiveTask: true,
      latestTaskStatus: 'running',
    }, modelCaller)
    expect(decision.source).toBe('fast_rule')
    expect(decision.action).toBe('status')
    expect(decision.message).toMatch(/already running/i)
  })
})
