<script setup lang="ts">
defineProps<{ compact?: boolean }>()
</script>

<template>
  <div :class="['text-xs text-muted-foreground', compact ? '' : 'p-2 rounded bg-yellow-50 border border-yellow-200']">
    ⚕️ 本工具仅供参考，不构成医疗建议。如有特殊饮食需求请咨询医生。
  </div>
</template>
