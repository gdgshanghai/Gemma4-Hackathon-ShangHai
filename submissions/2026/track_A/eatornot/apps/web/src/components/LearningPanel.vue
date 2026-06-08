<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import { getLearningPoints, getUserId } from '@/api/client'

const props = defineProps<{ userId?: string }>()

const points = ref<string[]>([])

async function load() {
  try {
    const data = await getLearningPoints(props.userId || getUserId())
    points.value = data.learning_points || []
  } catch {}
}

onMounted(load)
</script>

<template>
  <Card v-if="points.length">
    <CardHeader class="pb-2">
      <CardTitle class="text-base">🧠 学习记录</CardTitle>
    </CardHeader>
    <CardContent class="space-y-2 text-sm">
      <div v-for="(pt, i) in points" :key="i" class="p-2 rounded bg-gray-50">
        <p class="text-sm">{{ pt }}</p>
      </div>
      <div class="text-xs text-muted-foreground">
        共 {{ points.length }} 条学习记录
      </div>
    </CardContent>
  </Card>
  <div v-else class="text-xs text-muted-foreground py-2">暂无学习记录</div>
</template>
