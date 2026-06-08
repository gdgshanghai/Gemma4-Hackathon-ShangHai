import { ref, readonly } from 'vue'
import { getUserId } from '@/api/client'

const API_BASE = ''

// Shared reactive state (singleton across components)
const _pushEnabled = ref(false)
const _pushSupported = ref('serviceWorker' in navigator && 'PushManager' in window)
let _registration: ServiceWorkerRegistration | null = null

export function useNotifications() {
  const supported = ref('Notification' in window)

  async function requestPermission(): Promise<boolean> {
    if (!('Notification' in window)) return false
    if (Notification.permission === 'granted') return true
    if (Notification.permission === 'denied') return false
    const result = await Notification.requestPermission()
    return result === 'granted'
  }

  function notify(title: string, options?: NotificationOptions) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return
    if (document.visibilityState === 'visible') return
    const notification = new Notification(title, {
      icon: '/favicon.svg',
      ...options,
    })
    notification.onclick = () => {
      window.focus()
      notification.close()
    }
  }

  // ---- Push Subscription ----

  async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
    if (!_pushSupported.value) return null
    try {
      _registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
      return _registration
    } catch (e) {
      console.error('[Push] SW registration failed:', e)
      return null
    }
  }

  async function getVapidKey(): Promise<string | null> {
    try {
      const resp = await fetch(`${API_BASE}/api/push/vapid-public-key`)
      if (!resp.ok) return null
      const data = await resp.json()
      return data.publicKey || null
    } catch {
      return null
    }
  }

  async function enablePush(): Promise<boolean> {
    if (!_pushSupported.value) return false

    const permitted = await requestPermission()
    if (!permitted) return false

    const reg = _registration || await registerServiceWorker()
    if (!reg) return false

    const vapidKey = await getVapidKey()
    if (!vapidKey) {
      console.warn('[Push] VAPID key not configured — using basic notifications only')
      _pushEnabled.value = true
      return true
    }

    try {
      const subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: vapidKey,
      })

      // Send subscription to backend
      const resp = await fetch(`${API_BASE}/api/push/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: getUserId(),
          subscription: subscription.toJSON(),
        }),
      })

      if (resp.ok) {
        _pushEnabled.value = true
        console.log('[Push] Subscribed successfully')
        return true
      }
      return false
    } catch (e) {
      console.error('[Push] Subscription failed:', e)
      return false
    }
  }

  async function disablePush(): Promise<void> {
    if (!_registration) return
    try {
      const subscription = await _registration.pushManager.getSubscription()
      if (subscription) {
        await fetch(`${API_BASE}/api/push/unsubscribe`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: subscription.endpoint }),
        })
        await subscription.unsubscribe()
      }
    } catch (e) {
      console.error('[Push] Unsubscribe failed:', e)
    }
    _pushEnabled.value = false
  }

  async function initPush(): Promise<void> {
    if (!_pushSupported.value) return
    const reg = await registerServiceWorker()
    if (!reg) return
    // Check if already subscribed
    try {
      const sub = await reg.pushManager.getSubscription()
      _pushEnabled.value = !!sub
    } catch {
      _pushEnabled.value = false
    }
  }

  return {
    // Basic notifications
    requestPermission,
    notify,
    supported,
    // Push subscriptions
    enablePush,
    disablePush,
    initPush,
    pushEnabled: readonly(_pushEnabled),
    pushSupported: readonly(_pushSupported),
  }
}
