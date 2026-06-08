<template>
  <div class="scene-timeline-bar">
    <div class="scene-timeline-bar-header">
      <h4 class="scene-timeline-bar-title">{{ $t('liveReview.sceneTimelineTitle') }}</h4>
      <p class="scene-timeline-bar-desc">{{ $t('liveReview.sceneTimelineDesc') }}</p>
    </div>

    <div v-if="hasSegments" class="scene-timeline-bar-legend">
      <div
        v-for="item in legendItems"
        :key="item.sceneKey"
        class="scene-timeline-bar-legend-item"
      >
        <span class="scene-timeline-bar-legend-dot" :style="{ backgroundColor: item.color }"></span>
        <i :class="sceneIconClass(item.sceneKey)" class="scene-timeline-bar-legend-icon"></i>
        <span>{{ sceneLabel(item.sceneKey) }}</span>
      </div>
    </div>

    <div v-if="hasSegments" class="scene-timeline-bar-track-wrap">
      <div class="scene-timeline-bar-track">
        <el-tooltip
          v-for="(segment, index) in segments"
          :key="`${segment.sceneKey}-${index}`"
          effect="dark"
          placement="top"
          :content="segmentTooltip(segment)"
        >
          <div
            class="scene-timeline-bar-segment"
            :style="segmentStyle(segment)"
          >
            <i
              v-if="segmentWidthPercent(segment) >= 8"
              :class="sceneIconClass(segment.sceneKey)"
              class="scene-timeline-bar-segment-icon"
            ></i>
          </div>
        </el-tooltip>
      </div>
      <div class="scene-timeline-bar-axis">
        <span>0</span>
        <span>{{ durationLabel }}</span>
      </div>
    </div>

    <div v-if="hasSegments" class="scene-timeline-bar-list">
      <div
        v-for="(segment, index) in segments"
        :key="`detail-${segment.sceneKey}-${index}`"
        class="scene-timeline-bar-list-item"
        :class="{ 'is-summary-loading': summaryState(index).loading }"
        v-loading="summaryState(index).loading"
        :element-loading-text="$t('liveReview.sceneSegmentSummarizing')"
        element-loading-spinner="el-icon-loading"
        element-loading-background="rgba(15, 23, 42, 0.82)"
        :style="{ borderLeftColor: segment.color }"
      >
        <div class="scene-timeline-bar-list-head">
          <i :class="sceneIconClass(segment.sceneKey)" :style="{ color: segment.color }"></i>
          <span class="scene-timeline-bar-list-title">{{ sceneLabel(segment.sceneKey) }}</span>
          <span class="scene-timeline-bar-list-time">
            {{ segment.startText }} - {{ segment.endText }}
          </span>
        </div>
        <span class="scene-timeline-bar-list-duration">{{ segment.durationText }}</span>
        <div class="scene-timeline-bar-list-summary">
          <template v-if="summaryState(index).data">
            <p class="scene-timeline-bar-summary-line">
              <span class="scene-timeline-bar-summary-label">{{ $t('liveReview.sceneSegmentLiveContent') }}</span>
              {{ summaryState(index).data.sceneText }}
            </p>
            <p class="scene-timeline-bar-summary-line">
              <span class="scene-timeline-bar-summary-label">{{ $t('liveReview.sceneSegmentAudience') }}</span>
              {{ summaryState(index).data.audienceInterest }}
            </p>
            <p class="scene-timeline-bar-summary-line">
              <span class="scene-timeline-bar-summary-label">{{ $t('liveReview.sceneSegmentStreamer') }}</span>
              {{ summaryState(index).data.streamerSummary }}
            </p>
            <p v-if="summaryState(index).error" class="scene-timeline-bar-summary-error">
              {{ summaryState(index).error }}
            </p>
          </template>
          <p v-else-if="summaryState(index).error" class="scene-timeline-bar-summary-error">
            {{ summaryState(index).error }}
          </p>
        </div>
      </div>
    </div>

    <el-empty v-else :description="$t('liveReview.sceneTimelineEmpty')"></el-empty>
  </div>
</template>

<script>
import {
  buildSegmentSummarySaveRecord,
  callQwenChat,
  extractJsonObject,
  formatStreamDuration,
  isValidCachedSegmentSummary,
  normalizeCachedSegmentSummary,
  resolveLiveContentSceneText,
  saveLiveArchiveSegmentSummaries
} from '@/utils/liveArchive'

