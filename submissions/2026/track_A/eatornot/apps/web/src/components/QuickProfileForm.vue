<script setup lang="ts">
import { ref } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, Button } from '@/components/ui'
import type { QuickProfileData } from '@/api/client'

const emit = defineEmits<{ 'complete': [data: QuickProfileData] }>()

const form = ref<QuickProfileData>({
  meal_goal: 'lose_weight',
  budget_limit: 30,
  hunger_level: 3,
  craving_level: 3,
  mood: 'normal',
  allergies: [],
})

const goals = [
  { v: 'lose_weight', l: '减脂', e: '🔥' },
  { v: 'cheap', l: '省钱', e: '💰' },
  { v: 'satisfying', l: '吃爽', e: '🍔' },
  { v: 'balanced', l: '均衡', e: '⚖️' },
]

const moods = [
  { v: 'normal', l: '正常' },
  { v: 'tired', l: '疲惫' },
  { v: 'stressed', l: '压力大' },
  { v: 'happy', l: '开心' },
  { v: 'sad', l: '低落' },
]

function submit() {
  emit('complete', { ...form.value })
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <Card class="max-w-md w-full">
      <CardHeader>
        <CardTitle>⚡ 快速选择</CardTitle>
        <p class="text-sm text-muted-foreground">告诉我你的需求，30秒出方案</p>
      </CardHeader>
      <CardContent class="space-y-4">
        <div>
          <label class="block text-sm font-medium mb-2">这顿的目标</label>
          <div class="grid grid-cols-4 gap-2">
            <button v-for="g in goals" :key="g.v" @click="form.meal_goal = g.v as any"
              :class="['p-2 rounded-lg border text-center text-sm transition-all', form.meal_goal === g.v ? 'border-orange-500 bg-orange-50' : 'border-gray-200']">
              <div class="text-lg">{{ g.e }}</div>
              <div>{{ g.l }}</div>
            </button>
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">预算上限 (元)</label>
          <input v-model.number="form.budget_limit" type="number" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium mb-1">饥饿程度: {{ form.hunger_level }}/5</label>
          <input v-model.number="form.hunger_level" type="range" min="1" max="5" class="w-full" />
        </div>
        <div>
          <label class="block text-sm font-medium mb-2">现在心情</label>
          <div class="flex flex-wrap gap-2">
            <button v-for="m in moods" :key="m.v" @click="form.mood = m.v as any"
              :class="['px-3 py-1.5 rounded-md text-sm border transition-all', form.mood === m.v ? 'bg-orange-500 text-white border-orange-500' : 'border-gray-300']">
              {{ m.l }}
            </button>
          </div>
        </div>
        <Button class="w-full mt-4" size="lg" @click="submit">开始推荐 🚀</Button>
      </CardContent>
    </Card>
  </div>
</template>
