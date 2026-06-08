import { createServer } from 'node:http'
import { createReadStream, statSync } from 'node:fs'
import { join, extname } from 'node:path'

const ROOT = new URL('./dist', import.meta.url).pathname
const PORT = 4173

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.wasm': 'application/wasm',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.webmanifest': 'application/manifest+json',
}

const SECURITY_HEADERS = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
  'Cross-Origin-Resource-Policy': 'cross-origin',
}

createServer((req, res) => {
  let pathname = decodeURIComponent(new URL(req.url, 'http://x').pathname)
  let filePath = join(ROOT, pathname)

  const tryServe = (path) => {
    try {
      const stat = statSync(path)
      if (stat.isDirectory()) return tryServe(join(path, 'index.html'))
      const ext = extname(path)
      res.writeHead(200, {
        'Content-Type': MIME[ext] || 'application/octet-stream',
        'Cache-Control': ext === '.html' ? 'no-cache' : 'public, max-age=31536000, immutable',
        ...SECURITY_HEADERS,
      })
      createReadStream(path).pipe(res)
      return true
    } catch {
      return false
    }
  }

  if (!tryServe(filePath)) {
    // SPA fallback
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', ...SECURITY_HEADERS })
    createReadStream(join(ROOT, 'index.html')).pipe(res)
  }
}).listen(PORT, '0.0.0.0', () => {
  console.log(`Serving dist/ on http://0.0.0.0:${PORT}`)
})
