<template>
  <div class="auto-clip-panel">
    <div class="auto-clip-panel-header">
      <h4 class="auto-clip-panel-title">{{ $t('liveReview.autoClipTitle') }}</h4>
      <p class="auto-clip-panel-desc">{{ $t('liveReview.autoClipDesc') }}</p>
    </div>

    <div class="auto-clip-panel-controls">
      <div class="auto-clip-duration-block">
        <span class="auto-clip-label">{{ $t('liveReview.autoClipDuration') }}</span>
        <div class="auto-clip-duration-actions">
          <el-button
            size="mini"
            icon="el-icon-minus"
            :disabled="clipDurationSeconds <= minDuration || loading || exporting"
            @click="adjustDuration(-stepDuration)"
          ></el-button>
          <span class="auto-clip-duration-value">{{ clipDurationText }}</span>
          <el-button
            size="mini"
            icon="el-icon-plus"
            :disabled="clipDurationSeconds >= maxDuration || loading || exporting"
            @click="adjustDuration(stepDuration)"
          ></el-button>
        </div>
        <span class="auto-clip-duration-range">
          {{ $t('liveReview.autoClipDurationRange') }}
        </span>
      </div>

      <div v-if="suggestion" class="auto-clip-suggestion">
        <div class="auto-clip-suggestion-item">
          <span class="auto-clip-label">{{ $t('liveReview.autoClipSuggestedStart') }}</span>
          <span class="auto-clip-value">{{ suggestion.startText }}</span>
        </div>
        <div class="auto-clip-suggestion-item">
          <span class="auto-clip-label">{{ $t('liveReview.autoClipSuggestedEnd') }}</span>
          <span class="auto-clip-value">{{ suggestion.endText }}</span>
        </div>
      </div>
    </div>

    <div class="auto-clip-panel-footer">
      <el-button
        type="primary"
        size="small"
        :disabled="!canExport"
        @click="confirmClip"
      >
        {{ $t('liveReview.autoClipConfirm') }}
      </el-button>
      <p v-if="lastOutputPath" class="auto-clip-output-path">
        {{ $t('liveReview.autoClipSavedTo') }}
      </p>
      <div v-if="lastOutputPath" class="auto-clip-output-card">
        <p class="auto-clip-output-file">{{ lastOutputFileName }}</p>
        <p class="auto-clip-output-full">{{ lastOutputPath }}</p>
        <el-button size="mini" plain @click="copyOutputPath">
          {{ $t('liveReview.autoClipCopyPath') }}
        </el-button>
      </div>
      <p v-if="!hasRecording" class="auto-clip-warning">
        {{ $t('liveReview.autoClipNoRecording') }}
      </p>
    </div>

    <el-dialog
      :visible.sync="exporting"
      :title="$t('liveReview.autoClipExportingTitle')"
      width="420px"
      append-to-body
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
      custom-class="auto-clip-loading-dialog"
    >
      <div class="auto-clip-loading-body">
        <div class="auto-clip-loading-spinner" aria-hidden="true">
          <span class="auto-clip-loading-ring"></span>
          <span class="auto-clip-loading-core"></span>
        </div>
        <p class="auto-clip-loading-text">{{ $t('liveReview.autoClipExportingDesc') }}</p>
        <p v-if="suggestion" class="auto-clip-loading-range">
          {{ suggestion.startText }} → {{ suggestion.endText }}
          · {{ clipDurationText }}
        </p>
      </div>
    </el-dialog>

    <el-dialog
      :visible.sync="exportSuccessVisible"
      :title="$t('liveReview.autoClipExportSuccessTitle')"
      width="520px"
      append-to-body
      custom-class="auto-clip-success-dialog"
    >
      <div class="auto-clip-success-body">
        <p class="auto-clip-success-desc">{{ $t('liveReview.autoClipExportSuccessDesc') }}</p>
        <div class="auto-clip-success-path-box">
          <p v-if="lastOutputFileName" class="auto-clip-success-file">{{ lastOutputFileName }}</p>
          <p class="auto-clip-success-path">{{ lastOutputPath }}</p>
        </div>
      </div>
      <span slot="footer" class="auto-clip-success-footer">
        <el-button size="small" @click="copyOutputPath">
          {{ $t('liveReview.autoClipCopyPath') }}
        </el-button>
        <el-button type="primary" size="small" @click="exportSuccessVisible = false">
          {{ $t('liveReview.autoClipExportSuccessConfirm') }}
        </el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import {
  CLIP_DURATION_DEFAULT,
  CLIP_DURATION_MAX,
  CLIP_DURATION_MIN,
  CLIP_DURATION_STEP,
  clampClipDuration,
  exportLiveArchiveClip,
  fetchLiveArchiveClipSuggestion,
  formatStreamDuration
} from '@/utils/liveArchive'

