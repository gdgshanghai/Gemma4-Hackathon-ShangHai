export function getLiveArchiveRoomId(roomKeyValue) {
  if (roomKeyValue !== null && roomKeyValue !== undefined && roomKeyValue !== '') {
    return String(roomKeyValue).replace(/[^\w-]/g, '_')
  }
  return 'test_room'
}

export function formatLiveInfoTimestamp(timestamp) {
  let ts = Number(timestamp || 0)
  if (ts <= 0) {
    ts = Math.floor(Date.now() / 1000)
  }
  let date = new Date(ts * 1000)
  let pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function formatStreamDuration(seconds) {
  let total = Math.max(0, Math.floor(Number(seconds) || 0))
  if (total === 0) {
    return '0秒'
  }
  let hours = Math.floor(total / 3600)
  let minutes = Math.floor((total % 3600) / 60)
  let secs = total % 60
  let parts = []
  if (hours > 0) {
    parts.push(`${hours}小时`)
  }
  if (minutes > 0) {
    parts.push(`${minutes}分`)
  }
  if (secs > 0 || parts.length === 0) {
    parts.push(`${secs}秒`)
  }
  return parts.join('')
}

export function formatGiftValue(value) {
  return `${Number(value || 0).toFixed(2)} 元`
}

/** 与 data/.../summary.txt v2 及后端 SCENE_DEFINITIONS 保持一致 */
export const SEGMENT_SUMMARY_VERSION = 2

export const LIVE_CONTENT_OPTIONS = [
  { liveContentType: 'gaming', sceneKey: 'gaming', sceneText: '游戏中' },
  { liveContentType: 'singing', sceneKey: 'singing', sceneText: '唱歌中' },
  { liveContentType: 'watching', sceneKey: 'watching', sceneText: '观看视频中' }
]

const LIVE_CONTENT_TEXT_MAP = LIVE_CONTENT_OPTIONS.reduce((map, item) => {
  map[item.liveContentType] = item.sceneText
  return map
}, {})

export function resolveLiveContentSceneText(liveContentType, fallbackText = '') {
  let key = String(liveContentType || '').trim()
  if (LIVE_CONTENT_TEXT_MAP[key]) {
    return LIVE_CONTENT_TEXT_MAP[key]
  }
  return String(fallbackText || '').trim()
}

/** 将 summary.txt 单段或接口 cachedSummary 规范为前端展示结构 */
export function normalizeCachedSegmentSummary(cached, segment = {}) {
  let source = cached || {}
  let fallbackSegment = segment || {}
  let liveContentType = String(
    source.liveContentType || source.sceneKey || fallbackSegment.sceneKey || ''
  ).trim()
  let sceneText = String(source.sceneText || '').trim()
  if (sceneText === '') {
    sceneText = resolveLiveContentSceneText(liveContentType, fallbackSegment.sceneText)
  }
  return {
    liveContentType,
    sceneKey: liveContentType,
    sceneText,
    audienceInterest: String(source.audienceInterest || '').trim(),
    streamerSummary: String(source.streamerSummary || '').trim()
  }
}

export function isValidCachedSegmentSummary(cached, segment = {}) {
  let normalized = normalizeCachedSegmentSummary(cached, segment)
  return normalized.liveContentType !== ''
    && (normalized.audienceInterest !== '' || normalized.streamerSummary !== '')
}

/** 构建写入 summary.txt 的单段记录（v2 字段） */
export function buildSegmentSummarySaveRecord(segment, summaryData = {}) {
  let segmentInfo = segment || {}
  let summary = summaryData || {}
  let liveContentType = String(
    summary.liveContentType || summary.sceneKey || segmentInfo.sceneKey || ''
  ).trim()
  let sceneText = String(summary.sceneText || '').trim()
  if (sceneText === '') {
    sceneText = resolveLiveContentSceneText(liveContentType, segmentInfo.sceneText)
  }
  return {
    liveContentType,
    sceneKey: liveContentType,
    sceneText,
    startSeconds: segmentInfo.startSeconds,
    endSeconds: segmentInfo.endSeconds,
    startText: segmentInfo.startText,
    endText: segmentInfo.endText,
    durationText: segmentInfo.durationText,
    audienceInterest: String(summary.audienceInterest || '').trim(),
    streamerSummary: String(summary.streamerSummary || '').trim()
  }
}

export function formatLiveStreamSummary(data) {
  let durationText = formatStreamDuration(data.streamDurationSeconds)
  let giftValueText = formatGiftValue(data.totalGiftValue)
  let recordingFilePath = String(data.recordingFilePath || '').trim()
  let pathText = recordingFilePath || '未知位置'
  return `您已直播${durationText}，收到礼物价值${giftValueText}，录播文件保存到了${pathText}，辛苦了。`
}

export async function fetchLiveArchiveList(roomId, limit = 10, generateCovers = true) {
  let safeRoomId = encodeURIComponent(String(roomId || '').trim())
  let safeLimit = Math.max(1, Math.min(10, Number(limit) || 10))
  let generateFlag = generateCovers ? '1' : '0'
  let res = await fetch(`/api/live/archive/list?roomId=${safeRoomId}&limit=${safeLimit}&generateCovers=${generateFlag}`)
  let data = await res.json()
  if (!data.success) {
    throw new Error(data.error || 'fetch live archive list failed')
  }
  return data.data || []
}

export async function fetchLiveArchiveSession(roomId, streamStartFolder, generateCover = false) {
  let safeRoomId = encodeURIComponent(String(roomId || '').trim())
  let safeFolder = encodeURIComponent(String(streamStartFolder || '').trim())
  let generateFlag = generateCover ? '1' : '0'
  let res = await fetch(
    `/api/live/archive/session?roomId=${safeRoomId}&streamStartFolder=${safeFolder}&generateCover=${generateFlag}`
  )
  let data = await res.json()
  if (!data.success) {
    throw new Error(data.error || 'fetch live archive session failed')
  }
  return data.data
}

export function extractJsonObject(text) {
  try {
    return JSON.parse(text)
  } catch {
    let match = String(text || '').match(/\{[\s\S]*\}/)
    if (!match) {
      return null
    }
    try {
      return JSON.parse(match[0])
    } catch {
      return null
    }
  }
}

export const QWEN_CHAT_TIMEOUT_MS = 90000

export async function callQwenChat(message, history = [], options = {}) {
  let timeoutMs = Number(options.timeoutMs || QWEN_CHAT_TIMEOUT_MS)
  let controller = typeof AbortController !== 'undefined' ? new AbortController() : null
  let timeoutId = null
  if (controller && timeoutMs > 0) {
    timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  }
  try {
    let res = await fetch('/api/qwen/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
      signal: controller ? controller.signal : undefined
    })
    let data = await res.json()
    if (!data.success) {
      throw new Error(data.error || 'Qwen API failed')
    }
    return {
      response: data.response || '',
      usage: data.usage || {}
    }
  } catch (e) {
    if (controller && e && e.name === 'AbortError') {
      throw new Error('Qwen request timeout')
    }
    throw e
  } finally {
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId)
    }
  }
}

