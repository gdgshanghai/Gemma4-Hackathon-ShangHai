<template>
  <div class="live-review-detail-page">
    <div class="live-review-detail-hero">
      <div>
        <el-button icon="el-icon-back" size="mini" plain @click="goBack">
          {{ $t('liveReview.back') }}
        </el-button>
        <p class="live-review-detail-kicker">
          {{ $t('liveReview.roomLabel') }}: {{ roomId }} · {{ streamStartFolder }}
        </p>
      </div>
    </div>

    <el-card v-loading="loading" class="live-review-detail-card" shadow="never">
      <el-tabs v-model="activeTab" stretch>
        <el-tab-pane :label="$t('liveReview.tabSummary')" name="summary">
          <div v-if="session" class="live-review-summary">
            <h2 class="live-review-summary-title">{{ sessionTitle }}</h2>
            <div class="live-review-summary-grid">
              <div class="live-review-summary-item">
                <span class="label">{{ $t('home.reviewStartTime') }}</span>
                <span class="value">{{ session.startTime || '-' }}</span>
              </div>
              <div class="live-review-summary-item">
                <span class="label">{{ $t('home.reviewEndTime') }}</span>
                <span class="value">{{ session.endTime || '-' }}</span>
              </div>
              <div class="live-review-summary-item">
                <span class="label">{{ $t('home.reviewDuration') }}</span>
                <span class="value">{{ session.durationText || '-' }}</span>
              </div>
              <div class="live-review-summary-item">
                <span class="label">{{ $t('home.reviewGiftValue') }}</span>
                <span class="value">{{ session.giftValueText || '-' }}</span>
              </div>
              <div class="live-review-summary-item">
                <span class="label">{{ $t('home.reviewDanmakuCount') }}</span>
                <span class="value">{{ session.danmakuCount }}</span>
              </div>
            </div>
            <div v-if="session.hasCover" class="live-review-summary-cover-wrap">
              <el-image
                class="live-review-summary-cover"
                fit="cover"
                :src="coverDisplayUrl"
              ></el-image>
            </div>
            <scene-timeline-bar
              v-loading="sceneTimelineLoading"
              :timeline="sceneTimeline"
              :room-id="roomId"
              :stream-start-folder="streamStartFolder"
            />
          </div>
          <el-empty v-else-if="!loading" :description="$t('liveReview.sessionNotFound')"></el-empty>
        </el-tab-pane>

        <el-tab-pane :label="$t('liveReview.tabClips')" name="clips">
          <div v-loading="clipTimelineLoading" class="live-review-clips">
            <el-collapse v-model="activeClipPanels" class="live-review-clip-collapse">
              <el-collapse-item :title="$t('liveReview.clipDanmakuHighlights')" name="danmaku">
                <p class="live-review-clip-desc">{{ $t('liveReview.clipDanmakuDesc') }}</p>
                <clip-timeline-chart
                  ref="danmakuChart"
                  :title="$t('liveReview.clipDanmakuHighlights')"
                  theme="blue"
                  :series-name="$t('liveReview.clipDanmakuSeries')"
                  :points="clipTimeline ? clipTimeline.danmakuTimeline : []"
                  :x-max="clipTimeline ? clipTimeline.durationSeconds : 0"
                  value-key="count"
                  :empty-text="$t('liveReview.clipNoDanmakuData')"
                  :highlight-range="danmakuHighlightRange"
                />
                <auto-clip-panel
                  clip-type="danmaku"
                  :room-id="roomId"
                  :stream-start-folder="streamStartFolder"
                  :has-recording="!!(clipTimeline && clipTimeline.hasRecording)"
                  :ready="!!clipTimeline"
                  @suggestion-change="onDanmakuSuggestionChange"
                />
              </el-collapse-item>
              <el-collapse-item :title="$t('liveReview.clipGiftHighlights')" name="gift">
                <p class="live-review-clip-desc">{{ $t('liveReview.clipGiftDesc') }}</p>
                <clip-timeline-chart
                  ref="giftChart"
                  :title="$t('liveReview.clipGiftHighlights')"
                  theme="gold"
                  :series-name="$t('liveReview.clipGiftSeries')"
                  :points="clipTimeline ? clipTimeline.giftTimeline : []"
                  :x-max="clipTimeline ? clipTimeline.durationSeconds : 0"
                  value-key="amount"
                  :empty-text="$t('liveReview.clipNoGiftData')"
                  :y-value-formatter="formatGiftAxisLabel"
                  :highlight-range="giftHighlightRange"
                />
                <auto-clip-panel
                  clip-type="gift"
                  :room-id="roomId"
                  :stream-start-folder="streamStartFolder"
                  :has-recording="!!(clipTimeline && clipTimeline.hasRecording)"
                  :ready="!!clipTimeline"
                  @suggestion-change="onGiftSuggestionChange"
                />
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-tab-pane>

        <el-tab-pane :label="$t('liveReview.tabInterest')" name="interest">
          <el-empty :description="$t('liveReview.comingSoon')"></el-empty>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script>
