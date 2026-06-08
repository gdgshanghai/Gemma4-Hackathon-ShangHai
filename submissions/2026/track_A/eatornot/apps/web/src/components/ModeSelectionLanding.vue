<script setup lang="ts">
import { Card, CardContent, CardDescription, CardHeader, CardTitle, Button } from '@/components/ui'
import TerminalSkillBanner from '@/components/TerminalSkillBanner.vue'

defineEmits<{
  'select-mode': [mode: 'long_term' | 'quick']
}>()
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-orange-50 to-amber-50 flex items-center justify-center p-4">
    <div class="max-w-4xl w-full">
      <div class="text-center mb-12">
        <h1 class="text-5xl font-bold text-gray-900 mb-3">
          <span class="inline-block animate-bounce" style="animation-duration: 2s">🍔</span> EatOrNot
        </h1>
        <p class="text-lg text-gray-500">AI 智囊团帮你决定「吃什么」</p>
        <p class="text-sm text-gray-400 mt-1">8 个专业 Agent 圆桌辩论 → 3 个方案 → 1 个最佳选择</p>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card class="cursor-pointer hover:shadow-lg hover:-translate-y-1 transition-all duration-200 border-orange-200" @click="$emit('select-mode', 'long_term')">
          <CardHeader>
            <div class="text-4xl mb-2">📊</div>
            <CardTitle class="text-xl">长期管理我的饮食</CardTitle>
            <CardDescription>建立个人档案，追踪体重、预算、营养目标</CardDescription>
          </CardHeader>
          <CardContent>
            <ul class="space-y-2 text-sm text-gray-600 mb-6">
              <li class="flex items-center gap-2"><span class="text-orange-500">✓</span> 设定减脂/增肌/维持目标</li>
              <li class="flex items-center gap-2"><span class="text-orange-500">✓</span> 追踪每日热量和预算</li>
              <li class="flex items-center gap-2"><span class="text-orange-500">✓</span> 记录用餐历史</li>
              <li class="flex items-center gap-2"><span class="text-orange-500">✓</span> 个性化推荐</li>
            </ul>
            <Button class="w-full" size="lg">开始建档</Button>
          </CardContent>
        </Card>
        <Card class="cursor-pointer hover:shadow-lg hover:-translate-y-1 transition-all duration-200 border-amber-200 relative" @click="$emit('select-mode', 'quick')">
          <div class="absolute -top-2 -right-2 bg-orange-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm">推荐</div>
          <CardHeader>
            <div class="text-4xl mb-2">⚡</div>
            <CardTitle class="text-xl">就这顿帮我选一下</CardTitle>
            <CardDescription>快速选择，无需注册，30秒搞定</CardDescription>
          </CardHeader>
          <CardContent>
            <ul class="space-y-2 text-sm text-gray-600 mb-6">
              <li class="flex items-center gap-2"><span class="text-amber-500">✓</span> 告诉我你的预算和心情</li>
              <li class="flex items-center gap-2"><span class="text-amber-500">✓</span> 3个方案即刻呈现</li>
              <li class="flex items-center gap-2"><span class="text-amber-500">✓</span> 无需建档</li>
              <li class="flex items-center gap-2"><span class="text-amber-500">✓</span> 快速下单</li>
            </ul>
            <Button variant="outline" class="w-full border-amber-300 text-amber-700 hover:bg-amber-50" size="lg">快速选择</Button>
          </CardContent>
        </Card>
      </div>
      <div class="mt-6">
        <TerminalSkillBanner />
      </div>
      <p class="text-center text-xs text-gray-400 mt-8">⚕️ 本工具仅供参考，不构成医疗建议。</p>
    </div>
  </div>
</template>
