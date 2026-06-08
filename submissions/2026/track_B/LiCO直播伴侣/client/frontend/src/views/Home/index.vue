<template>
  <div class="home-container">
    <div class="topbar">
      <obs-live-status-bar
        variant="compact"
        @streaming-active-change="onObsStreamingActiveChange"
      />
      <div class="topbar-spacer"></div>
      <div class="topbar-right">
        <el-button class="topbar-help" size="mini" plain @click="openTutorial">{{ $t('home.tutorial') }}</el-button>
        <el-dropdown trigger="click" @command="handleLanguageChange">
          <span class="lang-dropdown">
            <i class="el-icon-discover"></i> {{ currentLanguageName }} <i class="el-icon-arrow-down"></i>
          </span>
          <el-dropdown-menu slot="dropdown">
            <el-dropdown-item command="zh">简体中文</el-dropdown-item>
            <el-dropdown-item command="ja">日本語</el-dropdown-item>
            <el-dropdown-item command="en">English</el-dropdown-item>
          </el-dropdown-menu>
        </el-dropdown>
        <el-button
          class="topbar-exit"
          size="mini"
          plain
          :loading="exitAppLoading"
          @click="exitApp"
        >{{ $t('home.exitApp') }}</el-button>
      </div>
    </div>
    <div class="home-content" :class="{ 'home-content-live': isLiveMode }">
      <div v-if="!isLiveMode">
        <el-alert
          v-if="qwenStatusChecked && !qwenLlmConnected"
          class="home-qwen-alert"
          type="warning"
          :closable="false"
          show-icon
          :title="$t('home.qwenUnavailableTitle')"
        >
          <p>{{ $t('home.qwenUnavailableDesc') }}</p>
          <p v-if="qwenStatusError" class="home-qwen-alert-detail">{{ qwenStatusError }}</p>
          <p v-if="qwenConfigPath" class="home-qwen-alert-detail">{{ $t('home.qwenConfigPath') }}: {{ qwenConfigPath }}</p>
        </el-alert>
        <el-form :model="form" ref="form" label-width="150px" class="lico-form home-launch-form">
          <div class="home-hero">
            <div class="home-brand-wrap">
              <div class="home-brand-frame" aria-hidden="true">
                <span class="home-brand-ornament home-brand-ornament--tl">✦</span>
                <span class="home-brand-ornament home-brand-ornament--tr">♡</span>
                <span class="home-brand-ornament home-brand-ornament--bl">✦</span>
                <span class="home-brand-ornament home-brand-ornament--br">♡</span>
              </div>
              <h1 class="home-brand-title-wrap">
                <span class="home-brand-title">{{ brandTitle }}</span>
              </h1>
            </div>
            <el-form-item
              class="launch-room-field launch-room-combined"
              label-width="0"
              :prop="roomFormProp"
              :rules="roomFormRules"
              :key="roomFormProp"
            >
              <div class="launch-room-combined-row">
                <span class="launch-platform-label">{{ $t('home.livePlatformLabel') }}</span>
                <div class="launch-platform-select-wrap">
                  <launch-platform-icon
                    class="launch-platform-select-icon"
                    :platform="form.livePlatform"
                  />
                  <el-select
                    v-model="form.livePlatform"
                    class="launch-platform-select"
                    popper-class="launch-platform-select-dropdown"
                  >
                    <el-option
                      v-for="item in livePlatformOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    >
                      <span class="launch-platform-option">
                        <launch-platform-icon :platform="item.value" />
                        <span>{{ item.label }}</span>
                      </span>
                    </el-option>
                  </el-select>
                </div>
                <el-select
                  v-model="form.roomKeyType"
                  class="launch-room-type-select"
                  :disabled="!isBilibiliPlatform"
                >
                  <el-option :label="$t('home.authCode')" :value="2"></el-option>
                  <el-option :label="$t('home.roomId')" :value="1"></el-option>
                </el-select>
                <div
                  class="launch-room-input-wrap"
                  :class="{ 'is-platform-disabled': !isBilibiliPlatform }"
                >
                  <el-input
                    v-if="isBilibiliPlatform && form.roomKeyType === 1"
                    v-model.number="form.roomId"
                    class="launch-room-input"
                    type="number"
                    min="1"
                  ></el-input>
                  <el-tooltip
                    v-else-if="isBilibiliPlatform && form.roomKeyType === 2"
                    placement="top-start"
                  >
                    <div slot="content">
                      <el-link
                        type="primary"
                        :href="$router.resolve({ name: 'help' }).href"
                      >{{ $t('home.howToGetAuthCode') }}</el-link>
                    </div>
                    <el-input
                      v-model="form.authCode"
                      class="launch-room-input"
                    ></el-input>
                  </el-tooltip>
                  <el-input
                    v-else
                    :value="platformComingSoonText"
                    class="launch-room-input launch-room-input--locked"
                    readonly
                    disabled
                  ></el-input>
                </div>
              </div>
            </el-form-item>

          <div class="launch-button-group">
            <el-button
              class="launch-button"
              type="primary"
              :disabled="!roomUrl"
              @click="enterRoom"
            >
              <i class="el-icon-video-play"></i>
              <span>{{$t('home.enterRoom')}}</span>
            </el-button>
            <el-button
              class="launch-button launch-button--review"
              :disabled="!roomUrl || reviewListLoading"
              :loading="reviewListLoading"
              @click="toggleReviewPanel"
            >
              <i v-if="!reviewListLoading" class="el-icon-document"></i>
              <span>{{ reviewListLoading ? $t('home.reviewGeneratingCovers') : $t('home.enterReview') }}</span>
            </el-button>
          </div>
          <div v-show="reviewPanelVisible" class="home-review-panel">
            <div
              v-loading="reviewListLoading"
              :element-loading-text="$t('home.reviewGeneratingCovers')"
              element-loading-spinner="el-icon-loading"
              class="home-review-list-wrap"
            >
              <el-empty
                v-if="!reviewListLoading && liveReviewSessions.length === 0"
                :description="$t('home.reviewListEmpty')"
              ></el-empty>
              <div v-else class="home-review-list">
                <el-card
                  v-for="session in liveReviewSessions"
                  :key="session.streamStartFolder"
                  shadow="never"
                  class="home-review-card lico-card"
                >
                  <div class="home-review-card-body">
                    <div
                      class="home-review-cover-wrap"
                      v-loading="session.coverLoading"
                      :element-loading-text="$t('home.reviewCoverGenerating')"
                      element-loading-spinner="el-icon-loading"
                    >
                      <el-image
                        v-if="session.hasCover"
                        class="home-review-cover"
                        fit="cover"
                        lazy
                        :src="session.coverDisplayUrl || session.coverUrl"
                      >
                        <div slot="error" class="home-review-cover-placeholder">
                          <i class="el-icon-video-camera"></i>
                        </div>
                      </el-image>
                      <div v-else class="home-review-cover home-review-cover-placeholder">
                        <i class="el-icon-video-camera"></i>
                      </div>
                    </div>
                    <div class="home-review-meta">
                      <p><strong>{{ $t('home.reviewStartTime') }}:</strong> {{ session.startTime || '-' }}</p>
                      <p><strong>{{ $t('home.reviewEndTime') }}:</strong> {{ session.endTime || '-' }}</p>
                      <p><strong>{{ $t('home.reviewDuration') }}:</strong> {{ session.durationText || '-' }}</p>
                      <p><strong>{{ $t('home.reviewGiftValue') }}:</strong> {{ session.giftValueText || '-' }}</p>
                      <p><strong>{{ $t('home.reviewDanmakuCount') }}:</strong> {{ session.danmakuCount }}</p>
                      <el-button
                        size="mini"
                        type="primary"
                        plain
                        @click="openReviewDetail(session)"
                      >{{ $t('home.reviewViewDetail') }}</el-button>
                    </div>
                  </div>
                </el-card>
              </div>
            </div>
          </div>
          </div>
          <el-collapse v-model="settingPanels" class="home-settings-collapse">
          <el-collapse-item name="settings">
            <template slot="title">
              <i class="el-icon-setting"></i>
              <span>Setting</span>
            </template>
            <div class="home-card-wrap">
              <el-card class="lico-card">
              <el-row :gutter="20">
                <el-col :xs="24" :sm="8">
                  <el-form-item :label="$t('home.showDanmaku')">
                    <el-switch v-model="form.showDanmaku"></el-switch>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item :label="$t('home.showGift')">
                    <el-switch v-model="form.showGift"></el-switch>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item :label="$t('home.showGiftName')">
                    <el-switch v-model="form.showGiftName"></el-switch>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :xs="24" :sm="8">
                  <el-form-item :label="$t('home.mergeSimilarDanmaku')">
                    <el-switch v-model="form.mergeSimilarDanmaku"></el-switch>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item :label="$t('home.mergeGift')">
                    <el-switch v-model="form.mergeGift"></el-switch>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :xs="24" :sm="24">
                  <el-form-item :label="$t('home.obsSplitAudioTracks')">
                    <el-switch v-model="form.obsSplitAudioTracks"></el-switch>
                    <p class="home-setting-hint">{{ $t('home.obsSplitAudioTracksTip') }}</p>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :xs="24" :sm="8">
                  <el-form-item :label="$t('home.minGiftPrice')">
                    <el-input v-model.number="form.minGiftPrice" type="number" min="0">
                      <template slot="append">元</template>
                    </el-input>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item :label="$t('home.maxNumber')">
                    <el-input v-model.number="form.maxNumber" type="number" min="1"></el-input>
                  </el-form-item>
                </el-col>
              </el-row>

              <p v-if="obsRoomUrl.length > 1024">
                <el-alert :title="$t('home.urlTooLong')" type="warning" show-icon :closable="false"></el-alert>
              </p>
              <el-tooltip :content="$t('home.roomUrlUpdated')" v-model="showRoomUrlUpdatedTip" manual placement="top">
                <el-form-item :label="$t('home.roomUrl')">
                  <el-input ref="roomUrlInput" readonly :value="obsRoomUrl" style="width: calc(100% - 8em); margin-right: 1em;"></el-input>
                  <el-button type="primary" icon="el-icon-copy-document" @click="copyUrl"></el-button>
                </el-form-item>
              </el-tooltip>
              <el-form-item>
                <div class="lico-button-group">
                  <el-button size="medium" @click="copyTestRoomUrl">{{$t('home.copyTestRoomUrl')}}</el-button>
                  <el-button size="medium" icon="el-icon-download" @click="exportConfig">{{$t('home.exportConfig')}}</el-button>
                  <el-button size="medium" icon="el-icon-upload2" @click="importConfig">{{$t('home.importConfig')}}</el-button>
                </div>
              </el-form-item>
              </el-card>
            </div>
          </el-collapse-item>
          </el-collapse>
        </el-form>
      </div>
      <div
        v-else
        ref="liveModeContainer"
        class="live-mode-container"
        :class="{ 'live-mode-container-hidden': hideRoomStream, 'live-mode-container-resizing': isResizingLivePanels }"
      >
        <div v-if="!hideRoomStream" class="live-left" :style="liveLeftStyle">
          <div class="live-header">
            <el-button icon="el-icon-back" circle @click="isLiveMode = false"></el-button>
            <span class="live-title">{{ $t('home.room') }}: {{ roomKeyValue }}</span>
            <el-switch
              v-model="hideRoomStream"
              class="live-hide-switch"
              :active-text="$t('home.hideRoomDanmaku')"
            ></el-switch>
          </div>
          <iframe ref="roomIframe" :src="roomUrl" class="room-iframe" @load="syncPsychTabConfigToRoom"></iframe>
        </div>
        <div
          v-if="!hideRoomStream"
          class="live-resizer"
          :class="{ 'live-resizer-active': isResizingLivePanels }"
          title="点击开始/停止调整宽度"
          @click.prevent.stop="toggleResize"
          @touchstart.prevent.stop="toggleResize"
        >
          <div class="live-resizer-line"></div>
        </div>
        <div
          v-if="isResizingLivePanels"
          class="live-resize-capture"
          @mousemove.prevent="onResizeMove"
          @touchmove.prevent="onResizeMove"
          @click.prevent.stop="stopResize"
          @touchend.prevent.stop="stopResize"
          @touchcancel.prevent.stop="stopResize"
        ></div>
        <div v-if="hideRoomStream" class="live-right live-right-full">
          <div class="live-header live-header-compact">
            <el-button icon="el-icon-back" circle @click="isLiveMode = false"></el-button>
            <span class="live-title">{{ $t('home.room') }}: {{ roomKeyValue }}</span>
            <el-switch
              v-model="hideRoomStream"
              class="live-hide-switch"
              :active-text="$t('home.hideRoomDanmaku')"
            ></el-switch>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import _ from 'lodash'
