import fs from 'node:fs/promises'
import path from 'node:path'
import { requestModelSummary } from './llmClient.js'
import { singleCellDataRoot, reviewDataRoot } from './paths.js'
import { csvTable, ensurePipelineDirs, runVisibleDockerTool, toContainerScript, type PipelineEventSink } from './pipelineCommon.js'
import { demoToolImages } from './toolImages.js'
import type { ModelPlan, PipelineResult, ProviderConfig } from './types.js'

function scanpyScript(): string {
  return String.raw`
set -e
python - <<'PY'
import csv
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc

data_dir = Path("/data")
out_dir = Path("/out")
out_dir.mkdir(parents=True, exist_ok=True)

metadata = pd.read_csv(data_dir / "metadata" / "cell_metadata.csv").set_index("cell_id")
matrix = pd.read_csv(data_dir / "matrix" / "gene_counts.csv").set_index("gene")
markers = pd.read_csv(data_dir / "reference" / "gene_markers.csv")

adata = ad.AnnData(matrix.T.astype(float))
adata.obs = metadata.loc[adata.obs_names].copy()

sc.pp.calculate_qc_metrics(adata, percent_top=None, inplace=True)
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.tl.pca(adata, n_comps=min(3, adata.n_obs - 1, adata.n_vars - 1), svd_solver="arpack")
sc.pp.neighbors(adata, n_neighbors=min(3, max(2, adata.n_obs - 1)), n_pcs=min(3, adata.obsm["X_pca"].shape[1]))
sc.tl.leiden(adata, resolution=0.6, key_added="cluster")
sc.tl.rank_genes_groups(adata, "cluster", method="wilcoxon")

cell_summary = adata.obs[["sample", "condition", "expected_cell_type", "cluster", "total_counts", "n_genes_by_counts"]].copy()
cell_summary.insert(0, "cell_id", cell_summary.index)
cell_summary.to_csv(out_dir / "cell_clusters.csv", index=False)

marker_rows = []
ranked = adata.uns["rank_genes_groups"]
for cluster in ranked["names"].dtype.names:
    for rank, gene in enumerate(ranked["names"][cluster][:5], start=1):
        marker_info = markers[markers["gene"] == gene]
        marker_rows.append({
            "cluster": cluster,
            "rank": rank,
            "gene": gene,
            "score": float(ranked["scores"][cluster][rank - 1]),
            "marker_for": "" if marker_info.empty else marker_info.iloc[0]["marker_for"],
            "interpretation": "" if marker_info.empty else marker_info.iloc[0]["interpretation"],
        })
pd.DataFrame(marker_rows).to_csv(out_dir / "marker_genes.csv", index=False)

activation_genes = [gene for gene in ["IFNG", "MKI67"] if gene in adata.var_names]
state_rows = []
raw_counts = matrix.T
for gene in activation_genes:
    control_mean = raw_counts.loc[metadata["condition"] == "control", gene].mean()
    treatment_mean = raw_counts.loc[metadata["condition"] == "treatment", gene].mean()
    log2fc = np.log2((treatment_mean + 1) / (control_mean + 1))
    state_rows.append({
        "gene": gene,
        "controlMean": round(float(control_mean), 3),
        "treatmentMean": round(float(treatment_mean), 3),
        "log2FoldChange": round(float(log2fc), 3),
        "direction": "up" if log2fc > 0.5 else "down" if log2fc < -0.5 else "stable",
    })
pd.DataFrame(state_rows).to_csv(out_dir / "cell_state_changes.csv", index=False)

summary = {
    "cells": int(adata.n_obs),
    "genes": int(adata.n_vars),
    "clusters": int(adata.obs["cluster"].nunique()),
    "tool": "Scanpy",
}

with (out_dir / "scanpy_summary.json").open("w") as handle:
    json.dump(summary, handle, indent=2)
PY
`
}

function limmaStateScript(): string {
  return String.raw`
set -e
Rscript - <<'RSCRIPT'
suppressPackageStartupMessages(library(limma))

data_dir <- "/data"
out_dir <- "/out"
metadata <- read.csv(file.path(data_dir, "metadata", "cell_metadata.csv"), stringsAsFactors = FALSE)
counts <- read.csv(file.path(data_dir, "matrix", "gene_counts.csv"), stringsAsFactors = FALSE, check.names = FALSE)
markers <- read.csv(file.path(data_dir, "reference", "gene_markers.csv"), stringsAsFactors = FALSE)

matrix <- as.matrix(counts[, -1])
rownames(matrix) <- counts$gene
mode(matrix) <- "numeric"
sample_conditions <- setNames(metadata$condition, metadata$cell_id)
matrix <- matrix[, metadata$cell_id]
log_expr <- log2(matrix + 1)

condition <- factor(sample_conditions[colnames(log_expr)], levels = c("control", "treatment"))
design <- model.matrix(~ condition)
fit <- lmFit(log_expr, design)
fit <- eBayes(fit)
result <- topTable(fit, coef = "conditiontreatment", number = Inf, sort.by = "P")
result$gene <- rownames(result)
result <- merge(result, markers, by = "gene", all.x = TRUE)
result <- result[, c("gene", "marker_for", "interpretation", "logFC", "AveExpr", "t", "P.Value", "adj.P.Val", "B")]
write.csv(result, file.path(out_dir, "limma_cell_state_changes.csv"), row.names = FALSE, quote = FALSE)
RSCRIPT
`
}

