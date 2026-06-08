import { demoToolImages } from './toolImages.js'
import type { PlannedStep } from './types.js'
import { findWorkflow, workflowCatalog, type WorkflowContract, type WorkflowKey } from './workflowCatalog.js'
import { sanitizePublicText } from './reviewAgentGuards.js'

export type PublicBioToolPlanStep = {
  stepId: string
  title: string
  toolName: string
  toolImage: string
  purpose: string
  inputs: string[]
  outputs: string[]
  dependsOn: string[]
}

export type ValidatedToolLevelPlan = {
  workflowKey: WorkflowKey
  workflowName: string
  intent: string
  comparison: string
  steps: PublicBioToolPlanStep[]
  validation: string
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => sanitizePublicText(item).trim())
    .filter(Boolean)
    .slice(0, 8)
}

function compactContractStep(step: PlannedStep) {
  return {
    stepId: step.id,
    title: step.title,
    toolName: step.toolName || 'not specified',
    toolImage: step.toolImage || 'not specified',
    description: step.description,
  }
}

export function publicBioToolCatalogForTrace() {
  return [
    {
      key: 'fastqc',
      name: 'FastQC',
      image: demoToolImages.fastqc.image,
      role: 'FASTQ read quality control.',
      workflows: ['bulk_rna_seq', 'single_cell_rna_seq'],
    },
    {
      key: 'trimmomatic',
      name: 'Trimmomatic',
      image: demoToolImages.trimmomatic.image,
      role: 'Single-end read preprocessing for the public bulk RNA-seq workflow.',
      workflows: ['bulk_rna_seq'],
    },
    {
      key: 'fastp',
      name: 'fastp',
      image: demoToolImages.fastp.image,
      role: 'Read preprocessing and quality reports for the public single-cell workflow.',
      workflows: ['single_cell_rna_seq'],
    },
    {
      key: 'kallisto',
      name: 'kallisto',
      image: demoToolImages.kallisto.image,
      role: 'Transcript quantification for the public bulk RNA-seq workflow.',
      workflows: ['bulk_rna_seq'],
    },
    {
      key: 'pydeseq2',
      name: 'PyDESeq2',
      image: demoToolImages.pydeseq2.image,
      role: 'Differential expression from the public bulk RNA-seq count matrix.',
      workflows: ['bulk_rna_seq'],
    },
    {
      key: 'multiqc',
      name: 'MultiQC',
      image: demoToolImages.multiqc.image,
      role: 'Aggregation of public QC and workflow reports.',
      workflows: ['bulk_rna_seq'],
    },
    {
      key: 'scanpy',
      name: 'Scanpy',
      image: demoToolImages.scanpy.image,
      role: 'Single-cell QC, normalization, clustering, and marker-gene analysis.',
      workflows: ['single_cell_rna_seq'],
    },
    {
      key: 'limma',
      name: 'limma',
      image: demoToolImages.limma.image,
      role: 'Linear-model differential analysis for public single-cell marker and proteomics workflows.',
      workflows: ['single_cell_rna_seq', 'proteomics_lfq'],
    },
    {
      key: 'openms',
      name: 'OpenMS',
      image: demoToolImages.openms.image,
      role: 'mzML-like input inspection for the public proteomics workflow.',
      workflows: ['proteomics_lfq'],
    },
    {
      key: 'msstats',
      name: 'MSstats',
      image: demoToolImages.msstats.image,
      role: 'LFQ table compatibility check for downstream MS statistical workflows.',
      workflows: ['proteomics_lfq'],
    },
    {
      key: 'gemma4_summary',
      name: 'Gemma 4 via OpenAI-compatible API',
      image: 'local model endpoint',
      role: 'Public result reflection after deterministic workflow execution.',
      workflows: ['bulk_rna_seq', 'single_cell_rna_seq', 'proteomics_lfq'],
    },
  ]
}

export function publicWorkflowContractForModel(workflow: WorkflowContract) {
  return {
    workflowKey: workflow.key,
    workflowName: workflow.name,
    description: workflow.description,
    executionMode: workflow.executionMode,
    executionNote: workflow.executionNote,
    sampleData: workflow.sampleData,
    expectedStepOrder: workflow.steps.map((step) => step.id),
    steps: workflow.steps.map(compactContractStep),
    boundary: 'The model may draft the visible tool-level plan, but execution uses only this fixed public contract.',
  }
}

