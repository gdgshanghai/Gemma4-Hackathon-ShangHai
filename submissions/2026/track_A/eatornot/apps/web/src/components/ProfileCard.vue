<script setup lang="ts">
import { Card, CardContent } from '@/components/ui'
import type { UserProfile } from '@/api/client'

defineProps<{ profile: UserProfile }>()
</script>

<template>
  <Card>
    <CardContent class="p-4 text-sm space-y-1">
      <div class="font-medium">{{ profile.name }}</div>
      <div class="text-muted-foreground">{{ profile.height_cm }}cm · {{ profile.weight_kg }}kg · {{ profile.age }}岁</div>
    </CardContent>
  </Card>
</template>
