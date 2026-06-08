<script setup lang="ts">
import { ref } from 'vue'

defineEmits<{ 'submit': [satisfaction: number, notes: string] }>()

const satisfaction = ref(4)
const notes = ref('')
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-2">
      <span class="text-sm">满意度:</span>
      <button v-for="s in 5" :key="s" @click="satisfaction = s" :class="['text-lg', s <= satisfaction ? 'text-orange-500' : 'text-gray-300']">
        {{ s <= satisfaction ? '★' : '☆' }}
      </button>
    </div>
    <textarea v-model="notes" class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm" rows="2" placeholder="有什么想说的？（可选）" />
    <button class="mt-2 px-4 py-2 rounded-md bg-orange-500 text-white text-sm hover:bg-orange-600 transition-colors" @click="$emit('submit', satisfaction, notes)">提交反馈</button>
  </div>
</template>
