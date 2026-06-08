<template>
  <div class="obs-live-status-bar" :class="[`obs-live-status-bar--${variant}`]">
    <span
      class="obs-live-status-dot"
      :class="{ 'is-live': obsStreamingActive }"
      aria-hidden="true"
    ></span>
    <span class="obs-live-status-label">{{ $t('layout.obsLiveStatus') }}:</span>
    <span class="obs-live-status-text">
      {{ obsStreamingActive ? $t('layout.obsStreaming') : $t('layout.obsNotStreaming') }}
    </span>
  </div>
</template>

<script>
import { ObsAgentConnection } from '@/utils/obsAgentConnection'

export default {
  name: 'ObsLiveStatusBar',
  props: {
    variant: {
      type: String,
      default: 'bar'
    }
  },
  data() {
    return {
      obsAgentConnection: null,
      obsAgentState: {
        connected: false,
        streamingActive: false
      }
    }
  },
  computed: {
    obsStreamingActive() {
      return Boolean(this.obsAgentState.streamingActive)
    }
  },
  mounted() {
    this.obsAgentConnection = new ObsAgentConnection(state => {
      const prevStreamingActive = Boolean(this.obsAgentState.streamingActive)
      this.obsAgentState = state
      const nextStreamingActive = Boolean(state.streamingActive)
      if (prevStreamingActive !== nextStreamingActive) {
        this.$emit('streaming-active-change', nextStreamingActive)
      }
    })
    this.obsAgentConnection.start()
    this.obsAgentConnection.refreshFromHttp()
  },
  beforeDestroy() {
    if (this.obsAgentConnection !== null) {
      this.obsAgentConnection.stop()
      this.obsAgentConnection = null
    }
  }
}
</script>

<style scoped>
.obs-live-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  flex-shrink: 0;
}

.obs-live-status-bar--bar {
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid rgba(121, 100, 230, 0.15);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  color: #606266;
}

.obs-live-status-bar--compact {
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(17, 18, 52, 0.72);
  border: 1px solid rgba(121, 100, 230, 0.28);
  color: #efe9ff;
}

.obs-live-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f56c6c;
  box-shadow: 0 0 0 2px rgba(245, 108, 108, 0.18);
  flex-shrink: 0;
}

.obs-live-status-dot.is-live {
  background: #67c23a;
  box-shadow: 0 0 0 2px rgba(103, 194, 58, 0.18);
}

.obs-live-status-bar--compact .obs-live-status-label {
  color: rgba(239, 233, 255, 0.72);
}

.obs-live-status-bar--compact .obs-live-status-text {
  color: #ffffff;
}

.obs-live-status-label {
  color: #909399;
}

.obs-live-status-text {
  font-weight: 600;
  color: #303133;
}
</style>
