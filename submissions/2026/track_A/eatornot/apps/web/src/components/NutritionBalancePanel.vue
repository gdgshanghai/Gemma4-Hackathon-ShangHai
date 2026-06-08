<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, Progress } from '@/components/ui'
import { getUserId } from '@/api/client'

const props = defineProps<{ userId?: string }>()

const balance = ref<any>(null)

async function fetchBalance() {
  try {
    const res = await fetch(`/api/balance/overview?user_id=${props.userId || getUserId()}`)
    balance.value = await res.json()
  } catch {}
}

onMounted(fetchBalance)

function pct(value: number, target: number): number {
  if (!target) return 0
  return Math.min((value / target) * 100, 100)
}
</script>

<template>
  <Card v-if="balance">
    <CardHeader class="pb-2">
      <CardTitle class="text-base">🥗 营养平衡</CardTitle>
    </CardHeader>
    <CardContent class="space-y-3 text-sm">
      <div v-for="nut in (balance.nutrients || [])" :key="nut.name" class="space-y-1">
        <div class="flex justify-between">
          <span>{{ nut.name }}</span>
          <span class="text-muted-foreground">{{ nut.current?.toFixed(0) }} / {{ nut.target?.toFixed(0) }}{{ nut.unit }}</span>
        </div>
        <Progress :value="pct(nut.current, nut.target)" />
      </div>
      <div v-if="balance.gaps?.length" class="text-xs text-yellow-600 space-y-0.5">
        <div v-for="g in balance.gaps" :key="g">⚠️ {{ g }}</div>
      </div>
    </CardContent>
  </Card>
</template>
