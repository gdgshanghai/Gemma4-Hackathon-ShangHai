<script setup lang="ts">
import { ProgressRoot, ProgressIndicator } from 'radix-vue'
import { cn } from '@/lib/utils'
const props = defineProps<{ value?: number; class?: string; max?: number }>()
</script>
<template>
  <ProgressRoot
    :class="cn('relative h-4 w-full overflow-hidden rounded-full bg-secondary', props.class)"
    :model-value="props.value ?? 0"
    :max="props.max ?? 100"
  >
    <ProgressIndicator
      class="h-full w-full flex-1 bg-primary transition-all"
      :style="{ transform: `translateX(-${100 - (props.value || 0)}%)` }"
    />
  </ProgressRoot>
</template>
