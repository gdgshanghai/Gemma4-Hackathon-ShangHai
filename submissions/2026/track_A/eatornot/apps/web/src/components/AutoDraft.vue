<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Card, CardContent, CardHeader, CardTitle, Button } from '@/components/ui'
import { getUserId } from '@/api/client'

const props = defineProps<{ userId?: string }>()
const emit = defineEmits<{ 'confirm': [draft: any] }>()

const draft = ref<any>(null)
const loading = ref(false)

async function fetchDraft() {
  loading.value = true
  try {
    const res = await fetch(`/api/draft/auto?user_id=${props.userId || getUserId()}`)
    if (!res.ok) return
    const data = await res.json()
    if (data.items) draft.value = data
  } catch {
    draft.value = null
  } finally {
    loading.value = false
  }
}

async function confirmDraft() {
  if (!draft.value) return
  emit('confirm', draft.value)
}

onMounted(fetchDraft)
</script>

<template>
  <Card v-if="draft || loading">
    <CardHeader class="pb-2"><CardTitle class="text-base">🤖 智能推荐</CardTitle></CardHeader>
    <CardContent class="space-y-2 text-sm">
      <div v-if="loading && !draft" class="text-xs text-muted-foreground py-2">正在生成推荐...</div>
      <template v-if="draft">
        <div v-for="item in draft.items || []" :key="item.name" class="flex justify-between">
          <span>{{ item.name }}</span>
          <span class="text-muted-foreground">¥{{ item.price }}</span>
        </div>
        <div v-if="draft.nutrition" class="text-xs text-muted-foreground">
          💰 ¥{{ draft.total_price }} · 🔥 {{ draft.nutrition.calories }}kcal · 🥩 {{ draft.nutrition.protein }}g
        </div>
        <div v-if="draft.reasons?.length" class="text-xs text-muted-foreground space-y-0.5">
          <div v-for="r in draft.reasons" :key="r">✅ {{ r }}</div>
        </div>
        <div class="flex gap-2">
          <Button size="sm" class="flex-1" :disabled="loading" @click="confirmDraft">确认</Button>
          <Button size="sm" variant="outline" :disabled="loading" @click="fetchDraft">🔄 换一个</Button>
        </div>
      </template>
    </CardContent>
  </Card>
</template>
