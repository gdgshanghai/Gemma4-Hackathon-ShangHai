<script setup lang="ts">
import { ref, computed } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, Button, Progress } from '@/components/ui'
import type { RecommendationPlan } from '@/api/client'
import { useAppStore } from '@/composables/useAppStore'

const props = defineProps<{ plan: RecommendationPlan }>()
const emit = defineEmits<{ 'refine': [message: string]; 'confirm': [] }>()

const { profile } = useAppStore()
const refineInput = ref('')

const budgetPercent = computed(() => {
  const budget = profile.value?.daily_budget || 50
  return Math.min((props.plan.estimated_price / budget) * 100, 100)
})
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle class="text-lg">{{ plan.title }}</CardTitle>
    </CardHeader>
    <CardContent class="space-y-4">
      <div class="space-y-1">
        <div v-for="item in plan.items" :key="item.name" class="flex justify-between text-sm">
          <span>{{ item.name }}</span>
          <span class="text-muted-foreground">¥{{ item.price }} / {{ item.calories }}kcal</span>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2 text-sm border-t pt-3">
        <div>💰 总计: ¥{{ plan.estimated_price.toFixed(0) }}</div>
        <div>🔥 热量: {{ plan.estimated_calories.toFixed(0) }} kcal</div>
      </div>
      <div class="space-y-1">
        <div class="text-xs text-muted-foreground">预算使用</div>
        <Progress :value="budgetPercent" />
      </div>
      <div class="flex gap-2">
        <textarea v-model="refineInput" class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm" rows="2" placeholder="想调整什么？" />
        <Button size="sm" :disabled="!refineInput.trim()" @click="emit('refine', refineInput); refineInput = ''">调整</Button>
      </div>
      <Button class="w-full" size="lg" @click="emit('confirm')">确认下单 🛒</Button>
    </CardContent>
  </Card>
</template>
