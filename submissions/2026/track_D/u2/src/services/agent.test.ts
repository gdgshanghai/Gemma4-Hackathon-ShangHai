import { describe, expect, it } from 'vitest'
import { buildModelMessages, buildSystemPrompt, hasCrisisSignal } from './agent'

describe('U2 system prompt', () => {
  it('把医疗安全、信任状态和本地知识放入 system role', () => {
    const prompt = buildSystemPrompt('hesitant', [{
      id: 'e1',
      direction: 'hesitant',
      quote: '不相信医院',
      weight: 2,
      createdAt: Date.now(),
    }], 'U=U 本地资料')
    expect(prompt).toContain('不输出感染概率')
    expect(prompt).toContain('不提供个体药物、停药或换药建议')
    expect(prompt).toContain('当前医院信任状态：hesitant')
    expect(prompt).toContain('U=U 本地资料')
  })

  it('模型消息的第一条始终为 system，最后一条为当前用户消息', () => {
    const result = buildModelMessages('我想了解 U=U', [], 'unknown', [])
    expect(result.messages[0].role).toBe('system')
    expect(result.messages.at(-1)).toEqual({ role: 'user', content: '我想了解 U=U' })
    expect(result.messages[0].content).toContain('U=U')
  })

  it('危机识别在模型调用前执行', () => {
    expect(hasCrisisSignal('我已经不想活了')).toBe(true)
  })
})
