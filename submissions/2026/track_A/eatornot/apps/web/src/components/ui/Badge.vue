<script setup lang="ts">
import { computed } from 'vue'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive text-white",
        outline: "text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  }
)

type BadgeVariants = VariantProps<typeof badgeVariants>
interface Props extends /* @vue-ignore */ BadgeVariants { class?: string }
const props = withDefaults(defineProps<Props>(), { variant: 'default' })
const classes = computed(() => cn(badgeVariants({ variant: props.variant }), props.class))
</script>
<template>
  <div :class="classes"><slot /></div>
</template>
