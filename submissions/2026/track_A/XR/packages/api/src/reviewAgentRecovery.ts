import { workflowSummaryForPublicTrace, publicWorkflowOrThrow } from './reviewAgentGuards.js'
import type { ChatToolCall } from './llmClient.js'
import type { PublicToolName } from './publicToolManifest.js'
import type { WorkflowKey } from './workflowCatalog.js'

function exampleWorkflow(workflowKey?: string) {
  try {
    return publicWorkflowOrThrow(workflowKey || 'bulk_rna_seq')
  } catch {
    return publicWorkflowOrThrow('bulk_rna_seq')
  }
}

function workflowForPrompt(prompt?: string, workflowKey?: string) {
  if (workflowKey) return exampleWorkflow(workflowKey)
  const lower = (prompt || '').toLowerCase()
  if (lower.includes('single-cell') || lower.includes('single cell') || lower.includes('scanpy')) {
    return publicWorkflowOrThrow('single_cell_rna_seq')
  }
  if (lower.includes('proteomics') || lower.includes('protein') || lower.includes('lfq')) {
    return publicWorkflowOrThrow('proteomics_lfq')
  }
  return publicWorkflowOrThrow('bulk_rna_seq')
}

function exampleToolLevelPlan(workflowKey?: string) {
  const workflow = exampleWorkflow(workflowKey)
  return {
    workflowKey: workflow.key,
    intent: workflow.description,
    comparison: workflow.key === 'bulk_rna_seq' ? 'treatment vs control' : 'condition comparison',
    steps: workflow.steps.map((step, index) => ({
      stepId: step.id,
      toolName: step.toolName || 'not specified',
      toolImage: step.toolImage || 'not specified',
      purpose: step.description,
      inputs: index === 0 ? workflow.sampleData.files.slice(0, 2) : [`artifact from ${workflow.steps[index - 1].id}`],
      outputs: [`public artifact from ${step.id}`],
      dependsOn: index === 0 ? [] : [workflow.steps[index - 1].id],
    })),
  }
}

export function schemaFallbackExampleForTool(name: PublicToolName, directArguments: boolean, workflowKey?: string, prompt?: string): string {
  const workflow = workflowForPrompt(prompt, workflowKey)
  const comparison = workflow.key === 'bulk_rna_seq' ? 'treatment vs control' : 'condition comparison'
  const argsByTool: Record<PublicToolName, Record<string, unknown>> = {
    inspect_available_bio_tools: {},
    inspect_available_workflows: {},
    inspect_workflow_contract: { workflowKey: workflow.key },
    inspect_sample_data: { workflowKey: workflow.key },
    select_workflow: {
      workflowKey: workflow.key,
      reason: 'Short reason based on the user request.',
      comparison,
    },
    draft_tool_level_plan: exampleToolLevelPlan(workflow.key),
    draft_execution_plan: {
      workflowKey: workflow.key,
      intent: workflow.description,
      comparison,
      requestedOutputs: ['QC summary', 'differential expression report'],
    },
    summarize_results: {
      workflowKey: workflow.key,
      compactResult: 'Public toy result summary.',
    },
  }
  const args = argsByTool[name]
  return JSON.stringify(directArguments ? args : { toolName: name, arguments: args })
}

const controlledRecoveryPriority: PublicToolName[] = [
  'inspect_available_bio_tools',
  'inspect_available_workflows',
  'select_workflow',
  'inspect_workflow_contract',
  'inspect_sample_data',
  'draft_tool_level_plan',
  'draft_execution_plan',
]

export function controlledRecoveryToolCall(
  allowedNames: PublicToolName[],
  index: number,
  workflowKey?: WorkflowKey,
  prompt?: string,
): ChatToolCall | undefined {
  const name = controlledRecoveryPriority.find((candidate) => allowedNames.includes(candidate))
  if (!name) return undefined
  const workflow = workflowForPrompt(prompt, workflowKey)
  const comparison = workflow.key === 'bulk_rna_seq' || (prompt || '').toLowerCase().includes('treatment')
    ? 'treatment vs control'
    : 'condition comparison'
  const argsByTool: Partial<Record<PublicToolName, Record<string, unknown>>> = {
    inspect_available_bio_tools: {},
    inspect_available_workflows: {},
    inspect_workflow_contract: { workflowKey: workflow.key },
    inspect_sample_data: { workflowKey: workflow.key },
    select_workflow: {
      workflowKey: workflow.key,
      reason: `Controlled recovery selected ${workflow.name} after the model endpoint returned an empty planning response.`,
      comparison,
    },
    draft_tool_level_plan: exampleToolLevelPlan(workflow.key),
    draft_execution_plan: {
      workflowKey: workflow.key,
      intent: workflow.description,
      comparison,
      requestedOutputs: ['QC summary', 'differential analysis', 'public review report'],
    },
  }
  return {
    id: `system-recovery-${name}-${index + 1}`,
    type: 'function',
    function: {
      name,
      arguments: JSON.stringify(argsByTool[name] || {}),
    },
  }
}

export function workflowCatalogForPlanner() {
  return workflowSummaryForPublicTrace().map((workflow) => ({
    key: workflow.key,
    name: workflow.name,
    description: workflow.description,
    executionMode: workflow.executionMode,
  }))
}
