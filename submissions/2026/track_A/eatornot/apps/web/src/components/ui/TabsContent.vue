<script setup lang="ts">
import { TabsContent } from 'radix-vue'
import { cn } from '@/lib/utils'
const props = defineProps<{ value: string; class?: string }>()
</script>
<template>
  <TabsContent :value="value" :class="cn('mt-2', props.class)">
    <slot />
  </TabsContent>
</template>
