import type { TrustEvidence, TrustLevel } from '../types'
import { uid } from '../utils'

const hesitant = ['不相信医院', '医院骗', '不想去医院', '医生不可信', '不信医生', '官方不可信']
const trusting = ['相信医生', '准备去医院', '已经复诊', '遵医嘱', '医生建议', '按时复查']

export function inferTrustEvidence(text: string): TrustEvidence | null {
  const hesitantHit = hesitant.find((keyword) => text.includes(keyword))
  if (hesitantHit) return { id: uid('trust'), direction: 'hesitant', quote: hesitantHit, weight: 2, createdAt: Date.now() }
  const trustHit = trusting.find((keyword) => text.includes(keyword))
  if (trustHit) return { id: uid('trust'), direction: 'trust', quote: trustHit, weight: 1, createdAt: Date.now() }
  return null
}

export function currentTrustLevel(evidence: TrustEvidence[]): TrustLevel {
  const recent = evidence.filter((item) => Date.now() - item.createdAt < 1000 * 60 * 60 * 24 * 30).slice(-12)
  const score = recent.reduce((sum, item) => sum + (item.direction === 'trust' ? item.weight : -item.weight), 0)
  if (score >= 2) return 'trust'
  if (score <= -2) return 'hesitant'
  return 'unknown'
}
