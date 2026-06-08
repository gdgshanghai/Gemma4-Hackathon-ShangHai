import { spawn } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'
import { dataRoot, reviewDataRoot } from './paths.js'
import { requestModelSummary } from './llmClient.js'
import { demoToolImages } from './toolImages.js'
import { csvTable, parseCsv, runVisibleDockerTool, toContainerScript, type PipelineEventSink } from './pipelineCommon.js'
import type {
  CountMatrix,
  DifferentialGene,
  ModelPlan,
  PipelineResult,
  ProviderConfig,
  SampleMetadata,
  SampleQc,
} from './types.js'

function parseMetadata(csv: string): SampleMetadata[] {
  const lines = csv.trim().split(/\r?\n/)
  return lines.slice(1).map((line) => {
    const [sampleId, condition, fastq] = line.split(',')
    if (!sampleId || !condition || !fastq) {
      throw new Error(`Invalid metadata line: ${line}`)
    }
    if (condition !== 'control' && condition !== 'treatment') {
      throw new Error(`Unsupported condition: ${condition}`)
    }
    return { sampleId, condition, fastq }
  })
}

function parseFastq(raw: string): string[] {
  const lines = raw.trim().split(/\r?\n/)
  if (lines.length % 4 !== 0) {
    throw new Error('FASTQ file must contain groups of four lines.')
  }

  const reads: string[] = []
  for (let i = 0; i < lines.length; i += 4) {
    if (!lines[i].startsWith('@') || lines[i + 2] !== '+') {
      throw new Error(`Invalid FASTQ record near line ${i + 1}`)
    }
    if (lines[i + 1].trim().length !== lines[i + 3].trim().length) {
      throw new Error(`FASTQ sequence and quality lengths differ near line ${i + 1}`)
    }
    reads.push(lines[i + 1].trim().toUpperCase())
  }
  return reads
}

function parseReference(raw: string): Record<string, string> {
  const markers: Record<string, string> = {}
  let currentGene = ''

  for (const line of raw.trim().split(/\r?\n/)) {
    if (line.startsWith('>')) {
      currentGene = line.slice(1).trim()
      markers[currentGene] = ''
    } else if (currentGene) {
      markers[currentGene] += line.trim().toUpperCase()
    }
  }

  return markers
}

function gcPercent(reads: string[]): number {
  const joined = reads.join('')
  if (!joined.length) return 0
  const gc = Array.from(joined).filter((base) => base === 'G' || base === 'C').length
  return Number(((gc / joined.length) * 100).toFixed(2))
}

function averageLength(reads: string[]): number {
  if (!reads.length) return 0
  return Number((reads.reduce((sum, read) => sum + read.length, 0) / reads.length).toFixed(2))
}

function countReads(reads: string[], markers: Record<string, string>): Record<string, number> {
  const counts: Record<string, number> = {}

  for (const gene of Object.keys(markers)) {
    const marker = markers[gene]
    counts[gene] = reads.filter((read) => read.includes(marker)).length
  }

  return counts
}

