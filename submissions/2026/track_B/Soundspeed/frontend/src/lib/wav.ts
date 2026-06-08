// 浏览器端音频 → 16kHz 单声道 16-bit WAV。
// MediaRecorder 录出的是 webm/opus，后端 enroll 只认 WAV/PCM，故在前端解码+重采样+编码成 WAV
// 再上传，与手动上传 WAV 文件完全等价（后端零改动）。

// Float32 [-1,1] PCM → 16-bit PCM WAV Blob。
export function encodeWav16(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i))
  }
  writeStr(0, "RIFF")
  view.setUint32(4, 36 + samples.length * 2, true)
  writeStr(8, "WAVE")
  writeStr(12, "fmt ")
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true) // byte rate = sr * blockAlign
  view.setUint16(32, 2, true) // block align = channels * bytesPerSample
  view.setUint16(34, 16, true) // bits per sample
  writeStr(36, "data")
  view.setUint32(40, samples.length * 2, true)
  let off = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    off += 2
  }
  return new Blob([view], { type: "audio/wav" })
}

// 任意录音 Blob（webm/opus 等）→ 16kHz 单声道 WAV Blob。
// 用浏览器自带解码（decodeAudioData）+ OfflineAudioContext 重采样到 16k 单声道。
export async function blobToWav16kMono(blob: Blob): Promise<Blob> {
  const TARGET = 16000
  const arr = await blob.arrayBuffer()

  type ACtor = typeof AudioContext
  const AC: ACtor =
    window.AudioContext ?? (window as unknown as { webkitAudioContext: ACtor }).webkitAudioContext
  const ctx = new AC()
  let decoded: AudioBuffer
  try {
    decoded = await ctx.decodeAudioData(arr)
  } finally {
    ctx.close()
  }

  const length = Math.max(1, Math.ceil(decoded.duration * TARGET))
  type OACtor = typeof OfflineAudioContext
  const OAC: OACtor =
    window.OfflineAudioContext ??
    (window as unknown as { webkitOfflineAudioContext: OACtor }).webkitOfflineAudioContext
  const offline = new OAC(1, length, TARGET) // 单声道 + 16k：自动下混 + 重采样
  const src = offline.createBufferSource()
  src.buffer = decoded
  src.connect(offline.destination)
  src.start()
  const rendered = await offline.startRendering()

  return encodeWav16(rendered.getChannelData(0), TARGET)
}