function createReport(modelPlan: ModelPlan, modelSummary: string): string {
  return [
    '# Single-cell RNA-seq Demo Analysis Report',
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
    'Executed with a real public Scanpy Docker runtime.',
    '',
    '## Model Interpretation',
    modelSummary,
    '',
  ].join('\n')
}

export async function runSingleCellDemo(
  jobId: string,
  provider: ProviderConfig,
  modelPlan: ModelPlan,
  emitEvent?: PipelineEventSink,
): Promise<PipelineResult> {
  const outputDir = path.join(reviewDataRoot, 'jobs', jobId)
  const { logDir } = await ensurePipelineDirs(outputDir)
  const fastqcDir = path.join(outputDir, 'single_cell_fastqc')
  const fastpDir = path.join(outputDir, 'single_cell_fastp')
  await fs.mkdir(fastqcDir, { recursive: true })
  await fs.mkdir(fastpDir, { recursive: true })
  const toolRuns = []

  toolRuns.push(await runVisibleDockerTool({
    id: '01-fastqc',
    name: 'FastQC single-cell read quality control',
    image: demoToolImages.fastqc.image,
    toolKey: 'fastqc',
    mounts: [
      { host: singleCellDataRoot, container: '/data', mode: 'ro' },
      { host: fastqcDir, container: '/fastqc', mode: 'rw' },
    ],
    outputs: [
      path.join(fastqcDir, 'control_cells_fastqc.html'),
      path.join(fastqcDir, 'treatment_cells_fastqc.html'),
    ],
    command: toContainerScript('fastqc -o /fastqc /data/fastq/control_cells.fastq /data/fastq/treatment_cells.fastq'),
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '02-fastp',
    name: 'fastp single-cell read preprocessing',
    image: demoToolImages.fastp.image,
    toolKey: 'fastp',
    mounts: [
      { host: singleCellDataRoot, container: '/data', mode: 'ro' },
      { host: fastpDir, container: '/fastp', mode: 'rw' },
    ],
    outputs: [
      path.join(fastpDir, 'control_cells.trimmed.fastq'),
      path.join(fastpDir, 'treatment_cells.trimmed.fastq'),
      path.join(fastpDir, 'control_fastp.json'),
      path.join(fastpDir, 'treatment_fastp.json'),
    ],
    command: toContainerScript([
      'fastp -i /data/fastq/control_cells.fastq -o /fastp/control_cells.trimmed.fastq -j /fastp/control_fastp.json -h /fastp/control_fastp.html --thread 1',
      'fastp -i /data/fastq/treatment_cells.fastq -o /fastp/treatment_cells.trimmed.fastq -j /fastp/treatment_fastp.json -h /fastp/treatment_fastp.html --thread 1',
    ].join(' && ')),
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '03-scanpy',
    name: 'Scanpy single-cell clustering and marker analysis',
    image: demoToolImages.scanpy.image,
    toolKey: 'scanpy',
    mounts: [
      { host: singleCellDataRoot, container: '/data', mode: 'ro' },
      { host: outputDir, container: '/out', mode: 'rw' },
    ],
    outputs: [
      path.join(outputDir, 'cell_clusters.csv'),
      path.join(outputDir, 'marker_genes.csv'),
      path.join(outputDir, 'cell_state_changes.csv'),
      path.join(outputDir, 'scanpy_summary.json'),
    ],
    command: toContainerScript(scanpyScript()),
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '04-limma',
    name: 'limma marker-level cell-state comparison',
    image: demoToolImages.limma.image,
    toolKey: 'limma',
    mounts: [
      { host: singleCellDataRoot, container: '/data', mode: 'ro' },
      { host: outputDir, container: '/out', mode: 'rw' },
    ],
    outputs: [
      path.join(outputDir, 'limma_cell_state_changes.csv'),
    ],
    command: toContainerScript(limmaStateScript()),
  }, logDir, emitEvent))

  emitEvent?.({
    id: 'model-interpretation',
    phase: 'model',
    status: 'running',
    title: 'Generate model interpretation',
    detail: `Sending Scanpy outputs to ${provider.model}.`,
    toolName: 'OpenAI-compatible model endpoint',
  })

  const stateChanges = await fs.readFile(path.join(outputDir, 'cell_state_changes.csv'), 'utf8')
  const modelSummary = await requestModelSummary(provider, [
    {
      role: 'user',
      content: `Final answer only. One short sentence. Single-cell Scanpy result: ${stateChanges}`,
    },
  ], 'Model interpretation unavailable; inspect the Scanpy cluster, marker, and cell-state tables for computed results.')

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
    workflowKey: 'single_cell_rna_seq',
    plan: modelPlan.steps,
    modelPlan,
    agentRun: modelPlan.agentRun,
    toolRuns,
    tables: [
      await csvTable('Cell clusters', path.join(outputDir, 'cell_clusters.csv')),
      await csvTable('Marker genes', path.join(outputDir, 'marker_genes.csv')),
      await csvTable('Treatment-associated cell-state changes', path.join(outputDir, 'cell_state_changes.csv')),
      await csvTable('limma marker-level cell-state comparison', path.join(outputDir, 'limma_cell_state_changes.csv')),
    ],
    outputDir,
    reportMarkdown,
    summary: modelSummary,
  }
}
