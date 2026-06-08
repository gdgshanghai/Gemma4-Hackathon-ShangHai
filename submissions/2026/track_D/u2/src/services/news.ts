import { LOCAL_NEWS } from '../content/knowledge'
import type { NewsItem } from '../types'

const endpoint = import.meta.env.VITE_NEWS_WORKER_URL as string | undefined
const allowedTopics = new Set(['treatment', 'prevention', 'research', 'policy'])

export async function fetchNews(topic = 'treatment'): Promise<{ items: NewsItem[]; online: boolean }> {
  if (!endpoint || !allowedTopics.has(topic)) return { items: LOCAL_NEWS, online: false }
  try {
    const response = await fetch(`${endpoint.replace(/\/$/, '')}/api/news?topic=${encodeURIComponent(topic)}`)
    if (!response.ok) throw new Error(String(response.status))
    const data = await response.json() as { items?: NewsItem[] }
    return { items: data.items?.length ? data.items : LOCAL_NEWS, online: true }
  } catch {
    return { items: LOCAL_NEWS, online: false }
  }
}
