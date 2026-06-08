<script setup lang="ts">
import { Button } from '@/components/ui'

defineEmits<{
  'reset-conversation': []
  'reset-profile': []
}>()
</script>

<template>
  <div class="flex gap-2">
    <Button variant="ghost" size="sm" @click="$emit('reset-conversation')">清空对话</Button>
    <Button variant="ghost" size="sm" @click="$emit('reset-profile')">重置档案</Button>
  </div>
</template>
