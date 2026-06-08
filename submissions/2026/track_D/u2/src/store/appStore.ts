import { create } from 'zustand'
import type { AppPreferences } from '../types'
import type { ModelState } from '../services/localAI'
import { localAI } from '../services/localAI'
import { repository } from '../data/repository'

interface AppState {
  ready: boolean
  preferences: AppPreferences | null
  hidden: boolean
  toast: string
  model: ModelState
  bootstrap(): Promise<void>
  updatePreferences(patch: Partial<AppPreferences>): Promise<void>
  setHidden(hidden: boolean): void
  showToast(message: string): void
  setModel(model: ModelState): void
}

let toastTimer: number | undefined

export const useAppStore = create<AppState>((set, get) => ({
  ready: false,
  preferences: null,
  hidden: false,
  toast: '',
  model: { status: 'idle', progress: 0 },
  async bootstrap() {
    const prefs = await repository.preferences()
    set({ preferences: prefs, ready: true })
    // If the user previously consented to model download, resume automatically
    if (prefs.modelConsent && localAI.state().status === 'idle') {
      void localAI.initialize()
    }
  },
  async updatePreferences(patch) {
    const current = get().preferences
    if (!current) return
    const next = { ...current, ...patch }
    await repository.savePreferences(next)
    set({ preferences: next })
  },
  setHidden(hidden) {
    set({ hidden })
  },
  showToast(message) {
    window.clearTimeout(toastTimer)
    set({ toast: message })
    toastTimer = window.setTimeout(() => set({ toast: '' }), 2600)
  },
  setModel(model) {
    set({ model })
  },
}))