import download from 'downloadjs'

import ObsLiveStatusBar from '@/components/ObsLiveStatusBar'
import LaunchPlatformIcon from '@/components/LaunchPlatformIcon'
import { mergeConfig } from '@/utils'
import { fetchObsBridgeState } from '@/utils/obsAgentConnection'
import {
  appendLiveArchiveRecord,
  fetchLiveArchiveCover,
  fetchLiveArchiveList,
  formatLiveInfoTimestamp,
  formatLiveStreamSummary,
  getLiveArchiveRoomId
} from '@/utils/liveArchive'
import * as mainApi from '@/api/main'
import * as chatConfig from '@/api/chatConfig'
import * as i18n from '@/i18n'

export default {
  name: 'Home',
  components: { ObsLiveStatusBar, LaunchPlatformIcon },
  data() {
    const savedLivePlatform = String(window.localStorage.livePlatform || 'bilibili').trim()
    const livePlatform = ['bilibili', 'douyin', 'xiaohongshu', 'twitch'].includes(savedLivePlatform)
      ? savedLivePlatform
      : 'bilibili'
    return {
      brandTitle: 'ℒ𝒾𝒞𝒪\n主播伴侣',
      isLiveMode: false,
      obsStreamEnterPending: false,
      exitAppLoading: false,
      hideRoomStream: false,
      liveLeftPercent: 58,
      isResizingLivePanels: false,
      backgroundUrl: require('@/assets/img/background.jpg'),
      serverConfig: {
        enableTranslate: true,
        enableUploadFile: true,
        loaderUrl: ''
      },
      form: {
        ...chatConfig.getLocalConfig(),
        livePlatform,
        roomKeyType: parseInt(window.localStorage.roomKeyType || '2'),
        roomId: parseInt(window.localStorage.roomId || '1'),
        authCode: window.localStorage.authCode || '',
      },
      settingPanels: [],
      reviewPanelVisible: false,
      reviewListLoading: false,
      liveReviewSessions: [],
      // 因为$refs.form.validate是异步的所以不能直接用计算属性
      // getUnvalidatedRoomUrl -> unvalidatedRoomUrl -> updateRoomUrl -> roomUrl
      roomUrl: '',
      roomAgentState: null,
      psychTabConfig: this.createDefaultPsychTabConfig(),
      qwenStatusChecked: false,
      qwenLlmConnected: true,
      qwenStatusError: '',
      qwenConfigPath: '',
      showRoomUrlUpdatedTip: false,
      roomIdBackup: null,
      authCodeBackup: null,
    }
  },
  computed: {
    currentLanguageName() {
      const langMap = {
        'zh': '简体中文',
        'ja': '日本語',
        'en': 'English'
      }
      return langMap[this.$i18n.locale] || 'Language'
    },
    roomKeyValue() {
      if (this.form.roomKeyType === 1) {
        return this.form.roomId
      } else {
        return this.form.authCode
      }
    },
    unvalidatedRoomUrl() {
      return this.getUnvalidatedRoomUrl(false)
    },
    obsRoomUrl() {
      if (this.roomUrl === '') {
        return ''
      }
      if (this.serverConfig.loaderUrl === '') {
        return this.roomUrl
      }
      let url = new URL(this.serverConfig.loaderUrl)
      url.searchParams.append('url', this.roomUrl)
      return url.href
    },
    liveLeftStyle() {
      if (this.hideRoomStream) {
        return {}
      }
      return {
        flex: `0 0 ${this.liveLeftPercent}%`,
        width: `${this.liveLeftPercent}%`
      }
    },
    livePlatformOptions() {
      return [
        { value: 'bilibili', label: this.$t('home.livePlatformBilibili') },
        { value: 'douyin', label: this.$t('home.livePlatformDouyin') },
        { value: 'xiaohongshu', label: this.$t('home.livePlatformXiaohongshu') },
        { value: 'twitch', label: this.$t('home.livePlatformTwitch') }
      ]
    },
    isBilibiliPlatform() {
      return this.form.livePlatform === 'bilibili'
    },
    platformComingSoonText() {
      return this.$t('home.platformComingSoon')
    },
    roomFormProp() {
      if (!this.isBilibiliPlatform) {
        return null
      }
      return this.form.roomKeyType === 1 ? 'roomId' : 'authCode'
    },
    roomFormRules() {
      if (!this.isBilibiliPlatform) {
        return []
      }
      return this.form.roomKeyType === 1 ? this.roomIdRules : this.authCodeRules
    },
    roomIdRules() {
      if (!this.isBilibiliPlatform) {
        return []
      }
      return [
        { required: true, message: this.$t('home.roomIdEmpty') },
        { type: 'integer', min: 1, message: this.$t('home.roomIdInteger') }
      ]
    },
    authCodeRules() {
      if (!this.isBilibiliPlatform) {
        return []
      }
      return [
        { required: true, message: this.$t('home.authCodeEmpty') },
        { pattern: /^[0-9A-Z]{12,14}$/, message: this.$t('home.authCodeFormatError') }
      ]
    }
  },
  watch: {
    'form.obsSplitAudioTracks'(value) {
      chatConfig.setLocalConfig(this.form)
      this.syncObsBridgeConfig(value)
    },
    'form.livePlatform'(value, oldValue) {
      window.localStorage.livePlatform = value
      if (value !== 'bilibili' && oldValue === 'bilibili') {
        this.roomIdBackup = this.form.roomId
        this.authCodeBackup = this.form.authCode
      }
      if (value === 'bilibili' && oldValue && oldValue !== 'bilibili') {
        if (this.roomIdBackup !== null && this.roomIdBackup !== '') {
          this.form.roomId = this.roomIdBackup
        }
        if (this.authCodeBackup !== null && this.authCodeBackup !== '') {
          this.form.authCode = this.authCodeBackup
        }
      }
      this.updateRoomUrl()
      this.$nextTick(() => {
        if (this.$refs.form) {
          this.$refs.form.clearValidate(['roomId', 'authCode'])
        }
      })
    },
    unvalidatedRoomUrl: 'updateRoomUrl',
    roomUrl: _.debounce(function(val, oldVal) {
      // 提示用户URL已更新
      // 如果语言不是默认的中文，则刷新页面时也会有一次提示，没办法
      if (val !== '' && oldVal !== '') {
        this.showRoomUrlUpdatedTip = true
        this.delayHideRoomUrlUpdatedTip()
      }

      // 保存配置
      window.localStorage.roomKeyType = this.form.roomKeyType
      window.localStorage.roomId = this.form.roomId
      window.localStorage.authCode = this.form.authCode
      chatConfig.setLocalConfig(this.form)
      
      // 更新服务端房间配置（供Unity使用）
      this.updateServerRoomConfig()

      if (val && this.obsStreamEnterPending) {
        this.tryAutoEnterLiveMode()
      }
    }, 500),
    '$route.query.review': function(value) {
      if (String(value || '') === '1') {
        this.openReviewPanelFromRoute()
      }
    }
  },
  mounted() {
    this.updateServerConfig()
    this.updateRoomUrl()
    // 初始化时也更新服务端房间配置
    this.updateServerRoomConfig()
    this.syncObsBridgeConfig(this.form.obsSplitAudioTracks)
    this.checkQwenLlmStatus()
    window.addEventListener('message', this.onRoomWindowMessage)
    this.openReviewPanelFromRoute()
  },
  beforeDestroy() {
    window.removeEventListener('message', this.onRoomWindowMessage)
    this.stopResize()
  },
  methods: {
    async checkQwenLlmStatus() {
      try {
        const res = await fetch('/api/qwen/status')
        const data = await res.json()
        this.qwenStatusChecked = true
        this.qwenConfigPath = data.configPath || ''
        this.qwenLlmConnected = Boolean(data.configured && data.connected)
        this.qwenStatusError = data.error || ''
      } catch (e) {
        this.qwenStatusChecked = true
        this.qwenLlmConnected = false
        this.qwenStatusError = e && e.message ? e.message : String(e)
      }
    },

    async handleLanguageChange(lang) {
      await i18n.setLocale(lang)
    },
    openTutorial() {
      this.$router.push({ name: 'help' })
    },
    async exitApp() {
      try {
        await this.$confirm(
          this.$t('home.exitAppConfirm'),
          this.$t('home.exitApp'),
          {
            type: 'warning',
            confirmButtonText: this.$t('home.exitApp'),
            cancelButtonText: this.$t('home.exitAppCancel')
          }
        )
      } catch {
        return
      }
      this.exitAppLoading = true
      try {
        await mainApi.shutdownApp()
        this.$message.success(this.$t('home.exitAppSuccess'))
        window.setTimeout(() => {
          window.close()
        }, 500)
      } catch (e) {
        this.$message.error(`${this.$t('home.exitAppFailed')}${e}`)
      } finally {
        this.exitAppLoading = false
      }
    },
    async syncObsBridgeConfig(splitAudioTracks) {
      const enabled = splitAudioTracks !== undefined
        ? Boolean(splitAudioTracks)
        : Boolean(this.form.obsSplitAudioTracks)
      try {
        await fetch('/api/obs/config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            splitAudioTracks: enabled
          })
        })
      } catch (e) {
        console.error('Failed to sync OBS bridge config:', e)
      }
    },

    async updateServerRoomConfig() {
      // 只在使用房间ID时更新服务端配置
      if (this.form.roomKeyType !== 1 || !this.form.roomId) {
        return
      }
      try {
        await fetch('/api/room_config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            roomId: this.form.roomId,
            autoTranslate: this.form.autoTranslate
          })
        })
      } catch (e) {
        console.error('Failed to update server room config:', e)
      }
    },
    async updateServerConfig() {
      try {
        this.serverConfig = (await mainApi.getServerInfo()).config
      } catch (e) {
        this.$message.error(`Failed to fetch server information: ${e}`)
        throw e
      }
    },
    async updateRoomUrl() {
      // 防止切换roomKeyType时校验的还是老规则
      await this.$nextTick()
      try {
        await this.$refs.form.validate()
      } catch {
        this.roomUrl = ''
        return
      }
      // 没有异步的校验规则，应该不需要考虑竞争条件
      this.roomUrl = this.unvalidatedRoomUrl
    },
    delayHideRoomUrlUpdatedTip: _.debounce(function() {
      this.showRoomUrlUpdatedTip = false
    }, 3000),

    addEmoticon() {
      this.form.emoticons.push({
        keyword: '[Kappa]',
        url: ''
      })
    },
    delEmoticon(index) {
      this.form.emoticons.splice(index, 1)
    },
    uploadEmoticon(emoticon) {
      let input = document.createElement('input')
      input.type = 'file'
      input.accept = 'image/png, image/jpeg, image/jpg, image/gif'
      input.onchange = async() => {
        let file = input.files[0]
        if (file.size > 1024 * 1024) {
          this.$message.error(this.$t('home.emoticonFileTooLarge'))
          return
        }

        let res
        try {
          res = await mainApi.uploadEmoticon(file)
        } catch (e) {
          this.$message.error(`Failed to upload: ${e}`)
          throw e
        }
        emoticon.url = res.url
      }
      input.click()
    },

    enterRoom() {
      this.hideRoomStream = false
      this.roomAgentState = null
      this.isLiveMode = true
    },
    onObsStreamingActiveChange(streamingActive) {
      this.obsStreamEnterPending = streamingActive
      if (!streamingActive) {
        return
      }
      this.tryAutoEnterLiveMode()
    },
    tryAutoEnterLiveMode() {
      if (this.isLiveMode || !this.roomUrl) {
        return
      }
      this.enterRoom()
      this.recordLiveStreamStartInfo()
    },
    async recordLiveStreamStartInfo() {
      try {
        let obsState = await fetchObsBridgeState()
        if (!obsState || !obsState.streamingActive) {
          return
        }
        let streamStartedAt = Number(obsState.streamStartedAt || obsState.lastStreamStartedAt || 0)
        if (streamStartedAt <= 0) {
          return
        }
        let roomId = getLiveArchiveRoomId(this.roomKeyValue)
        let timeText = formatLiveInfoTimestamp(streamStartedAt)
        await appendLiveArchiveRecord(roomId, streamStartedAt, 'live_info', `【开始直播】${timeText}`)
      } catch (e) {
        console.warn('Record live stream start info failed:', e)
      }
    },
    toggleReviewPanel() {
      if (this.reviewPanelVisible) {
        this.reviewPanelVisible = false
        return
      }
      if (this.reviewListLoading) {
        return
      }
      this.reviewPanelVisible = true
      this.loadLiveReviewList()
    },
    openReviewPanelFromRoute() {
      if (String(this.$route.query.review || '') !== '1') {
        return
      }
      if (this.isLiveMode) {
        this.isLiveMode = false
      }
      this.reviewPanelVisible = true
      if (!this.reviewListLoading && this.liveReviewSessions.length === 0) {
        this.loadLiveReviewList()
      }
      if (Object.keys(this.$route.query).length > 0) {
        this.$router.replace({ name: 'home' }).catch(() => {})
      }
    },
    async loadLiveReviewList() {
      this.reviewListLoading = true
      try {
        let roomId = getLiveArchiveRoomId(this.roomKeyValue)
        let sessions = await fetchLiveArchiveList(roomId, 10, true)
        this.liveReviewSessions = sessions.map(session => ({
          ...session,
          coverLoading: !session.hasCover && Boolean(session.canGenerateCover),
          coverDisplayUrl: session.hasCover
            ? `${session.coverUrl}?v=${Date.now()}`
            : ''
        }))
        await this.generateMissingCovers()
      } catch (e) {
        this.liveReviewSessions = []
        this.$message.error(e.message || this.$t('home.reviewListLoadFailed'))
      } finally {
        this.reviewListLoading = false
      }
    },
    async generateMissingCovers() {
      for (let index = 0; index < this.liveReviewSessions.length; index++) {
        let session = this.liveReviewSessions[index]
        if (session.hasCover || !session.canGenerateCover) {
          continue
        }
        this.$set(this.liveReviewSessions[index], 'coverLoading', true)
        try {
          let ok = await fetchLiveArchiveCover(session.coverUrl)
          if (ok) {
            this.$set(this.liveReviewSessions[index], 'hasCover', true)
            this.$set(
              this.liveReviewSessions[index],
              'coverDisplayUrl',
              `${session.coverUrl}?v=${Date.now()}`
            )
          }
        } catch (e) {
          console.warn('Generate live archive cover failed:', e)
        } finally {
          this.$set(this.liveReviewSessions[index], 'coverLoading', false)
        }
      }
    },
    openReviewDetail(session) {
      if (!session || !session.streamStartFolder) {
        return
      }
      let roomId = String(session.roomId || getLiveArchiveRoomId(this.roomKeyValue))
      this.$router.push({
        name: 'live_review_detail',
        params: {
          roomId,
          streamStartFolder: session.streamStartFolder
        }
      })
    },
    onRoomWindowMessage(event) {
      if (event.origin !== window.location.origin) {
        return
      }
      if (!event.data) {
        return
      }
      let roomIframe = this.$refs.roomIframe
      if (event.data.type === 'roomStreamingStopped') {
        if (roomIframe && event.source !== roomIframe.contentWindow) {
          return
        }
        this.handleRoomStreamingStopped(event.data.data || {})
        return
      }
      if (event.data.type !== 'roomPsychAgentUpdate') {
        return
      }
      if (roomIframe && event.source !== roomIframe.contentWindow) {
        return
      }
      this.roomAgentState = event.data.data || null
    },
    handleRoomStreamingStopped(data) {
      if (!this.isLiveMode) {
        return
      }
      this.isLiveMode = false
      this.obsStreamEnterPending = false
      this.roomAgentState = null
      let summaryText = formatLiveStreamSummary(data)
      this.$alert(
        summaryText,
        '直播结束',
        { confirmButtonText: '好的' }
      )
    },
    onPsychTabConfigChange(config) {
      this.psychTabConfig = config
      this.syncPsychTabConfigToRoom()
    },
    createDefaultPsychTabConfig() {
      return {
        voice: { enabled: true, windowSeconds: 30 },
        psych: { enabled: true, windowSeconds: 30 },
        gift: { enabled: true, windowSeconds: 30 },
        scene: { enabled: true, windowSeconds: 30 }
      }
    },
    syncPsychTabConfigToRoom() {
      if (!this.psychTabConfig) {
        return
      }
      let roomIframe = this.$refs.roomIframe
      if (!roomIframe || !roomIframe.contentWindow) {
        return
      }
      roomIframe.contentWindow.postMessage({
        type: 'roomSetPsychTabConfig',
        data: this.psychTabConfig
      }, window.location.origin)
    },
    toggleResize(event) {
      if (this.isResizingLivePanels) {
        this.stopResize()
      } else {
        this.startResize(event)
      }
    },
    startResize(event) {
      if (this.hideRoomStream) {
        return
      }
      this.isResizingLivePanels = true
      window.addEventListener('mousemove', this.onResizeMove)
      window.addEventListener('touchmove', this.onResizeMove, { passive: false })
      this.onResizeMove(event)
    },
    onResizeMove(event) {
      if (!this.isResizingLivePanels || this.hideRoomStream) {
        return
      }
      if (event.cancelable) {
        event.preventDefault()
      }
      const container = this.$refs.liveModeContainer
      if (!container) {
        return
      }
      const rect = container.getBoundingClientRect()
      const clientX = event.touches && event.touches.length > 0 ? event.touches[0].clientX : event.clientX
      if (typeof clientX !== 'number') {
        return
      }
      const relativeX = clientX - rect.left
      const minPercent = 28
      const maxPercent = 72
      const nextPercent = (relativeX / rect.width) * 100
      this.liveLeftPercent = Math.min(maxPercent, Math.max(minPercent, nextPercent))
    },
    stopResize() {
      if (!this.isResizingLivePanels) {
        return
      }
      this.isResizingLivePanels = false
      window.removeEventListener('mousemove', this.onResizeMove)
      window.removeEventListener('touchmove', this.onResizeMove)
    },
    copyTestRoomUrl() {
      window.navigator.clipboard.writeText(this.getUnvalidatedRoomUrl(true))
    },
    getUnvalidatedRoomUrl(isTestRoom) {
      if (!this.isBilibiliPlatform) {
        return ''
      }
      // 重要的字段放在前面，因为如果被截断就连接不了房间了
      let frontFields = {
        roomKeyType: this.form.roomKeyType,
        templateUrl: this.form.templateUrl,
      }
      let backFields = {
        lang: this.$i18n.locale,
        emoticons: JSON.stringify(this.form.emoticons)
      }
      let ignoredNames = new Set(['roomId', 'authCode'])
      let query = { ...frontFields }
      for (let name in this.form) {
        if (!(name in frontFields || name in backFields || ignoredNames.has(name))) {
          query[name] = this.form[name]
        }
      }
      Object.assign(query, backFields)

      // 去掉和默认值相同的字段，缩短URL长度
      query = Object.fromEntries(Object.entries(query).filter(
        ([name, value]) => {
          let defaultValue = chatConfig.DEFAULT_CONFIG[name]
          if (defaultValue === undefined) {
            return true
          }
          if (typeof defaultValue === 'object') {
            defaultValue = JSON.stringify(defaultValue)
          }
          return value !== defaultValue
        }
      ))

      let resolved
      if (isTestRoom) {
        resolved = this.$router.resolve({ name: 'test_room', query })
      } else {
        resolved = this.$router.resolve({ name: 'room', params: { roomKeyValue: this.roomKeyValue }, query })
      }
      return `${window.location.protocol}//${window.location.host}${resolved.href}`
    },
    copyUrl() {
      this.$refs.roomUrlInput.select()
      document.execCommand('Copy')
    },

    exportConfig() {
      let cfg = mergeConfig(this.form, chatConfig.DEFAULT_CONFIG)
      download(JSON.stringify(cfg, null, 2), 'blivechat.json', 'application/json')
    },
    importConfig() {
      let input = document.createElement('input')
      input.type = 'file'
      input.accept = 'application/json'
      input.onchange = () => {
        let reader = new window.FileReader()
        reader.onload = () => {
          let cfg
          try {
            cfg = JSON.parse(reader.result)
          } catch (e) {
            this.$message.error(this.$t('home.failedToParseConfig') + e)
            return
          }
          this.importConfigFromObj(cfg)
        }
        reader.readAsText(input.files[0])
      }
      input.click()
    },
    importConfigFromObj(cfg) {
      cfg = mergeConfig(cfg, chatConfig.deepCloneDefaultConfig())
      chatConfig.sanitizeConfig(cfg)
      this.form = {
        ...cfg,
        roomKeyType: this.form.roomKeyType,
        roomId: this.form.roomId,
        authCode: this.form.authCode
      }
    }
  }
}
</script>

