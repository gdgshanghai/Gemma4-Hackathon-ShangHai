<template>
  <div class="psych-page">
    <el-card class="page-card">
      <div slot="header" class="page-header">
        <span class="page-title">{{ $t('psych.title') }}</span>
        <div class="page-controls">
          <span class="control-label">联合分析间隔</span>
          <el-input-number
            v-model="perTabConfig.psych.windowSeconds"
            :min="10"
            :max="300"
            :step="5"
            size="small"
          ></el-input-number>
          <span class="control-label">秒</span>
          <el-button size="mini" type="primary" @click="savePsychTabConfig">应用</el-button>
          <el-button size="mini" :loading="loading" @click="refreshAll">{{ $t('psych.refresh') }}</el-button>
        </div>
      </div>

      <div class="panel-stack">
        <!-- 心理分析 -->
        <el-card class="panel" shadow="never">
          <div class="panel-header">
            <span class="panel-title">{{ $t('psych.analysisTab') }}</span>
            <div class="panel-controls">
              <el-switch v-model="perTabConfig.psych.enabled" size="small"></el-switch>
              <span class="control-label">{{ $t('psych.enabled') }}</span>
              <span v-if="latest" class="panel-ts">{{ formatTime(latest.ts) }}</span>
            </div>
          </div>
          <template v-if="latest">
            <div class="metric-grid">
              <el-card shadow="never" class="metric-card">
                <div class="metric-name">{{ $t('psych.stress') }}</div>
                <div class="metric-value">{{ toPercent(latest.analysis.stress) }}</div>
              </el-card>
              <el-card shadow="never" class="metric-card">
                <div class="metric-name">{{ $t('psych.valence') }}</div>
                <div class="metric-value">{{ toPercent(latest.analysis.valence) }}</div>
              </el-card>
              <el-card shadow="never" class="metric-card">
                <div class="metric-name">{{ $t('psych.fatigue') }}</div>
                <div class="metric-value">{{ toPercent(latest.analysis.fatigue) }}</div>
              </el-card>
              <el-card shadow="never" class="metric-card">
                <div class="metric-name">{{ $t('psych.engagement') }}</div>
                <div class="metric-value">{{ toPercent(latest.analysis.engagement) }}</div>
              </el-card>
            </div>
            <div class="summary-block">
              <p><strong>{{ $t('psych.summary') }}:</strong> {{ latest.analysis.summary || '-' }}</p>
              <p><strong>{{ $t('psych.confidence') }}:</strong> {{ toPercent(latest.analysis.confidence) }}</p>
              <p><strong>{{ $t('psych.danmakuDistill') }}:</strong> {{ formatDanmakuDistill(latest.analysis) }}</p>
            </div>
          </template>
          <el-empty v-else :description="$t('psych.noData')" :image-size="60"></el-empty>
        </el-card>

        <!-- 语音观察 -->
        <el-card class="panel" shadow="never">
          <div class="panel-header">
            <span class="panel-title">{{ $t('psych.voiceTab') }}</span>
            <div class="panel-controls">
              <el-switch v-model="perTabConfig.voice.enabled" size="small"></el-switch>
              <span class="control-label">{{ $t('psych.enabled') }}</span>
              <span v-if="voiceLatest" class="panel-ts">{{ formatTime(voiceLatest.ts) }}</span>
            </div>
          </div>
          <div v-if="voiceLatest" class="report-card">
            <p><strong>{{ $t('psych.soundType') }}:</strong> {{ voiceLatest.soundType || '-' }}</p>
            <p><strong>{{ $t('psych.activity') }}:</strong> {{ voiceLatest.activity || '-' }}</p>
            <p><strong>{{ $t('psych.voiceState') }}:</strong> {{ voiceLatest.psychologicalState || '-' }}</p>
            <p><strong>{{ $t('psych.confidence') }}:</strong> {{ toPercent(voiceLatest.confidence) }}</p>
            <p><strong>{{ $t('psych.summary') }}:</strong> {{ voiceLatest.summary || '-' }}</p>
            <p v-if="voiceLatest.transcript"><strong>{{ $t('psych.transcript') }}:</strong> {{ voiceLatest.transcript }}</p>
          </div>
          <el-empty v-else :description="$t('psych.noVoiceData')" :image-size="60"></el-empty>
        </el-card>

        <!-- 礼物统计 -->
        <el-card class="panel" shadow="never">
          <div class="panel-header">
            <span class="panel-title">{{ $t('psych.giftTab') }}</span>
            <div class="panel-controls">
              <el-switch v-model="perTabConfig.gift.enabled" size="small"></el-switch>
              <span class="control-label">{{ $t('psych.enabled') }}</span>
              <span v-if="latest" class="panel-ts">{{ formatTime(latest.ts) }}</span>
            </div>
          </div>
          <template v-if="latest">
            <div class="metric-grid gift-grid">
              <el-card shadow="never" class="metric-card">
                <div class="metric-name">{{ $t('psych.giftCount') }}</div>
                <div class="metric-value">{{ latest.metrics.giftCount || 0 }}</div>
              </el-card>
              <el-card shadow="never" class="metric-card">
                <div class="metric-name">{{ $t('psych.giftValue') }}</div>
                <div class="metric-value">{{ formatCurrency(latest.metrics.giftValue) }}</div>
              </el-card>
              <el-card shadow="never" class="metric-card">
                <div class="metric-name">{{ $t('psych.superChatCount') }}</div>
                <div class="metric-value">{{ latest.metrics.superChatCount || 0 }}</div>
              </el-card>
              <el-card shadow="never" class="metric-card">
                <div class="metric-name">{{ $t('psych.superChatValue') }}</div>
                <div class="metric-value">{{ formatCurrency(latest.metrics.superChatValue) }}</div>
              </el-card>
            </div>
            <div class="summary-block">
              <p v-if="localGiftSummary"><strong>累计礼物价值:</strong> {{ formatCurrency(localGiftSummary.totalGiftValue) }}</p>
              <p><strong>{{ $t('psych.giftInsight') }}:</strong> {{ buildGiftInsight(latest.metrics) }}</p>
            </div>
          </template>
          <el-empty v-else :description="$t('psych.noGiftData')" :image-size="60"></el-empty>
        </el-card>

        <!-- 画面场景 -->
        <el-card class="panel" shadow="never">
          <div class="panel-header">
            <span class="panel-title">{{ $t('psych.sceneTab') }}</span>
            <div class="panel-controls">
              <el-switch v-model="perTabConfig.scene.enabled" size="small"></el-switch>
              <span class="control-label">{{ $t('psych.enabled') }}</span>
              <span v-if="sceneLatest" class="panel-ts">{{ formatTime(sceneLatest.ts) }}</span>
            </div>
          </div>
          <div v-if="sceneLatest" class="report-card">
            <p><strong>{{ $t('psych.sceneCategory') }}:</strong> {{ sceneLatest.category || '-' }}</p>
            <p><strong>{{ $t('psych.confidence') }}:</strong> {{ toPercent(sceneLatest.confidence) }}</p>
            <p><strong>{{ $t('psych.summary') }}:</strong> {{ sceneLatest.summary || '-' }}</p>
            <p v-if="(sceneLatest.evidence || []).length">
              <strong>{{ $t('psych.evidence') }}:</strong> {{ (sceneLatest.evidence || []).join(' / ') }}
            </p>
          </div>
          <el-empty v-else :description="$t('psych.noSceneData')" :image-size="60"></el-empty>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script>