function mean(values: number[]): number {
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function differential(counts: CountMatrix, metadata: SampleMetadata[]): DifferentialGene[] {
  const genes = Object.keys(counts)
  const controlSamples = metadata.filter((sample) => sample.condition === 'control').map((sample) => sample.sampleId)
  const treatmentSamples = metadata.filter((sample) => sample.condition === 'treatment').map((sample) => sample.sampleId)

  return genes
    .map((gene) => {
      const controlMean = mean(controlSamples.map((sampleId) => counts[gene][sampleId] ?? 0))
      const treatmentMean = mean(treatmentSamples.map((sampleId) => counts[gene][sampleId] ?? 0))
      const log2FoldChange = Math.log2((treatmentMean + 1) / (controlMean + 1))
      const score = Math.abs(log2FoldChange) * Math.log2(controlMean + treatmentMean + 2)
      const direction: DifferentialGene['direction'] =
        log2FoldChange > 0.5 ? 'up' : log2FoldChange < -0.5 ? 'down' : 'stable'

      return {
        gene,
        controlMean: Number(controlMean.toFixed(3)),
        treatmentMean: Number(treatmentMean.toFixed(3)),
        log2FoldChange: Number(log2FoldChange.toFixed(3)),
        score: Number(score.toFixed(3)),
        direction,
      }
    })
    .sort((a, b) => b.score - a.score)
}

function toCsv(rows: Array<Record<string, string | number>>): string {
  if (!rows.length) return ''
  const headers = Object.keys(rows[0])
  const body = rows.map((row) => headers.map((header) => row[header]).join(','))
  return [headers.join(','), ...body].join('\n') + '\n'
}

function countMatrixToCsv(counts: CountMatrix, metadata: SampleMetadata[]): string {
  const sampleIds = metadata.map((sample) => sample.sampleId)
  const rows = Object.entries(counts).map(([gene, sampleCounts]) => ({
    gene,
    ...Object.fromEntries(sampleIds.map((sampleId) => [sampleId, sampleCounts[sampleId] ?? 0])),
  }))
  return toCsv(rows)
}

function createReport(
  prompt: string,
  qc: SampleQc[],
  differentialGenes: DifferentialGene[],
  modelSummary: string,
  modelPlan: ModelPlan,
): string {
  const topGenes = differentialGenes
    .map((gene) => `- ${gene.gene}: ${gene.direction}, log2FC=${gene.log2FoldChange}, score=${gene.score}`)
    .join('\n')

  const qcLines = qc
    .map((sample) => `- ${sample.sampleId} (${sample.condition}): ${sample.reads} reads, ${sample.averageLength} bp average, ${sample.gcPercent}% GC`)
    .join('\n')

  return [
    '# Bulk RNA-seq Toy Analysis Report',
    '',
    `Prompt: ${prompt}`,
    '',
    '## Gemma 4 Planning',
    `Model: ${modelPlan.model}`,
    `Plan source: ${modelPlan.source === 'model' ? 'Generated by Gemma 4' : 'Fallback template'}`,
    `Agent mode: ${modelPlan.agentRun?.mode || 'not recorded'}`,
    `Intent: ${modelPlan.intent}`,
    `Comparison: ${modelPlan.comparison}`,
    'Grounding: plan wording is attached to public tool containers before execution.',
    '',
    modelPlan.steps.map((step, index) => `${index + 1}. ${step.title} - ${step.toolName || 'tool step'}`).join('\n'),
    '',
    '## Agent Tool Calling',
    modelPlan.agentRun?.toolCalls.length
      ? modelPlan.agentRun.toolCalls.map((toolCall, index) => `${index + 1}. ${toolCall.name} - ${toolCall.origin} - ${toolCall.status}`).join('\n')
      : 'No planner tool calls were recorded; inspect the planning trace for fallback details.',
    '',
    '## Execution',
    'Executed with real Docker tool containers: FastQC, Trimmomatic, kallisto, PyDESeq2, and MultiQC.',
    '',
    '## QC',
    qcLines,
    '',
    '## Differential Summary',
    topGenes,
    '',
    '## Model Interpretation',
    modelSummary,
    '',
  ].join('\n')
}

async function readFastqcSummary(fastqcDir: string, metadata: SampleMetadata[]): Promise<SampleQc[]> {
  return Promise.all(metadata.map(async (sample) => {
    const zipPath = path.join(fastqcDir, `${sample.sampleId}_fastqc.zip`)
    const zipList = await runLocalProcess('unzip', ['-p', zipPath, `${sample.sampleId}_fastqc/fastqc_data.txt`])
    if (zipList.code !== 0) {
      throw new Error(`Unable to read FastQC data for ${sample.sampleId}: ${zipList.stderr}`)
    }

    const metrics = Object.fromEntries(zipList.stdout
      .split(/\r?\n/)
      .map((line) => line.split('\t'))
      .filter((parts) => parts.length >= 2)
      .map(([key, value]) => [key, value]))

    return {
      sampleId: sample.sampleId,
      condition: sample.condition,
      reads: Number(metrics['Total Sequences'] || 0),
      averageLength: Number(metrics['Sequence length'] || 0),
      gcPercent: Number(metrics['%GC'] || 0),
    }
  }))
}

function runLocalProcess(command: string, args: string[]): Promise<{ stdout: string; stderr: string; code: number | null }> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'] })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (chunk: Buffer) => {
      stdout += chunk.toString()
    })
    child.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString()
    })
    child.on('error', reject)
    child.on('close', (code: number | null) => resolve({ stdout, stderr, code }))
  })
}

