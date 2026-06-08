export function uid(prefix = 'u2') {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export function todayKey(date = new Date()) {
  return date.toISOString().slice(0, 10)
}

export function formatDate(value: number | string, withTime = false) {
  const date = typeof value === 'number' ? new Date(value) : new Date(`${value}T12:00:00`)
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  }).format(date)
}

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

export function downloadText(name: string, content: string, type = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

export async function fileToDataUrl(file: File) {
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}
