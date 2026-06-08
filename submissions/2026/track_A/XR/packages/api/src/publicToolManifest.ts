import { workflowCatalog } from './workflowCatalog.js'

export type PublicToolName =
  | 'inspect_available_bio_tools'
  | 'inspect_available_workflows'
  | 'inspect_workflow_contract'
  | 'inspect_sample_data'
  | 'select_workflow'
  | 'draft_tool_level_plan'
  | 'draft_execution_plan'
  | 'summarize_results'

export type PublicToolDefinition = {
  type: 'function'
  function: {
    name: PublicToolName
    description: string
    parameters: Record<string, unknown>
  }
}

function objectSchema(properties: Record<string, unknown>, required: string[] = []) {
  return {
    type: 'object',
    properties,
    required,
    additionalProperties: false,
  }
}

const workflowEnum = workflowCatalog.map((workflow) => workflow.key)
const stepIdEnum = workflowCatalog.flatMap((workflow) => workflow.steps.map((step) => step.id))
const toolNameEnum = Array.from(new Set(workflowCatalog.flatMap((workflow) => workflow.steps.map((step) => step.toolName || 'not specified'))))
const toolImageEnum = Array.from(new Set(workflowCatalog.flatMap((workflow) => workflow.steps.map((step) => step.toolImage || 'not specified'))))

function stringArraySchema(description: string) {
  return {
    type: 'array',
    items: { type: 'string' },
    description,
  }
}

// 中文：这些是暴露给 Gemma 4 的公开函数调用契约，评审可从这里确认 Agent 只能选择公开 workflow、样例数据和工具容器。
// EN: These are the public function-calling contracts exposed to Gemma 4, so reviewers can verify the agent is limited to public workflows, sample data, and tool containers.
export const publicToolDefinitions: PublicToolDefinition[] = [
  {
    type: 'function',
    function: {
      name: 'inspect_available_bio_tools',
      description: 'List concrete public bioinformatics tools available for Gemma 4 tool-level planning.',
      parameters: objectSchema({}),
    },
  },
  {
    type: 'function',
    function: {
      name: 'inspect_available_workflows',
      description: 'List public review workflows and public tool containers available in this demo.',
      parameters: objectSchema({}),
    },
  },
  {
    type: 'function',
    function: {
      name: 'inspect_workflow_contract',
      description: 'Inspect the fixed public workflow contract for one selected workflow before drafting a tool-level plan.',
      parameters: objectSchema({
        workflowKey: {
          type: 'string',
          enum: workflowEnum,
          description: 'Public workflow key to inspect.',
        },
      }, ['workflowKey']),
    },
  },
  {
    type: 'function',
    function: {
      name: 'inspect_sample_data',
      description: 'Inspect public toy sample data for one selected workflow.',
      parameters: objectSchema({
        workflowKey: {
          type: 'string',
          enum: workflowEnum,
          description: 'Public workflow key to inspect.',
        },
      }, ['workflowKey']),
    },
  },
  {
    type: 'function',
    function: {
      name: 'select_workflow',
      description: 'Select one public workflow for the user request and explain the public review reason.',
      parameters: objectSchema({
        workflowKey: {
          type: 'string',
          enum: workflowEnum,
        },
        reason: {
          type: 'string',
          description: 'Short public reason for selecting this workflow.',
        },
        comparison: {
          type: 'string',
          description: 'Comparison extracted from the request, such as treatment vs control.',
        },
      }, ['workflowKey', 'reason', 'comparison']),
    },
  },
  {
    type: 'function',
    function: {
      name: 'draft_tool_level_plan',
      description: 'Draft a concrete bioinformatics tool-level plan that follows the selected public workflow contract exactly.',
      parameters: objectSchema({
        workflowKey: {
          type: 'string',
          enum: workflowEnum,
        },
        intent: {
          type: 'string',
          description: 'Short public analysis intent extracted from the request.',
        },
        comparison: {
          type: 'string',
          description: 'Condition comparison for the public toy workflow.',
        },
        steps: {
          type: 'array',
          description: 'Tool-level steps in the exact public workflow contract order.',
          items: objectSchema({
            stepId: {
              type: 'string',
              enum: stepIdEnum,
              description: 'Step id from the selected public workflow contract.',
            },
            toolName: {
              type: 'string',
              enum: toolNameEnum,
              description: 'Public tool name from the selected workflow contract.',
            },
            toolImage: {
              type: 'string',
              enum: toolImageEnum,
              description: 'Pinned public container image from the selected workflow contract.',
            },
            purpose: {
              type: 'string',
              description: 'Why this public tool step is needed for the user request.',
            },
            inputs: stringArraySchema('Public toy data or previous-step artifacts consumed by this step.'),
            outputs: stringArraySchema('Public review artifacts expected from this step.'),
            dependsOn: stringArraySchema('Earlier public step ids this step depends on.'),
          }, ['stepId', 'toolName', 'toolImage', 'purpose']),
        },
      }, ['workflowKey', 'intent', 'comparison', 'steps']),
    },
  },
  {
    type: 'function',
    function: {
      name: 'draft_execution_plan',
      description: 'Draft visible execution plan steps using only the selected public workflow contract.',
      parameters: objectSchema({
        workflowKey: {
          type: 'string',
          enum: workflowEnum,
        },
        intent: {
          type: 'string',
          description: 'Short analysis intent extracted from the request.',
        },
        comparison: {
          type: 'string',
          description: 'Condition comparison for the public toy workflow.',
        },
        requestedOutputs: {
          type: 'array',
          items: { type: 'string' },
          description: 'Requested public outputs such as QC, count matrix, differential summary, or report.',
        },
      }, ['workflowKey', 'intent', 'comparison']),
    },
  },
  {
    type: 'function',
    function: {
      name: 'summarize_results',
      description: 'Summarize public computed result tables in one concise sentence with one caveat.',
      parameters: objectSchema({
        workflowKey: {
          type: 'string',
          enum: workflowEnum,
        },
        compactResult: {
          type: 'string',
          description: 'Compact public result table summary.',
        },
      }, ['workflowKey', 'compactResult']),
    },
  },
]

export function publicToolNames() {
  return publicToolDefinitions.map((definition) => definition.function.name)
}
