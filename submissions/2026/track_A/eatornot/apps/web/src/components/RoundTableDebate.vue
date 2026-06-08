<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, Badge } from '@/components/ui'
import type { DebateResult } from '@/api/client'

const props = defineProps<{ debate?: DebateResult | null }>()

// --- Agent 配色映射 ---
interface AgentStyle { emoji: string; color: string; bg: string; border: string; label: string }
const AGENT_CONFIG: Record<string, AgentStyle> = {
  '档案Agent':     { emoji: '📋', color: 'text-blue-700',    bg: 'bg-blue-50',    border: 'border-blue-400',    label: '档案' },
  '减脂Agent':     { emoji: '🏋️', color: 'text-green-700',   bg: 'bg-green-50',   border: 'border-green-400',   label: '减脂' },
  '营养Agent':     { emoji: '🥗', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-400', label: '营养' },
  '预算Agent':     { emoji: '💰', color: 'text-amber-700',   bg: 'bg-amber-50',   border: 'border-amber-400',   label: '预算' },
  '食欲Agent':     { emoji: '😋', color: 'text-pink-700',    bg: 'bg-pink-50',    border: 'border-pink-400',    label: '食欲' },
  '时间Agent':     { emoji: '⏰', color: 'text-violet-700',  bg: 'bg-violet-50',  border: 'border-violet-400',  label: '时间' },
  '安全Agent':     { emoji: '🛡️', color: 'text-red-700',     bg: 'bg-red-50',     border: 'border-red-400',     label: '安全' },
  '未来模拟Agent': { emoji: '🔮', color: 'text-indigo-700',  bg: 'bg-indigo-50',  border: 'border-indigo-400',  label: '模拟' },
  '调度Agent':     { emoji: '🎭', color: 'text-gray-700',    bg: 'bg-gray-50',    border: 'border-gray-400',    label: '调度' },
}
const DEFAULT_STYLE: AgentStyle = { emoji: '🤖', color: 'text-gray-700', bg: 'bg-gray-50', border: 'border-gray-400', label: 'Agent' }

function agentStyle(name: string): AgentStyle {
  return AGENT_CONFIG[name] || DEFAULT_STYLE
}

function confidenceColor(c: number | undefined): string {
  if (!c) return 'bg-gray-300'
  if (c > 0.7) return 'bg-green-500'
  if (c > 0.4) return 'bg-yellow-500'
  return 'bg-red-500'
}

// --- 时间线阶段 ---
const stageIcons: Record<string, string> = {
  initial_opinions: '💬',
  conflicts: '⚡',
  compromise: '🤝',
  final_vote: '✅',
}
const stageLabels: Record<string, string> = {
  initial_opinions: '初始判断',
  conflicts: '发现冲突',
  compromise: '形成妥协',
  final_vote: '最终投票',
}

const activeStage = ref('')
const stageOrder = computed(() => props.debate?.stages?.map(s => s.stage) || [])

// --- 自动播放 ---
const isAutoPlaying = ref(false)
let autoTimer: ReturnType<typeof setInterval> | null = null

function startAutoPlay() {
  const stages = props.debate?.stages
  if (!stages?.length) return
  isAutoPlaying.value = true
  activeStage.value = stages[0]!.stage
  let idx = 0
  autoTimer = setInterval(() => {
    idx++
    if (idx >= stages.length) {
      stopAutoPlay()
      return
    }
    activeStage.value = stages[idx]!.stage
  }, 2500)
}

function stopAutoPlay() {
  isAutoPlaying.value = false
  if (autoTimer) { clearInterval(autoTimer); autoTimer = null }
}

function selectStage(stage: string) {
  stopAutoPlay()
  activeStage.value = stage
}

onMounted(() => { startAutoPlay() })
onUnmounted(() => { stopAutoPlay() })

// --- 当前阶段数据 ---
const currentStage = computed(() => {
  return props.debate?.stages?.find(s => s.stage === activeStage.value)
})

const isStageActive = (stage: string) => {
  const order = stageOrder.value
  const activeIdx = order.indexOf(activeStage.value)
  const stageIdx = order.indexOf(stage)
  return stageIdx === activeIdx
}

const isStagePast = (stage: string) => {
  const order = stageOrder.value
  const activeIdx = order.indexOf(activeStage.value)
  const stageIdx = order.indexOf(stage)
  return stageIdx < activeIdx
}

// --- 投票汇总（final_vote 阶段） ---
const voteSummary = computed(() => {
  const stage = props.debate?.stages?.find(s => s.stage === 'final_vote')
  if (!stage?.messages?.length) return null
  const counts = { approve: 0, warn: 0, reject: 0 }
  stage.messages.forEach((m: any) => { if (m.vote) counts[m.vote as keyof typeof counts]++ })
  const total = counts.approve + counts.warn + counts.reject
  return total > 0 ? { ...counts, total } : null
})
</script>

<template>
  <Card v-if="debate?.stages?.length">
    <CardHeader class="pb-3">
      <div class="flex items-center justify-between">
        <CardTitle class="text-base">🤖 智囊团圆桌辩论</CardTitle>
        <button @click="isAutoPlaying ? stopAutoPlay() : startAutoPlay()"
          class="text-xs px-2 py-1 rounded border hover:bg-gray-50 transition-colors">
          {{ isAutoPlaying ? '⏸ 暂停' : '▶ 重播' }}
        </button>
      </div>
    </CardHeader>
    <CardContent>
      <!-- 时间线 -->
      <div class="flex items-center mb-6 px-1">
        <template v-for="(s, idx) in debate.stages" :key="s.stage">
          <button @click="selectStage(s.stage)"
            class="flex flex-col items-center gap-1 min-w-[60px] transition-all relative">
            <div :class="[
              'w-9 h-9 rounded-full flex items-center justify-center text-sm transition-all',
              isStageActive(s.stage) ? 'bg-primary text-white ring-2 ring-primary/30 scale-110' :
              isStagePast(s.stage) ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-400'
            ]">
              <span v-if="isStagePast(s.stage) && !isStageActive(s.stage)">✓</span>
              <span v-else>{{ stageIcons[s.stage] || '📋' }}</span>
            </div>
            <span class="text-[10px] leading-tight text-center"
              :class="isStageActive(s.stage) ? 'text-primary font-medium' : 'text-muted-foreground'">
              {{ stageLabels[s.stage] || s.title?.replace(/第.轮：/, '') }}
            </span>
          </button>
          <div v-if="idx < debate.stages.length - 1"
            class="flex-1 h-0.5 mx-1 mt-[-12px]"
            :class="isStagePast(debate.stages[idx + 1]?.stage || '') || isStageActive(debate.stages[idx + 1]?.stage || '') ? 'bg-primary' : 'bg-gray-200'" />
        </template>
      </div>

      <!-- 投票汇总条 (final_vote) -->
      <div v-if="activeStage === 'final_vote' && voteSummary" class="mb-4">
        <div class="flex h-3 rounded-full overflow-hidden">
          <div class="bg-green-500 transition-all duration-500" :style="{ width: `${voteSummary.approve / voteSummary.total * 100}%` }" />
          <div class="bg-yellow-500 transition-all duration-500" :style="{ width: `${voteSummary.warn / voteSummary.total * 100}%` }" />
          <div class="bg-red-500 transition-all duration-500" :style="{ width: `${voteSummary.reject / voteSummary.total * 100}%` }" />
        </div>
        <div class="flex justify-between text-xs mt-1.5 text-muted-foreground">
          <span>👍 {{ voteSummary.approve }} 通过</span>
          <span>⚠️ {{ voteSummary.warn }} 警告</span>
          <span>❌ {{ voteSummary.reject }} 反对</span>
        </div>
      </div>

      <!-- 阶段消息 -->
      <div v-if="currentStage" class="space-y-3">
        <template v-for="(msg, i) in currentStage.messages" :key="i">
          <!-- 冲突对比布局 -->
          <div v-if="activeStage === 'conflicts' && msg.conflict_with" class="space-y-2">
            <div class="grid grid-cols-2 gap-3">
              <div :class="['p-3 rounded-lg border-l-4', agentStyle(msg.agent).bg, agentStyle(msg.agent).border]">
                <div class="flex items-center gap-1.5 mb-1">
                  <span class="text-base">{{ agentStyle(msg.agent).emoji }}</span>
                  <span class="font-medium text-xs" :class="agentStyle(msg.agent).color">{{ msg.agent }}</span>
                </div>
                <p class="text-sm text-gray-700">{{ msg.position }}</p>
              </div>
              <div :class="['p-3 rounded-lg border-l-4', agentStyle(msg.conflict_with).bg, agentStyle(msg.conflict_with).border]">
                <div class="flex items-center gap-1.5 mb-1">
                  <span class="text-base">{{ agentStyle(msg.conflict_with).emoji }}</span>
                  <span class="font-medium text-xs" :class="agentStyle(msg.conflict_with).color">{{ msg.conflict_with }}</span>
                </div>
                <p class="text-xs text-gray-500 italic">VS</p>
              </div>
            </div>
            <div v-if="msg.reason" class="text-xs text-center text-red-700 bg-red-50 rounded p-2 border border-red-200">
              ⚡ {{ msg.reason }}
            </div>
          </div>

          <!-- 普通消息气泡 -->
          <div v-else :class="['p-3 rounded-lg border-l-4 transition-all', agentStyle(msg.agent).bg, agentStyle(msg.agent).border]">
            <div class="flex items-center gap-2 mb-1.5">
              <span class="text-base">{{ agentStyle(msg.agent).emoji }}</span>
              <span class="font-medium text-sm" :class="agentStyle(msg.agent).color">{{ msg.agent }}</span>
              <!-- Vote badge -->
              <Badge v-if="msg.vote" variant="outline" size="sm"
                :class="msg.vote === 'approve' ? 'text-green-700 border-green-300' : msg.vote === 'warn' ? 'text-yellow-700 border-yellow-300' : 'text-red-700 border-red-300'">
                {{ msg.vote === 'approve' ? '👍' : msg.vote === 'warn' ? '⚠️' : '❌' }} {{ msg.vote }}
              </Badge>
              <!-- 置信度条 -->
              <div class="flex items-center gap-1 ml-auto">
                <div class="w-14 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div class="h-full rounded-full transition-all duration-500"
                    :class="confidenceColor(msg.confidence)"
                    :style="{ width: `${(msg.confidence || 0) * 100}%` }" />
                </div>
                <span class="text-[10px] text-muted-foreground w-7 text-right">{{ Math.round((msg.confidence || 0) * 100) }}%</span>
              </div>
            </div>
            <p class="text-sm text-gray-700">{{ msg.position }}</p>
            <p v-if="msg.warning" class="text-xs text-yellow-700 mt-1">⚠️ {{ msg.warning }}</p>
            <div v-if="msg.accepted_by?.length" class="text-xs text-muted-foreground mt-1">
              ✅ 接受: {{ msg.accepted_by.join('、') }}
            </div>
          </div>
        </template>
      </div>
    </CardContent>
  </Card>
</template>
