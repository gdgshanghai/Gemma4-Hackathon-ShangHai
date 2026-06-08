import { describe, expect, it } from 'vitest'
import { evaluateRisk } from './risk'

describe('HIV 风险分流', () => {
  it('72 小时内有意义暴露优先紧急就医评估', () => {
    expect(evaluateRisk('pep', {
      time: '24–48 小时',
      exposure: '无防护性行为',
      source: '不确定',
      fluid: '可能有',
    })).toBe('urgent')
  })

  it('不输出概率，只返回分流等级', () => {
    expect(evaluateRisk('general', {
      sex: '没有',
      partners: '否',
      needle: '否',
      test: '半年内',
    })).toBe('low')
  })
})