export function validateToolLevelPlan(args: Record<string, unknown>): ValidatedToolLevelPlan {
  const workflow = findWorkflow(args.workflowKey)
  const rawSteps = Array.isArray(args.steps) ? args.steps : []
  if (!rawSteps.length) {
    throw new Error('draft_tool_level_plan must include a non-empty steps array.')
  }

  const expectedIds = workflow.steps.map((step) => step.id)
  const seen = new Set<string>()
  const validatedSteps = rawSteps.map((rawStep, index) => {
    if (!rawStep || typeof rawStep !== 'object') {
      throw new Error(`Tool-level plan step ${index + 1} must be an object.`)
    }
    const record = rawStep as Record<string, unknown>
    const contractStep = workflow.steps[index]
    if (!contractStep) {
      throw new Error(`Tool-level plan contains an extra step at position ${index + 1}.`)
    }

    const stepId = sanitizePublicText(record.stepId || record.id).trim()
    if (stepId !== contractStep.id) {
      throw new Error(`Tool-level plan step ${index + 1} must be ${contractStep.id}, got ${stepId || 'empty'}.`)
    }
    if (seen.has(stepId)) {
      throw new Error(`Duplicate tool-level plan step: ${stepId}.`)
    }

    const toolName = sanitizePublicText(record.toolName || contractStep.toolName).trim()
    if (toolName && contractStep.toolName && toolName !== contractStep.toolName) {
      throw new Error(`Step ${stepId} must use public tool ${contractStep.toolName}, got ${toolName}.`)
    }

    const toolImage = sanitizePublicText(record.toolImage || contractStep.toolImage).trim()
    if (toolImage && contractStep.toolImage && toolImage !== contractStep.toolImage) {
      throw new Error(`Step ${stepId} must use public image ${contractStep.toolImage}, got ${toolImage}.`)
    }

    const dependsOn = stringList(record.dependsOn)
    for (const dependency of dependsOn) {
      if (!seen.has(dependency)) {
        throw new Error(`Step ${stepId} depends on ${dependency}, which is not an earlier public contract step.`)
      }
    }
    seen.add(stepId)

    return {
      stepId,
      title: contractStep.title,
      toolName: contractStep.toolName || 'not specified',
      toolImage: contractStep.toolImage || 'not specified',
      purpose: sanitizePublicText(record.purpose || contractStep.description).trim() || contractStep.description,
      inputs: stringList(record.inputs),
      outputs: stringList(record.outputs),
      dependsOn,
    }
  })

  const actualIds = validatedSteps.map((step) => step.stepId)
  if (actualIds.join('|') !== expectedIds.join('|')) {
    throw new Error(`Tool-level plan must follow public contract order: ${expectedIds.join(' -> ')}.`)
  }

  return {
    workflowKey: workflow.key,
    workflowName: workflow.name,
    intent: sanitizePublicText(args.intent || workflow.description),
    comparison: sanitizePublicText(args.comparison || 'condition comparison'),
    steps: validatedSteps,
    validation: 'Tool-level plan matched the public workflow contract, public tool names, and public container allowlist.',
  }
}

export function plannedStepsFromValidatedToolPlan(plan: ValidatedToolLevelPlan): PlannedStep[] {
  const workflow = findWorkflow(plan.workflowKey)
  return workflow.steps.map((contractStep, index) => {
    const planned = plan.steps[index]
    return {
      id: contractStep.id,
      title: contractStep.title,
      description: planned?.purpose || contractStep.description,
      toolName: contractStep.toolName,
      toolImage: contractStep.toolImage,
    }
  })
}

export function toolPlanPromptLines(workflowKey: WorkflowKey): string {
  const workflow = findWorkflow(workflowKey)
  return workflow.steps
    .map((step, index) => [
      `${index + 1}. stepId=${step.id}`,
      `toolName=${step.toolName || 'not specified'}`,
      `toolImage=${step.toolImage || 'not specified'}`,
      `purpose=${step.description}`,
    ].join('; '))
    .join('\n')
}

export function workflowKeysWithPublicToolPlans(): WorkflowKey[] {
  return workflowCatalog.map((workflow) => workflow.key)
}