import {
  fetchLiveArchiveSession,
  fetchLiveArchiveClipTimeline,
  fetchLiveArchiveSceneTimeline,
  formatLiveReviewSessionTitle
} from '@/utils/liveArchive'
import ClipTimelineChart from '@/components/ClipTimelineChart.vue'
import AutoClipPanel from '@/components/AutoClipPanel.vue'
import SceneTimelineBar from '@/components/SceneTimelineBar.vue'

export default {
  name: 'LiveReviewDetail',
  components: {
    ClipTimelineChart,
    AutoClipPanel,
    SceneTimelineBar
  },
  props: {
    roomId: {
      type: String,
      required: true
    },
    streamStartFolder: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      activeTab: 'summary',
      activeClipPanels: ['danmaku'],
      loading: false,
      clipTimelineLoading: false,
      sceneTimelineLoading: false,
      session: null,
      sceneTimeline: null,
      clipTimeline: null,
      danmakuHighlightRange: null,
      giftHighlightRange: null
    }
  },
  computed: {
    sessionTitle() {
      if (!this.session) {
        return ''
      }
      return formatLiveReviewSessionTitle(this.session.startTime, this.streamStartFolder)
    },
    coverDisplayUrl() {
      if (!this.session || !this.session.coverUrl) {
        return ''
      }
      return `${this.session.coverUrl}?v=${Date.now()}`
    }
  },
  watch: {
    roomId: 'loadSession',
    streamStartFolder: 'loadSession',
    activeTab(value) {
      if (value === 'clips' && !this.clipTimeline && !this.clipTimelineLoading) {
        this.loadClipTimeline()
      }
    },
    activeClipPanels() {
      this.$nextTick(() => {
        this.resizeClipCharts()
      })
    }
  },
  mounted() {
    this.loadSession()
  },
  methods: {
    goBack() {
      this.$router.push({ name: 'home', query: { review: '1' } })
    },
    async loadSession() {
      this.loading = true
      this.clipTimeline = null
      this.sceneTimeline = null
      try {
        this.session = await fetchLiveArchiveSession(this.roomId, this.streamStartFolder, false)
        await this.loadSceneTimeline()
        if (this.activeTab === 'clips') {
          await this.loadClipTimeline()
        }
      } catch (e) {
        this.session = null
        this.sceneTimeline = null
        this.$message.error(e.message || this.$t('liveReview.loadFailed'))
      } finally {
        this.loading = false
      }
    },
    async loadSceneTimeline() {
      this.sceneTimelineLoading = true
      try {
        this.sceneTimeline = await fetchLiveArchiveSceneTimeline(
          this.roomId,
          this.streamStartFolder
        )
      } catch (e) {
        this.sceneTimeline = null
        this.$message.error(e.message || this.$t('liveReview.sceneTimelineLoadFailed'))
      } finally {
        this.sceneTimelineLoading = false
      }
    },
    async loadClipTimeline() {
      this.clipTimelineLoading = true
      this.danmakuHighlightRange = null
      this.giftHighlightRange = null
      try {
        this.clipTimeline = await fetchLiveArchiveClipTimeline(this.roomId, this.streamStartFolder)
        this.$nextTick(() => {
          this.resizeClipCharts()
        })
      } catch (e) {
        this.clipTimeline = null
        this.$message.error(e.message || this.$t('liveReview.clipTimelineLoadFailed'))
      } finally {
        this.clipTimelineLoading = false
      }
    },
    formatGiftAxisLabel(value) {
      return `${Number(value || 0).toFixed(2)} 元`
    },
    onDanmakuSuggestionChange(suggestion) {
      this.danmakuHighlightRange = suggestion
        ? { startSeconds: suggestion.startSeconds, endSeconds: suggestion.endSeconds }
        : null
    },
    onGiftSuggestionChange(suggestion) {
      this.giftHighlightRange = suggestion
        ? { startSeconds: suggestion.startSeconds, endSeconds: suggestion.endSeconds }
        : null
    },
    resizeClipCharts() {
      ['danmakuChart', 'giftChart'].forEach(refName => {
        let chartComponent = this.$refs[refName]
        if (chartComponent && typeof chartComponent.handleResize === 'function') {
          chartComponent.handleResize()
        }
      })
    }
  }
}
</script>