import { getPsychHistory, getPsychLatest, updatePsychConfig } from '@/api/psych'

export default {
  name: 'PsychState',
  props: {
    roomAgentState: {
      type: Object,
      default: null
    }
  },
  data: function() {
    return {
      loading: false,
      latest: null,
      localGiftSummary: null,
      voiceLatest: null,
      sceneLatest: null,
      localConfig: { enabled: true, roomId: 0, windowSeconds: 30 },
      pollTimer: null,
      perTabConfig: {
        voice: { enabled: true, windowSeconds: 30 },
        psych: { enabled: true, windowSeconds: 30 },
        gift: { enabled: true, windowSeconds: 30 },
        scene: { enabled: true, windowSeconds: 30 }
      }
    }
  },
  mounted: function() {
    this.notifyTabConfigChange()
    this.refreshAll()
    this.pollTimer = window.setInterval(() => this.refreshDataOnly(), 5000)
  },
  watch: {
    roomAgentState: {
      handler: function(value) {
        this.applyRoomAgentState(value)
      },
      deep: true,
      immediate: true
    },
    perTabConfig: {
      handler: function() {
        this.notifyTabConfigChange()
      },
      deep: true
    }
  },
  beforeDestroy: function() {
    if (this.pollTimer) {
      window.clearInterval(this.pollTimer)
      this.pollTimer = null
    }
  },
  methods: {
    refreshAll: async function() {
      this.loading = true
      try {
        await Promise.all([this.refreshDataOnly(), this.refreshHistory()])
      } finally {
        this.loading = false
      }
    },
    refreshDataOnly: async function() {
      const res = await getPsychLatest()
      if (res && res.success) {
        this.latest = res.data
        this.localConfig.enabled = Boolean(res.config && res.config.enabled)
        this.localConfig.roomId = Number((res.config && res.config.roomId) || 0)
        this.localConfig.windowSeconds = Number((res.config && res.config.windowSeconds) || 30)
        this.hydrateLatestExtraReports(res.data)
        this.applyRoomAgentState(this.roomAgentState)
      }
    },
    refreshHistory: async function() {
      const res = await getPsychHistory(20)
      if (res && res.success) {
        const rows = (res.data || []).slice().reverse()
        this.hydrateHistoryExtraReports(rows)
        this.applyRoomAgentState(this.roomAgentState)
      }
    },
    applyRoomAgentState: function(state) {
      if (!state || typeof state !== 'object') {
        return
      }
      if (state.latestPsychAnalysis) {
        this.latest = state.latestPsychAnalysis
      }
      if (state.latestGiftSummary) {
        this.localGiftSummary = state.latestGiftSummary
      }
      if (state.latestVoiceReport && state.latestVoiceReport.report) {
        this.voiceLatest = this.normalizeVoiceReport(
          state.latestVoiceReport.report,
          state.latestVoiceReport.usage,
          state.latestVoiceReport.ts
        )
      }
      if (state.latestSceneReport && state.latestSceneReport.report) {
        this.sceneLatest = this.normalizeSceneReport(
          state.latestSceneReport.report,
          state.latestSceneReport.usage,
          state.latestSceneReport.ts
        )
      }
    },
    notifyTabConfigChange: function() {
      this.$emit('tab-config-change', JSON.parse(JSON.stringify(this.perTabConfig)))
    },
    hydrateLatestExtraReports: function(latest) {
      if (!latest || typeof latest !== 'object') {
        return
      }
      const voice = this.extractReport(latest, ['voiceReport', 'audioReport', 'asrReport'])
      const scene = this.extractReport(latest, ['sceneReport', 'visionReport'])
      if (voice) {
        this.voiceLatest = this.normalizeVoiceReport(voice, null, latest.ts)
      }
      if (scene) {
        this.sceneLatest = this.normalizeSceneReport(scene, null, latest.ts)
      }
    },
    hydrateHistoryExtraReports: function(rows) {
      if (!Array.isArray(rows) || rows.length === 0) {
        return
      }
      // 历史里取最近一条带 voiceReport/sceneReport 的，用来在初次加载时兜底显示
      for (const row of rows) {
        if (!this.voiceLatest) {
          const voice = this.extractReport(row, ['voiceReport', 'audioReport', 'asrReport'])
          if (voice) {
            this.voiceLatest = this.normalizeVoiceReport(voice, null, row.ts)
          }
        }
        if (!this.sceneLatest) {
          const scene = this.extractReport(row, ['sceneReport', 'visionReport'])
          if (scene) {
            this.sceneLatest = this.normalizeSceneReport(scene, null, row.ts)
          }
        }
        if (this.voiceLatest && this.sceneLatest) {
          break
        }
      }
    },
    extractReport: function(source, keys) {
      const containers = [source, source && source.analysis, source && source.extra, source && source.reports, source && source.ai]
      for (let i = 0; i < containers.length; i++) {
        const container = containers[i]
        if (!container || typeof container !== 'object') {
          continue
        }
        for (let j = 0; j < keys.length; j++) {
          const key = keys[j]
          if (container[key] && typeof container[key] === 'object') {
            return container[key]
          }
        }
      }
      return null
    },
    normalizeVoiceReport: function(report, usage, ts) {
      return {
        ts: ts || report.audioAt || report.micAudioAt || new Date().toISOString(),
        transcript: String(report.transcript || ''),
        soundType: String(report.soundType || report.desktopSoundType || '-'),
        activity: String(report.activity || '-'),
        psychologicalState: String(report.psychologicalState || '-'),
        confidence: Number(report.confidence || 0),
        evidence: Array.isArray(report.evidence) ? report.evidence : [],
        summary: String(report.summary || ''),
        tokenUsageText: this.buildTokenUsageText(usage)
      }
    },
    normalizeSceneReport: function(report, usage, ts) {
      return {
        ts: ts || report.frameAt || new Date().toISOString(),
        category: String(report.category || '-'),
        confidence: Number(report.confidence || 0),
        evidence: Array.isArray(report.evidence) ? report.evidence : [],
        summary: String(report.summary || ''),
        tokenUsageText: this.buildTokenUsageText(usage)
      }
    },
    buildTokenUsageText: function(usage) {
      if (!usage || typeof usage !== 'object') {
        return ''
      }
      const input = Number(usage.inputTokens || 0)
      const output = Number(usage.outputTokens || 0)
      const total = Number(usage.totalTokens || (input + output))
      return `${this.$t('psych.inputTokens')}: ${input}, ${this.$t('psych.outputTokens')}: ${output}, ${this.$t('psych.totalTokens')}: ${total}`
    },
    savePsychTabConfig: async function() {
      const payload = {
        enabled: this.perTabConfig.psych.enabled,
        roomId: this.localConfig.roomId > 0 ? this.localConfig.roomId : null,
        windowSeconds: this.perTabConfig.psych.windowSeconds
      }
      const res = await updatePsychConfig(payload)
      if (res && res.success) {
        this.$message.success(this.$t('psych.configSaved'))
        await this.refreshDataOnly()
      } else {
        this.$message.error((res && res.error) || this.$t('psych.configSaveFailed'))
      }
    },
    formatDanmakuDistill: function(analysis) {
      if (!analysis || !analysis.danmakuDistill) {
        if (analysis && Array.isArray(analysis.riskFlags) && analysis.riskFlags.length > 0) {
          return analysis.riskFlags.join(' / ')
        }
        return '-'
      }
      const distill = analysis.danmakuDistill
      const label = String(distill.label || this.$t('psych.danmakuDistill')).trim()
      const text = String(distill.text || '').trim()
      return text !== '' ? `${label}: ${text}` : '-'
    },
    toPercent: function(v) {
      const n = Number(v || 0)
      return `${(n * 100).toFixed(1)}%`
    },
    formatCurrency: function(v) {
      return Number(v || 0).toFixed(2)
    },
    formatTime: function(ts) {
      if (!ts) {
        return '-'
      }
      const date = new Date(ts)
      if (!Number.isNaN(date.getTime())) {
        return date.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
      }
      const matched = String(ts).match(/(\d{2}:\d{2}:\d{2})/)
      return matched ? matched[1] : String(ts)
    },
    buildGiftInsight: function(metrics) {
      const giftCount = Number(metrics.giftCount || 0)
      const giftValue = Number(metrics.giftValue || 0)
      const superChatCount = Number(metrics.superChatCount || 0)
      const superChatValue = Number(metrics.superChatValue || 0)
      if (giftCount + superChatCount === 0) {
        return this.$t('psych.giftInsightLow')
      }
      if (giftValue + superChatValue >= 200) {
        return this.$t('psych.giftInsightHigh')
      }
      return this.$t('psych.giftInsightMid')
    }
  }
}
</script>

