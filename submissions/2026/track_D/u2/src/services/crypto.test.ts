import { describe, expect, it } from 'vitest'
import { createPin, decryptJson, encryptJson, lockSession, unlockPin } from './crypto'

describe('PIN 加密', () => {
  it('正确 PIN 可恢复数据，错误 PIN 被拒绝', async () => {
    const metadata = await createPin('2468')
    const encrypted = await encryptJson({ private: 'local-only' })
    lockSession()
    await expect(unlockPin('1111', metadata.salt, metadata.verifier)).rejects.toThrow('PIN 不正确')
    await unlockPin('2468', metadata.salt, metadata.verifier)
    await expect(decryptJson(encrypted.iv, encrypted.ciphertext)).resolves.toEqual({ private: 'local-only' })
  })
})
