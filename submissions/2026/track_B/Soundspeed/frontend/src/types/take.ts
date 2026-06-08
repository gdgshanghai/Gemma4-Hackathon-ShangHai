// 本地 UI 状态枚举（mark 标记 / status badge）。recording 为前端录制态，非后端 take.status。
// 后端 take 状态用 types/api.ts 的 TakeStatus（无 recording）。
export type Status = "keep" | "ng" | "pass" | "tbd" | "recording"
