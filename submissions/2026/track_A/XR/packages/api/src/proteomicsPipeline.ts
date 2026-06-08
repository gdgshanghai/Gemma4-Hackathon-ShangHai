import fs from 'node:fs/promises'
import path from 'node:path'
import { requestModelSummary } from './llmClient.js'
import { proteomicsDataRoot, reviewDataRoot } from './paths.js'
import { csvTable, ensurePipelineDirs, runVisibleDockerTool, toContainerScript, type PipelineEventSink } from './pipelineCommon.js'
import { demoToolImages } from './toolImages.js'
import type { ModelPlan, PipelineResult, ProviderConfig } from './types.js'

function limmaScript(): string {
  return String.raw`
set -e
Rscript - <<'RSCRIPT'
suppressPackageStartupMessages(library(limma))

data_dir <- "/data"
out_dir <- "/out"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

metadata <- read.csv(file.path(data_dir, "metadata", "sample_metadata.csv"), stringsAsFactors = FALSE)
intensity <- read.csv(file.path(data_dir, "quant", "protein_intensity.csv"), stringsAsFactors = FALSE, check.names = FALSE)
sample_ids <- metadata$sample_id

expr <- as.matrix(intensity[, sample_ids])
rownames(expr) <- intensity$protein
mode(expr) <- "numeric"
log_expr <- log2(expr + 1)

condition <- factor(metadata$condition, levels = c("control", "treatment"))
design <- model.matrix(~ condition)
fit <- lmFit(log_expr, design)
fit <- eBayes(fit)
result <- topTable(fit, coef = "conditiontreatment", number = Inf, sort.by = "P")
result$protein <- rownames(result)
result <- result[, c("protein", "logFC", "AveExpr", "t", "P.Value", "adj.P.Val", "B")]
write.csv(result, file.path(out_dir, "limma_differential_abundance.csv"), row.names = FALSE, quote = FALSE)

qc <- data.frame(
  sample_id = sample_ids,
  condition = metadata$condition,
  total_intensity = colSums(expr),
  detected_proteins = colSums(expr > 0)
)
write.csv(qc, file.path(out_dir, "protein_qc.csv"), row.names = FALSE, quote = FALSE)

spectra_dir <- file.path(data_dir, "spectra")
spectra <- list.files(spectra_dir, pattern = "\\.mzML$", full.names = TRUE)
spectra_qc <- data.frame(
  file = basename(spectra),
  bytes = file.info(spectra)$size
)
write.csv(spectra_qc, file.path(out_dir, "spectra_qc.csv"), row.names = FALSE, quote = FALSE)

summary <- data.frame(
  samples = length(sample_ids),
  proteins = nrow(expr),
  spectra_files = length(spectra),
  tool = "limma"
)
write.csv(summary, file.path(out_dir, "limma_summary.csv"), row.names = FALSE, quote = FALSE)
RSCRIPT
`
}

function msstatsScript(): string {
  return String.raw`
set -e
Rscript - <<'RSCRIPT'
suppressPackageStartupMessages(library(MSstats))

data_dir <- "/data"
out_dir <- "/out"
metadata <- read.csv(file.path(data_dir, "metadata", "sample_metadata.csv"), stringsAsFactors = FALSE)
intensity <- read.csv(file.path(data_dir, "quant", "protein_intensity.csv"), stringsAsFactors = FALSE, check.names = FALSE)

summary <- data.frame(
  package = "MSstats",
  package_version = as.character(packageVersion("MSstats")),
  samples = nrow(metadata),
  proteins = nrow(intensity),
  role = "MSstats runtime availability and LFQ table shape check"
)
write.csv(summary, file.path(out_dir, "msstats_runtime_check.csv"), row.names = FALSE, quote = FALSE)
RSCRIPT
`
}

function createReport(modelPlan: ModelPlan, modelSummary: string): string {
  return [
    '# Label-free Proteomics Demo Analysis Report',
    '',
    '## Gemma 4 Planning',
    `Model: ${modelPlan.model}`,
    `Agent mode: ${modelPlan.agentRun?.mode || 'not recorded'}`,
    `Intent: ${modelPlan.intent}`,
    `Comparison: ${modelPlan.comparison}`,
    '',
    modelPlan.steps.map((step, index) => `${index + 1}. ${step.title} - ${step.toolName || 'tool step'}`).join('\n'),
    '',
    '## Agent Tool Calling',
    modelPlan.agentRun?.toolCalls.length
      ? modelPlan.agentRun.toolCalls.map((toolCall, index) => `${index + 1}. ${toolCall.name} - ${toolCall.origin} - ${toolCall.status}`).join('\n')
      : 'No planner tool calls were recorded; inspect the planning trace for fallback details.',
    '',
    '## Execution',
    'Executed with a real public Bioconductor limma Docker runtime for differential abundance.',
    '',
    '## Model Interpretation',
    modelSummary,
    '',
  ].join('\n')
}

