import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * take 编号显示：take_number 拼上冲突后缀 take_suffix（''/'+'/'++'…）。
 * suffix='' → "3"；suffix='+' → "3+"。后端撞号时自动加后缀，前端只负责拼接。
 * 接受任意带这两字段的对象（含 store 里只填了部分字段的 take）。
 */
export function formatTakeLabel(take: {
  take_number: number | null
  take_suffix?: string | null
}): string {
  if (take.take_number == null) return "—"
  return `${take.take_number}${take.take_suffix ?? ""}`
}

/**
 * 把秒数格式化为 "mm:ss" 或 "h:mm:ss"（>= 1h 时显示小时位）。
 * 用于 REC 按钮的录制时长显示。
 */
export function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`
  }
  return `${m}:${s.toString().padStart(2, "0")}`
}
