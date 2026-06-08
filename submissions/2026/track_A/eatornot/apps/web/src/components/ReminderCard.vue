<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Card, CardContent, Button } from '@/components/ui'
import { useNotifications } from '@/composables/useNotifications'
import { fetchReminders, acceptReminder, snoozeReminder, dismissReminder, getUserId } from '@/api/client'

const props = defineProps<{ userId?: string }>()
const emit = defineEmits<{ 'accept': [reminder: any] }>()

const { requestPermission, notify, supported } = useNotifications()
const reminders = ref<any[]>([])
const dismissedIds = ref(new Set<string>())
const notifiedIds = ref(new Set<string>())

async function loadReminders() {
  try {
    const data = await fetchReminders(props.userId || getUserId())
    const filtered = (data.reminders || []).filter((r: any) => !dismissedIds.value.has(r.reminder_id))
    reminders.value = filtered
    if (supported.value) {
      requestPermission()
      const fresh = filtered.filter((r: any) => !notifiedIds.value.has(r.reminder_id))
      if (fresh.length > 0) {
        notify(fresh[0].title, { body: fresh[0].message })
        fresh.forEach((r: any) => notifiedIds.value.add(r.reminder_id))
      }
    }
  } catch {}
}

async function handleAccept(reminder: any) {
  await acceptReminder(reminder.reminder_id)
  emit('accept', reminder)
  reminders.value = reminders.value.filter(r => r.reminder_id !== reminder.reminder_id)
}

async function handleSnooze(id: string) {
  await snoozeReminder(id)
  reminders.value = reminders.value.filter(r => r.reminder_id !== id)
}

async function handleDismiss(id: string) {
  await dismissReminder(id)
  dismissedIds.value.add(id)
  reminders.value = reminders.value.filter(r => r.reminder_id !== id)
}

const urgencyColors: Record<string, string> = {
  high: 'border-l-red-500',
  normal: 'border-l-yellow-500',
  low: 'border-l-gray-300',
}
const typeIcons: Record<string, string> = {
  meal_time: '⏰',
  missed_meal: '🍽️',
  long_gap_without_food: '⏱️',
  nutrition_gap: '🥗',
  budget_available: '💰',
  late_night_warning: '🌙',
}

let interval: number
onMounted(() => {
  loadReminders()
  interval = window.setInterval(loadReminders, 2 * 60 * 1000)
})
onUnmounted(() => clearInterval(interval))
</script>

<template>
  <div v-if="reminders.length" class="space-y-3">
    <Card v-for="r in reminders" :key="r.reminder_id" :class="`border-l-4 ${urgencyColors[r.urgency] || 'border-l-gray-300'}`">
      <CardContent class="p-4 space-y-2">
        <div class="flex items-center gap-2">
          <span class="text-lg">{{ typeIcons[r.type] || '💡' }}</span>
          <span class="font-medium text-sm">{{ r.title }}</span>
        </div>
        <p class="text-sm text-gray-600">{{ r.message }}</p>
        <div class="flex gap-2">
          <Button size="sm" @click="handleAccept(r)">帮我搭配</Button>
          <Button size="sm" variant="outline" @click="handleSnooze(r.reminder_id)">稍后提醒</Button>
          <Button size="sm" variant="ghost" @click="handleDismiss(r.reminder_id)">今天不吃了</Button>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
