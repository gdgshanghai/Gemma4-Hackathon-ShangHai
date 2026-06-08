<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import { getDemoMetrics, getUserId } from '@/api/client'

const props = defineProps<{ userId?: string }>()

interface Metric { name: string; value: string | number; unit?: string }
const metrics = ref<Metric[]>([])
const note = ref('')

async function load() {
  try {
    const data = await getDemoMetrics(props.userId || getUserId())
    if (data.is_simulated) note.value = data.simulated_note || ''
    const items: Metric[] = []
    for (const [key, val] of Object.entries(data)) {
      if (val && typeof val === 'object' && 'current' in (val as any)) {
        const v = val as { current: number; description: string }
        items.push({ name: v.description, value: v.current })
      }
    }
    metrics.value = items
  } catch {}
}

onMounted(load)
</script>

<template>
  <Card v-if="metrics.length">
    <CardHeader class="pb-2">
      <CardTitle class="text-base">📈 本周统计</CardTitle>
    </CardHeader>
    <CardContent class="text-sm space-y-2">
      <div v-for="m in metrics" :key="m.name" class="flex justify-between">
        <span>{{ m.name }}</span>
        <span class="font-medium">{{ m.value }}{{ m.unit || '' }}</span>
      </div>
      <div v-if="note" class="text-xs text-muted-foreground mt-2">
        {{ note }}
      </div>
    </CardContent>
  </Card>
  <div v-else class="text-xs text-muted-foreground py-2">暂无统计数据</div>
</template>