export async function saveLiveArchiveSegmentSummaries(roomId, streamStartFolder, segments) {
  let res = await fetch('/api/live/archive/segment-summaries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      roomId,
      streamStartFolder,
      segments
    })
  })
  let data = await res.json()
  if (!data.success) {
    throw new Error(data.error || 'save live archive segment summaries failed')
  }
  return data.data
}

export async function fetchLiveArchiveSceneTimeline(roomId, streamStartFolder) {
  let safeRoomId = encodeURIComponent(String(roomId || '').trim())
  let safeFolder = encodeURIComponent(String(streamStartFolder || '').trim())
  let res = await fetch(
    `/api/live/archive/scene-timeline?roomId=${safeRoomId}&streamStartFolder=${safeFolder}`
  )
  let data = await res.json()
  if (!data.success) {
    throw new Error(data.error || 'fetch live archive scene timeline failed')
  }
  return data.data
}

export async function fetchLiveArchiveClipTimeline(roomId, streamStartFolder) {
  let safeRoomId = encodeURIComponent(String(roomId || '').trim())
  let safeFolder = encodeURIComponent(String(streamStartFolder || '').trim())
  let res = await fetch(
    `/api/live/archive/clip-timeline?roomId=${safeRoomId}&streamStartFolder=${safeFolder}`
  )
  let data = await res.json()
  if (!data.success) {
    throw new Error(data.error || 'fetch live archive clip timeline failed')
  }
  return data.data
}

