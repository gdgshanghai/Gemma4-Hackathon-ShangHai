<script setup lang="ts">
import { ref, watch } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'

const props = defineProps<{
  userId?: string
  mood?: string
  goal?: string
}>()

const emit = defineEmits<{ 'select': [mode: string] }>()

const moods = [
  { key: 'normal', label: '正常', icon: '😊' },
  { key: 'tired', label: '疲惫', icon: '😴' },
  { key: 'stressed', label: '压力大', icon: '😰' },
  { key: 'happy', label: '开心', icon: '🥳' },
  { key: 'sad', label: '低落', icon: '😢' },
]

const modes = [
  { key: 'disciplined', label: '自律模式', icon: '🎯', desc: '严格按目标执行' },
  { key: 'balanced', label: '均衡模式', icon: '⚖️', desc: '兼顾享受与健康' },
  { key: 'indulgence', label: '放纵模式', icon: '🎉', desc: '开心最重要' },
]

function goalToMode(goal?: string): string {
  if (goal === 'lose_weight') return 'disciplined'
  if (goal === 'gain_muscle') return 'disciplined'
  return 'balanced'
}

function moodToMode(mood: string): string {
  if (mood === 'stressed' || mood === 'sad') return 'indulgence'
  if (mood === 'happy') return 'balanced'
  if (mood === 'tired') return 'balanced'
  return goalToMode(props.goal)
}

const selectedMood = ref(props.mood || 'normal')
const selectedMode = ref(goalToMode(props.goal))

watch(selectedMood, (mood) => {
  selectedMode.value = moodToMode(mood)
})
</script>

<template>
  <Card>
    <CardHeader class="pb-2">
      <CardTitle class="text-base">🎯 今日模式</CardTitle>
    </CardHeader>
    <CardContent class="space-y-3">
      <!-- 心情选择 -->
      <div>
        <div class="text-xs text-muted-foreground mb-1.5">现在的心情</div>
        <div class="flex flex-wrap gap-1">
          <button v-for="m in moods" :key="m.key" @click="selectedMood = m.key"
            :class="['flex items-center gap-0.5 px-2 py-1 rounded-lg text-xs border transition-all',
              selectedMood === m.key ? 'border-primary bg-orange-50 text-orange-700' : 'border-gray-200 hover:border-gray-300']">
            <span class="text-sm">{{ m.icon }}</span>
            <span>{{ m.label }}</span>
          </button>
        </div>
      </div>

      <!-- 模式选择 -->
      <div class="space-y-1.5">
        <div class="text-xs text-muted-foreground">选择模式</div>
        <button v-for="m in modes" :key="m.key" @click="selectedMode = m.key; emit('select', m.key)"
          :class="['w-full flex items-center gap-2 p-2 rounded-lg border text-sm transition-all text-left',
            selectedMode === m.key ? 'border-orange-500 bg-orange-50' : 'border-gray-200 hover:border-gray-300']">
          <span class="text-lg">{{ m.icon }}</span>
          <div>
            <div class="font-medium">{{ m.label }}</div>
            <div class="text-xs text-muted-foreground">{{ m.desc }}</div>
          </div>
        </button>
      </div>
    </CardContent>
  </Card>
</template>
