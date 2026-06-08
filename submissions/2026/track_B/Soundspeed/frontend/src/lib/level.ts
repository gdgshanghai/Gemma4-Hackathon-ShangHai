// 电平量化（去抖）：把连续 RMS 电平 [0,1] 映射到固定档位整数。
// 用途：useMicLevel 的 rAF 每帧拿到一个电平值，只有「档位变了」才需要 setState 触发重渲；
// 静音时 rms 近恒定 → 档位不变 → 不 setState，掐掉待机 60fps 全树重渲。
// steps 默认 100：远多于电平条最终 7 格，量化不引入可见跳变，但足以把每帧 setState 收敛掉。

export function levelBucket(level: number, steps = 100): number {
  const safe = Math.min(1, Math.max(0, level))
  return Math.round(safe * steps)
}
