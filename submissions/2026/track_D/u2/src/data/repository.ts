import { openDB, type DBSchema, type IDBPDatabase } from 'idb'
import type { AppPreferences, PageResult } from '../types'
import { decryptJson, encryptJson } from '../services/crypto'

interface RecordEnvelope {
  id: string
  type: string
  createdAt: number
  date?: string
  encrypted: boolean
  payload?: unknown
  iv?: string
  ciphertext?: string
}

interface U2DB extends DBSchema {
  records: {
    key: string
    value: RecordEnvelope
    indexes: { 'by-type': string; 'by-createdAt': number }
  }
  settings: {
    key: string
    value: unknown
  }
}

const DEFAULT_PREFERENCES: AppPreferences = {
  onboardingDone: false,
  userStatus: null,
  saveLocal: true,
  saveChat: true,
  hideEnabled: true,
  encrypted: false,
  modelConsent: false,
}

let database: Promise<IDBPDatabase<U2DB>> | null = null

function db() {
  if (!database) {
    database = openDB<U2DB>('u2-local-v1', 1, {
      upgrade(store) {
        const records = store.createObjectStore('records', { keyPath: 'id' })
        records.createIndex('by-type', 'type')
        records.createIndex('by-createdAt', 'createdAt')
        store.createObjectStore('settings')
      },
    })
  }
  return database
}

async function unwrap<T>(record: RecordEnvelope) {
  if (!record.encrypted) return record.payload as T
  return decryptJson<T>(record.iv!, record.ciphertext!)
}

export const repository = {
  async preferences() {
    const saved = await (await db()).get('settings', 'preferences') as Partial<AppPreferences> | undefined
    return { ...DEFAULT_PREFERENCES, ...saved }
  },

  async savePreferences(preferences: AppPreferences) {
    await (await db()).put('settings', preferences, 'preferences')
  },

  async save<T extends { id: string; createdAt?: number; date?: string }>(type: string, value: T) {
    const preferences = await this.preferences()
    const envelope: RecordEnvelope = {
      id: value.id,
      type,
      createdAt: value.createdAt ?? Date.now(),
      date: value.date,
      encrypted: preferences.encrypted,
    }
    if (preferences.encrypted) Object.assign(envelope, await encryptJson(value))
    else envelope.payload = value
    await (await db()).put('records', envelope)
    return value
  },

  async get<T>(id: string) {
    const record = await (await db()).get('records', id)
    return record ? unwrap<T>(record) : null
  },

  async list<T>(type: string, page = 1, pageSize = 20, predicate?: (item: T) => boolean): Promise<PageResult<T>> {
    const records = await (await db()).getAllFromIndex('records', 'by-type', type)
    const values = await Promise.all(records.map(unwrap<T>))
    const filtered = predicate ? values.filter(predicate) : values
    filtered.sort((a, b) => Number((b as { createdAt?: number }).createdAt ?? 0) - Number((a as { createdAt?: number }).createdAt ?? 0))
    const start = (page - 1) * pageSize
    return { items: filtered.slice(start, start + pageSize), total: filtered.length, page, pageSize }
  },

  async count(type: string) {
    return (await db()).countFromIndex('records', 'by-type', type)
  },

  async remove(id: string) {
    await (await db()).delete('records', id)
  },

  async clearType(type: string) {
    const database = await db()
    const keys = await database.getAllKeysFromIndex('records', 'by-type', type)
    const tx = database.transaction('records', 'readwrite')
    for (const key of keys) await tx.store.delete(key)
    await tx.done
  },

  async resetAll() {
    const database = await db()
    await database.clear('records')
    await database.clear('settings')
  },

  async migrateEncryption(enabled: boolean) {
    const database = await db()
    const records = await database.getAll('records')
    const values = await Promise.all(records.map(async (record) => ({
      type: record.type,
      value: await unwrap<Record<string, unknown>>(record),
    })))
    const preferences = await this.preferences()
    await this.savePreferences({ ...preferences, encrypted: enabled })
    const tx = database.transaction('records', 'readwrite')
    for (const { type, value } of values) {
      const envelope: RecordEnvelope = {
        id: String(value.id),
        type,
        createdAt: Number(value.createdAt ?? Date.now()),
        date: typeof value.date === 'string' ? value.date : undefined,
        encrypted: enabled,
      }
      if (enabled) Object.assign(envelope, await encryptJson(value))
      else envelope.payload = value
      await tx.store.put(envelope)
    }
    await tx.done
  },
}