<style scoped>
.home-container {
  position: relative;
  min-height: 100vh;
  background-image: v-bind('`url(${backgroundUrl})`');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
}

.home-container::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 50% 52%, rgba(156, 74, 255, 0.18), rgba(7, 8, 28, 0) 28%),
    linear-gradient(180deg, rgba(4, 5, 18, 0.38), rgba(4, 5, 18, 0.12) 42%, rgba(4, 5, 18, 0.62));
  z-index: 0;
}

.topbar,
.home-content {
  position: relative;
  z-index: 1;
}

.topbar {
  height: 64px;
  background: rgba(6, 8, 28, 0.34);
  backdrop-filter: blur(16px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
  box-shadow: 0 1px 0 rgba(189, 129, 255, 0.16);
  position: sticky;
  top: 0;
  z-index: 100;
}

.topbar-spacer {
  flex: 1;
  min-width: 0;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.topbar-help {
  border-radius: 999px;
  border-color: rgba(121, 100, 230, 0.35);
  color: #7964e6;
  font-weight: 600;
  background: rgba(17, 18, 52, 0.72);
}

.topbar-help:hover {
  border-color: #7964e6;
  color: #5d45d3;
  background: rgba(121, 100, 230, 0.08);
}

.topbar-exit {
  border-radius: 999px;
  border-color: rgba(245, 108, 108, 0.45);
  color: #ffb4b4;
  font-weight: 600;
  background: rgba(17, 18, 52, 0.72);
}

.topbar-exit:hover,
.topbar-exit:focus {
  border-color: #f56c6c;
  color: #fff;
  background: rgba(245, 108, 108, 0.18);
}

.lang-dropdown {
  cursor: pointer;
  color: #efe9ff;
  font-weight: 600;
  font-size: 0.95rem;
  padding: 8px 16px;
  border-radius: 12px;
  transition: all 0.2s;
}

.lang-dropdown:hover {
  background: rgba(121, 100, 230, 0.18);
}

.home-content {
  padding: 24px clamp(16px, 3vw, 40px) 40px;
  max-width: min(1440px, 96vw);
  margin: 0 auto;
  width: 100%;
  flex: 1;
  box-sizing: border-box;
}

.home-content-live {
  max-width: none;
  margin: 0;
  padding: 16px 20px 20px;
}

.home-qwen-alert {
  max-width: 920px;
  margin: 0 auto 16px;
}

.home-qwen-alert-detail {
  margin: 6px 0 0;
  font-size: 12px;
  word-break: break-all;
}

.home-hero {
  position: relative;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(36px, 5.5vh, 56px);
  min-height: clamp(360px, 52vh, 580px);
  margin-bottom: 0;
  padding: clamp(28px, 4vh, 48px) clamp(16px, 3vw, 32px);
  width: 100%;
  box-sizing: border-box;
}

.home-brand-wrap {
  position: relative;
  width: min(640px, 92vw);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: clamp(12px, 2vw, 24px) clamp(20px, 4vw, 40px);
  pointer-events: none;
  user-select: none;
}

.home-brand-frame {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.home-brand-ornament {
  position: absolute;
  color: #fff8fc;
  font-size: clamp(18px, 3vw, 28px);
}

.home-brand-ornament--tl {
  top: 0;
  left: 0;
}

.home-brand-ornament--tr {
  top: 0;
  right: 0;
}

.home-brand-ornament--bl {
  bottom: 0;
  left: 0;
}

.home-brand-ornament--br {
  bottom: 0;
  right: 0;
}

.home-brand-title-wrap {
  position: relative;
  z-index: 1;
  display: inline-block;
  margin: 0;
}

.home-brand-title {
  display: block;
  font-family: 'STKaiti', 'KaiTi', 'Songti SC', 'Noto Serif SC', 'Microsoft YaHei', serif;
  font-weight: 700;
  font-size: clamp(42px, 8vw, 88px);
  line-height: 1.08;
  letter-spacing: 2px;
  white-space: pre-line;
  text-align: center;
  color: #ffffff;
  filter: none;
  text-shadow: none;
  -webkit-text-stroke: 0;
  animation: none;
}

.launch-room-combined {
  margin-bottom: 0 !important;
}

.launch-room-combined-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.launch-platform-label {
  flex-shrink: 0;
  color: rgba(246, 241, 255, 0.88);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.launch-platform-select-wrap {
  position: relative;
  flex: 0 0 clamp(118px, 20vw, 148px);
  min-width: 0;
}

.launch-platform-select-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  z-index: 2;
  transform: translateY(-50%);
  pointer-events: none;
}

.launch-platform-select,
.launch-room-type-select {
  width: 100%;
}

.launch-platform-select :deep(.el-input__inner),
.launch-room-type-select :deep(.el-input__inner) {
  height: 48px;
  color: #f6f1ff;
  border-color: rgba(224, 202, 255, 0.36);
  background: transparent;
  box-shadow: inset 0 0 0 1px rgba(153, 102, 255, 0.1), 0 14px 44px rgba(15, 9, 50, 0.26);
  backdrop-filter: blur(10px);
}

.launch-platform-select :deep(.el-input__inner) {
  padding-left: 40px;
}

.launch-room-type-select {
  flex: 0 0 clamp(108px, 18vw, 132px);
}

.launch-room-input-wrap {
  flex: 1 1 auto;
  min-width: 0;
}

.launch-room-input {
  width: 100%;
}

.launch-room-input-wrap.is-platform-disabled :deep(.el-input__inner),
.launch-room-input--locked :deep(.el-input__inner) {
  height: 48px;
  color: rgba(246, 241, 255, 0.52) !important;
  -webkit-text-fill-color: rgba(246, 241, 255, 0.52);
  text-align: center;
  letter-spacing: 0.5px;
  cursor: not-allowed;
  border-color: rgba(148, 163, 184, 0.28) !important;
  background: rgba(15, 23, 42, 0.55) !important;
  box-shadow: inset 0 0 0 1px rgba(100, 116, 139, 0.22) !important;
  opacity: 1;
}

.launch-platform-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.launch-room-field {
  position: relative;
  width: min(760px, 94vw);
  margin: 0 auto;
  margin-bottom: 0 !important;
}

.launch-room-field :deep(.el-form-item__content) {
  margin-left: 0 !important;
}

.launch-room-field :deep(.launch-room-input .el-input__inner) {
  height: 48px;
  color: #f6f1ff;
  border-color: rgba(224, 202, 255, 0.36);
  background: transparent;
  box-shadow: inset 0 0 0 1px rgba(153, 102, 255, 0.1), 0 14px 44px rgba(15, 9, 50, 0.26);
  backdrop-filter: blur(10px);
}

.launch-room-field :deep(.el-input__inner::placeholder) {
  color: rgba(246, 241, 255, 0.62);
}

.launch-room-field :deep(.el-select .el-input__inner) {
  border-right-color: rgba(224, 202, 255, 0.22);
}

.launch-button-group {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: clamp(16px, 3vw, 28px);
  flex-wrap: wrap;
  width: min(720px, 92vw);
  margin-top: clamp(4px, 1vh, 12px);
}

.launch-button {
  position: relative;
  left: auto;
  top: auto;
  transform: none;
  min-width: clamp(190px, 24vw, 300px);
  height: clamp(58px, 7vw, 82px);
  border-radius: 999px !important;
  border: 1px solid rgba(255, 255, 255, 0.48) !important;
  font-size: clamp(1.1rem, 2vw, 1.45rem);
  font-weight: 900;
  letter-spacing: 0;
}

.launch-button:not(.launch-button--review) {
  background:
    radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0) 34%),
    linear-gradient(135deg, #ff72df, #8b45ff 46%, #4f7dff) !important;
  box-shadow:
    0 0 0 9px rgba(155, 82, 255, 0.16),
    0 0 42px rgba(202, 96, 255, 0.78),
    0 22px 60px rgba(7, 7, 28, 0.52);
  color: #ffffff !important;
}

.launch-button i {
  margin-right: 10px;
  font-size: 1.25em;
}

.launch-button:not(.launch-button--review):hover,
.launch-button:not(.launch-button--review):focus {
  transform: scale(1.035);
  box-shadow:
    0 0 0 11px rgba(155, 82, 255, 0.2),
    0 0 58px rgba(223, 121, 255, 0.92),
    0 24px 68px rgba(7, 7, 28, 0.58);
}

.launch-button--review,
.launch-button--review:hover,
.launch-button--review:focus,
.launch-button--review:active {
  background-color: #ffcc00 !important;
  background-image:
    radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0) 38%),
    linear-gradient(135deg, #fff176, #ffcc00 45%, #f5a623) !important;
  border-color: rgba(255, 255, 255, 0.58) !important;
  color: #5a4300 !important;
  box-shadow:
    0 0 0 9px rgba(255, 196, 0, 0.22),
    0 0 42px rgba(255, 204, 0, 0.72),
    0 22px 60px rgba(7, 7, 28, 0.52);
}

.launch-button--review:hover,
.launch-button--review:focus {
  transform: scale(1.035);
  background-color: #ffd633 !important;
  background-image:
    radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0) 38%),
    linear-gradient(135deg, #fff59d, #ffd633 45%, #ffb300) !important;
  box-shadow:
    0 0 0 11px rgba(255, 196, 0, 0.28),
    0 0 58px rgba(255, 214, 51, 0.88),
    0 24px 68px rgba(7, 7, 28, 0.58);
}

