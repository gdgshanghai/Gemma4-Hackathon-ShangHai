<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = defineProps<{
  compact?: boolean
}>()

const dismissed = ref(false)
const copiedStep = ref(-1)
const showSteps = ref(false)

onMounted(() => {
  if (!props.compact) {
    dismissed.value = localStorage.getItem('terminal-skill-dismissed') === 'true'
  }
})

function dismiss() {
  dismissed.value = true
  localStorage.setItem('terminal-skill-dismissed', 'true')
}

// One-line install prompt for Claude Code
const installPrompt = `请帮我安装 EatOrNot 终端点餐 Skill：创建 .claude/skills/meal-order.md，内容从 https://raw.githubusercontent.com/fgh23333/eatornot/main/scripts/claude-setup/skills/meal-order.md 获取，然后更新 .claude/settings.local.json 合并 https://raw.githubusercontent.com/fgh23333/eatornot/main/scripts/claude-setup/settings.local.json.template 的权限。完成后说"帮我点午餐"测试。`

function copyPrompt() {
  navigator.clipboard.writeText(installPrompt)
  copiedStep.value = 0
  setTimeout(() => { copiedStep.value = -1 }, 2000)
}
</script>

<template>
  <!-- Compact version for ReminderBell dropdown -->
  <div v-if="compact" class="p-3 bg-gradient-to-r from-indigo-50 to-purple-50 border-t">
    <div class="flex items-start gap-2">
      <span class="text-base flex-shrink-0">💻</span>
      <div class="flex-1 min-w-0">
        <p class="text-xs font-semibold text-indigo-900">终端也能点餐</p>
        <p class="text-[10px] text-indigo-600 mt-0.5">在 Claude Code 粘贴一句命令即可安装 Skill</p>
      </div>
    </div>
  </div>

  <!-- Full banner version for landing page / results -->
  <div v-else-if="!dismissed" class="max-w-2xl mx-auto">
    <div class="relative rounded-xl bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 border border-indigo-100 p-5 overflow-hidden">
      <button @click="dismiss"
        class="absolute top-2 right-2 w-6 h-6 rounded-full bg-white/60 hover:bg-white text-gray-400 hover:text-gray-600 flex items-center justify-center text-xs transition-colors z-10">
        ✕
      </button>

      <div class="flex items-start gap-3">
        <div class="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center text-xl flex-shrink-0">
          💻
        </div>
        <div class="flex-1">
          <h4 class="font-semibold text-indigo-900 text-sm">终端也能点餐！</h4>
          <p class="text-xs text-indigo-600 mt-1">
            在 <strong>Claude Code</strong> 或 <strong>Cursor</strong> 终端里，粘贴下方命令即可安装 Skill，然后说 <strong>"帮我点午餐"</strong> 即可获得 AI 推荐 + 一键下单
          </p>

          <!-- One-click install -->
          <div class="mt-3 bg-white/70 rounded-lg border border-indigo-200 overflow-hidden">
            <div class="px-3 py-1.5 bg-indigo-100/50 text-[10px] text-indigo-500 font-medium">
              📋 复制以下命令 → 粘贴到 Claude Code 终端
            </div>
            <div class="px-3 py-2 text-[11px] text-indigo-800 leading-relaxed">
              {{ installPrompt }}
            </div>
            <div class="px-3 py-2 border-t border-indigo-100">
              <button @click="copyPrompt"
                :class="[
                  'px-4 py-1.5 rounded-lg text-xs font-medium transition-all',
                  copiedStep === 0
                    ? 'bg-green-100 text-green-700 border border-green-200'
                    : 'bg-indigo-500 text-white hover:bg-indigo-600 shadow-sm'
                ]">
                {{ copiedStep === 0 ? '✓ 已复制到剪贴板' : '一键复制' }}
              </button>
            </div>
          </div>

          <div class="mt-3 flex items-center gap-4 text-[10px] text-indigo-400">
            <span>✅ 饭点自动提醒</span>
            <span>✅ AI 智能推荐</span>
            <span>✅ 终端直接下单</span>
            <span>✅ 支持 Mac/Win/Linux</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
