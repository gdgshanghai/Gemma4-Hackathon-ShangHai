<script setup lang="ts">
import { Badge, Button } from '@/components/ui'
import type { RecommendationPlan } from '@/api/client'

const props = defineProps<{
  plan: RecommendationPlan
  selected?: boolean
}>()

defineEmits<{ 'select': [] }>()

const modeConfig: Record<string, { label: string; icon: string; color: string; bg: string; border: string; gradient: string }> = {
  disciplined: {
    label: '自律模式', icon: '💪',
    color: 'text-green-700', bg: 'bg-green-50',
    border: 'border-green-200', gradient: 'from-green-50/80 to-emerald-50/40',
  },
  budget_friendly: {
    label: '省钱模式', icon: '💰',
    color: 'text-amber-700', bg: 'bg-amber-50',
    border: 'border-amber-200', gradient: 'from-amber-50/80 to-yellow-50/40',
  },
  controlled_indulgence: {
    label: '犒劳模式', icon: '🎉',
    color: 'text-pink-700', bg: 'bg-pink-50',
    border: 'border-pink-200', gradient: 'from-pink-50/80 to-rose-50/40',
  },
}

function getConfig(mode: string) {
  return modeConfig[mode] || {
    label: mode, icon: '🍽️', color: 'text-gray-700', bg: 'bg-gray-50',
    border: 'border-gray-200', gradient: 'from-gray-50/80 to-gray-100/40',
  }
}

function kcalLevel(cal: number) {
  if (cal < 400) return { label: '低卡', cls: 'bg-green-100 text-green-700' }
  if (cal < 700) return { label: '中等', cls: 'bg-amber-100 text-amber-700' }
  return { label: '高热量', cls: 'bg-red-100 text-red-700' }
}
</script>

<template>
  <div
    :class="[
      'rounded-xl border-2 transition-all duration-300 overflow-hidden cursor-pointer group',
      'hover:shadow-lg hover:-translate-y-1',
      selected
        ? 'border-orange-500 shadow-lg ring-1 ring-orange-300'
        : getConfig(plan.mode).border + ' hover:' + getConfig(plan.mode).border,
    ]"
    @click="$emit('select')">
    <!-- Gradient header -->
    <div :class="['px-4 pt-4 pb-3 bg-gradient-to-r', getConfig(plan.mode).gradient]">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-2xl">{{ getConfig(plan.mode).icon }}</span>
          <div>
            <h3 class="font-bold text-base text-gray-900">{{ plan.title }}</h3>
            <Badge :class="(getConfig(plan.mode).bg + ' ' + getConfig(plan.mode).color)" variant="secondary" class="text-[10px] px-1.5 py-0">
              {{ getConfig(plan.mode).label }}
            </Badge>
          </div>
        </div>
      </div>

      <!-- Item pills -->
      <div class="flex flex-wrap gap-1.5 mt-3">
        <span v-for="(item, i) in plan.items" :key="i"
          class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-white/80 text-xs font-medium text-gray-700 shadow-sm backdrop-blur-sm">
          <span class="w-1.5 h-1.5 rounded-full" :class="getConfig(plan.mode).bg" />
          {{ item.name }}
        </span>
      </div>
    </div>

    <!-- Stats -->
    <div class="px-4 py-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
      <div class="flex items-center gap-1.5">
        <span class="text-base">💰</span>
        <span v-if="plan.estimated_price > 0" class="font-bold text-gray-900">¥{{ plan.estimated_price.toFixed(0) }}</span>
        <span v-else class="font-bold text-green-600 text-xs px-2 py-0.5 rounded-full bg-green-50">预算内</span>
      </div>
      <div class="flex items-center gap-1.5">
        <span class="text-base">🔥</span>
        <span class="font-bold text-gray-900">{{ plan.estimated_calories.toFixed(0) }} kcal</span>
        <span :class="['text-[10px] px-1.5 py-0.5 rounded-full font-medium', kcalLevel(plan.estimated_calories).cls]">
          {{ kcalLevel(plan.estimated_calories).label }}
        </span>
      </div>
      <div class="flex items-center gap-1.5 text-gray-600">
        <span>💪</span><span>蛋白质 {{ plan.protein.toFixed(0) }}g</span>
      </div>
      <div class="flex items-center gap-1.5 text-gray-600">
        <span>🧂</span><span>钠 {{ plan.sodium.toFixed(0) }}mg</span>
      </div>
    </div>

    <!-- Pros / Cons -->
    <div class="px-4 pb-2 flex flex-wrap gap-1">
      <span v-for="p in plan.pros" :key="p"
        class="text-[11px] px-2 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-100">
        ✅ {{ p }}
      </span>
      <span v-for="c in plan.cons" :key="c"
        class="text-[11px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
        ⚠️ {{ c }}
      </span>
    </div>

    <!-- Reason -->
    <div class="px-4 pb-3">
      <p class="text-xs text-gray-500 leading-relaxed italic">"{{ plan.final_reason }}"</p>
    </div>

    <!-- Action button -->
    <div class="px-4 pb-4">
      <button
        :class="[
          'w-full py-2 rounded-lg text-sm font-semibold transition-all duration-200',
          selected
            ? 'bg-orange-500 text-white shadow-md'
            : 'bg-white border-2 text-gray-700 hover:bg-orange-50 hover:border-orange-300 hover:text-orange-700',
          selected ? '' : getConfig(plan.mode).border,
        ]">
        {{ selected ? '✓ 已选择此方案' : '选择此方案' }}
      </button>
    </div>
  </div>
</template>