.home-card-wrap {
  margin: 0;
}

.home-settings-collapse {
  max-width: min(980px, 92vw);
  margin: clamp(24px, 4vh, 40px) auto 0;
  border: none;
}

.home-review-panel {
  width: min(980px, 92vw);
  margin: clamp(20px, 3vh, 28px) auto 0;
}

.home-review-list-wrap {
  min-height: 120px;
}

.home-review-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.home-review-card :deep(.el-card__body) {
  padding: 18px 20px;
}

.home-review-card-body {
  display: flex;
  flex-direction: row;
  gap: 18px;
  align-items: flex-start;
}

.home-review-cover-wrap {
  flex: none;
  position: relative;
  min-width: 190px;
  min-height: 105px;
}

.home-review-cover,
.home-review-cover-placeholder {
  width: 190px;
  height: 105px;
  border-radius: 12px;
  overflow: hidden;
}

.home-review-cover-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(239, 233, 255, 0.72);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(201, 165, 255, 0.18);
  font-size: 28px;
}

.home-review-meta {
  flex: 1;
  min-width: 0;
  color: #efe9ff;
}

.home-review-meta p {
  margin: 0 0 8px;
  line-height: 1.5;
  word-break: break-word;
}

@media only screen and (max-width: 768px) {
  .home-review-card-body {
    flex-direction: column;
  }

  .home-review-cover,
  .home-review-cover-placeholder {
    width: 100%;
    max-width: 100%;
    height: auto;
    aspect-ratio: 16 / 9;
  }
}