<style scoped>
.psych-page {
  padding: 10px;
}

:deep(.el-card) {
  border-radius: 12px;
  border: none;
  box-shadow: none;
  background: transparent;
}

.page-card :deep(.el-card__header) {
  border-bottom: none;
  padding-bottom: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.page-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: #312b4b;
}

.page-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.el-button--mini) {
  border-radius: 8px;
  font-weight: 600;
}

.panel-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel {
  border-radius: 12px !important;
  border: 1px solid #eee9ff !important;
  background: rgba(255, 255, 255, 0.85) !important;
  padding: 12px 14px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0edff;
}

.panel-title {
  font-weight: 700;
  color: #312b4b;
  font-size: 14px;
}

.panel-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.panel-ts {
  font-size: 12px;
  color: #7c7694;
  margin-left: 8px;
}

.control-label {
  color: #4a4563;
  font-size: 12px;
  font-weight: 600;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 10px 0;
}

@media (min-width: 960px) {
  .metric-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.metric-card {
  text-align: center;
  padding: 10px;
  border-radius: 12px !important;
  border: 1px solid #f0edff !important;
  background: #ffffff !important;
}

.metric-name {
  color: #7c7694;
  font-size: 12px;
}

.metric-value {
  margin-top: 5px;
  font-size: 18px;
  font-weight: 800;
  color: #7964e6;
}

.summary-block {
  font-size: 13px;
  line-height: 1.6;
  color: #4a4563;
  margin: 8px 0 0;
}

.summary-block p {
  margin: 4px 0;
}

.report-card {
  padding: 10px 4px;
  color: #4a4563;
  font-size: 13px;
  line-height: 1.6;
}

.report-card p {
  margin: 4px 0;
}

.gift-grid {
  margin-bottom: 8px;
}
</style>
