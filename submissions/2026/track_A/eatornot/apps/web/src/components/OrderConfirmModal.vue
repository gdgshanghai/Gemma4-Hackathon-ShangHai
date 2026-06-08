<script setup lang="ts">
import { ref, computed } from 'vue'
import { DialogRoot, DialogContent } from '@/components/ui'
import { Button } from '@/components/ui'
import { createOrder, searchStores, type RecommendationPlan } from '@/api/client'

const props = defineProps<{ plan: RecommendationPlan }>()
const emit = defineEmits<{
  'order-complete': [result: { success: boolean; message: string }]
  'close': []
}>()

const loading = ref(false)
const step = ref<'location' | 'stores' | 'confirm'>('location')
const city = ref('')
const keyword = ref('')
const stores = ref<any[]>([])
const storeLoading = ref(false)
const selectedStore = ref<any>(null)

async function searchNearbyStores() {
  if (!city.value.trim()) return
  storeLoading.value = true
  try {
    const result = await searchStores(city.value, keyword.value)
    stores.value = result.stores || []
    if (stores.value.length > 0) {
      step.value = 'stores'
    }
  } catch {
    stores.value = []
  } finally {
    storeLoading.value = false
  }
}

function selectStore(store: any) {
  selectedStore.value = store
  step.value = 'confirm'
}

async function handleConfirm() {
  loading.value = true
  try {
    const result = await createOrder(props.plan, selectedStore.value?.storeCode || 'S001')
    if (result.success) {
      emit('order-complete', { success: true, message: result.message || `下单成功！${selectedStore.value?.storeName || ''}` })
    } else {
      emit('order-complete', { success: false, message: result.message || '下单失败' })
    }
  } catch {
    emit('order-complete', { success: false, message: '下单请求失败' })
  } finally {
    loading.value = false
  }
}

const totalPrice = computed(() =>
  props.plan.items.reduce((s, i) => s + (i.price || 0), 0)
)
</script>

<template>
  <DialogRoot :default-open="true">
    <DialogContent class="max-w-lg">
      <!-- Step 1: Location Input -->
      <div v-if="step === 'location'">
        <h2 class="text-lg font-semibold mb-1">📍 选择门店</h2>
        <p class="text-sm text-gray-500 mb-4">输入你的位置，搜索附近麦当劳门店</p>
        <div class="space-y-3">
          <div>
            <label class="text-sm font-medium text-gray-700">城市</label>
            <input v-model="city" placeholder="如：北京、上海、深圳"
              class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-orange-400 focus:ring-1 focus:ring-orange-400 outline-none" />
          </div>
          <div>
            <label class="text-sm font-medium text-gray-700">位置/商圈（可选）</label>
            <input v-model="keyword" placeholder="如：王府井、三里屯、公司"
              class="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-orange-400 focus:ring-1 focus:ring-orange-400 outline-none"
              @keydown.enter="searchNearbyStores" />
          </div>
          <Button class="w-full" @click="searchNearbyStores" :disabled="!city.trim() || storeLoading">
            {{ storeLoading ? '搜索中...' : '🔍 搜索附近门店' }}
          </Button>
        </div>
        <div class="flex gap-3 mt-4">
          <Button variant="outline" class="flex-1" @click="emit('close')">取消</Button>
        </div>
      </div>

      <!-- Step 2: Store List -->
      <div v-else-if="step === 'stores'">
        <h2 class="text-lg font-semibold mb-1">🏪 附近门店</h2>
        <p class="text-sm text-gray-500 mb-3">{{ city }} · 共 {{ stores.length }} 家门店</p>
        <div class="max-h-64 overflow-y-auto space-y-2">
          <div v-for="store in stores" :key="store.storeCode"
            @click="selectStore(store)"
            class="p-3 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50 cursor-pointer transition-all">
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium">{{ store.storeName }}</span>
              <span class="text-xs text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full">{{ store.distance }}</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">{{ store.address }}</p>
          </div>
        </div>
        <div class="flex gap-3 mt-4">
          <Button variant="outline" class="flex-1" @click="step = 'location'">← 重新搜索</Button>
          <Button variant="outline" class="flex-1" @click="emit('close')">取消</Button>
        </div>
      </div>

      <!-- Step 3: Confirm Order -->
      <div v-else>
        <h2 class="text-lg font-semibold mb-1">📋 确认订单</h2>
        <div v-if="selectedStore" class="text-sm bg-gray-50 rounded-lg p-2 mb-3 flex items-center gap-2">
          <span>🏪</span>
          <span class="font-medium">{{ selectedStore.storeName }}</span>
          <span class="text-gray-400">{{ selectedStore.distance }}</span>
        </div>
        <div class="space-y-2 mb-3">
          <div v-for="(item, i) in plan.items" :key="i" class="flex justify-between text-sm">
            <span>{{ item.name }}</span>
            <span>{{ item.calories }}kcal</span>
          </div>
        </div>
        <div class="border-t pt-3 space-y-1 text-sm">
          <div v-if="totalPrice > 0">总计: ¥{{ totalPrice.toFixed(0) }}</div>
          <div v-else class="text-green-600 text-xs">价格以下单时为准</div>
          <div>总热量: {{ plan.estimated_calories.toFixed(0) }} 千卡</div>
        </div>
        <div v-if="plan.safety_warnings.length" class="mt-3 space-y-1">
          <div v-for="w in plan.safety_warnings" :key="w" class="text-sm text-yellow-600">⚠️ {{ w }}</div>
        </div>
        <div class="flex gap-3 mt-5">
          <Button variant="outline" class="flex-1" @click="step = 'stores'" :disabled="loading">← 换门店</Button>
          <Button class="flex-1 bg-orange-500 hover:bg-orange-600 text-white" @click="handleConfirm" :disabled="loading">
            {{ loading ? '下单中...' : '✓ 确认下单' }}
          </Button>
        </div>
      </div>
    </DialogContent>
  </DialogRoot>
</template>