.home-settings-collapse :deep(.el-collapse-item__header) {
  width: 156px;
  height: 42px;
  margin: 0 auto;
  justify-content: center;
  gap: 8px;
  color: #efe9ff;
  font-weight: 800;
  border: 1px solid rgba(218, 188, 255, 0.26);
  border-radius: 999px;
  background: rgba(14, 16, 45, 0.58);
  backdrop-filter: blur(14px);
  box-shadow: 0 12px 36px rgba(26, 13, 72, 0.28);
}

.home-settings-collapse :deep(.el-collapse-item__arrow) {
  margin: 0 0 0 6px;
}

.home-settings-collapse :deep(.el-collapse-item__wrap) {
  margin-top: 16px;
  border-bottom: none;
  background: transparent;
}

.home-setting-hint {
  margin: 8px 0 0;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
  line-height: 1.5;
}

.home-settings-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

.lico-card {
  background: rgba(10, 12, 36, 0.7) !important;
  backdrop-filter: blur(24px);
  border: 1px solid rgba(201, 165, 255, 0.18) !important;
  box-shadow: 0 18px 70px rgba(3, 5, 20, 0.36) !important;
}

.lico-form :deep(.el-form-item__label) {
  color: #efe9ff;
  font-weight: 700;
}

.lico-form :deep(.el-card__body),
.lico-form {
  color: #efe9ff;
}

