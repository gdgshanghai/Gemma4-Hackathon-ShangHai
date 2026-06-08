import { describe, expect, it } from 'vitest'
import { currentTrustLevel, inferTrustEvidence } from './trust'

describe('动态医院信任推断', () => {
  it('近期新信息可以改变状态', () => {
    const first = inferTrustEvidence('我不相信医院说的话')!
    const later = [
      { ...inferTrustEvidence('我准备去医院复诊')!, weight: 2 },
      { ...inferTrustEvidence('我会遵医嘱按时复查')!, weight: 2 },
    ]
    expect(currentTrustLevel([first])).toBe('hesitant')
    expect(currentTrustLevel([first, ...later])).toBe('trust')
  })
})
