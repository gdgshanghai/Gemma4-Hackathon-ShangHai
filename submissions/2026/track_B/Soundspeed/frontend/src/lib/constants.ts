import type { Status } from "@/types/take"

export const STATUS_DOT: Record<Status, string> = {
  // #28 配色对调：KEEP=bg-primary（黄/金），PASS=bg-green-500（绿）。
  // 4.x 把枚举 keeper→keep / hold→pass，沿用 #28 对调后的配色。
  keep: "bg-primary",
  ng: "bg-destructive",
  pass: "bg-green-500",
  tbd: "bg-muted-foreground",
  recording: "bg-destructive animate-pulse",
}

export const STATUS_LABEL: Record<Status, string> = {
  keep: "KEEP",
  ng: "NG",
  pass: "PASS",
  tbd: "TBD",
  recording: "REC",
}

export const MARK_ORDER: Status[] = ["ng", "keep", "pass"]

export const SPEAKER_OPTIONS = ["SZA", "YY", "Unknown"]

export const SPEAKER_DOT: Record<string, string> = {
  SZA: "bg-primary",
  YY: "bg-secondary-foreground",
  Unknown: "bg-muted-foreground",
}

export const SPEAKER_TEXT: Record<string, string> = {
  SZA: "text-primary",
  YY: "text-secondary-foreground",
  Unknown: "text-muted-foreground",
}

// ---- 实时转录 speaker 分色 ----
// 真实 diarize 输出是 SPEAKER_0x，确定性哈希把任意 speaker 字符串映射到固定调色板，
// 保证同一 speaker 每次渲染同色。text / dot 两套调色板按同一 hash index 取色（不漂移）。
// null（未知 / ch2 无 speaker）→ muted。

const SPEAKER_TEXT_PALETTE = [
  "text-primary",
  "text-secondary-foreground",
  "text-green-600",
  "text-orange-600",
  "text-purple-600",
] as const

const SPEAKER_DOT_PALETTE = [
  "bg-primary",
  "bg-secondary-foreground",
  "bg-green-600",
  "bg-orange-600",
  "bg-purple-600",
] as const

function speakerHashIndex(speaker: string): number {
  let hash = 0
  for (let i = 0; i < speaker.length; i++) {
    hash = (hash * 31 + speaker.charCodeAt(i)) | 0
  }
  return Math.abs(hash) % SPEAKER_TEXT_PALETTE.length
}

export function speakerColor(speaker: string | null): string {
  if (!speaker) return "text-muted-foreground"
  return SPEAKER_TEXT_PALETTE[speakerHashIndex(speaker)]
}

export function speakerDot(speaker: string | null): string {
  if (!speaker) return "bg-muted-foreground"
  return SPEAKER_DOT_PALETTE[speakerHashIndex(speaker)]
}