.lico-form :deep(.el-tabs--border-card) {
  border-radius: 16px;
  overflow: hidden;
  border: none;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  background: rgba(255, 255, 255, 0.7) !important;
}

.lico-form :deep(.el-tabs__item.is-active) {
  color: #7964e6 !important;
  background-color: #fff !important;
}

.lico-form :deep(.el-tabs__header) {
  background-color: rgba(243, 240, 255, 0.8) !important;
  border-bottom: none !important;
}

.lico-button-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 20px;
}

:deep(.el-button--primary) {
  background-color: #7964e6 !important;
  border-color: #7964e6 !important;
  border-radius: 10px;
  font-weight: 600;
  padding: 12px 24px;
}

.launch-button.el-button--primary:not(.launch-button--review) {
  background:
    radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0) 34%),
    linear-gradient(135deg, #ff72df, #8b45ff 46%, #4f7dff) !important;
  border-color: rgba(255, 255, 255, 0.48) !important;
}

.home-container :deep(.launch-button--review.el-button) {
  background-color: #ffcc00 !important;
  border-color: rgba(255, 255, 255, 0.58) !important;
}

:deep(.el-button) {
  border-radius: 10px;
}

:deep(.el-input__inner), :deep(.el-textarea__inner) {
  border-radius: 10px;
  border: 1px solid rgba(210, 184, 255, 0.36);
  background: rgba(255, 255, 255, 0.9);
}

