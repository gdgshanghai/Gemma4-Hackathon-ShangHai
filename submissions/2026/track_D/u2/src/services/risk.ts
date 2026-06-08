import type { RiskKind, RiskRecord } from '../types'

export const RISK_QUESTIONS = {
  pep: [
    { key: 'time', question: '最近一次可能暴露发生在多久前？', options: ['24 小时内', '24–48 小时', '48–72 小时', '超过 72 小时'] },
    { key: 'exposure', question: '暴露方式属于哪种？', options: ['无防护性行为', '安全套破裂/脱落', '共用针具', '其他或不确定'] },
    { key: 'source', question: '对方 HIV 感染状态是否已知？', options: ['已知阳性', '不确定', '已知阴性'] },
    { key: 'fluid', question: '是否可能有黏膜或破损皮肤接触体液？', options: ['有', '可能有', '没有'] },
  ],
  general: [
    { key: 'sex', question: '近 6 个月是否有无防护性行为？', options: ['多次', '偶尔', '没有'] },
    { key: 'partners', question: '近 6 个月是否有多个性伴侣？', options: ['是', '否'] },
    { key: 'needle', question: '是否共用过注射器具？', options: ['是', '否', '不确定'] },
    { key: 'test', question: '最近一次 HIV 检测是什么时候？', options: ['从未检测', '半年以上', '半年内'] },
  ],
} satisfies Record<RiskKind, Array<{ key: string; question: string; options: string[] }>>

export function evaluateRisk(kind: RiskKind, answers: Record<string, string>): RiskRecord['urgency'] {
  if (kind === 'pep') {
    const within72 = answers.time !== '超过 72 小时'
    const exposure = ['无防护性行为', '安全套破裂/脱落', '共用针具'].includes(answers.exposure)
    if (within72 && exposure && (answers.source !== '已知阴性' || answers.fluid !== '没有')) return 'urgent'
    if (exposure || answers.source !== '已知阴性') return 'consult'
    return 'low'
  }
  if (answers.needle === '是' || answers.sex === '多次' || answers.sex === '偶尔' || answers.test === '从未检测') return 'consult'
  return 'low'
}