export default {
  name: 'AutoClipPanel',
  props: {
    roomId: {
      type: String,
      required: true
    },
    streamStartFolder: {
      type: String,
      required: true
    },
    clipType: {
      type: String,
      required: true
    },
    hasRecording: {
      type: Boolean,
      default: false
    },
    ready: {
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      clipDurationSeconds: CLIP_DURATION_DEFAULT,
      minDuration: CLIP_DURATION_MIN,
      maxDuration: CLIP_DURATION_MAX,
      stepDuration: CLIP_DURATION_STEP,
      suggestion: null,
      loading: false,
      exporting: false,
      exportSuccessVisible: false,
      lastOutputPath: '',
      lastOutputFileName: ''
    }
  },
  computed: {
    clipDurationText() {
      return formatStreamDuration(this.clipDurationSeconds)
    },
    canExport() {
      return (
        this.ready
        && this.hasRecording
        && Boolean(this.suggestion)
        && !this.loading
        && !this.exporting
        && this.suggestion.endSeconds > this.suggestion.startSeconds
      )
    }
  },
  watch: {
    ready(value) {
      if (value) {
        this.loadSuggestion()
      }
    },
    roomId() {
      this.resetAndReload()
    },
    streamStartFolder() {
      this.resetAndReload()
    },
    clipType() {
      this.resetAndReload()
    }
  },
  mounted() {
    if (this.ready) {
      this.loadSuggestion()
    }
  },
  methods: {
    resetAndReload() {
      this.lastOutputPath = ''
      this.lastOutputFileName = ''
      this.exportSuccessVisible = false
      this.clipDurationSeconds = CLIP_DURATION_DEFAULT
      if (this.ready) {
        this.loadSuggestion()
      } else {
        this.suggestion = null
      }
    },
    adjustDuration(delta) {
      this.clipDurationSeconds = clampClipDuration(this.clipDurationSeconds + delta)
      this.loadSuggestion()
    },
    async loadSuggestion() {
      if (!this.ready) {
        return
      }
      this.loading = true
      try {
        this.suggestion = await fetchLiveArchiveClipSuggestion(
          this.roomId,
          this.streamStartFolder,
          this.clipType,
          this.clipDurationSeconds
        )
        this.clipDurationSeconds = clampClipDuration(
          this.suggestion.clipDurationSeconds || this.clipDurationSeconds
        )
        this.$emit('suggestion-change', this.suggestion)
      } catch (e) {
        this.suggestion = null
        this.$message.error(e.message || this.$t('liveReview.autoClipSuggestionFailed'))
      } finally {
        this.loading = false
      }
    },
    async confirmClip() {
      if (!this.canExport) {
        return
      }
      this.exporting = true
      try {
        let result = await exportLiveArchiveClip(
          this.roomId,
          this.streamStartFolder,
          this.clipType,
          this.suggestion.startSeconds,
          this.suggestion.endSeconds
        )
        this.lastOutputPath = result.outputPath || ''
        this.lastOutputFileName = result.outputFileName || ''
        this.exportSuccessVisible = Boolean(this.lastOutputPath)
        this.$emit('clip-exported', result)
      } catch (e) {
        this.$message.error(e.message || this.$t('liveReview.autoClipExportFailed'))
      } finally {
        this.exporting = false
      }
    },
    async copyOutputPath() {
      if (!this.lastOutputPath) {
        return
      }
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(this.lastOutputPath)
        } else {
          let input = document.createElement('textarea')
          input.value = this.lastOutputPath
          input.setAttribute('readonly', 'readonly')
          input.style.position = 'absolute'
          input.style.left = '-9999px'
          document.body.appendChild(input)
          input.select()
          document.execCommand('copy')
          document.body.removeChild(input)
        }
        this.$message.success(this.$t('liveReview.autoClipCopyPathSuccess'))
      } catch (e) {
        this.$message.error(this.$t('liveReview.autoClipCopyPathFailed'))
      }
    }
  }
}
</script>

