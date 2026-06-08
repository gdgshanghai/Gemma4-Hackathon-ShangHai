import type { LabMetric, ReportAnalysis } from '../types'
import { localAI } from './localAI'
import { todayKey } from '../utils'

const OCR_PROMPT = '请读取这张医学检测报告图片中的所有可见文字，重点识别：检测日期、检测机构名称、CD4 细胞计数数值（单位 cells/μL）、HIV 病毒载量数值（单位 copies/mL，若为"检测不到"或"<"也请原文输出）。如实输出图片上的原文，不要解释或评论。'

interface ParsedFields {
  cd4: number | null
  viralLoad: number | null
  viralLoadText: string
  testDate: string
  institution: string
}

function parseOcrFields(ocrText: string): ParsedFields {
  // CD4: match "CD4 450", "CD4+: 350", "CD4细胞 280"
  const cd4Match = ocrText.match(/CD4[+＋细胞\s]*[：:＝=\s]*(\d{2,4})/i)
  const cd4 = cd4Match ? parseInt(cd4Match[1], 10) : null

  // Viral load: handle <20, undetectable, 检测不到, numeric values
  let viralLoad: number | null = null
  let viralLoadText = ''
  const vlLineMatch = ocrText.match(/(?:病毒载量|HIV[- ]?RNA|viral\s*load)[^\n]*/i)
  if (vlLineMatch) {
    viralLoadText = vlLineMatch[0].trim()
    if (/检测不到|未检出|undetectable/i.test(viralLoadText)) {
      viralLoad = 0
    } else {
      const belowMatch = viralLoadText.match(/[<＜]\s*(\d+)/)
      const numMatch = viralLoadText.match(/(\d+)/)
      if (belowMatch) viralLoad = parseInt(belowMatch[1], 10)
      else if (numMatch) viralLoad = parseInt(numMatch[1], 10)
    }
  }

  // Test date: YYYY-MM-DD, YYYY年MM月DD日, YYYYMMDD
  let testDate = ''
  const datePatterns: RegExp[] = [
    /(\d{4})[年\-\/](\d{1,2})[月\-\/](\d{1,2})/,
    /(\d{4})(\d{2})(\d{2})/,
  ]
  for (const pattern of datePatterns) {
    const m = ocrText.match(pattern)
    if (m) {
      testDate = `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`
      break
    }
  }

  // Institution: look for 医院/中心/机构/检验 followed by name
  const instMatch = ocrText.match(/([^\n，,。.\s]{2,15}(?:医院|中心|机构|检验科|实验室))/)
  const institution = instMatch ? instMatch[1].trim() : ''

  return { cd4, viralLoad, viralLoadText, testDate, institution }
}

export async function extractReport(file: File): Promise<ReportAnalysis> {
  let ocrText = ''
  let confidence = 0
  if (localAI.state().status === 'ready' && file.type.startsWith('image/')) {
    try {
      ocrText = await localAI.analyzeImage(file, OCR_PROMPT)
    } catch {
      ocrText = ''
    }
  }

  const parsed = ocrText ? parseOcrFields(ocrText) : { cd4: null, viralLoad: null, viralLoadText: '', testDate: '', institution: '' }
  const hasStructuredFields = parsed.cd4 !== null || parsed.viralLoad !== null
  if (ocrText) confidence = hasStructuredFields ? 0.85 : 0.6

  return {
    reportType: file.type === 'application/pdf' ? 'PDF 检测报告' : '检测报告',
    testDate: parsed.testDate || todayKey(),
    institution: parsed.institution,
    cd4: parsed.cd4,
    viralLoad: parsed.viralLoad,
    viralLoadText: parsed.viralLoadText,
    ocrText: ocrText || '未能稳定识别字段。请对照原报告手动确认下方信息后再保存。',
    explanation: '保存后，U2 会把已确认字段加入趋势；不会依据单份报告给出诊断或换药建议。',
    doctorQuestions: ['这次结果与我的历史趋势相比意味着什么？', '下一次建议在什么时候复查？'],
    confidence,
  }
}

export function explainMetrics(metrics: LabMetric[]) {
  if (!metrics.length) return '还没有可分析的指标。录入两次以上结果后，可以看到趋势。'
  const sorted = [...metrics].sort((a, b) => a.date.localeCompare(b.date))
  const latest = sorted.at(-1)!
  const previous = sorted.at(-2)
  if (!previous) return '目前只有一次记录。单次数值不适合判断趋势，建议按医嘱复查。'
  const viralSuppressed = latest.viralLoad !== null && latest.viralLoad <= 50
  const cd4Change = latest.cd4 !== null && previous.cd4 !== null ? latest.cd4 - previous.cd4 : null
  if (viralSuppressed) return `最近病毒载量处于较低水平${cd4Change !== null ? `，CD4 较上次${cd4Change >= 0 ? '增加' : '减少'} ${Math.abs(cd4Change)}` : ''}。请结合复查间隔和医生意见理解。`
  return '最近记录存在值得复诊时确认的变化。先检查服药和检测时间记录，不要自行停药或换药。'
}