const SCENE_ICON_MAP = {
  gaming: 'el-icon-s-platform',
  singing: 'el-icon-microphone',
  watching: 'el-icon-video-camera'
}

export default {
  name: 'SceneTimelineBar',
  props: {
    timeline: {
      type: Object,
      default: null
    },
    roomId: {
      type: String,
      default: ''
    },
    streamStartFolder: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      segmentSummaries: {},
      summarizeRunId: 0,
      summarizeTimerId: null
    }
  },
  watch: {
    timeline: {
      immediate: true,
      handler() {
        this.scheduleSummarizeAllSegments()
      }
    }
  },
  beforeDestroy() {
    if (this.summarizeTimerId !== null) {
      window.clearTimeout(this.summarizeTimerId)
      this.summarizeTimerId = null
    }
  },
  computed: {
    durationSeconds() {
      return Number(this.timeline && this.timeline.durationSeconds) || 0
    },
    durationLabel() {
      return formatStreamDuration(this.durationSeconds)
    },
    segments() {
      return (this.timeline && this.timeline.segments) || []
    },
    legendItems() {
      return (this.timeline && this.timeline.sceneLegend) || []
    },
    hasSegments() {
      return this.segments.length > 0 && this.durationSeconds > 0
    }
  },
  methods: {
    sceneLabel(sceneKey) {
      let key = `liveReview.sceneType.${sceneKey}`
      if (this.$te(key)) {
        return this.$t(key)
      }
      let segment = this.segments.find(item => item.sceneKey === sceneKey)
      return segment ? segment.sceneText : sceneKey
    },
    sceneIconClass(sceneKey) {
      return SCENE_ICON_MAP[sceneKey] || 'el-icon-info'
    },
    segmentWidthPercent(segment) {
      let duration = this.durationSeconds
      if (duration <= 0) {
        return 0
      }
      let span = Math.max(0, Number(segment.endSeconds) - Number(segment.startSeconds))
      return (span / duration) * 100
    },
    segmentStyle(segment) {
      let width = this.segmentWidthPercent(segment)
      return {
        width: `${Math.max(width, 0.8)}%`,
        backgroundColor: segment.color,
        minWidth: width >= 3 ? '28px' : '6px'
      }
    },
    segmentTooltip(segment) {
      return `${this.sceneLabel(segment.sceneKey)} · ${segment.startText} - ${segment.endText} · ${segment.durationText}`
    },
    summaryState(index) {
      return this.segmentSummaries[index] || { loading: false, data: null, error: '' }
    },
    scheduleSummarizeAllSegments() {
      if (this.summarizeTimerId !== null) {
        window.clearTimeout(this.summarizeTimerId)
      }
      this.summarizeTimerId = window.setTimeout(() => {
        this.summarizeTimerId = null
        this.summarizeAllSegments()
      }, 200)
    },
    hasCachedSummary(segment) {
      return isValidCachedSegmentSummary(segment && segment.cachedSummary, segment)
    },
    applyCachedSummary(index, segment) {
      let data = normalizeCachedSegmentSummary(segment.cachedSummary, segment)
      this.$set(this.segmentSummaries, index, {
        loading: false,
        data,
        error: ''
      })
    },
    buildSummarySavePayload() {
      return this.segments.map((segment, index) => {
        let state = this.summaryState(index)
        return buildSegmentSummarySaveRecord(segment, state.data || {})
      })
    },
    async persistSegmentSummariesIfNeeded(needsSave) {
      if (!needsSave) {
        return
      }
      let roomId = String(this.roomId || '').trim()
      let streamFolder = String(this.streamStartFolder || '').trim()
      if (roomId === '' || streamFolder === '') {
        return
      }
      try {
        await saveLiveArchiveSegmentSummaries(
          roomId,
          streamFolder,
          this.buildSummarySavePayload()
        )
      } catch (e) {
        console.warn('Save segment summaries failed:', e)
      }
    },
    async summarizeAllSegments() {
      let runId = ++this.summarizeRunId
      this.segmentSummaries = {}
      if (!this.hasSegments) {
        return
      }
      let needsSave = false
      let tasks = this.segments.map((segment, index) => {
        if (this.hasCachedSummary(segment)) {
          this.applyCachedSummary(index, segment)
          return Promise.resolve()
        }
        return this.summarizeSegment(segment, index, runId).then(didGenerate => {
          if (didGenerate) {
            needsSave = true
          }
        })
      })
      await Promise.all(tasks)
      if (runId !== this.summarizeRunId) {
        return
      }
      await this.persistSegmentSummariesIfNeeded(needsSave)
    },
    buildSegmentArchiveText(excerpts, emptyText) {
      let lines = Array.isArray(excerpts) ? excerpts.filter(item => String(item || '').trim() !== '') : []
      if (lines.length === 0) {
        return emptyText
      }
      return lines.join('\n')
    },
    buildStreamerSummaryFallbackText(segment) {
      let pictureText = this.buildSegmentArchiveText(
        segment.pictureConclusions,
        ''
      )
      let voiceText = this.buildSegmentArchiveText(
        segment.voiceExcerpts,
        ''
      )
      if (pictureText !== '' && voiceText !== '') {
        return `${pictureText}（画面优先）`.slice(0, 120)
      }
      if (pictureText !== '') {
        return pictureText.slice(0, 120)
      }
      if (voiceText !== '') {
        return voiceText.slice(0, 120)
      }
      return this.$t('liveReview.sceneSegmentNoStreamerSource')
    },
    fallbackSegmentSummary(segment) {
      let mentalText = this.buildSegmentArchiveText(
        segment.mentalExcerpts,
        this.$t('liveReview.sceneSegmentNoMental')
      )
      return normalizeCachedSegmentSummary({
        liveContentType: segment.sceneKey,
        sceneKey: segment.sceneKey,
        sceneText: segment.sceneText || resolveLiveContentSceneText(segment.sceneKey),
        audienceInterest: mentalText.slice(0, 120),
        streamerSummary: this.buildStreamerSummaryFallbackText(segment)
      }, segment)
    },
    buildSegmentSummaryPrompt(segment) {
      let mentalText = this.buildSegmentArchiveText(
        segment.mentalExcerpts,
        this.$t('liveReview.sceneSegmentNoMental')
      )
      let voiceText = this.buildSegmentArchiveText(
        segment.voiceExcerpts,
        this.$t('liveReview.sceneSegmentNoVoice')
      )
      let pictureText = this.buildSegmentArchiveText(
        segment.pictureConclusions,
        this.$t('liveReview.sceneSegmentNoPicture')
      )
      return [
        '你是直播复盘助手。请根据本时段的心理分析、画面场景结论与语音观察记录，撰写复盘摘要。',
        '严格输出JSON，不要markdown。',
        '字段: audienceInterest（本时段观众兴趣与弹幕氛围，不超过60字）, streamerSummary（主播行为与直播内容，不超过60字）。',
        '撰写 streamerSummary 时：综合语音观察（voice）与画面场景结论（picture）；若两者描述冲突，必须以 picture 为准，voice 仅作补充。',
        `时段: ${segment.startText} - ${segment.endText}`,
        `画面场景类型: ${segment.sceneText || this.sceneLabel(segment.sceneKey)}`,
        `观众心理分析记录（mental）:\n${mentalText}`,
        `画面场景结论（picture，冲突时优先）:\n${pictureText}`,
        `语音观察记录（voice）:\n${voiceText}`
      ].join('\n')
    },
    normalizeSegmentSummary(obj, segment) {
      let fallback = this.fallbackSegmentSummary(segment)
      return normalizeCachedSegmentSummary({
        liveContentType: fallback.liveContentType,
        sceneKey: fallback.sceneKey,
        sceneText: fallback.sceneText,
        audienceInterest: String((obj && obj.audienceInterest) || fallback.audienceInterest).trim().slice(0, 120),
        streamerSummary: String((obj && obj.streamerSummary) || fallback.streamerSummary).trim().slice(0, 120)
      }, segment)
    },
    async summarizeSegment(segment, index, runId) {
      this.$set(this.segmentSummaries, index, { loading: true, data: null, error: '' })
      try {
        let prompt = this.buildSegmentSummaryPrompt(segment)
        let result = await callQwenChat(prompt, [])
        if (runId !== this.summarizeRunId) {
          return false
        }
        let obj = extractJsonObject(result.response || '')
        let data = obj === null
          ? this.fallbackSegmentSummary(segment)
          : this.normalizeSegmentSummary(obj, segment)
        this.$set(this.segmentSummaries, index, { loading: false, data, error: '' })
        return true
      } catch (e) {
        if (runId !== this.summarizeRunId) {
          return false
        }
        console.warn('Scene segment summary fallback:', e)
        let timeoutHint = String((e && e.message) || '').includes('timeout')
          ? this.$t('liveReview.sceneSegmentSummaryTimeout')
          : ''
        this.$set(this.segmentSummaries, index, {
          loading: false,
          data: this.fallbackSegmentSummary(segment),
          error: timeoutHint
        })
        return true
      }
    }
  }
}
</script>

