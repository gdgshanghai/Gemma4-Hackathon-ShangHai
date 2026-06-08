import { describe, expect, it } from 'vitest'
import { scoreAssessment } from './assessments'

describe('心理量表计分', () => {
  it('按完整 GAD-7 计分并分级', () => {
    expect(scoreAssessment('GAD-7', [2, 2, 2, 2, 2, 1, 1])).toEqual({
      score: 12,
      level: '中度',
      selfHarmRisk: false,
    })
  })

  it('PHQ-9 第 9 题非零时优先标记风险', () => {
    expect(scoreAssessment('PHQ-9', [0, 0, 0, 0, 0, 0, 0, 0, 1]).selfHarmRisk).toBe(true)
  })
})
