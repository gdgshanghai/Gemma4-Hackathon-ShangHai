<script setup lang="ts">
import { DialogContent, DialogPortal, DialogTitle, DialogClose } from 'radix-vue'
import { cn } from '@/lib/utils'
import DialogOverlay from './DialogOverlay.vue'
import { X } from 'lucide-vue-next'
const props = defineProps<{ class?: string }>()
</script>
<template>
  <DialogPortal>
    <DialogOverlay />
    <DialogContent :class="cn('fixed left-1/2 top-1/2 z-50 grid w-full max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 border bg-background p-6 shadow-lg rounded-lg', props.class)">
      <slot />
      <DialogClose class="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100">
        <X class="h-4 w-4" />
      </DialogClose>
    </DialogContent>
  </DialogPortal>
</template>
