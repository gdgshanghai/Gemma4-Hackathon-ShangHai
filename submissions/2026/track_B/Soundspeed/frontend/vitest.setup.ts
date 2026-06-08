// vitest 跑在 node 环境（store 是纯 zustand 逻辑，不需要 DOM）。node 25 暴露了一个残缺的
// localStorage（typeof 是 object 但 getItem 不是函数），会让 session store 的 readToken 抛错。
// 这里用内存版 localStorage 覆盖掉，给 store 一个可用、可隔离的存储。
class MemoryStorage {
  private store = new Map<string, string>()
  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) as string) : null
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value))
  }
  removeItem(key: string): void {
    this.store.delete(key)
  }
  clear(): void {
    this.store.clear()
  }
}

Object.defineProperty(globalThis, "localStorage", {
  value: new MemoryStorage(),
  writable: true,
  configurable: true,
})
