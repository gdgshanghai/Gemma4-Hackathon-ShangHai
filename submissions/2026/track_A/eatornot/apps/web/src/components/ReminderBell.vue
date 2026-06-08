<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useNotifications } from '@/composables/useNotifications'
import { Button } from '@/components/ui'
import { getUserId } from '@/api/client'
import TerminalSkillBanner from '@/components/TerminalSkillBanner.vue'

const { pushEnabled, pushSupported, enablePush, disablePush, initPush, notify } = useNotifications()

const unreadCount = ref(0)
const reminders = ref<any[]>([])
const expanded = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const API_BASE = ''

async function togglePush() {
  if (pushEnabled.value) {
    await disablePush()
  } else {
    const ok = await enablePush()
    if (ok) {
      notify('🔔 饭点提醒已开启', { body: '将在早餐/午餐/晚餐时间推送推荐' })
    }
  }
}

async function fetchReminders() {
  try {
    const resp = await fetch(`${API_BASE}/api/reminders?user_id=${getUserId()}`)
    if (!resp.ok) return
    const data = await resp.json()
    reminders.value = data.reminders || []
    unreadCount.value = reminders.value.length
  } catch {
    // Silently fail — polling will retry
  }
}

async function acknowledgeReminder(id: number) {
  try {
    await fetch(`${API_BASE}/api/reminders/${id}/ack`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: getUserId() }),
    })
  } catch { /* ignore */ }
  reminders.value = reminders.value.filter((r: any) => r.id !== id)
  unreadCount.value = reminders.value.length
}

function mealIcon(type: string) {
  if (type === '早餐') return '🌅'
  if (type === '午餐') return '☀️'
  if (type === '晚餐') return '🌆'
  return '🌙'
}

onMounted(async () => {
  await initPush()
  await fetchReminders()
  // Poll every 60s
  pollTimer = setInterval(fetchReminders, 60_000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="relative">
    <!-- Bell button -->
    <button
      class="relative p-1.5 rounded-md hover:bg-gray-100 transition-colors"
      @click="expanded = !expanded"
      :title="pushEnabled ? '提醒已开启' : '点击开启饭点提醒'"
    >
      <span class="text-lg">{{ pushEnabled ? '🔔' : '🔕' }}</span>
      <span v-if="unreadCount > 0"
        class="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-bold">
        {{ unreadCount > 9 ? '9+' : unreadCount }}
      </span>
    </button>

    <!-- Dropdown panel -->
    <div v-if="expanded"
      class="absolute right-0 top-full mt-2 w-72 bg-white rounded-lg shadow-lg border z-50 overflow-hidden">
      <!-- Push toggle -->
      <div class="p-3 border-b bg-gray-50">
        <label class="flex items-center justify-between cursor-pointer">
          <span class="text-sm font-medium">饭点推送提醒</span>
          <button
            v-if="pushSupported"
            @click.stop="togglePush"
            :class="[
              'relative w-10 h-5 rounded-full transition-colors',
              pushEnabled ? 'bg-orange-500' : 'bg-gray-300'
            ]">
            <span :class="[
              'absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow',
              pushEnabled ? 'translate-x-5' : ''
            ]" />
          </button>
          <span v-else class="text-xs text-gray-400">不支持</span>
        </label>
        <p class="text-xs text-gray-400 mt-1">
          {{ pushEnabled ? '早 8:03 / 午 12:07 / 晚 18:03 自动推送' : '开启后将在饭点推送 AI 推荐方案' }}
        </p>
      </div>

      <!-- Reminders list -->
      <div v-if="reminders.length" class="max-h-64 overflow-y-auto">
        <div v-for="r in reminders" :key="r.id"
          class="p-3 border-b last:border-b-0 hover:bg-gray-50">
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5">
                <span>{{ mealIcon(r.meal_type) }}</span>
                <span class="text-sm font-medium">{{ r.meal_type }}推荐</span>
              </div>
              <p class="text-xs text-gray-500 mt-1">
                {{ r.recommendation?.summary || '智囊团为你准备了推荐方案' }}
              </p>
              <!-- Mini plan preview -->
              <div v-if="r.recommendation?.plans?.length" class="mt-2 space-y-1">
                <div v-for="p in r.recommendation.plans.slice(0, 2)" :key="p.id"
                  class="text-xs text-gray-600 flex items-center gap-1">
                  <span>{{ p.title }}</span>
                  <span class="text-gray-400">¥{{ p.estimated_price }}</span>
                </div>
              </div>
            </div>
            <button @click="acknowledgeReminder(r.id)"
              class="text-gray-400 hover:text-red-400 text-sm flex-shrink-0" title="关闭">✕</button>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else class="p-4 text-center text-sm text-gray-400">
        暂无新提醒
      </div>

      <!-- Terminal skill tip -->
      <TerminalSkillBanner compact />
    </div>
  </div>
</template>