export async function runBulkRnaseqDemo(
  jobId: string,
  prompt: string,
  provider: ProviderConfig,
  modelPlan: ModelPlan,
  emitEvent?: PipelineEventSink,
): Promise<PipelineResult> {
  const outputDir = path.join(reviewDataRoot, 'jobs', jobId)
  const logDir = path.join(outputDir, 'logs')
  const fastqcDir = path.join(outputDir, 'fastqc')
  const trimmedDir = path.join(outputDir, 'trimmed')
  const trimmomaticDir = path.join(outputDir, 'trimmomatic')
  const multiqcDir = path.join(outputDir, 'multiqc')
  await fs.mkdir(outputDir, { recursive: true })
  await fs.mkdir(fastqcDir, { recursive: true })
  await fs.mkdir(trimmedDir, { recursive: true })
  await fs.mkdir(trimmomaticDir, { recursive: true })
  await fs.mkdir(multiqcDir, { recursive: true })

  const toolRuns = []
  const metadata = parseMetadata(await fs.readFile(path.join(dataRoot, 'metadata.csv'), 'utf8'))
  const fastqInputs = metadata.map((sample) => `/data/${sample.fastq}`).join(' ')
  const sampleIds = metadata.map((sample) => sample.sampleId)

  toolRuns.push(await runVisibleDockerTool({
    id: '01-fastqc',
    name: 'FastQC read quality control',
    image: demoToolImages.fastqc.image,
    toolKey: 'fastqc',
    mounts: [
      { host: dataRoot, container: '/data', mode: 'ro' },
      { host: fastqcDir, container: '/fastqc', mode: 'rw' },
    ],
    outputs: metadata.flatMap((sample) => [
      path.join(fastqcDir, `${sample.sampleId}_fastqc.html`),
      path.join(fastqcDir, `${sample.sampleId}_fastqc.zip`),
    ]),
    command: toContainerScript(`fastqc -o /fastqc ${fastqInputs}`),
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '02-trimmomatic',
    name: 'Trimmomatic read preprocessing',
    image: demoToolImages.trimmomatic.image,
    toolKey: 'trimmomatic',
    mounts: [
      { host: dataRoot, container: '/data', mode: 'ro' },
      { host: trimmedDir, container: '/trimmed', mode: 'rw' },
      { host: trimmomaticDir, container: '/trimmomatic', mode: 'rw' },
    ],
    outputs: metadata.map((sample) => path.join(trimmedDir, `${sample.sampleId}.fastq`)),
    command: toContainerScript(metadata.map((sample) => [
      `trimmomatic SE -phred33 -threads 1 /data/${sample.fastq} /trimmed/${sample.sampleId}.fastq MINLEN:20`,
      `echo "${sample.sampleId},trimmed,/trimmed/${sample.sampleId}.fastq" >> /trimmomatic/trimmomatic_summary.csv`,
    ].join(' && ')).join(' && ')),
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '03-kallisto',
    name: 'kallisto transcript quantification',
    image: demoToolImages.kallisto.image,
    toolKey: 'kallisto',
    mounts: [
      { host: dataRoot, container: '/data', mode: 'ro' },
      { host: outputDir, container: '/out', mode: 'rw' },
      { host: trimmedDir, container: '/trimmed', mode: 'ro' },
    ],
    outputs: [path.join(outputDir, 'count_matrix.csv')],
    command: toContainerScript([
      'set -e',
      'mkdir -p /out/kallisto_index /out/kallisto_quant',
      'kallisto index -i /out/kallisto_index/transcripts.idx -k 21 /data/reference_transcripts.fa',
      sampleIds.map((sampleId) => `kallisto quant --plaintext -i /out/kallisto_index/transcripts.idx -o /out/kallisto_quant/${sampleId} --single -l 30 -s 2 /trimmed/${sampleId}.fastq`).join('\n'),
      `printf 'gene,${sampleIds.join(',')}\\n' > /out/count_matrix.csv`,
      `awk 'FNR==1{next}{count[$1]=count[$1]","int($4+0.5)}END{for (gene in count) print gene count[gene]}' ${sampleIds.map((sampleId) => `/out/kallisto_quant/${sampleId}/abundance.tsv`).join(' ')} | sort >> /out/count_matrix.csv`,
    ].join('\n')),
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '04-pydeseq2',
    name: 'PyDESeq2 differential expression',
    image: demoToolImages.pydeseq2.image,
    toolKey: 'pydeseq2',
    mounts: [
      { host: dataRoot, container: '/data', mode: 'ro' },
      { host: outputDir, container: '/out', mode: 'rw' },
    ],
    outputs: [path.join(outputDir, 'differential_expression.csv')],
  }, logDir, emitEvent))

  toolRuns.push(await runVisibleDockerTool({
    id: '05-multiqc',
    name: 'MultiQC report aggregation',
    image: demoToolImages.multiqc.image,
    toolKey: 'multiqc',
    mounts: [
      { host: outputDir, container: '/out', mode: 'ro' },
      { host: multiqcDir, container: '/multiqc', mode: 'rw' },
    ],
    outputs: [
      path.join(multiqcDir, 'multiqc_report.html'),
      path.join(multiqcDir, 'multiqc_data'),
    ],
    command: toContainerScript('multiqc /out -o /multiqc --force'),
  }, logDir, emitEvent))

  const qc = await readFastqcSummary(fastqcDir, metadata)
  await fs.writeFile(path.join(outputDir, 'qc_summary.csv'), toCsv(qc.map((sample) => ({
    sampleId: sample.sampleId,
    condition: sample.condition,
    reads: sample.reads,
    averageLength: sample.averageLength,
    gcPercent: sample.gcPercent,
  }))))
  const counts = parseCountMatrix(await fs.readFile(path.join(outputDir, 'count_matrix.csv'), 'utf8'))
  const differentialGenes = parseCsv(await fs.readFile(path.join(outputDir, 'differential_expression.csv'), 'utf8'))
    .map((row) => ({
      gene: String(row.gene),
      controlMean: Number(row.controlMean),
      treatmentMean: Number(row.treatmentMean),
      log2FoldChange: Number(row.log2FoldChange),
      score: Number(row.score),
      direction: row.direction as DifferentialGene['direction'],
    }))
  const compactResult = differentialGenes
    .map((gene) => `${gene.gene}: ${gene.direction}, log2FC ${gene.log2FoldChange}`)
    .join('; ')

  emitEvent?.({
    id: 'model-interpretation',
    phase: 'model',
    status: 'running',
    title: 'Generate model interpretation',
    detail: `Sending compact result to ${provider.model}.`,
    toolName: 'OpenAI-compatible model endpoint',
  })

  let modelSummary = ''
  try {
    modelSummary = await requestModelSummary(provider, [
      {
        role: 'user',
        content: `Final answer only. One short sentence. Toy RNA-seq result: ${compactResult}.`,
      },
    ], 'Model interpretation unavailable; inspect the bulk RNA-seq differential expression table for computed results.')
    emitEvent?.({
      id: 'model-interpretation',
      phase: 'model',
      status: 'completed',
      title: 'Generate model interpretation',
      detail: modelSummary,
      toolName: 'OpenAI-compatible model endpoint',
    })
  } catch (error) {
    emitEvent?.({
      id: 'model-interpretation',
      phase: 'model',
      status: 'failed',
      title: 'Generate model interpretation',
      detail: error instanceof Error ? error.message : 'Model interpretation failed.',
      toolName: 'OpenAI-compatible model endpoint',
    })
    throw error
  }

  const reportMarkdown = createReport(prompt, qc, differentialGenes, modelSummary, modelPlan)

  await fs.writeFile(path.join(outputDir, 'report.md'), reportMarkdown)

  return {
    jobId,
    workflowKey: 'bulk_rna_seq',
    plan: modelPlan.steps,
    modelPlan,
    agentRun: modelPlan.agentRun,
    toolRuns,
    qc,
    counts,
    differential: differentialGenes,
    tables: [
      await csvTable('QC summary', path.join(outputDir, 'qc_summary.csv')).catch(() => ({
        title: 'QC summary',
        columns: ['sampleId', 'condition', 'reads', 'averageLength', 'gcPercent'],
        rows: qc,
      })),
      {
        title: 'Differential expression',
        columns: ['gene', 'controlMean', 'treatmentMean', 'log2FoldChange', 'score', 'direction'],
        rows: differentialGenes,
      },
    ],
    outputDir,
    reportMarkdown,
    summary: modelSummary,
  }
}

function parseCountMatrix(raw: string): CountMatrix {
  const rows = parseCsv(raw)
  const counts: CountMatrix = {}
  for (const row of rows) {
    const gene = String(row.gene)
    counts[gene] = {}
    for (const [key, value] of Object.entries(row)) {
      if (key !== 'gene') {
        counts[gene][key] = Number(value)
      }
    }
  }
  return counts
}

export const testOnly = {
  parseFastq,
  parseMetadata,
  parseReference,
  differential,
}
