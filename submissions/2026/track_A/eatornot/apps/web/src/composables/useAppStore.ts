import { ref } from 'vue'
import {
  fetchProfile,
  saveProfile,
  resetProfile,
  fetchRecommendation,
  refinePlan,
  createOrder,
  submitFeedback,
  resetConversation,
  getUserId,
  type UserProfile,
  type RecommendationResponse,
  type RecommendationPlan,
  type QuickProfileData,
} from '@/api/client'

// Strip LLM <thought> tags from text for clean display
function stripThought(text: string): string {
  return text.replace(/<thought>[\s\S]*?<\/thought>/g, '').trim()
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export type AppPhase = 'mode_selection' | 'onboarding' | 'quick_form' | 'main_app'

// Singleton state (shared across all components)
const phase = ref<AppPhase>('mode_selection')
const mode = ref<'long_term' | 'quick'>('long_term')
const profile = ref<UserProfile | null>(null)
const quickProfile = ref<QuickProfileData | null>(null)
const recommendation = ref<RecommendationResponse | null>(null)
const selectedPlan = ref<RecommendationPlan | null>(null)
const showOrderModal = ref(false)
const orderResult = ref<string | null>(null)
const showDebate = ref(true)
const chatMessages = ref<ChatMessage[]>([])
const showFeedback = ref(false)
const feedbackResult = ref<string | null>(null)
const loading = ref(false)
const inputValue = ref('')

// Initialize from localStorage cache for instant render
const savedMode = localStorage.getItem('eatornot_mode') as 'long_term' | 'quick' | null
const savedProfile = localStorage.getItem('eatornot_profile')
if (savedMode && savedProfile) {
  mode.value = savedMode
  profile.value = JSON.parse(savedProfile)
  phase.value = 'main_app'
}

// Hydrate profile from backend (source of truth), localStorage serves as cache
fetchProfile(getUserId())
  .then(p => {
    if (p.onboarding_complete) {
      profile.value = p
      localStorage.setItem('eatornot_profile', JSON.stringify(p))
      const m = (p.mode === 'quick' ? 'quick' : 'long_term') as 'long_term' | 'quick'
      mode.value = m
      localStorage.setItem('eatornot_mode', m)
      phase.value = 'main_app'
    } else {
      // Backend says onboarding incomplete — clear stale cache, go back to onboarding
      localStorage.removeItem('eatornot_profile')
      localStorage.removeItem('eatornot_mode')
      phase.value = 'landing'
    }
  })
  .catch(() => {})

export function useAppStore() {
  // ============ Mode Selection ============
  function selectMode(selectedMode: 'long_term' | 'quick') {
    mode.value = selectedMode
    localStorage.setItem('eatornot_mode', selectedMode)
    if (selectedMode === 'long_term') {
      phase.value = 'onboarding'
    } else {
      phase.value = 'quick_form'
    }
  }

  // ============ Profile Complete ============
  async function completeOnboarding(newProfile: UserProfile) {
    const saved = await saveProfile(newProfile)
    profile.value = saved
    localStorage.setItem('eatornot_profile', JSON.stringify(saved))
    phase.value = 'main_app'
  }

  function completeQuickProfile(qp: QuickProfileData) {
    quickProfile.value = qp
    phase.value = 'main_app'
  }

  // ============ Recommend ============
  async function handleRecommend(message?: string) {
    const msg = message || inputValue.value
    if (!msg.trim()) return
    loading.value = true
    orderResult.value = null
    selectedPlan.value = null
    showFeedback.value = false
    feedbackResult.value = null

    chatMessages.value.push({ role: 'user', content: msg })

    try {
      const result = await fetchRecommendation(msg, {
        mode: mode.value,
        quickProfile: mode.value === 'quick' ? quickProfile.value || undefined : undefined,
        context: {
          time_pressure: 'high',
          mood: quickProfile.value?.mood || 'tired',
          meal_type: 'dinner',
        },
      })
      recommendation.value = result
      chatMessages.value.push({ role: 'assistant', content: stripThought(result.summary || '') })
    } catch (err) {
      chatMessages.value.push({ role: 'assistant', content: '抱歉，分析失败了，请重试。' })
    }
    loading.value = false
  }

  // ============ Refine Plan ============
  async function handleRefine(message: string) {
    if (!selectedPlan.value) return
    chatMessages.value.push({ role: 'user', content: message })
    loading.value = true

    try {
      const refined = await refinePlan(selectedPlan.value.id, message)
      selectedPlan.value = {
        ...selectedPlan.value,
        items: refined.items.map((i: any) => ({
          ...i,
          carbohydrate: i.carbohydrate || i.carbs || 0,
        })),
        estimated_price: refined.price,
        estimated_calories: refined.nutrition.calories,
        protein: refined.nutrition.protein,
        fat: refined.nutrition.fat,
        sodium: refined.nutrition.sodium,
        version: refined.version,
      } as any

      const changeLog = refined.change_log || []
      const lastChange = changeLog[changeLog.length - 1]
      chatMessages.value.push({
        role: 'assistant',
        content: `已更新方案：${lastChange?.what_changed || message}。${lastChange?.impact || ''}`,
      })
    } catch (err) {
      chatMessages.value.push({ role: 'assistant', content: '修改失败，请重试。' })
    }
    loading.value = false
  }

  // ============ Order ============
  function handleOrderComplete(result: { success: boolean; message: string }) {
    showOrderModal.value = false
    if (result.success) {
      orderResult.value = result.message
      showFeedback.value = true
      fetchProfile().then(p => { profile.value = p })
    } else {
      orderResult.value = `下单失败：${result.message}`
    }
  }

  // ============ Feedback ============
  async function handleSubmitFeedback(satisfaction: number, notes: string) {
    try {
      const result = await submitFeedback({ meal_id: 'meal-0001', satisfaction, notes })
      feedbackResult.value = result.message
      showFeedback.value = false
    } catch (err) {
      feedbackResult.value = '反馈提交失败'
    }
  }

  // ============ Reset ============
  async function handleResetConversation() {
    await resetConversation()
    recommendation.value = null
    selectedPlan.value = null
    orderResult.value = null
    showFeedback.value = false
    feedbackResult.value = null
    chatMessages.value = []
  }

  async function handleResetProfile() {
    await resetProfile()
    localStorage.removeItem('eatornot_mode')
    localStorage.removeItem('eatornot_profile')
    profile.value = null
    quickProfile.value = null
    recommendation.value = null
    selectedPlan.value = null
    chatMessages.value = []
    phase.value = 'mode_selection'
  }

  return {
    // State
    phase, mode, profile, quickProfile,
    recommendation, selectedPlan, showOrderModal,
    orderResult, showDebate, chatMessages,
    showFeedback, feedbackResult, loading, inputValue,
    // Actions
    selectMode, completeOnboarding, completeQuickProfile,
    handleRecommend, handleRefine, handleOrderComplete,
    handleSubmitFeedback, handleResetConversation, handleResetProfile,
  }
}
