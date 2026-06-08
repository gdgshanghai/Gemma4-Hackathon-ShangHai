<script setup lang="ts">
import { ref } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, Button, Progress } from '@/components/ui'
import type { UserProfile } from '@/api/client'

const emit = defineEmits<{ 'complete': [profile: UserProfile] }>()

const step = ref(0)
const totalSteps = 3

const form = ref({
  user_id: `user_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
  name: '',
  sex: 'male',
  age: 25,
  height_cm: 170,
  weight_kg: 70,
  goal: 'lose_weight' as 'lose_weight' | 'maintain' | 'gain_muscle',
  activity_level: 'sedentary' as string,
  daily_budget: 50,
  weekly_indulgence_allowance: 2,
  taste_preferences: [] as string[],
  allergies: [] as string[],
  meal_schedule: { breakfast: '08:00', lunch: '12:00', dinner: '18:30' },
})

const tasteOptions = ['辣', '甜', '咸', '酸', '清淡']
const allergyOptions = ['花生', '牛奶', '鸡蛋', '海鲜', '麸质']

function toggleItem(arr: string[], item: string) {
  const idx = arr.indexOf(item)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(item)
}

function nextStep() {
  if (step.value < totalSteps - 1) step.value++
  else {
    emit('complete', {
      ...form.value,
      onboarding_complete: true,
      mode: 'long_term',
    } as UserProfile)
  }
}

function prevStep() {
  if (step.value > 0) step.value--
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <Card class="max-w-lg w-full">
      <CardHeader>
        <CardTitle>📋 建立你的饮食档案</CardTitle>
        <Progress :value="((step + 1) / totalSteps) * 100" class="mt-2" />
        <p class="text-sm text-muted-foreground mt-1">步骤 {{ step + 1 }} / {{ totalSteps }}</p>
      </CardHeader>
      <CardContent>
        <!-- Step 0: Basic Info -->
        <div v-if="step === 0" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1">姓名</label>
            <input v-model="form.name" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" placeholder="你的名字" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium mb-1">性别</label>
              <select v-model="form.sex" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
                <option value="male">男</option>
                <option value="female">女</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">年龄</label>
              <input v-model.number="form.age" type="number" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium mb-1">身高 (cm)</label>
              <input v-model.number="form.height_cm" type="number" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
            </div>
            <div>
              <label class="block text-sm font-medium mb-1">体重 (kg)</label>
              <input v-model.number="form.weight_kg" type="number" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
            </div>
          </div>
        </div>

        <!-- Step 1: Goals -->
        <div v-if="step === 1" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-2">目标</label>
            <div class="grid grid-cols-3 gap-3">
              <button v-for="g in [{v:'lose_weight',l:'减脂',e:'🔥'},{v:'maintain',l:'维持',e:'⚖️'},{v:'gain_muscle',l:'增肌',e:'💪'}]"
                :key="g.v" @click="form.goal = g.v as any"
                :class="['p-3 rounded-lg border text-center transition-all', form.goal === g.v ? 'border-orange-500 bg-orange-50' : 'border-gray-200 hover:border-gray-300']">
                <div class="text-2xl">{{ g.e }}</div>
                <div class="text-sm mt-1">{{ g.l }}</div>
              </button>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">活动水平</label>
            <select v-model="form.activity_level" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm">
              <option value="sedentary">久坐不动</option>
              <option value="light">轻度活动</option>
              <option value="moderate">中度活动</option>
              <option value="active">高度活动</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium mb-1">每日预算 (元)</label>
            <input v-model.number="form.daily_budget" type="number" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" />
          </div>
        </div>

        <!-- Step 2: Preferences -->
        <div v-if="step === 2" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-2">口味偏好</label>
            <div class="flex flex-wrap gap-2">
              <button v-for="t in tasteOptions" :key="t" @click="toggleItem(form.taste_preferences, t)"
                :class="['px-3 py-1 rounded-full text-sm border transition-all', form.taste_preferences.includes(t) ? 'bg-orange-500 text-white border-orange-500' : 'border-gray-300 text-gray-600']">
                {{ t }}
              </button>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium mb-2">过敏/忌口</label>
            <div class="flex flex-wrap gap-2">
              <button v-for="a in allergyOptions" :key="a" @click="toggleItem(form.allergies, a)"
                :class="['px-3 py-1 rounded-full text-sm border transition-all', form.allergies.includes(a) ? 'bg-red-500 text-white border-red-500' : 'border-gray-300 text-gray-600']">
                {{ a }}
              </button>
            </div>
          </div>
        </div>

        <!-- Navigation -->
        <div class="flex justify-between mt-6">
          <Button v-if="step > 0" variant="outline" @click="prevStep">← 上一步</Button>
          <div v-else />
          <Button @click="nextStep">
            {{ step < totalSteps - 1 ? '下一步 →' : '开始使用 🚀' }}
          </Button>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