<style scoped>
.scene-timeline-bar {
  margin-top: 24px;
  padding: 18px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.scene-timeline-bar-header {
  margin-bottom: 14px;
}

.scene-timeline-bar-title {
  margin: 0 0 6px;
  color: #e2e8f0;
  font-size: 16px;
  font-weight: 600;
}

.scene-timeline-bar-desc {
  margin: 0;
  color: rgba(226, 232, 240, 0.68);
  font-size: 13px;
  line-height: 1.5;
}

.scene-timeline-bar-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 20px;
  margin-bottom: 14px;
}

.scene-timeline-bar-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgba(226, 232, 240, 0.88);
  font-size: 13px;
}

.scene-timeline-bar-legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.scene-timeline-bar-legend-icon {
  font-size: 15px;
}

.scene-timeline-bar-track-wrap {
  margin-bottom: 16px;
}

.scene-timeline-bar-track {
  display: flex;
  width: 100%;
  min-height: 44px;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.5);
}

.scene-timeline-bar-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  transition: filter 0.2s ease;
  cursor: default;
}

.scene-timeline-bar-segment:hover {
  filter: brightness(1.08);
}

.scene-timeline-bar-segment-icon {
  color: rgba(15, 23, 42, 0.92);
  font-size: 18px;
  text-shadow: 0 1px 2px rgba(255, 255, 255, 0.35);
}

