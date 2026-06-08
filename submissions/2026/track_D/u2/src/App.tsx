import { useEffect } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { useAppStore } from './store/appStore'
import { localAI } from './services/localAI'
import Onboarding from './pages/Onboarding'
import SafeScreen from './pages/SafeScreen'
import CompanionPage, { ConversationHistory } from './pages/Companion'
import HealthPage, { AssessmentPage, AssessmentPicker, HealthLogPage, MedicationPage, ReportPage, ReportUploadPage, RiskPage, TimelinePage, TrendsPage } from './pages/Health'
import SupportPage, { CareGuidePage, KnowledgePage, MindfulnessPage, NewsPage, ResourcesPage } from './pages/Support'
import SettingsPage, { DataPage, ModelPage, PrivacyPage } from './pages/Settings'
import { UnlockScreen } from './pages/Settings'
import { isSessionUnlocked } from './services/crypto'
import { useState } from 'react'

export default function App() {
  const [unlockVersion, setUnlockVersion] = useState(0)
  const ready = useAppStore((state) => state.ready)
  const preferences = useAppStore((state) => state.preferences)
  const hidden = useAppStore((state) => state.hidden)
  const bootstrap = useAppStore((state) => state.bootstrap)
  const setModel = useAppStore((state) => state.setModel)

  useEffect(() => {
    void bootstrap()
    return localAI.subscribe(setModel)
  }, [bootstrap, setModel])

  if (!ready || !preferences) return <div className="u2-screen empty-state"><div className="orb pulse" /><p>正在打开你的本地空间…</p></div>
  if (!preferences.onboardingDone) return <Onboarding />
  if (preferences.encrypted && !isSessionUnlocked()) return <UnlockScreen onUnlocked={() => setUnlockVersion(unlockVersion + 1)} />
  if (hidden) return <SafeScreen />

  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/companion" replace />} />
        <Route path="/companion" element={<CompanionPage />} />
        <Route path="/companion/history" element={<ConversationHistory />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/health/log" element={<HealthLogPage />} />
        <Route path="/health/medications" element={<MedicationPage />} />
        <Route path="/health/trends" element={<TrendsPage />} />
        <Route path="/health/assessments" element={<AssessmentPicker />} />
        <Route path="/health/assessment/:kind" element={<AssessmentPage />} />
        <Route path="/health/risk" element={<RiskPage />} />
        <Route path="/health/reports" element={<ReportPage />} />
        <Route path="/health/reports/upload" element={<ReportUploadPage />} />
        <Route path="/health/timeline" element={<TimelinePage />} />
        <Route path="/support" element={<SupportPage />} />
        <Route path="/support/knowledge" element={<KnowledgePage />} />
        <Route path="/support/news" element={<NewsPage />} />
        <Route path="/support/care" element={<CareGuidePage />} />
        <Route path="/support/mindfulness" element={<MindfulnessPage />} />
        <Route path="/support/resources" element={<ResourcesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/settings/privacy" element={<PrivacyPage />} />
        <Route path="/settings/data" element={<DataPage />} />
        <Route path="/settings/model" element={<ModelPage />} />
        <Route path="*" element={<Navigate to="/companion" replace />} />
      </Route>
    </Routes>
  )
}
