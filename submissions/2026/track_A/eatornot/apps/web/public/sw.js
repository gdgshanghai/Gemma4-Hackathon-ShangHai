// Service Worker for EatOrNot — handles push notifications + background sync
// This file MUST be in public/ so Vite serves it from the root

self.addEventListener('push', (event) => {
  let data = {
    title: '🍽️ 饭点提醒',
    body: '智囊团为你准备了推荐方案',
    url: '/',
  }

  if (event.data) {
    try {
      data = { ...data, ...event.data.json() }
    } catch {
      data.body = event.data.text()
    }
  }

  const options = {
    body: data.body,
    icon: '/favicon.svg',
    badge: '/favicon.svg',
    data: { url: data.url || '/' },
    tag: `meal-reminder-${Date.now()}`,
    requireInteraction: true,
    vibrate: [200, 100, 200],
    actions: [
      { action: 'view', title: '查看推荐' },
      { action: 'dismiss', title: '跳过' },
    ],
  }

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()

  if (event.action === 'dismiss') return

  const url = event.notification.data?.url || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      // Focus existing window if open
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url)
          return client.focus()
        }
      }
      // Otherwise open new window
      return self.clients.openWindow(url)
    })
  )
})

// Background sync for offline subscription updates
self.addEventListener('sync', (event) => {
  if (event.tag === 'push-subscription-update') {
    event.waitUntil(
      // Re-subscribe if needed — the app will handle this on next load
      Promise.resolve()
    )
  }
})
