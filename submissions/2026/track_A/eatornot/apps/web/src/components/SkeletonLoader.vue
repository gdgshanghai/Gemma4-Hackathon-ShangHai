<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const agents = [
  { name: '档案 Agent', icon: '📋', desc: '分析用户画像...', color: 'bg-blue-500' },
  { name: '减脂 Agent', icon: '🏋️', desc: '计算热量目标...', color: 'bg-green-500' },
  { name: '营养 Agent', icon: '🥗', desc: '评估营养素...', color: 'bg-emerald-500' },
  { name: '预算 Agent', icon: '💰', desc: '控制开销...', color: 'bg-amber-500' },
  { name: '食欲 Agent', icon: '🍫', desc: '分析情绪进食...', color: 'bg-pink-500' },
  { name: '时间 Agent', icon: '⏰', desc: '评估时间压力...', color: 'bg-purple-500' },
  { name: '安全 Agent', icon: '⚠️', desc: '检查过敏原...', color: 'bg-red-500' },
  { name: '未来 Agent', icon: '🔮', desc: '预测用餐影响...', color: 'bg-indigo-500' },
]

const activeCount = ref(0)
const phase = ref(0) // 0: 启动, 1: 并行分析, 2: 辩论, 3: 生成方案
const phases = [
  { label: '🚀 调度 Agent', sub: 'Orchestrator 正在根据需求选择最合适的 Agent...' },
  { label: '⚡ 并行分析', sub: '多个 Agent 同时工作，从不同维度评估方案' },
  { label: '🔥 圆桌辩论', sub: '4 阶段辩论进行中 — 初始判断 → 发现冲突 → 形成妥协 → 最终投票' },
  { label: '🎯 生成方案', sub: '基于辩论结果，为你精心搭配 3 个方案...' },
]

let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  timer = setInterval(() => {
    if (phase.value < 1 && activeCount.value < agents.length) {
      activeCount.value = Math.min(activeCount.value + 1, agents.length)
    }
    // Advance phase based on time
    if (activeCount.value >= 3 && phase.value < 1) phase.value = 1
    if (activeCount.value >= agents.length && phase.value < 2) phase.value = 2
    if (phase.value === 2 && Math.random() > 0.7) phase.value = 3
  }, 800)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="space-y-5">
    <!-- Phase indicator -->
    <div class="bg-gradient-to-r from-orange-50 to-amber-50 rounded-xl p-4 border border-orange-100">
      <div class="flex items-center gap-3 mb-3">
        <div class="flex gap-1">
          <span class="w-2 h-2 rounded-full bg-orange-500 animate-bounce" style="animation-delay: 0ms" />
          <span class="w-2 h-2 rounded-full bg-orange-400 animate-bounce" style="animation-delay: 150ms" />
          <span class="w-2 h-2 rounded-full bg-orange-300 animate-bounce" style="animation-delay: 300ms" />
        </div>
        <span class="font-semibold text-orange-900">{{ phases[phase]?.label ?? '分析中...' }}</span>
      </div>
      <p class="text-sm text-orange-700">{{ phases[phase]?.sub ?? '' }}</p>
      <!-- Progress bar -->
      <div class="mt-3 h-1.5 bg-orange-200 rounded-full overflow-hidden">
        <div class="h-full bg-gradient-to-r from-orange-400 to-amber-400 rounded-full transition-all duration-1000 ease-out"
          :style="{ width: `${Math.min(25 + phase * 25, 95)}%` }" />
      </div>
    </div>

    <!-- Agent grid -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
      <div v-for="(agent, i) in agents" :key="i"
        :class="[
          'rounded-lg p-2.5 border transition-all duration-500',
          i < activeCount
            ? 'bg-white border-gray-200 shadow-sm'
            : 'bg-gray-50 border-gray-100 opacity-40'
        ]">
        <div class="flex items-center gap-1.5 mb-1">
          <span class="text-base">{{ agent.icon }}</span>
          <span class="text-xs font-medium text-gray-700 truncate">{{ agent.name }}</span>
        </div>
        <div v-if="i < activeCount" class="flex items-center gap-1">
          <div :class="['w-1.5 h-1.5 rounded-full animate-pulse', agent.color]" />
          <span class="text-[10px] text-gray-500">{{ agent.desc }}</span>
        </div>
        <div v-else class="h-3 bg-gray-100 rounded w-16" />
      </div>
    </div>

    <!-- Plan skeletons with gradient cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div v-for="(cfg, i) in [
        { icon: '💪', title: '自律方案', gradient: 'from-green-50 to-emerald-50', border: 'border-green-100' },
        { icon: '💰', title: '省钱方案', gradient: 'from-amber-50 to-yellow-50', border: 'border-amber-100' },
        { icon: '🎉', title: '犒劳方案', gradient: 'from-pink-50 to-rose-50', border: 'border-pink-100' },
      ]" :key="i"
        :class="['rounded-xl border p-4 space-y-3 bg-gradient-to-br animate-pulse', cfg.gradient, cfg.border]">
        <div class="flex items-center gap-2">
          <span class="text-lg">{{ cfg.icon }}</span>
          <div class="h-4 bg-white/60 rounded w-20" />
          <div class="ml-auto h-5 bg-white/60 rounded-full w-16" />
        </div>
        <div class="flex gap-1.5">
          <div class="h-5 bg-white/60 rounded-full w-16" />
          <div class="h-5 bg-white/60 rounded-full w-14" />
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div class="h-3.5 bg-white/60 rounded w-full" />
          <div class="h-3.5 bg-white/60 rounded w-full" />
          <div class="h-3.5 bg-white/60 rounded w-full" />
          <div class="h-3.5 bg-white/60 rounded w-full" />
        </div>
        <div class="h-8 bg-white/60 rounded-lg w-full" />
      </div>
    </div>
  </div>
</template>
