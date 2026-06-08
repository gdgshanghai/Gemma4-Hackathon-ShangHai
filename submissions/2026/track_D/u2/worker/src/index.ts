interface Env {
  ALLOWED_ORIGIN?: string
}

const topics: Record<string, string> = {
  treatment: '"HIV treatment" OR "antiretroviral therapy"',
  prevention: '"HIV prevention" OR "U=U"',
  research: '"HIV research"',
  policy: '"HIV public health policy"',
}

function json(data: unknown, status = 200, origin = '*') {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': origin,
      'cache-control': 'public, max-age=900',
    },
  })
}

export default {
  async fetch(request: Request, env: Env) {
    const url = new URL(request.url)
    const origin = env.ALLOWED_ORIGIN || '*'
    if (request.method === 'OPTIONS') return json({}, 204, origin)
    if (request.method !== 'GET' || url.pathname !== '/api/news') return json({ error: 'Not found' }, 404, origin)
    const topic = url.searchParams.get('topic') || 'treatment'
    if (!topics[topic]) return json({ error: 'Unsupported topic' }, 400, origin)

    const endpoint = new URL('https://api.gdeltproject.org/api/v2/doc/doc')
    endpoint.searchParams.set('query', `${topics[topic]} sourcecountry:China`)
    endpoint.searchParams.set('mode', 'ArtList')
    endpoint.searchParams.set('format', 'json')
    endpoint.searchParams.set('maxrecords', '10')
    endpoint.searchParams.set('sort', 'HybridRel')

    try {
      const response = await fetch(endpoint, { headers: { accept: 'application/json' } })
      if (!response.ok) throw new Error(`upstream ${response.status}`)
      const payload = await response.json() as { articles?: Array<{ url: string; title: string; seendate: string; domain: string; language: string }> }
      const fetchedAt = new Date().toISOString()
      const items = (payload.articles || []).filter((item) => item.url && item.title).map((item, index) => ({
        id: `${topic}-${index}-${item.seendate}`,
        title: item.title,
        summary: '公开资讯索引，请打开原始来源核实全文、发布日期与医学结论。',
        topic,
        source: item.domain,
        url: item.url,
        publishedAt: item.seendate,
        fetchedAt,
      }))
      return json({ items }, 200, origin)
    } catch {
      return json({ items: [], error: 'Public news source unavailable' }, 503, origin)
    }
  },
}
