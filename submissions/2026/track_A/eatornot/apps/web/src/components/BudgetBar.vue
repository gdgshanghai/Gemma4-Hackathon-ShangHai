<script setup lang="ts">
import { Card, CardContent, Progress } from '@/components/ui'
import { computed } from 'vue'

const props = defineProps<{
  dailyBudget: number
  spentToday: number
}>()

const percentage = computed(() => {
  if (props.dailyBudget <= 0) return 0
  return Math.min((props.spentToday / props.dailyBudget) * 100, 100)
})

const remaining = computed(() => Math.max(props.dailyBudget - props.spentToday, 0))
</script>

<template>
  <Card>
    <CardContent class="p-3 space-y-1">
      <div class="flex justify-between text-sm">
        <span class="text-muted-foreground">今日预算</span>
        <span>¥{{ spentToday.toFixed(0) }} / ¥{{ dailyBudget.toFixed(0) }}</span>
      </div>
      <Progress :value="percentage" />
      <div class="text-xs text-muted-foreground">剩余 ¥{{ remaining.toFixed(0) }}</div>
    </CardContent>
  </Card>
</template>
