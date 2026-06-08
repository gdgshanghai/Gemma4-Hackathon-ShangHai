import { describe, expect, it } from "vitest"

import { levelBucket } from "@/lib/level"

// levelBucket：电平去抖的核心。把 [0,1] 切成固定档位，上游靠「档位变没变」决定是否重渲。
describe("levelBucket", () => {
  it("两端取值：0 → 0，1 → steps", () => {
    expect(levelBucket(0)).toBe(0)
    expect(levelBucket(1)).toBe(100)
    expect(levelBucket(1, 7)).toBe(7)
  })

  it("越界钳制：负数 → 0，超过 1 → steps", () => {
    expect(levelBucket(-0.5)).toBe(0)
    expect(levelBucket(2)).toBe(100)
  })

  it("同一档位内的抖动归到同一档（去抖的关键性质）", () => {
    // 0.011 与 0.014 都落在 round(1.x)=1 档：静音/微抖时档位不变，上游不该重渲。
    expect(levelBucket(0.011)).toBe(levelBucket(0.014))
  })

  it("跨档位变化要给出不同档（不能把真实变化也吞掉）", () => {
    expect(levelBucket(0.011)).not.toBe(levelBucket(0.02))
  })
})