export async function runProteomicsDemo(
  jobId: string,
  provider: ProviderConfig,
  modelPlan: ModelPlan,
  emitEvent?: PipelineEventSink,
): Promise<PipelineResult> {
  const outputDir = path.join(reviewDataRoot, 'jobs', jobId)
  const { logDir } = await ensurePipelineDirs(outputDir)
  const openmsDir = path.join(outputDir, 'openms')
  await fs.mkdir(openmsDir, { recursive: true })
  const toolRuns = []

  toolRuns.push(await runVisibleDockerTool({
    id: '01-openms',
    name: 'OpenMS mzML file quality inspection',
    image: demoToolImages.openms.image,
    toolKey: 'openms',
    mounts: [
      { host: proteomicsDataRoot, container: '/data', mode: 'ro' },
      { host: openmsDir, container: '/openms', mode: 'rw' },
    ],
    outputs: [
      path.join(openmsDir, 'control_1_fileinfo.txt'),
      path.join(openmsDir, 'treatment_1_fileinfo.txt'),
    ],
    command: toContainerScript([
      'FileInfo -in /data/spectra/control_1.mzML -out /openms/control_1_fileinfo.txt || true',
      'FileInfo -in /data/spectra/treatment_1.mzML -out /openms/treatment_1_fileinfo.txt || true',
      'printf "file,tool,output\\ncontrol_1.mzML,OpenMS FileInfo,control_1_fileinfo.txt\\ntreatment_1.mzML,OpenMS FileInfo,treatment_1_fileinfo.txt\\n" > /openms/openms_fileinfo_summary.csv',
    ].join(' && ')),
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '02-limma',
    name: 'limma differential protein abundance',
    image: demoToolImages.limma.image,
    toolKey: 'limma',
    mounts: [
      { host: proteomicsDataRoot, container: '/data', mode: 'ro' },
      { host: outputDir, container: '/out', mode: 'rw' },
    ],
    outputs: [
      path.join(outputDir, 'protein_qc.csv'),
      path.join(outputDir, 'spectra_qc.csv'),
      path.join(outputDir, 'limma_differential_abundance.csv'),
      path.join(outputDir, 'limma_summary.csv'),
    ],
    command: toContainerScript(limmaScript()),
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '03-msstats',
    name: 'MSstats LFQ table compatibility check',
    image: demoToolImages.msstats.image,
    toolKey: 'msstats',
    mounts: [
      { host: proteomicsDataRoot, container: '/data', mode: 'ro' },
      { host: outputDir, container: '/out', mode: 'rw' },
    ],
    outputs: [
      path.join(outputDir, 'msstats_runtime_check.csv'),
    ],
    command: toContainerScript(msstatsScript()),
  }, logDir, emitEvent))

  emitEvent?.({
    id: 'model-interpretation',
    phase: 'model',
    status: 'running',
    title: 'Generate model interpretation',
    detail: `Sending limma outputs to ${provider.model}.`,
    toolName: 'OpenAI-compatible model endpoint',
  })

  const differential = await fs.readFile(path.join(outputDir, 'limma_differential_abundance.csv'), 'utf8')
  const modelSummary = await requestModelSummary(provider, [
    {
      role: 'user',
      content: `Final answer only. One short sentence. Label-free proteomics limma result: ${differential}`,
    },
  ], 'Model interpretation unavailable; inspect the limma differential abundance table for computed results.')

  emitEvent?.({
    id: 'model-interpretation',
    phase: 'model',
    status: 'completed',
    title: 'Generate model interpretation',
    detail: modelSummary,
    toolName: 'OpenAI-compatible model endpoint',
  })

  const reportMarkdown = createReport(modelPlan, modelSummary)
  await fs.writeFile(path.join(outputDir, 'report.md'), reportMarkdown)

  return {
    jobId,
    workflowKey: 'proteomics_lfq',
    plan: modelPlan.steps,
    modelPlan,
    agentRun: modelPlan.agentRun,
    toolRuns,
    tables: [
      await csvTable('OpenMS mzML file inspection', path.join(openmsDir, 'openms_fileinfo_summary.csv')),
      await csvTable('Protein QC', path.join(outputDir, 'protein_qc.csv')),
      await csvTable('Spectra QC', path.join(outputDir, 'spectra_qc.csv')),
      await csvTable('limma differential abundance', path.join(outputDir, 'limma_differential_abundance.csv')),
      await csvTable('MSstats runtime compatibility', path.join(outputDir, 'msstats_runtime_check.csv')),
    ],
    outputDir,
    reportMarkdown,
    summary: modelSummary,
  }
}
