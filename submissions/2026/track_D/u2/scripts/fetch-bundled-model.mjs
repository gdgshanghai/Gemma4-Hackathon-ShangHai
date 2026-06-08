import { createWriteStream } from 'node:fs'
import { mkdir, stat } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { Readable } from 'node:stream'

const repo = process.env.U2_MODEL_REPO || 'onnx-community/gemma-4-E4B-it-ONNX'
const revision = process.env.U2_MODEL_REVISION || 'main'
const folder = repo.split('/').at(-1)
const destination = join(process.cwd(), 'public', 'models', folder)

async function exists(path, size) {
  try {
    const info = await stat(path)
    return !size || info.size === size
  } catch {
    return false
  }
}

async function download(path, expectedSize) {
  const output = join(destination, path)
  if (await exists(output, expectedSize)) {
    console.log(`skip ${path}`)
    return
  }
  await mkdir(dirname(output), { recursive: true })
  const url = `https://huggingface.co/${repo}/resolve/${revision}/${path}?download=true`
  const response = await fetch(url, { redirect: 'follow' })
  if (!response.ok || !response.body) throw new Error(`download failed ${response.status}: ${path}`)
  await new Promise((resolve, reject) => {
    const stream = createWriteStream(output)
    Readable.fromWeb(response.body).pipe(stream)
    stream.on('finish', resolve)
    stream.on('error', reject)
  })
  console.log(`saved ${path}`)
}

console.log(`Preparing bundled model ${repo} in ${destination}`)
const treeUrl = `https://huggingface.co/api/models/${repo}/tree/${revision}?recursive=true&expand=true`
const response = await fetch(treeUrl)
if (!response.ok) throw new Error(`Unable to read model tree: ${response.status}`)
const tree = await response.json()
const files = tree.filter((entry) => entry.type === 'file' && !entry.path.startsWith('.git'))
for (const file of files) await download(file.path, file.size)
console.log('Bundled model files are ready. Build with VITE_GEMMA_MODEL_SOURCE=bundled.')
