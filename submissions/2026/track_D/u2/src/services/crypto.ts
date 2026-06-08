const encoder = new TextEncoder()
const decoder = new TextDecoder()
let sessionKey: CryptoKey | null = null

function bytesToBase64(bytes: Uint8Array) {
  let binary = ''
  bytes.forEach((byte) => { binary += String.fromCharCode(byte) })
  return btoa(binary)
}

function base64ToBytes(value: string) {
  const binary = atob(value)
  return Uint8Array.from(binary, (char) => char.charCodeAt(0))
}

async function deriveKey(pin: string, salt: Uint8Array) {
  const material = await crypto.subtle.importKey('raw', encoder.encode(pin), 'PBKDF2', false, ['deriveKey'])
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: salt as BufferSource, iterations: 210_000, hash: 'SHA-256' },
    material,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

async function makeVerifier(key: CryptoKey) {
  const iv = new Uint8Array(12)
  const encrypted = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, encoder.encode('u2-pin-verifier'))
  return bytesToBase64(new Uint8Array(encrypted))
}

export async function createPin(pin: string) {
  if (!/^\d{4,8}$/.test(pin)) throw new Error('PIN 需为 4 到 8 位数字')
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const key = await deriveKey(pin, salt)
  sessionKey = key
  return { salt: bytesToBase64(salt), verifier: await makeVerifier(key) }
}

export async function unlockPin(pin: string, salt: string, verifier: string) {
  const key = await deriveKey(pin, base64ToBytes(salt))
  const valid = await makeVerifier(key) === verifier
  if (!valid) throw new Error('PIN 不正确')
  sessionKey = key
}

export function lockSession() {
  sessionKey = null
}

export function isSessionUnlocked() {
  return sessionKey !== null
}

export async function encryptJson(value: unknown) {
  if (!sessionKey) throw new Error('数据已锁定，请先输入 PIN')
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    sessionKey,
    encoder.encode(JSON.stringify(value)),
  )
  return { iv: bytesToBase64(iv), ciphertext: bytesToBase64(new Uint8Array(encrypted)) }
}

export async function decryptJson<T>(iv: string, ciphertext: string) {
  if (!sessionKey) throw new Error('数据已锁定，请先输入 PIN')
  const decrypted = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: base64ToBytes(iv) },
    sessionKey,
    base64ToBytes(ciphertext),
  )
  return JSON.parse(decoder.decode(decrypted)) as T
}
