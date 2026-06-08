<script setup lang="ts">
import { TabsTrigger } from 'radix-vue'
import { cn } from '@/lib/utils'
const props = defineProps<{ value: string; class?: string }>()
</script>
<template>
  <TabsTrigger :value="value" :class="cn('inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium transition-all focus-visible:outline-none data-[state=active]:bg-white data-[state=active]:text-foreground data-[state=active]:shadow-sm', props.class)">
    <slot />
  </TabsTrigger>
</template>