:deep(.el-input__inner:focus) {
  border-color: #bfaaff;
}

:deep(.el-switch.is-checked .el-switch__core) {
  background-color: #7964e6 !important;
  border-color: #7964e6 !important;
}

:deep(.el-card) {
  border-radius: 16px;
  border: none;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

/* 直播模式样式 */
.live-mode-container {
  position: relative;
  display: flex;
  width: 100%;
  height: calc(100vh - 96px);
  gap: 20px;
  padding: 10px;
  align-items: stretch;
}

.live-mode-container-hidden {
  gap: 0;
}

.live-left {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.live-header {
  padding: 10px 20px;
  display: flex;
  align-items: center;
  gap: 15px;
  background: rgba(255, 255, 255, 0.5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.live-title {
  font-weight: bold;
  color: #6a11cb;
  margin-right: auto;
}

.live-hide-switch {
  margin-left: auto;
}

.room-iframe {
  flex: 1;
  border: none;
  width: 100%;
}

.live-resizer {
  flex: 0 0 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: col-resize;
  user-select: none;
  position: relative;
  z-index: 3;
}

.live-resizer-line {
  width: 4px;
  height: 72px;
  border-radius: 999px;
  background: rgba(121, 100, 230, 0.35);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.55);
  transition: background 0.15s ease, box-shadow 0.15s ease, height 0.15s ease;
}

.live-resizer:hover .live-resizer-line,
.live-resizer-active .live-resizer-line {
  height: 92px;
  background: rgba(121, 100, 230, 0.72);
  box-shadow: 0 0 0 4px rgba(121, 100, 230, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.75);
}

.live-mode-container-resizing {
  cursor: col-resize;
  user-select: none;
}

.live-resize-capture {
  position: absolute;
  inset: 0;
  z-index: 2;
  cursor: col-resize;
  background: transparent;
}

.live-right {
  flex: 1 1 auto;
  min-width: 320px;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  overflow: visible;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.live-right-full {
  width: 100%;
  flex: 1 1 auto;
  min-width: 0;
}

.live-header-compact {
  border-radius: 20px 20px 0 0;
}

.live-right :deep(.el-card) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
</style>