<style scoped>
.live-review-detail-page {
  min-height: 100vh;
  padding: 24px clamp(16px, 3vw, 40px) 40px;
  box-sizing: border-box;
  background:
    radial-gradient(circle at 12% 18%, rgba(139, 69, 255, 0.18), transparent 34%),
    radial-gradient(circle at 88% 12%, rgba(255, 114, 223, 0.12), transparent 30%),
    linear-gradient(180deg, #120f2a 0%, #1a1440 42%, #0f0c24 100%);
}

.live-review-detail-hero {
  max-width: 980px;
  margin: 0 auto 20px;
}

.live-review-detail-kicker {
  margin: 12px 0 0;
  color: rgba(239, 233, 255, 0.72);
  font-size: 13px;
}

.live-review-detail-card {
  max-width: 980px;
  margin: 0 auto;
  border-radius: 18px;
  border: 1px solid rgba(201, 165, 255, 0.18);
  background: rgba(10, 12, 36, 0.82);
  backdrop-filter: blur(18px);
}

.live-review-detail-card :deep(.el-card__body) {
  padding: 20px 24px 28px;
}

.live-review-detail-card :deep(.el-tabs__item) {
  color: rgba(239, 233, 255, 0.72);
  font-weight: 600;
}

.live-review-detail-card :deep(.el-tabs__item.is-active) {
  color: #efe9ff;
}

.live-review-detail-card :deep(.el-tabs__active-bar) {
  background-color: #ffd633;
}

.live-review-summary-title {
  margin: 0 0 24px;
  color: #ffffff;
  font-size: clamp(24px, 4vw, 34px);
  font-weight: 700;
  line-height: 1.35;
}

.live-review-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.live-review-summary-item {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(201, 165, 255, 0.12);
}

.live-review-summary-item .label {
  display: block;
  margin-bottom: 6px;
  color: rgba(239, 233, 255, 0.62);
  font-size: 13px;
}

.live-review-summary-item .value {
  color: #efe9ff;
  font-size: 16px;
  font-weight: 600;
}

.live-review-summary-cover-wrap {
  margin-top: 24px;
}

.live-review-summary-cover {
  width: min(100%, 420px);
  height: auto;
  aspect-ratio: 16 / 9;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(201, 165, 255, 0.18);
}

.live-review-clips {
  min-height: 180px;
}

.live-review-clip-collapse {
  border: none;
}

.live-review-clip-collapse :deep(.el-collapse-item) {
  margin-bottom: 12px;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(201, 165, 255, 0.14);
  background: rgba(255, 255, 255, 0.03);
}

.live-review-clip-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 48px;
  padding: 12px 16px;
  color: #efe9ff;
  font-size: 15px;
  font-weight: 600;
  background: transparent;
  border-bottom: none;
}

.live-review-clip-collapse :deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom: none;
}

.live-review-clip-collapse :deep(.el-collapse-item__content) {
  padding: 0 16px 18px;
  color: rgba(239, 233, 255, 0.82);
}

.live-review-clip-desc {
  margin: 0 0 12px;
  color: rgba(239, 233, 255, 0.62);
  font-size: 13px;
  line-height: 1.5;
}
</style>
