export type MainTab = 'companion' | 'health' | 'support'
export type UserStatus = 'worry' | 'test' | 'diagnosed' | 'learn'
export type TrustLevel = 'trust' | 'hesitant' | 'unknown'
export type MoodLabel = '害怕' | '焦虑' | '难过' | '平静' | '麻木' | '愤怒' | '想哭' | '想找人聊聊'
export type AssessmentKind = 'PHQ-9' | 'GAD-7'
export type RiskKind = 'pep' | 'general'
export type TimelineCategory = '情绪' | '测评' | '医疗' | '用药' | '健康' | '正念'

export interface AppPreferences {
  onboardingDone: boolean
  userStatus: UserStatus | null
  saveLocal: boolean
  saveChat: boolean
  hideEnabled: boolean
  encrypted: boolean
  pinSalt?: string
  pinVerifier?: string
  modelConsent: boolean
}

export interface ChatMessage {
  id: string
  conversationId: string
  role: 'user' | 'assistant'
  content: string
  createdAt: number
  kind?: 'text' | 'emotion-card' | 'u-equals-u' | 'task-card'
}

export interface ConversationSummary {
  id: string
  conversationId: string
  title: string
  summary: string
  createdAt: number
}

export interface MoodRecord {
  id: string
  label: MoodLabel
  intensity: number
  note: string
  createdAt: number
}

export interface AssessmentRecord {
  id: string
  kind: AssessmentKind
  answers: number[]
  score: number
  level: string
  selfHarmRisk: boolean
  createdAt: number
}

export interface RiskRecord {
  id: string
  kind: RiskKind
  answers: Record<string, string>
  urgency: 'low' | 'consult' | 'urgent'
  createdAt: number
}

export interface HealthEntry {
  id: string
  date: string
  weight: number | null
  sleepHours: number | null
  symptoms: string[]
  note: string
  createdAt: number
}

export interface MedicationPlan {
  id: string
  name: string
  dose: string
  times: string[]
  requirement: string
  active: boolean
  createdAt: number
}

export interface MedicationLog {
  id: string
  planId: string
  date: string
  scheduledTime: string
  status: 'taken' | 'missed' | 'pending'
  confirmedAt?: number
}

export interface LabMetric {
  id: string
  date: string
  cd4: number | null
  viralLoad: number | null
  viralLoadText: string
  institution: string
  source: 'manual' | 'report'
  createdAt: number
}

export interface ReportAnalysis {
  reportType: string
  testDate: string
  institution: string
  cd4: number | null
  viralLoad: number | null
  viralLoadText: string
  ocrText: string
  explanation: string
  doctorQuestions: string[]
  confidence: number
}

export interface ReportRecord {
  id: string
  fileName: string
  mimeType: string
  fileData?: string
  analysis: ReportAnalysis
  createdAt: number
}

export interface TimelineEvent {
  id: string
  category: TimelineCategory
  title: string
  summary: string
  createdAt: number
  refId?: string
}

export interface FavoriteRecord {
  id: string
  articleId: string
  createdAt: number
}

export interface TrustEvidence {
  id: string
  direction: 'trust' | 'hesitant'
  quote: string
  weight: number
  createdAt: number
}

export interface KnowledgeArticle {
  id: string
  title: string
  category: string
  summary: string
  content: string
  source: string
  sourceUrl: string
  updatedAt: string
  keywords: string[]
}

export interface NewsItem {
  id: string
  title: string
  summary: string
  topic: string
  source: string
  url: string
  publishedAt: string
  fetchedAt: string
}

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export interface AgentReply {
  content: string
  crisis: boolean
  tool?: 'u-equals-u' | 'assessment' | 'risk' | 'meditation' | 'none'
  citations?: KnowledgeArticle[]
}
