<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Badge } from '@/components/ui'
import { getProviderStatus } from '@/api/client'

const status = ref<any>(null)

onMounted(async () => {
  try {
    status.value = await getProviderStatus()
  } catch {}
})
</script>

<template>
  <Badge v-if="status" :variant="status.is_healthy ? 'default' : 'destructive'">
    {{ status.name }} {{ status.is_healthy ? '✓' : '✗' }}
  </Badge>
</template>