<style scoped>
.auto-clip-panel {
  margin-top: 16px;
  padding: 16px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.auto-clip-panel-header {
  margin-bottom: 14px;
}

.auto-clip-panel-title {
  margin: 0 0 6px;
  color: #e2e8f0;
  font-size: 15px;
  font-weight: 600;
}

.auto-clip-panel-desc {
  margin: 0;
  color: rgba(226, 232, 240, 0.68);
  font-size: 13px;
  line-height: 1.5;
}

.auto-clip-panel-controls {
  display: grid;
  gap: 14px;
}

.auto-clip-duration-block {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
}

.auto-clip-label {
  color: rgba(226, 232, 240, 0.72);
  font-size: 13px;
}

.auto-clip-duration-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.auto-clip-duration-value {
  min-width: 72px;
  text-align: center;
  color: #f8fafc;
  font-size: 16px;
  font-weight: 600;
}

.auto-clip-duration-range {
  color: rgba(226, 232, 240, 0.52);
  font-size: 12px;
}

.auto-clip-suggestion {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.auto-clip-suggestion-item {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.auto-clip-value {
  display: block;
  margin-top: 6px;
  color: #f8fafc;
  font-size: 18px;
  font-weight: 700;
}

.auto-clip-panel-footer {
  margin-top: 16px;
}

.auto-clip-output-path {
  margin: 10px 0 0;
  color: rgba(125, 211, 252, 0.92);
  font-size: 12px;
}

.auto-clip-output-card {
  margin-top: 8px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(125, 211, 252, 0.24);
}

.auto-clip-output-file {
  margin: 0 0 6px;
  color: #f8fafc;
  font-size: 14px;
  font-weight: 600;
  word-break: break-all;
}

.auto-clip-output-full {
  margin: 0 0 10px;
  color: rgba(226, 232, 240, 0.82);
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
}

.auto-clip-success-body {
  padding-top: 4px;
}

.auto-clip-success-desc {
  margin: 0 0 12px;
  color: rgba(226, 232, 240, 0.82);
  font-size: 14px;
  line-height: 1.6;
}

.auto-clip-success-path-box {
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(125, 211, 252, 0.24);
}

.auto-clip-success-file {
  margin: 0 0 8px;
  color: #f8fafc;
  font-size: 15px;
  font-weight: 700;
  word-break: break-all;
}

.auto-clip-success-path {
  margin: 0;
  color: rgba(125, 211, 252, 0.95);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
}

.auto-clip-success-footer {
  display: inline-flex;
  gap: 8px;
}

.auto-clip-warning {
  margin: 10px 0 0;
  color: #fca5a5;
  font-size: 12px;
}

.auto-clip-loading-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 12px 20px;
  text-align: center;
}

.auto-clip-loading-spinner {
  position: relative;
  width: 72px;
  height: 72px;
  margin-bottom: 18px;
}

.auto-clip-loading-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 4px solid rgba(148, 163, 184, 0.18);
  border-top-color: #38bdf8;
  border-right-color: #2dd4bf;
  animation: auto-clip-spin 0.9s linear infinite;
}

.auto-clip-loading-core {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 14px;
  height: 14px;
  margin: -7px 0 0 -7px;
  border-radius: 50%;
  background: linear-gradient(135deg, #38bdf8, #2dd4bf);
  box-shadow: 0 0 18px rgba(56, 189, 248, 0.55);
  animation: auto-clip-pulse 1.2s ease-in-out infinite;
}

.auto-clip-loading-text {
  margin: 0;
  color: #e2e8f0;
  font-size: 15px;
  font-weight: 600;
}

.auto-clip-loading-range {
  margin: 10px 0 0;
  color: rgba(226, 232, 240, 0.68);
  font-size: 13px;
}

@keyframes auto-clip-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes auto-clip-pulse {
  0%, 100% {
    transform: scale(0.92);
    opacity: 0.85;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}
</style>

<style>
.auto-clip-loading-dialog {
  border-radius: 16px;
  background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
  border: 1px solid rgba(148, 163, 184, 0.22);
  box-shadow: 0 24px 48px rgba(2, 6, 23, 0.45);
}

.auto-clip-loading-dialog .el-dialog__header {
  padding: 20px 24px 8px;
}

.auto-clip-loading-dialog .el-dialog__title {
  color: #f8fafc;
  font-size: 18px;
  font-weight: 600;
}

.auto-clip-loading-dialog .el-dialog__body {
  padding: 0 24px 24px;
}

.auto-clip-loading-dialog .el-dialog__headerbtn {
  display: none;
}

.auto-clip-success-dialog {
  border-radius: 16px;
  background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
  border: 1px solid rgba(148, 163, 184, 0.22);
  box-shadow: 0 24px 48px rgba(2, 6, 23, 0.45);
}

.auto-clip-success-dialog .el-dialog__header {
  padding: 20px 24px 8px;
}

.auto-clip-success-dialog .el-dialog__title {
  color: #f8fafc;
  font-size: 18px;
  font-weight: 600;
}

.auto-clip-success-dialog .el-dialog__body {
  padding: 0 24px 8px;
}

.auto-clip-success-dialog .el-dialog__footer {
  padding: 12px 24px 20px;
}
</style>
