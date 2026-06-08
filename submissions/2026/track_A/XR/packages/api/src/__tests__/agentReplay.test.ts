import { describe, expect, it, vi } from 'vitest'
import { publicWorkflowOrThrow } from '../reviewAgentGuards.js'
import { requestReviewAgentPlan, type ReviewAgentModelCaller } from '../reviewAgentRuntime.js'
import type { ProviderConfig } from '../types.js'
import type { WorkflowKey } from '../workflowCatalog.js'

const provider: ProviderConfig = {
  provider: 'local_openai_compatible',
  baseUrl: 'http://127.0.0.1:11434/v1',
  apiKey: 'local-placeholder-token',
  model: 'gemma4:latest',
}

const replayCases: Array<{ workflowKey: WorkflowKey; prompt: string; script: string[] }> = [
  {
    workflowKey: 'bulk_rna_seq',
    prompt: 'Plan bulk RNA-seq treatment vs control analysis with QC, counting, differential summary, and report.',
    script: [
      'inspect_available_bio_tools',
      'select_workflow',
      'inspect_workflow_contract',
      'inspect_sample_data',
      'draft_tool_level_plan',
    ],
  },
  {
    workflowKey: 'single_cell_rna_seq',
    prompt: 'I have a 10x-style single-cell RNA-seq dataset and want to identify cell clusters, marker genes, and treatment-associated cell-state changes. Please plan the analysis using the available public tools.',
    script: [
      'inspect_available_bio_tools',
      'select_workflow',
      'inspect_sample_data',
      'inspect_workflow_contract',
      'draft_tool_level_plan',
    ],
  },
  {
    workflowKey: 'proteomics_lfq',
    prompt: 'I have label-free proteomics spectra for treatment and control samples. Please plan quality control, peptide or protein identification, quantification, differential abundance analysis, and a concise interpretation.',
    script: [
      'inspect_available_workflows',
      'inspect_available_bio_tools',
      'select_workflow',
      'inspect_sample_data',
      'inspect_workflow_contract',
      'draft_tool_level_plan',
    ],
  },
]

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

function argsForTool(name: string, workflowKey: WorkflowKey) {
  if (name === 'inspect_available_bio_tools' || name === 'inspect_available_workflows') return {}
  if (name === 'select_workflow') {
    return {
      workflowKey,
      reason: `Replay selected ${workflowKey}.`,
      comparison: 'treatment vs control',
    }
  }
  if (name === 'inspect_workflow_contract' || name === 'inspect_sample_data') return { workflowKey }
  if (name === 'draft_tool_level_plan') return toolLevelPlanArguments(workflowKey)
  return {}
}

function replayModelCaller(workflowKey: WorkflowKey, script: string[]): ReviewAgentModelCaller {
  let cursor = 0
  return vi.fn<ReviewAgentModelCaller>(async (_provider, _messages, tools) => {
    const allowed = allowedToolNames(tools)
    const scripted = script.find((name, index) => index >= cursor && allowed.includes(name))
    const name = scripted || allowed[0]
    cursor = Math.max(cursor + 1, script.indexOf(name) + 1)
    return {
      content: JSON.stringify({
        toolName: name,
        arguments: argsForTool(name, workflowKey),
      }),
      toolCalls: [],
    }
  })
}

describe('controlled planner replay', () => {
  it('replays the three preset prompts through schema guided planning without JSON fallback', async () => {
    for (const replayCase of replayCases) {
      const modelCaller = replayModelCaller(replayCase.workflowKey, replayCase.script)
      const plan = await requestReviewAgentPlan(provider, replayCase.prompt, modelCaller)

      expect(plan.workflowKey).toBe(replayCase.workflowKey)
      expect(plan.agentRun?.mode).toBe('guided_tool_calling')
      expect(plan.agentRun?.toolCalls.every((toolCall) => toolCall.origin === 'model_schema')).toBe(true)
      expect(plan.agentRun?.toolCalls.map((toolCall) => toolCall.name)).toEqual(replayCase.script)
      expect(plan.agentRun?.toolCalls.map((toolCall) => toolCall.name)).not.toContain('json_fallback_plan')
      expect(plan.steps.map((step) => step.id)).toEqual(publicWorkflowOrThrow(replayCase.workflowKey).steps.map((step) => step.id))
      expect(plan.sourceMessage).toMatch(/controlled public planner loop/i)
    }
  })
})