export const CLIP_DURATION_DEFAULT = 120
export const CLIP_DURATION_MIN = 15
export const CLIP_DURATION_MAX = 1800
export const CLIP_DURATION_STEP = 15

export function clampClipDuration(seconds) {
  let value = Number(seconds)
  if (!Number.isFinite(value) || value <= 0) {
    value = CLIP_DURATION_DEFAULT
  }
  return Math.max(CLIP_DURATION_MIN, Math.min(CLIP_DURATION_MAX, Math.round(value)))
}

export async function fetchLiveArchiveClipSuggestion(roomId, streamStartFolder, clipType, clipDurationSeconds) {
  let safeRoomId = encodeURIComponent(String(roomId || '').trim())
  let safeFolder = encodeURIComponent(String(streamStartFolder || '').trim())
  let safeType = encodeURIComponent(String(clipType || '').trim())
  let duration = clampClipDuration(clipDurationSeconds)
  let res = await fetch(
    `/api/live/archive/clip-suggestion?roomId=${safeRoomId}&streamStartFolder=${safeFolder}&clipType=${safeType}&clipDurationSeconds=${duration}`
  )
  let data = await res.json()
  if (!data.success) {
    throw new Error(data.error || 'fetch live archive clip suggestion failed')
  }
  return data.data
}

export async function exportLiveArchiveClip(roomId, streamStartFolder, clipType, startSeconds, endSeconds) {
  let res = await fetch('/api/live/archive/clip-export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      roomId,
      streamStartFolder,
      clipType,
      startSeconds: Math.max(0, Math.floor(Number(startSeconds) || 0)),
      endSeconds: Math.max(0, Math.floor(Number(endSeconds) || 0))
    })
  })
  let data = await res.json()
  if (!data.success) {
    throw new Error(data.error || 'export live archive clip failed')
  }
  return data.data
}

export function formatLiveReviewSessionTitle(startTime, streamStartFolder) {
  let dateText = ''
  let hourText = ''
  let startText = String(startTime || '').trim()
  if (startText !== '') {
    let match = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):/.exec(startText)
    if (match) {
      dateText = `${parseInt(match[2], 10)}月${parseInt(match[3], 10)}日`
      hourText = `${parseInt(match[4], 10)}点`
    }
  }
  if (dateText === '') {
    let folder = String(streamStartFolder || '').trim()
    let folderMatch = /^(\d{4})(\d{2})(\d{2})_(\d{2})/.exec(folder)
    if (folderMatch) {
      dateText = `${parseInt(folderMatch[2], 10)}月${parseInt(folderMatch[3], 10)}日`
      hourText = `${parseInt(folderMatch[4], 10)}点`
    }
  }
  if (dateText === '') {
    return ''
  }
  return `${dateText} 直播 ${hourText}场`
}

export async function fetchLiveArchiveCover(coverUrl) {
  let url = String(coverUrl || '').trim()
  if (url === '') {
    return false
  }
  let res = await fetch(`${url}${url.includes('?') ? '&' : '?'}v=${Date.now()}`)
  return res.ok
}

export async function appendLiveArchiveRecord(roomId, streamStartedAt, category, content) {
  let text = String(content || '').trim()
  let startedAt = Number(streamStartedAt || 0)
  if (text === '' || startedAt <= 0) {
    return false
  }
  try {
    let res = await fetch('/api/live/archive/append', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        roomId,
        streamStartedAt: startedAt,
        category,
        content: text
      })
    })
    let data = await res.json()
    if (!data.success) {
      throw new Error(data.error || 'append live archive failed')
    }
    return true
  } catch (e) {
    console.warn('Append live archive failed:', e)
    return false
  }
}
