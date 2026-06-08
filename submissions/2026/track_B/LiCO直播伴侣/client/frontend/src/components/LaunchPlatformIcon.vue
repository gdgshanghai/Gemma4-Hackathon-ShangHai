<template>
  <span
    class="launch-platform-icon"
    :class="`launch-platform-icon--${platform}`"
    :aria-label="ariaLabel"
    role="img"
  >
    <svg v-if="platform === 'bilibili'" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="3" fill="currentColor" opacity="0.95"/>
      <text x="12" y="15" text-anchor="middle" fill="#fff" font-size="7" font-weight="700">B</text>
    </svg>
    <svg v-else-if="platform === 'douyin'" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M16 7.5c1.2 0 2.2-.3 3-1v3.4c-.8.1-1.6.4-2.3.8V15c0 2.8-2.2 5-5 5s-5-2.2-5-5 2.2-5 5-5c.4 0 .8 0 1.2.1v3.3c-.4-.1-.8-.2-1.2-.2-1 0-1.8.8-1.8 1.8s.8 1.8 1.8 1.8 1.8-.8 1.8-1.8V3h3v4.5z"
      />
    </svg>
    <svg v-else-if="platform === 'xiaohongshu'" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="4" width="16" height="16" rx="4" fill="currentColor"/>
      <text x="12" y="15.5" text-anchor="middle" fill="#fff" font-size="8" font-weight="700">红</text>
    </svg>
    <svg v-else-if="platform === 'twitch'" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M4 4h16v11.5l-4 4h-3l-2-2H9v2H4V4zm3 3v5h2l2-2h2V7H7zm8 0v5h3l2-2V7h-5z"
      />
    </svg>
  </span>
</template>

<script>
const PLATFORM_LABELS = {
  bilibili: 'Bilibili',
  douyin: '抖音',
  xiaohongshu: '小红书',
  twitch: 'Twitch'
}

export default {
  name: 'LaunchPlatformIcon',
  props: {
    platform: {
      type: String,
      default: 'bilibili'
    }
  },
  computed: {
    ariaLabel() {
      return PLATFORM_LABELS[this.platform] || this.platform
    }
  }
}
</script>

<style scoped>
.launch-platform-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.launch-platform-icon svg {
  width: 100%;
  height: 100%;
}

.launch-platform-icon--bilibili {
  color: #00a1d6;
}

.launch-platform-icon--douyin {
  color: #fe2c55;
}

.launch-platform-icon--xiaohongshu {
  color: #ff2442;
}

.launch-platform-icon--twitch {
  color: #9146ff;
}
</style>