.scene-timeline-bar-axis {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  color: rgba(226, 232, 240, 0.62);
  font-size: 12px;
}

.scene-timeline-bar-list {
  display: grid;
  gap: 10px;
}

.scene-timeline-bar-list-item {
  position: relative;
  padding: 12px 14px;
  border-radius: 10px;
  border-left: 4px solid transparent;
  background: rgba(255, 255, 255, 0.04);
}

.scene-timeline-bar-list-item.is-summary-loading {
  min-height: 132px;
}

.scene-timeline-bar-list-item :deep(.el-loading-mask) {
  border-radius: 10px;
}

.scene-timeline-bar-list-item :deep(.el-loading-spinner) {
  margin-top: -18px;
}

.scene-timeline-bar-list-item :deep(.el-loading-spinner .el-loading-text) {
  margin-top: 10px;
  color: rgba(226, 232, 240, 0.88);
  font-size: 13px;
}

.scene-timeline-bar-list-item :deep(.el-loading-spinner .circular) {
  width: 36px;
  height: 36px;
}

.scene-timeline-bar-list-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.scene-timeline-bar-list-title {
  color: #f8fafc;
  font-size: 14px;
  font-weight: 600;
}

.scene-timeline-bar-list-time {
  color: rgba(226, 232, 240, 0.72);
  font-size: 13px;
}

.scene-timeline-bar-list-duration {
  display: block;
  margin-top: 6px;
  color: rgba(226, 232, 240, 0.56);
  font-size: 12px;
}

.scene-timeline-bar-list-summary {
  margin-top: 10px;
}

.scene-timeline-bar-summary-line {
  margin: 0 0 8px;
  color: rgba(226, 232, 240, 0.88);
  font-size: 13px;
  line-height: 1.55;
}

.scene-timeline-bar-summary-line:last-child {
  margin-bottom: 0;
}

.scene-timeline-bar-summary-label {
  display: inline-block;
  margin-right: 6px;
  color: rgba(226, 232, 240, 0.62);
  font-size: 12px;
}

.scene-timeline-bar-summary-error {
  margin: 0;
  color: #fca5a5;
  font-size: 13px;
}
</style>
