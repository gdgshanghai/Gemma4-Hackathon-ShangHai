<template>
  <div v-if="!useCustomTemplate" class="room-layout">
    <div class="room-main">
      <chat-renderer ref="renderer" :maxNumber="config.maxNumber" :showGiftName="config.showGiftName"></chat-renderer>
    </div>
    <aside class="room-side-panel">
      <section
        v-for="panel in roomSidePanels"
        :key="panel.key"
        class="side-section"
        :class="{ 'side-section--disabled': !panel.enabled }"
      >
        <header class="side-section__header">
          <span class="side-section__title">{{ panel.title }}</span>
          <span class="side-section__status">{{ panel.enabled ? panel.status : '未启动' }}</span>
        </header>
        <div v-if="panel.enabled" class="side-section__body">
          <div v-for="item in panel.items" :key="item.label" class="side-row">
            <span class="side-row__label">{{ item.label }}</span>
            <span class="side-row__value">{{ item.value }}</span>
          </div>
          <p v-if="panel.summary" class="side-summary">{{ panel.summary }}</p>
        </div>
      </section>
    </aside>
  </div>
  <div v-else class="template-container">
    <iframe ref="templateIframe" :src="config.templateUrl" class="template-iframe" frameborder="0"></iframe>
  </div>
</template>

<script>
import * as i18n from '@/i18n'
import { mergeConfig, toBool, toInt, toFloat } from '@/utils'
import * as trie from '@/utils/trie'
import * as pronunciation from '@/utils/pronunciation'
import * as chatConfig from '@/api/chatConfig'
import * as chat from '@/api/chat'
import * as chatModels from '@/api/chat/models'
import { ensureBaseUrlInited, getBaseUrl } from '@/api/base'
import ChatRenderer from '@/components/ChatRenderer'
import * as constants from '@/components/ChatRenderer/constants'
import {
  appendLiveArchiveRecord as appendLiveArchiveRecordApi,
  formatLiveInfoTimestamp,
  formatLiveStreamSummary
} from '@/utils/liveArchive'
/** @import * as blcsdk from '@/blcsdk' */

class DefaultRenderer {
  constructor(rendererVm) {
    this.addMessage = rendererVm.addMessage
    this.delMessages = rendererVm.delMessages
    this.updateMessage = rendererVm.updateMessage
    this.mergeSimilarText = rendererVm.mergeSimilarText
    this.mergeSimilarGift = rendererVm.mergeSimilarGift
  }

  destroy() {
    let dummyFunc = () => {}
    this.addMessage = dummyFunc
    this.delMessages = dummyFunc
    this.updateMessage = dummyFunc
    this.mergeSimilarText = dummyFunc
    this.mergeSimilarGift = dummyFunc
  }
}

const BLC_SDK_VERSION = '1.0.1'
const PRESET_CSS_URL = '/custom_public/preset.css'
// 有这个特征字符串的style元素则注入到模板里
const OBS_CSS_SIGN = 'blc-inject-into-template'

class CustomTemplateRenderer {
  constructor(templateIframe, config) {
    this._templateIframe = templateIframe
    this._config = config

    this._enabledSendMessageToTemplate = (type, data) => {
      let msg = { type, data }
      templateIframe.contentWindow.postMessage(msg, '*')
    }
    this._sendMessageToTemplate = () => {}

    this._boundOnWindowMessage = this._onWindowMessage.bind(this)
    window.addEventListener('message', this._boundOnWindowMessage)

    this._connected = false
    this._styleObserver = null
  }

  destroy() {
    if (this._styleObserver) {
      this._styleObserver.disconnect()
      this._styleObserver = null
    }

    window.removeEventListener('message', this._boundOnWindowMessage)

    let dummyFunc = () => {}
    this._enabledSendMessageToTemplate = dummyFunc
    this._sendMessageToTemplate = dummyFunc
  }

  addMessage(message) {
    this._sendMessageToTemplate('blcAddMsg', message)
  }

  delMessages(ids) {
    let data = { ids }
    this._sendMessageToTemplate('blcDelMsgs', data)
  }

  updateMessage(id, newValuesObj) {
    let data = { id, newValuesObj }
    this._sendMessageToTemplate('blcUpdateMsg', data)
  }

  mergeSimilarText() {
    return false
  }

  mergeSimilarGift() {
    return false
  }

  _onWindowMessage(event) {
    if (event.source !== this._templateIframe.contentWindow) {
      return
    }

    let { type } = event.data
    switch (type) {
    case 'blcTemplateConnect': {
      if (this._connected) {
        console.warn('模板重复连接')
        break
      }
      this._connected = true

      // 发送初始化消息
      let initData = {
        blcVersion: process.env.APP_VERSION,
        sdkVersion: BLC_SDK_VERSION,
        config: {
          showGiftName: this._config.showGiftName,
          mergeSimilarDanmaku: this._config.mergeSimilarDanmaku,
          mergeGift: this._config.mergeGift,
          maxNumber: this._config.maxNumber,
        }
      }
      this._sendMessageToTemplate = this._enabledSendMessageToTemplate
      this._sendMessageToTemplate('blcInit', initData)

      this._injectCss()
      break
    }
    }
  }

  _injectCss() {
    let injectCssUrls = []
    if (this._config.importPresetCss) {
      injectCssUrls.push(window.location.origin + PRESET_CSS_URL)
    }

    let injectCssArr = []
    for (let el of document.querySelectorAll('style')) {
      if (el.textContent.indexOf(OBS_CSS_SIGN) !== -1) {
        injectCssArr.push(el.textContent)
      }
    }

    if (injectCssUrls.length !== 0 || injectCssArr.length !== 0) {
      this._sendMessageToTemplate('blcInjectCss', {
        injectCssUrls: injectCssUrls,
        injectCss: injectCssArr.join('\n\n'),
      })
    }

    // OBS的自定义CSS可能在之后注入，再监听一段时间。OBS和直播姬都是注入到head的，如果有其他软件不是再改吧
    this._styleObserver = new MutationObserver(this._onDomMutate.bind(this))
    this._styleObserver.observe(document.head, { childList: true })
    window.setTimeout(() => {
      if (this._styleObserver) {
        this._styleObserver.disconnect()
        this._styleObserver = null
      }
    }, 30 * 1000)
  }

  _onDomMutate(mutations) {
    let injectCssArr = []
    for (let mutation of mutations) {
      if (mutation.type !== 'childList') {
        continue
      }
      for (let el of mutation.addedNodes) {
        if (el.nodeName !== 'STYLE') {
          continue
        }
        if (el.textContent.indexOf(OBS_CSS_SIGN) !== -1) {
          injectCssArr.push(el.textContent)
        }
      }
    }

    if (injectCssArr.length !== 0) {
      this._sendMessageToTemplate('blcInjectCss', {
        injectCssUrls: [],
        injectCss: injectCssArr.join('\n\n'),
      })
    }
  }
}

export default {
  name: 'Room',
  components: {
    ChatRenderer
  },
  props: {
    roomKeyType: {
      type: Number,
      default: 1
    },
    roomKeyValue: {
      type: [Number, String],
      default: null
    },
    strConfig: {
      type: Object,
      default: () => ({})
    }
  },
  data() {
    let customStyleElement = document.createElement('style')
    document.head.appendChild(customStyleElement)
    return {
      config: chatConfig.deepCloneDefaultConfig(),

      chatClient: null,
      textEmoticons: [], // 官方的文本表情（后端配置的）
      pronunciationConverter: null,

      customStyleElement, // 仅用于样式生成器中预览样式和使用自定义模板时
      presetCssLinkElement: null,

      pendingMsgIdToPromise: new Map(), // 正在异步处理，渲染器还没收到的消息，用于一些有时序依赖的消息

      renderer: null,
      obsAgent: {
        websocket: null,
        reconnectTimerId: null,
        shouldReconnect: false,
        monitoringActive: false,
        state: {
          connected: false,
          streamingActive: false,
          splitAudioTracks: false,
          lastEvent: null,
          latestFrame: null,
          latestAudio: null,
          latestMicAudio: null,
          latestDesktopAudio: null,
          streamStartedAt: 0,
          streamDurationSeconds: 0,
          recordingFilePath: '',
          updatedAt: null
        }
      },
      psychAgent: {
        timerId: null,
        giftReportTimerId: null,
        danmakuExportTimerId: null,
        atmosphereReportTimerId: null,
        obsAudioReportTimerId: null,
        obsVisionReportTimerId: null,
        running: false,
        obsAudioReportRunning: false,
        obsVisionReportRunning: false,
        windowSeconds: 10,
        tabConfig: {
          voice: { enabled: true, windowSeconds: 10 },
          psych: { enabled: true, windowSeconds: 10 },
          gift: { enabled: true, windowSeconds: 10 },
          scene: { enabled: true, windowSeconds: 60 }
        },
        texts: [],
        allDanmaku: [],
        atmosphereScore: 50,
        roomEmoticonDanmakuCount: 0,
        giftCount: 0,
        giftValue: 0,
        totalGiftValue: 0,
        superChatCount: 0,
        superChatValue: 0,
        memberCount: 0,
        users: new Set(),
        wordConfig: {
          positiveWords: [],
          negativeWords: [],
          pressureWords: [],
          game: [],
          singing: [],
          video: []
        },
        tokenUsage: {
          inputTokens: 0,
          outputTokens: 0,
          totalTokens: 0,
          requests: 0
        },
        analysisCount: 0,
        latestPsychAnalysis: null,
        latestGiftSummary: null,
        latestVoiceReport: null,
        latestSceneReport: null,
        latestJointReport: null
      },
      liveArchive: {
        streamStartedAt: 0,
        sessionReady: false
      },
      streamSession: {
        streamStartedAt: 0,
        finalDurationSeconds: 0,
        totalGiftValue: 0
      },
    }
  },
  computed: {
    blockKeywordsTrie() {
      let blockKeywords = this.config.blockKeywords.split('\n')
      let res = new trie.Trie()
      for (let keyword of blockKeywords) {
        if (keyword !== '') {
          res.set(keyword, true)
        }
      }
      return res
    },
    blockUsersSet() {
      let blockUsers = this.config.blockUsers.split('\n')
      blockUsers = blockUsers.filter(user => user !== '')
      return new Set(blockUsers)
    },
    emoticonsTrie() {
      let res = new trie.Trie()
      for (let emoticons of [this.config.emoticons, this.textEmoticons]) {
        for (let emoticon of emoticons) {
          if (emoticon.keyword !== '' && emoticon.url !== '') {
            res.set(emoticon.keyword, emoticon)
          }
        }
      }
      return res
    },
    useCustomTemplate() {
      return this.config.templateUrl !== ''
    },
    roomSidePanels() {
      const latest = this.psychAgent.latestPsychAnalysis || {}
      const analysis = latest.analysis || {}
      const metrics = latest.metrics || {}
      const joint = this.psychAgent.latestJointReport || {}
      const voice = (this.psychAgent.latestVoiceReport && this.psychAgent.latestVoiceReport.report) || {}
      const scene = (this.psychAgent.latestSceneReport && this.psychAgent.latestSceneReport.report) || {}
      const giftSummary = this.psychAgent.latestGiftSummary || {}
      let psychStatus = '等待中'
      if (joint.ts) {
        psychStatus = this.formatPanelTime(joint.ts)
      } else if (latest.ts) {
        psychStatus = this.formatPanelTime(latest.ts)
      }
      return [
        {
          key: 'psych',
          title: '心理分析',
          enabled: this.isPsychTabEnabled('psych'),
          status: psychStatus,
          items: [
            { label: '压力', value: this.toPanelPercent(analysis.stress) },
            { label: '积极度', value: this.toPanelPercent(analysis.valence) },
            { label: '置信度', value: this.toPanelPercent(analysis.confidence) }
          ],
          summary: String(analysis.summary || '等待联合分析返回').trim()
        },
        {
          key: 'voice',
          title: '语音观察',
          enabled: this.isPsychTabEnabled('voice'),
          status: this.psychAgent.latestVoiceReport ? this.formatPanelTime(this.psychAgent.latestVoiceReport.ts) : '等待中',
          items: [
            { label: '声音', value: voice.soundType || '-' },
            { label: '活动', value: voice.activity || '-' },
            { label: '置信度', value: this.toPanelPercent(voice.confidence) }
          ],
          summary: String(voice.summary || voice.psychologicalState || '等待语音结果').trim()
        },
        {
          key: 'gift',
          title: '礼物统计',
          enabled: this.isPsychTabEnabled('gift'),
          status: giftSummary.ts ? this.formatPanelTime(giftSummary.ts) : '实时',
          items: [
            { label: '本窗礼物', value: this.formatGiftValue(metrics.giftValue || this.psychAgent.giftValue) },
            { label: 'SC', value: this.formatGiftValue(metrics.superChatValue || this.psychAgent.superChatValue) },
            { label: '累计', value: this.formatGiftValue(giftSummary.totalGiftValue || this.psychAgent.totalGiftValue) }
          ],
          summary: `弹幕 ${Number(metrics.textCount || 0)} 条，用户 ${Number(metrics.uniqueUserCount || 0)} 人`
        },
        {
          key: 'scene',
          title: '画面场景',
          enabled: this.isPsychTabEnabled('scene'),
          status: this.psychAgent.latestSceneReport ? this.formatPanelTime(this.psychAgent.latestSceneReport.ts) : '等待中',
          items: [
            { label: '场景', value: scene.category || (analysis.liveEnvironment && analysis.liveEnvironment.label) || '-' },
            { label: '置信度', value: this.toPanelPercent(scene.confidence || (analysis.liveEnvironment && analysis.liveEnvironment.confidence)) },
            { label: '响应', value: joint.rawOutput ? `${joint.rawOutput.length} 字` : '-' }
          ],
          summary: String(scene.summary || '等待画面结果').trim()
        }
      ]
    },
  },
  beforeMount() {
    this.initConfig()

    // 主框架改成透明背景，防止影响到模板
    if (this.useCustomTemplate) {
      this.customStyleElement.textContent = 'body { background-color: transparent; }'
    }
  },
  mounted() {
    if (this.useCustomTemplate) {
      this.renderer = new CustomTemplateRenderer(this.$refs.templateIframe, this.config)
    } else {
      this.renderer = new DefaultRenderer(this.$refs.renderer)
    }

    if (document.visibilityState === 'visible') {
      this.init()
    } else {
      // 当前窗口不可见，延迟到可见时加载，防止OBS中一次并发太多请求（OBS中浏览器不可见时也会加载网页，除非显式设置）
      document.addEventListener('visibilitychange', this.onVisibilityChange)
    }

    window.addEventListener('message', this.onWindowMessage)
    this.startObsAgent()
  },
  beforeDestroy() {
    window.removeEventListener('message', this.onWindowMessage)
    this.stopObsAgent()
    this.stopPsychAgent()

    document.removeEventListener('visibilitychange', this.onVisibilityChange)
    if (this.chatClient) {
      this.chatClient.stop()
    }

    document.head.removeChild(this.customStyleElement)
    if (this.presetCssLinkElement) {
      document.head.removeChild(this.presetCssLinkElement)
    }

    if (this.renderer) {
      this.renderer.destroy()
    }
  },
  methods: {
    onVisibilityChange() {
      if (document.visibilityState !== 'visible') {
        return
      }
      document.removeEventListener('visibilitychange', this.onVisibilityChange)
      this.init()
    },
    async init() {
      let initChatClientPromise = this.initChatClient()
      this.initTextEmoticons()
      if (this.config.giftUsernamePronunciation !== '') {
        this.pronunciationConverter = new pronunciation.PronunciationConverter()
        this.pronunciationConverter.loadDict(this.config.giftUsernamePronunciation)
      }
      if (this.config.importPresetCss && !this.useCustomTemplate) {
        this.presetCssLinkElement = document.createElement('link')
        this.presetCssLinkElement.rel = 'stylesheet'
        this.presetCssLinkElement.href = PRESET_CSS_URL
        document.head.appendChild(this.presetCssLinkElement)
      }

      try {
        // 其他初始化就不用等了，就算失败了也不会有很大影响
        await initChatClientPromise
      } catch (e) {
        this.$message.error({
          message: `Failed to load: ${e}`,
          duration: 10 * 1000
        })
        throw e
      }

      // 提示用户已加载
      this.$message({
        message: 'Loaded',
        duration: 500
      })

      this.sendMessageToStylegen('stylegenExampleRoomLoad')
      this.tryInitLiveArchiveSession()
    },
    initConfig() {
      let locale = this.strConfig.lang
      if (locale) {
        i18n.setLocale(locale)
      }

      let cfg = {}
      // 留空的使用默认值
      for (let i in this.strConfig) {
        if (this.strConfig[i] !== '') {
          cfg[i] = this.strConfig[i]
        }
      }
      cfg = mergeConfig(cfg, chatConfig.deepCloneDefaultConfig())

      cfg.minGiftPrice = toFloat(cfg.minGiftPrice, chatConfig.DEFAULT_CONFIG.minGiftPrice)
      cfg.showDanmaku = toBool(cfg.showDanmaku)
      cfg.showGift = toBool(cfg.showGift)
      cfg.showGiftName = toBool(cfg.showGiftName)
      cfg.mergeSimilarDanmaku = toBool(cfg.mergeSimilarDanmaku)
      cfg.mergeGift = toBool(cfg.mergeGift)
      cfg.maxNumber = toInt(cfg.maxNumber, chatConfig.DEFAULT_CONFIG.maxNumber)

      cfg.blockGiftDanmaku = toBool(cfg.blockGiftDanmaku)
      cfg.blockMirrorMessages = toBool(cfg.blockMirrorMessages)
      cfg.blockLevel = toInt(cfg.blockLevel, chatConfig.DEFAULT_CONFIG.blockLevel)
      cfg.blockNewbie = toBool(cfg.blockNewbie)
      cfg.blockNotMobileVerified = toBool(cfg.blockNotMobileVerified)
      cfg.blockMedalLevel = toInt(cfg.blockMedalLevel, chatConfig.DEFAULT_CONFIG.blockMedalLevel)

      cfg.showDebugMessages = toBool(cfg.showDebugMessages)
      cfg.relayMessagesByServer = toBool(cfg.relayMessagesByServer)
      cfg.autoTranslate = toBool(cfg.autoTranslate)
      cfg.importPresetCss = toBool(cfg.importPresetCss)

      cfg.emoticons = this.toObjIfJson(cfg.emoticons)

      chatConfig.sanitizeConfig(cfg)
      this.config = cfg
    },
    startPsychAgent() {
      this.psychAgent.totalGiftValue = 0
      this.resetPsychWindow()
      this.resetDanmakuAtmosphereWindow()
      this.loadPsychAgentWords()
      this.updatePsychAgentTimers()
    },
    startObsAgent() {
      if (this.obsAgent.websocket !== null || this.obsAgent.reconnectTimerId !== null) {
        return
      }
      this.obsAgent.shouldReconnect = true
      this.connectObsAgent()
    },
    stopObsAgent() {
      this.obsAgent.shouldReconnect = false
      if (this.obsAgent.reconnectTimerId !== null) {
        window.clearTimeout(this.obsAgent.reconnectTimerId)
        this.obsAgent.reconnectTimerId = null
      }
      if (this.obsAgent.websocket !== null) {
        this.obsAgent.websocket.onopen = null
        this.obsAgent.websocket.onmessage = null
        this.obsAgent.websocket.onclose = null
        this.obsAgent.websocket.close()
        this.obsAgent.websocket = null
      }
    },
    async connectObsAgent() {
      if (!this.obsAgent.shouldReconnect) {
        return
      }
      try {
        await ensureBaseUrlInited()
        let baseUrl = getBaseUrl()
        if (baseUrl === null) {
          throw new Error('No available backend endpoint')
        }
        let url = `${baseUrl.replace(/^http(s?):/, 'ws$1:')}/api/obs-agent`
        let websocket = new WebSocket(url)
        this.obsAgent.websocket = websocket
        websocket.onopen = () => {
          this.obsAgent.state.connected = true
        }
        websocket.onmessage = this.onObsAgentMessage.bind(this)
        websocket.onclose = this.onObsAgentClose.bind(this)
      } catch (e) {
        console.warn('OBS agent connect failed:', e)
        this.scheduleObsAgentReconnect()
      }
    },
    onObsAgentClose() {
      this.obsAgent.websocket = null
      this.obsAgent.state.connected = false
      this.scheduleObsAgentReconnect()
    },
    scheduleObsAgentReconnect() {
      if (!this.obsAgent.shouldReconnect || this.obsAgent.reconnectTimerId !== null) {
        return
      }
      this.obsAgent.reconnectTimerId = window.setTimeout(() => {
        this.obsAgent.reconnectTimerId = null
        this.connectObsAgent()
      }, 3000)
    },
    onObsAgentMessage(event) {
      let body = null
      try {
        body = JSON.parse(event.data)
      } catch (e) {
        console.warn('Invalid OBS agent message:', e)
        return
      }
      if (body.type === 'state') {
        this.updateObsAgentState(body.data || {})
      } else if (body.type === 'event') {
        let nextState = { lastEvent: body.data || {} }
        if (body.data && body.data.streamingActive !== undefined) {
          nextState.streamingActive = body.data.streamingActive
        }
        if (body.data && body.data.streamStartedAt !== undefined) {
          nextState.streamStartedAt = body.data.streamStartedAt
        }
        if (body.data && body.data.streamDurationSeconds !== undefined) {
          nextState.streamDurationSeconds = body.data.streamDurationSeconds
        }
        if (body.data && body.data.recordingFilePath !== undefined) {
          nextState.recordingFilePath = body.data.recordingFilePath
        }
        this.updateObsAgentState(nextState)
      } else if (body.type === 'frame') {
        this.updateObsAgentState({ latestFrame: body.data || {} })
      } else if (body.type === 'config') {
        const config = body.data || {}
        this.updateObsAgentState({
          splitAudioTracks: Boolean(config.splitAudioTracks)
        })
      } else if (body.type === 'audio') {
        const audio = body.data || {}
        const trackRole = String(audio.trackRole || 'mixed').toLowerCase()
        if (trackRole === 'mic') {
          this.updateObsAgentState({ latestMicAudio: audio })
        } else if (trackRole === 'desktop') {
          this.updateObsAgentState({ latestDesktopAudio: audio })
        } else {
          this.updateObsAgentState({ latestAudio: audio })
        }
      }
    },
    updateObsAgentState(nextState) {
      let oldStreamingActive = Boolean(this.obsAgent.state.streamingActive)
      if (nextState.streamDurationSeconds !== undefined
          && Number(nextState.streamDurationSeconds) <= 0
          && Number(this.streamSession.finalDurationSeconds || 0) > 0) {
        nextState = {
          ...nextState,
          streamDurationSeconds: this.streamSession.finalDurationSeconds
        }
      }
      this.obsAgent.state = { ...this.obsAgent.state, ...nextState }
      let newStreamingActive = Boolean(this.obsAgent.state.streamingActive)
      if (oldStreamingActive !== newStreamingActive) {
        this.onObsStreamingStateChanged(newStreamingActive)
      }
    },
    onObsStreamingStateChanged(streamingActive) {
      this.obsAgent.monitoringActive = streamingActive
      if (streamingActive) {
        this.streamSession = {
          streamStartedAt: Number(this.obsAgent.state.streamStartedAt || 0) || Math.floor(Date.now() / 1000),
          finalDurationSeconds: 0,
          totalGiftValue: 0
        }
        this.resetLiveArchiveSession()
        this.startPsychAgent()
        this.reportObsVisionScene()
        this.reportObsAudioObservation()
        this.tryInitLiveArchiveSession()
      } else {
        let durationSeconds = this.resolveStreamDurationSeconds()
        let totalGiftValue = Number(this.psychAgent.totalGiftValue || 0)
        this.streamSession.finalDurationSeconds = durationSeconds
        this.streamSession.totalGiftValue = totalGiftValue
        this.stopPsychAgent()
        this.notifyParentObsStreamingStopped(durationSeconds, totalGiftValue)
      }
      let content = streamingActive ? '【OBS】推流已开始，Agent已开启串流监控' : '【OBS】推流已停止，Agent已暂停串流监控'
      this.onAddText(new chatModels.AddTextMsg({
        authorName: 'blivechat',
        authorType: constants.AUTHOR_TYPE_ADMIN,
        content,
        authorLevel: 60,
        id: `obs-${Date.now()}`
      }))
    },
    resolveStreamDurationSeconds(obsBridgeState) {
      let candidates = [
        Number(this.streamSession.finalDurationSeconds || 0),
        Number(this.obsAgent.state.streamDurationSeconds || 0),
        Number((this.obsAgent.state.lastEvent && this.obsAgent.state.lastEvent.streamDurationSeconds) || 0),
        obsBridgeState ? Number(obsBridgeState.streamDurationSeconds || 0) : 0,
        obsBridgeState ? Number(obsBridgeState.lastStreamDurationSeconds || 0) : 0,
        obsBridgeState && obsBridgeState.lastEvent
          ? Number(obsBridgeState.lastEvent.streamDurationSeconds || 0)
          : 0
      ]
      let streamStartedAt = Number(this.streamSession.streamStartedAt || this.obsAgent.state.streamStartedAt || 0)
      if (streamStartedAt > 0) {
        candidates.push(Math.max(0, Math.floor(Date.now() / 1000) - streamStartedAt))
      }
      return Math.max(...candidates.filter(value => Number.isFinite(value)), 0)
    },
    async notifyParentObsStreamingStopped(durationSeconds, totalGiftValue) {
      if (window.parent === window) {
        return
      }
      await new Promise(resolve => window.setTimeout(resolve, 500))
      let obsBridgeState = await this.fetchObsBridgeState()
      durationSeconds = Math.max(
        Number(durationSeconds || 0),
        this.resolveStreamDurationSeconds(obsBridgeState)
      )
      let recordingFilePath = this.resolveRecordingFilePath(obsBridgeState)
      await this.appendLiveStreamStopInfo(durationSeconds, totalGiftValue, recordingFilePath)
      window.parent.postMessage({
        type: 'roomStreamingStopped',
        data: {
          streamDurationSeconds: durationSeconds,
          totalGiftValue: Number(totalGiftValue || 0),
          recordingFilePath
        }
      }, window.location.origin)
    },
    resolveRecordingFilePath(obsBridgeState) {
      let candidates = [
        obsBridgeState && obsBridgeState.recordingFilePath,
        obsBridgeState && obsBridgeState.lastEvent && obsBridgeState.lastEvent.recordingFilePath,
        this.obsAgent.state.recordingFilePath,
        this.obsAgent.state.lastEvent && this.obsAgent.state.lastEvent.recordingFilePath
      ]
      for (let candidate of candidates) {
        let path = String(candidate || '').trim()
        if (path !== '') {
          return path
        }
      }
      return ''
    },
    async appendLiveStreamStopInfo(durationSeconds, totalGiftValue, recordingFilePath) {
      let streamStartedAt = Number(this.streamSession.streamStartedAt || 0)
      if (streamStartedAt <= 0) {
        let obsBridgeState = await this.fetchObsBridgeState()
        streamStartedAt = Number(
          (obsBridgeState && obsBridgeState.streamStartedAt)
          || (obsBridgeState && obsBridgeState.lastStreamStartedAt)
          || 0
        )
      }
      if (streamStartedAt <= 0) {
        return
      }
      if (!await this.ensureLiveArchiveSession(streamStartedAt)) {
        return
      }
      let roomId = this.getPsychRoomId()
      let stopTimeText = formatLiveInfoTimestamp(Math.floor(Date.now() / 1000))
      await appendLiveArchiveRecordApi(roomId, streamStartedAt, 'live_info', `【停止直播】${stopTimeText}`)
      await appendLiveArchiveRecordApi(roomId, streamStartedAt, 'live_info', formatLiveStreamSummary({
        streamDurationSeconds: durationSeconds,
        totalGiftValue,
        recordingFilePath
      }))
    },
    isPsychAgentActive() {
      return this.obsAgent.monitoringActive
    },
    stopPsychAgent() {
      if (this.psychAgent.timerId !== null) {
        window.clearInterval(this.psychAgent.timerId)
        this.psychAgent.timerId = null
      }
      if (this.psychAgent.giftReportTimerId !== null) {
        window.clearInterval(this.psychAgent.giftReportTimerId)
        this.psychAgent.giftReportTimerId = null
      }
      if (this.psychAgent.danmakuExportTimerId !== null) {
        window.clearInterval(this.psychAgent.danmakuExportTimerId)
        this.psychAgent.danmakuExportTimerId = null
      }
      if (this.psychAgent.atmosphereReportTimerId !== null) {
        window.clearInterval(this.psychAgent.atmosphereReportTimerId)
        this.psychAgent.atmosphereReportTimerId = null
      }
      if (this.psychAgent.obsAudioReportTimerId !== null) {
        window.clearInterval(this.psychAgent.obsAudioReportTimerId)
        this.psychAgent.obsAudioReportTimerId = null
      }
      if (this.psychAgent.obsVisionReportTimerId !== null) {
        window.clearInterval(this.psychAgent.obsVisionReportTimerId)
        this.psychAgent.obsVisionReportTimerId = null
      }
    },
    updatePsychAgentTimers() {
      this.stopPsychAgent()
      if (!this.isPsychAgentActive()) {
        return
      }
      this.psychAgent.windowSeconds = this.getPsychTabWindowSeconds('psych', 30) // 统一设置多模态联合分析的时间间隔，默认30秒
      this.psychAgent.timerId = window.setInterval(this.flushPsychAgent, this.psychAgent.windowSeconds * 1000)

      if (this.isPsychTabEnabled('gift')) {
        const seconds = this.getPsychTabWindowSeconds('gift', 10)
        this.psychAgent.giftReportTimerId = window.setInterval(this.reportTotalGiftValue, seconds * 1000)
      }
      this.psychAgent.danmakuExportTimerId = window.setInterval(this.exportDanmakuArchive, 60 * 60 * 1000)
    },
    isPsychTabEnabled(tabName) {
      const config = this.psychAgent.tabConfig && this.psychAgent.tabConfig[tabName]
      return !config || config.enabled !== false
    },
    getPsychTabWindowSeconds(tabName, fallback) {
      const config = this.psychAgent.tabConfig && this.psychAgent.tabConfig[tabName]
      const seconds = Number(config && config.windowSeconds)
      return Math.max(5, seconds || fallback)
    },
    applyPsychTabConfig(config) {
      if (!config || typeof config !== 'object') {
        return
      }
      const nextConfig = { ...this.psychAgent.tabConfig }
      for (let tabName of ['voice', 'psych', 'gift', 'scene']) {
        if (!config[tabName] || typeof config[tabName] !== 'object') {
          continue
        }
        nextConfig[tabName] = {
          enabled: config[tabName].enabled !== false,
          windowSeconds: this.getNormalizedPsychWindowSeconds(config[tabName].windowSeconds, nextConfig[tabName].windowSeconds)
        }
      }
      this.psychAgent.tabConfig = nextConfig
      this.psychAgent.windowSeconds = this.getPsychTabWindowSeconds('psych', 10)
      this.updatePsychAgentTimers()
    },
    getNormalizedPsychWindowSeconds(value, fallback) {
      const seconds = Number(value)
      return Math.max(5, seconds || fallback || 10)
    },
    resetPsychWindow() {
      this.psychAgent.texts = []
      this.psychAgent.giftCount = 0
      this.psychAgent.giftValue = 0
      this.psychAgent.superChatCount = 0
      this.psychAgent.superChatValue = 0
      this.psychAgent.memberCount = 0
      this.psychAgent.users = new Set()
    },
    resetDanmakuAtmosphereWindow() {
      this.psychAgent.atmosphereScore = 50
      this.psychAgent.roomEmoticonDanmakuCount = 0
    },
    recordPsychText(data) {
      if (!this.isPsychAgentActive()) {
        return
      }
      if (data.authorName === 'blivechat') {
        return
      }
      let content = (data.content || '').trim()
      if (content === '') {
        return
      }
      this.psychAgent.texts.push(content)
      this.psychAgent.users.add(data.uid || data.authorName || 'anonymous')
      this.psychAgent.allDanmaku.push({
        ts: new Date((data.timestamp || Math.floor(Date.now() / 1000)) * 1000).toISOString(),
        uid: data.uid || '',
        authorName: data.authorName || '',
        content,
        authorLevel: data.authorLevel || 0,
        medalLevel: data.medalLevel || 0,
        medalName: data.medalName || '',
        isMirror: Boolean(data.isMirror)
      })
      this.recordDanmakuAtmosphere(data, content)
    },
    recordDanmakuAtmosphere(data, content) {
      if (this.isRoomEmoticonDanmaku(data, content)) {
        this.psychAgent.atmosphereScore += 5
        this.psychAgent.roomEmoticonDanmakuCount++
      }

      let { positiveWords, negativeWords, pressureWords } = this.psychAgent.wordConfig
      this.psychAgent.atmosphereScore += this.countWordHitsInText(content, positiveWords)
      this.psychAgent.atmosphereScore -= this.countWordHitsInText(content, negativeWords)
      this.psychAgent.atmosphereScore -= this.countWordHitsInText(content, pressureWords) * 5
    },
    isRoomEmoticonDanmaku(data, content) {
      if (data.emoticon !== null && data.emoticon !== undefined && data.emoticon !== '') {
        return true
      }
      if (this.config.emoticons.length === 0 && this.textEmoticons.length === 0) {
        return false
      }

      let pos = 0
      while (pos < content.length) {
        if (this.emoticonsTrie.lazyMatch(content.substring(pos)) !== null) {
          return true
        }
        pos++
      }
      return false
    },
    countWordHitsInText(text, words) {
      let lowered = text.toLowerCase()
      let hits = 0
      for (let word of words) {
        if (lowered.indexOf(word.toLowerCase()) !== -1) {
          hits++
        }
      }
      return hits
    },
    recordPsychGift(data) {
      if (!this.isPsychAgentActive()) {
        return
      }
      let giftValue = Math.max(data.totalCoin || 0, 0) / 1000
      this.psychAgent.giftCount++
      this.psychAgent.giftValue += giftValue
      this.psychAgent.totalGiftValue += giftValue
    },
    getMemberGiftValue(data) {
      let guardLevelToPrice = {
        1: 19998,
        2: 1998,
        3: 138
      }
      let num = Math.max(Number(data.num || 1), 1)
      let levelPrice = (guardLevelToPrice[data.privilegeType] || 138) * num
      let reportedPrice = Math.max(Number(data.totalCoin || 0), 0) / 1000
      return Math.max(reportedPrice, levelPrice)
    },
    recordPsychMember(data) {
      if (!this.isPsychAgentActive()) {
        return
      }
      let memberValue = this.getMemberGiftValue(data)
      this.psychAgent.memberCount++
      this.psychAgent.giftValue += memberValue
      this.psychAgent.totalGiftValue += memberValue
    },
    recordPsychSuperChat(data) {
      if (!this.isPsychAgentActive()) {
        return
      }
      let superChatValue = Math.max(Number(data.price || 0), 0)
      this.psychAgent.superChatCount++
      this.psychAgent.superChatValue += superChatValue
      this.psychAgent.giftValue += superChatValue
      this.psychAgent.totalGiftValue += superChatValue
      if (data.content) {
        this.psychAgent.texts.push(data.content.trim())
      }
    },
    reportDanmakuAtmosphere() {
      if (!this.isPsychTabEnabled('psych')) {
        return
      }
      let score = this.psychAgent.atmosphereScore
      let roomEmoticonDanmakuCount = this.psychAgent.roomEmoticonDanmakuCount
      this.resetDanmakuAtmosphereWindow()
      if (score >= 40 && score <= 60) {
        return
      }

      let atmosphereText = score < 40 ? '当前弹幕氛围较差' : '当前弹幕氛围较好'
      let content = `${atmosphereText}，近1分钟房间专属表情发送${roomEmoticonDanmakuCount}次`
      this.onAddText(new chatModels.AddTextMsg({
        authorName: 'blivechat',
        authorType: constants.AUTHOR_TYPE_ADMIN,
        content,
        authorLevel: 60,
        id: `atmosphere-${Date.now()}`
      }))
    },
    async flushPsychAgent() {
      // 只要 psych/voice/scene 中任意一个 tab 开启，就需要触发联合分析
      const psychOn = this.isPsychTabEnabled('psych')
      const voiceOn = this.isPsychTabEnabled('voice')
      const sceneOn = this.isPsychTabEnabled('scene')
      if (!psychOn && !voiceOn && !sceneOn) {
        return
      }
      if (this.psychAgent.running) {
        return
      }
      this.psychAgent.running = true
      try {
        let metrics = await this.buildPsychMetrics()
        this.resetPsychWindow()
        let analysis = await this.analyzePsychMetrics(metrics)
        if (psychOn) {
          await this.addPsychSystemMessage(metrics, analysis)
        }
        if (voiceOn && analysis.voiceReport) {
          await this.applyJointVoiceReport(analysis.voiceReport, analysis.tokenUsage)
        }
        if (sceneOn && analysis.sceneReport) {
          await this.applyJointSceneReport(analysis.sceneReport, analysis.tokenUsage)
        }
      } finally {
        this.psychAgent.running = false
      }
    },
    async applyJointVoiceReport(voiceReport, tokenUsage) {
      this.psychAgent.latestVoiceReport = {
        ts: new Date().toISOString(),
        report: voiceReport,
        usage: tokenUsage
      }
      let obsBridgeState = await this.fetchObsBridgeState()
      let durationText = this.resolveLiveStreamDurationText(obsBridgeState)
      let content = this.formatVoiceReportContent(voiceReport, durationText)
      this.onAddText(new chatModels.AddTextMsg({
        authorName: 'blivechat',
        authorType: constants.AUTHOR_TYPE_ADMIN,
        content,
        authorLevel: 60,
        id: `voice-${Date.now()}`
      }))
      await this.appendLiveArchiveRecord('voice', content)
      this.emitPsychAgentUpdate()
    },
    async applyJointSceneReport(sceneReport, tokenUsage) {
      this.psychAgent.latestSceneReport = {
        ts: new Date().toISOString(),
        report: sceneReport,
        usage: tokenUsage
      }
      let obsBridgeState = await this.fetchObsBridgeState()
      let durationText = this.resolveLiveStreamDurationText(obsBridgeState)
      let content = this.formatSceneReportContent(sceneReport, durationText)
      this.onAddText(new chatModels.AddTextMsg({
        authorName: 'blivechat',
        authorType: constants.AUTHOR_TYPE_ADMIN,
        content,
        authorLevel: 60,
        id: `scene-${Date.now()}`
      }))
      await this.appendLiveArchiveRecord('picture', content)
      this.emitPsychAgentUpdate()
    },
    async loadPsychAgentWords() {
      try {
        let res = await fetch(`/psych-agent-words.json?_=${Date.now()}`, { cache: 'no-store' })
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`)
        }
        let wordConfig = this.normalizePsychAgentWords(await res.json())
        this.psychAgent.wordConfig = wordConfig
        return wordConfig
      } catch (e) {
        console.warn('Psych agent words fallback:', e)
        return this.psychAgent.wordConfig
      }
    },
    normalizePsychAgentWords(config) {
      let toWords = value => {
        if (!Array.isArray(value)) {
          return []
        }
        return value.map(item => String(item).trim()).filter(item => item !== '')
      }
      return {
        positiveWords: toWords(config.positiveWords),
        negativeWords: toWords(config.negativeWords),
        pressureWords: toWords(config.pressureWords),
        game: toWords(config.game),
        singing: toWords(config.singing),
        video: toWords(config.video)
      }
    },
    async fetchObsBridgeState() {
      try {
        let res = await fetch('/api/obs/state', { cache: 'no-store' })
        if (!res.ok) {
          return null
        }
        let data = await res.json()
        if (!data.success) {
          return null
        }
        return data.data || null
      } catch (e) {
        console.warn('Fetch OBS bridge state failed:', e)
        return null
      }
    },
    formatStreamDuration(seconds) {
      let total = Math.max(0, Math.floor(Number(seconds) || 0))
      if (total === 0) {
        return '0秒'
      }
      let hours = Math.floor(total / 3600)
      let minutes = Math.floor((total % 3600) / 60)
      let secs = total % 60
      let parts = []
      if (hours > 0) {
        parts.push(`${hours}小时`)
      }
      if (minutes > 0) {
        parts.push(`${minutes}分`)
      }
      if (secs > 0 || parts.length === 0) {
        parts.push(`${secs}秒`)
      }
      return parts.join('')
    },
    async buildPsychMetrics() {
      let wordConfig = await this.loadPsychAgentWords()
      let { positiveWords, negativeWords, pressureWords } = wordConfig
      let texts = this.psychAgent.texts.slice()

      let countHits = words => {
        let hits = 0
        for (let text of texts) {
          let lowered = text.toLowerCase()
          for (let word of words) {
            if (lowered.indexOf(word.toLowerCase()) !== -1) {
              hits++
            }
          }
        }
        return hits
      }

      let buildEnvironmentHint = (type, words) => {
        let hits = 0
        let messages = []
        for (let text of texts) {
          let hitCount = this.countWordHitsInText(text, words)
          if (hitCount > 0) {
            hits += hitCount
            if (messages.length < 5) {
              messages.push(text)
            }
          }
        }
        return { type, hits, messages }
      }

      return {
        windowSeconds: this.psychAgent.windowSeconds,
        textCount: texts.length,
        textPerMinute: texts.length * 60 / this.psychAgent.windowSeconds,
        uniqueUserCount: this.psychAgent.users.size,
        giftCount: this.psychAgent.giftCount,
        giftValue: this.psychAgent.giftValue,
        superChatCount: this.psychAgent.superChatCount,
        superChatValue: this.psychAgent.superChatValue,
        memberCount: this.psychAgent.memberCount,
        obs: this.buildObsAgentMetrics(),
        positiveHits: countHits(positiveWords),
        negativeHits: countHits(negativeWords),
        pressureHits: countHits(pressureWords),
        liveEnvironmentHints: [
          buildEnvironmentHint('game', wordConfig.game),
          buildEnvironmentHint('singing', wordConfig.singing),
          buildEnvironmentHint('video', wordConfig.video)
        ],
        sampleMessages: texts.slice(-15)
      }
    },
    pickDanmakuDistillFocus() {
      let focuses = [
        {
          type: 'atmosphere',
          label: '直播间氛围',
          promptHint: '概括最近弹幕反映的直播间整体氛围，例如热闹、冷清、正向、紧张、玩梗等'
        },
        {
          type: 'emotion',
          label: '观众情绪',
          promptHint: '概括观众当前主要情绪倾向，例如兴奋、抱怨、期待、调侃、不满等'
        },
        {
          type: 'opinion',
          label: '观众看法',
          promptHint: '概括观众对当前直播内容的主要看法、关注点或讨论方向'
        }
      ]
      return focuses[Math.floor(Math.random() * focuses.length)]
    },
    normalizeDanmakuDistill(raw, distillFocus) {
      let labels = {
        atmosphere: '直播间氛围',
        emotion: '观众情绪',
        opinion: '观众看法'
      }
      let type = raw && labels[raw.type] ? raw.type : (distillFocus && distillFocus.type) || 'atmosphere'
      let text = String((raw && raw.text) || '').trim()
      if (text === '') {
        text = '暂无足够弹幕可提炼'
      }
      return {
        type,
        label: labels[type],
        text: text.slice(0, 40)
      }
    },
    fallbackDanmakuDistill(metrics, distillFocus) {
      let focus = distillFocus || this.pickDanmakuDistillFocus()
      let texts = Array.isArray(metrics.sampleMessages) ? metrics.sampleMessages : []
      if (metrics.textCount === 0) {
        return {
          type: focus.type,
          label: focus.label,
          text: '最近窗口暂无新弹幕'
        }
      }
      if (focus.type === 'atmosphere') {
        if (metrics.positiveHits > metrics.negativeHits + metrics.pressureHits) {
          return { type: focus.type, label: focus.label, text: '弹幕互动活跃，整体氛围偏正向' }
        }
        if (metrics.negativeHits + metrics.pressureHits > metrics.positiveHits) {
          return { type: focus.type, label: focus.label, text: '负向与催播类弹幕偏多，氛围偏紧张' }
        }
        return { type: focus.type, label: focus.label, text: '弹幕量适中，直播间氛围较为平稳' }
      }
      if (focus.type === 'emotion') {
        if (metrics.pressureHits > 0) {
          return { type: focus.type, label: focus.label, text: '部分观众表现出催播或催促情绪' }
        }
        if (metrics.positiveHits > metrics.negativeHits) {
          return { type: focus.type, label: focus.label, text: '观众情绪整体偏积极，互动意愿较高' }
        }
        if (metrics.negativeHits > 0) {
          return { type: focus.type, label: focus.label, text: '观众情绪中存在一定抱怨或不满' }
        }
        return { type: focus.type, label: focus.label, text: '观众情绪较为中性，以围观讨论为主' }
      }
      let opinionText = texts.slice(-3).join('；')
      if (opinionText.length > 40) {
        opinionText = `${opinionText.slice(0, 37)}...`
      }
      return {
        type: focus.type,
        label: focus.label,
        text: opinionText || '观众主要在围观，尚未形成明确看法'
      }
    },
    async analyzePsychMetrics(metrics) {
      let distillFocus = this.pickDanmakuDistillFocus()

      // 即使弹幕为 0，只要 OBS 有可分析的画面或音频，也要发起联合请求
      const obsState = this.obsAgent.state || {}
      const hasFrame = obsState.latestFrame
        && (obsState.latestFrame.imageFilePath || obsState.latestFrame.ts)
      const hasAudio = this.hasObsAudioReady(obsState)
      if (metrics.textCount === 0 && !hasFrame && !hasAudio) {
        return this.fallbackPsychAnalysis(metrics, '暂无可分析内容（弹幕/画面/音频均为空）', distillFocus)
      }

      metrics.distillFocusLabel = distillFocus.label
      metrics.distillFocusPromptHint = distillFocus.promptHint

      const controller = new AbortController()
      // 客户端总超时给得宽一些：上传 2MB 大包 + 服务端推理可能 ≥ 45s
      const timeoutId = setTimeout(() => controller.abort(), 120000)

      try {
        let res = await fetch('/api/qwen/joint-report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ metrics }),
          signal: controller.signal
        })
        clearTimeout(timeoutId)
        let data = await res.json()
        if (!data.success) {
          throw new Error(data.error || 'Qwen joint-report failed')
        }
        const rawOutput = String(data.response || '')
        this.psychAgent.latestJointReport = {
          ts: new Date().toISOString(),
          rawOutput,
          report: data.report || null,
          timing: data.timing || null
        }
        let obj = data.report && Object.keys(data.report).length > 0
          ? data.report
          : this.extractJsonObject(rawOutput)
        if (obj === null) {
          obj = this.buildJointFallbackObjectFromRaw(rawOutput, metrics, distillFocus)
        }
        obj = this.normalizeJointReportObject(obj)
        let analysis = this.normalizePsychAnalysis(obj, distillFocus)
        analysis.tokenUsage = this.recordPsychTokenUsage(data.usage)
        analysis.voiceReport = this.normalizeJointVoiceReport(obj.voiceReport)
        analysis.sceneReport = this.normalizeJointSceneReport(obj.sceneReport)
        return analysis
      } catch (e) {
        clearTimeout(timeoutId)
        console.warn('Psych agent fallback:', e)
        return this.fallbackPsychAnalysis(metrics, 'Qwen不可用，使用规则分析', distillFocus)
      }
    },
    buildJointFallbackObjectFromRaw(rawOutput, metrics, distillFocus) {
      const text = String(rawOutput || '').trim()
      const lowerText = text.toLowerCase()
      const liveEnvironment = this.fallbackLiveEnvironment(metrics)
      if (lowerText.indexOf('game') !== -1 || text.indexOf('游戏') !== -1) {
        liveEnvironment.type = 'game'
        liveEnvironment.label = '直播游戏中'
        liveEnvironment.confidence = Math.max(liveEnvironment.confidence || 0, 0.5)
      } else if (lowerText.indexOf('anime') !== -1 || text.indexOf('视频') !== -1 || text.indexOf('观看') !== -1) {
        liveEnvironment.type = 'video'
        liveEnvironment.label = '观看视频中'
        liveEnvironment.confidence = Math.max(liveEnvironment.confidence || 0, 0.5)
      }
      const silent = lowerText.indexOf('silent') !== -1 || text.indexOf('无语音') !== -1 || text.indexOf('静音') !== -1
      return {
        stress: 0.25,
        valence: 0.55,
        fatigue: 0.2,
        engagement: Math.min(0.85, 0.25 + (Number(metrics.textPerMinute || 0) / 180)),
        confidence: text ? 0.35 : 0.2,
        summary: 'Qwen返回了非结构化调试内容，页面仅展示规则兜底结果',
        danmakuDistill: {
          type: (distillFocus && distillFocus.type) || 'atmosphere',
          label: (distillFocus && distillFocus.label) || '弹幕蒸馏',
          text: '模型未返回可展示的结构化中文结论'
        },
        liveEnvironment,
        voiceReport: {
          transcript: '',
          soundType: silent ? '无明显人声' : '无法判断主导声音类别',
          activity: silent ? '主播麦克风可能静音' : '结构化解析失败',
          psychologicalState: '无法判断心理状态',
          confidence: text ? 0.35 : 0.2,
          evidence: [],
          summary: silent ? '未检测到明显主播人声' : '模型未返回可展示的结构化语音结论'
        },
        sceneReport: {
          category: liveEnvironment.label || '无法判断',
          confidence: liveEnvironment.confidence || 0.3,
          evidence: [],
          summary: '模型未返回可展示的结构化画面结论'
        }
      }
    },
    normalizeJointVoiceReport(raw) {
      if (!raw || typeof raw !== 'object') {
        return null
      }
      let confidence = Number(raw.confidence)
      if (!Number.isFinite(confidence)) {
        confidence = 0.3
      }
      confidence = Math.max(0, Math.min(1, confidence))
      let evidence = Array.isArray(raw.evidence)
        ? raw.evidence.slice(0, 3).map(item => String(item).trim()).filter(item => item !== '')
        : []
      return {
        transcript: String(raw.transcript || '').trim(),
        soundType: String(raw.soundType || '').trim() || '无法判断主导声音类别',
        activity: String(raw.activity || '').trim() || '无法判断主播正在做什么',
        psychologicalState: String(raw.psychologicalState || '').trim() || '无法判断心理状态',
        confidence,
        evidence,
        summary: String(raw.summary || '').trim()
      }
    },
    normalizeJointSceneReport(raw) {
      if (!raw || typeof raw !== 'object') {
        return null
      }
      const allowed = new Set(['游戏中', '唱歌中', '观看视频中'])
      let category = String(raw.category || '').trim()
      if (!allowed.has(category)) {
        if (category.indexOf('唱') !== -1) {
          category = '唱歌中'
        } else if (category.indexOf('视频') !== -1 || category.indexOf('观看') !== -1) {
          category = '观看视频中'
        } else if (category.indexOf('游戏') !== -1) {
          category = '游戏中'
        } else {
          category = ''
        }
      }
      let confidence = Number(raw.confidence)
      if (!Number.isFinite(confidence)) {
        confidence = 0.3
      }
      confidence = Math.max(0, Math.min(1, confidence))
      let evidence = Array.isArray(raw.evidence)
        ? raw.evidence.slice(0, 3).map(item => String(item).trim()).filter(item => item !== '')
        : []
      let summary = String(raw.summary || '').trim()
      if (category === '' && evidence.length === 0 && summary === '') {
        return null
      }
      return {
        category: category || '无法判断',
        confidence,
        evidence,
        summary
      }
    },
    recordPsychTokenUsage(usage = {}) {
      let inputTokens = Number(usage.inputTokens || 0)
      let outputTokens = Number(usage.outputTokens || 0)
      let totalTokens = Number(usage.totalTokens || inputTokens + outputTokens)
      this.psychAgent.tokenUsage.inputTokens += inputTokens
      this.psychAgent.tokenUsage.outputTokens += outputTokens
      this.psychAgent.tokenUsage.totalTokens += totalTokens
      this.psychAgent.tokenUsage.requests++
      return {
        inputTokens,
        outputTokens,
        totalTokens,
        cumulativeInputTokens: this.psychAgent.tokenUsage.inputTokens,
        cumulativeOutputTokens: this.psychAgent.tokenUsage.outputTokens,
        cumulativeTotalTokens: this.psychAgent.tokenUsage.totalTokens,
        requests: this.psychAgent.tokenUsage.requests
      }
    },
    formatTokenUsageText(tokenUsage) {
      if (!tokenUsage) {
        return ''
      }
      return ` | Token累计 输入${tokenUsage.cumulativeInputTokens} 输出${tokenUsage.cumulativeOutputTokens}`
    },
    extractJsonObject(text) {
      text = String(text || '').trim()
      try {
        return JSON.parse(text)
      } catch {
        for (let start = text.indexOf('{'); start !== -1; start = text.indexOf('{', start + 1)) {
          for (let end = text.lastIndexOf('}'); end > start; end = text.lastIndexOf('}', end - 1)) {
            try {
              return JSON.parse(text.slice(start, end + 1))
            } catch {
              // 尝试下一个大括号范围
            }
          }
        }
        return null
      }
    },
    normalizePsychAnalysis(obj, distillFocus) {
      obj = this.normalizeJointReportObject(obj)
      let clamp = (value, defaultValue = 0.5) => {
        let n = Number(value)
        if (!Number.isFinite(n)) {
          n = defaultValue
        }
        return Math.max(0, Math.min(1, n))
      }
      return {
        stress: clamp(obj.stress),
        valence: clamp(obj.valence),
        fatigue: clamp(obj.fatigue),
        engagement: clamp(obj.engagement),
        confidence: clamp(obj.confidence, 0.3),
        danmakuDistill: this.normalizeDanmakuDistill(obj.danmakuDistill, distillFocus),
        summary: String(obj.summary || '').trim(),
        liveEnvironment: this.normalizeLiveEnvironment(obj.liveEnvironment)
      }
    },
    normalizeJointReportObject(obj) {
      if (!obj || typeof obj !== 'object') {
        return {}
      }
      const psych = obj.psychologicalAnalysis || obj.psychAnalysis || obj.analysis || obj['心理分析'] || obj['��������'] || null
      if (psych && typeof psych === 'object') {
        return {
          ...psych,
          voiceReport: obj.voiceReport || obj['语音观察'] || obj['����۲�'],
          sceneReport: obj.sceneReport || obj['画面场景'] || obj['������']
        }
      }
      return obj
    },
    normalizeLiveEnvironment(environment) {
      let labels = {
        game: '直播游戏中',
        singing: '主播唱歌中',
        video: '观看视频中',
        unknown: '无法判断'
      }
      let clamp = value => {
        let n = Number(value)
        if (!Number.isFinite(n)) {
          n = 0.3
        }
        return Math.max(0, Math.min(1, n))
      }
      let type = environment && labels[environment.type] ? environment.type : 'unknown'
      return {
        type,
        label: labels[type],
        confidence: clamp(environment && environment.confidence),
        evidence: Array.isArray(environment && environment.evidence) ? environment.evidence.slice(0, 3).map(item => String(item)) : []
      }
    },
    fallbackPsychAnalysis(metrics, summary, distillFocus) {
      let textCount = Math.max(metrics.textCount, 1)
      let negRatio = Math.min(metrics.negativeHits / textCount, 1)
      let posRatio = Math.min(metrics.positiveHits / textCount, 1)
      let pressureRatio = Math.min(metrics.pressureHits / textCount, 1)
      return {
        stress: Math.min(0.25 + (negRatio * 0.35) + (pressureRatio * 0.45), 1),
        valence: Math.max(0.15, Math.min(0.85, 0.55 + (posRatio * 0.25) - (negRatio * 0.3))),
        fatigue: Math.min(0.2 + (pressureRatio * 0.35) + (metrics.textPerMinute / 300), 1),
        engagement: Math.min(0.2 + (metrics.textPerMinute / 180) + (metrics.giftCount / 80), 1),
        confidence: 0.2,
        danmakuDistill: this.fallbackDanmakuDistill(metrics, distillFocus),
        summary,
        liveEnvironment: this.fallbackLiveEnvironment(metrics)
      }
    },
    fallbackLiveEnvironment(metrics) {
      let labels = {
        game: '直播游戏中',
        singing: '主播唱歌中',
        video: '观看视频中',
        unknown: '无法判断'
      }
      let hints = Array.isArray(metrics.liveEnvironmentHints) ? metrics.liveEnvironmentHints : []
      let sortedHints = hints.slice().sort((a, b) => b.hits - a.hits)
      let topHint = sortedHints[0]
      let secondHint = sortedHints[1]
      if (!topHint || topHint.hits <= 0 || (secondHint && topHint.hits === secondHint.hits)) {
        return {
          type: 'unknown',
          label: labels.unknown,
          confidence: 0.2,
          evidence: []
        }
      }
      let totalHits = hints.reduce((sum, hint) => sum + hint.hits, 0)
      let confidence = Math.min(0.85, Math.max(0.35, topHint.hits / Math.max(totalHits, 1)))
      return {
        type: topHint.type,
        label: labels[topHint.type] || labels.unknown,
        confidence,
        evidence: Array.isArray(topHint.messages) ? topHint.messages.slice(0, 3) : []
      }
    },
    buildObsAgentMetrics(obsBridgeState) {
      let state = obsBridgeState || this.obsAgent.state || {}
      let latestFrame = state.latestFrame || {}
      let latestAudio = state.latestAudio || {}
      let latestMicAudio = state.latestMicAudio || {}
      let latestDesktopAudio = state.latestDesktopAudio || {}
      let lastEvent = state.lastEvent || {}
      const splitAudioTracks = Boolean(state.splitAudioTracks)
      const activeMicAudio = splitAudioTracks ? latestMicAudio : latestAudio
      const activeDesktopAudio = splitAudioTracks ? latestDesktopAudio : {}
      return {
        connected: Boolean(state.connected),
        monitoringActive: Boolean(this.obsAgent.monitoringActive),
        streamingActive: Boolean(state.streamingActive),
        splitAudioTracks,
        streamStartedAt: Number(state.streamStartedAt || 0),
        streamDurationSeconds: Number(state.streamDurationSeconds || 0),
        lastEventType: lastEvent.type || '',
        lastEventAt: lastEvent.ts || '',
        latestFrameAt: latestFrame.ts || '',
        latestFrameSourceName: latestFrame.sourceName || '',
        latestFramePath: latestFrame.imageFilePath || '',
        latestFrameSummary: latestFrame.summary || '',
        audioLevel: Number(activeMicAudio.level || latestAudio.level || 0),
        audioRms: Number(activeMicAudio.rms || latestAudio.rms || 0),
        audioPeak: Number(activeMicAudio.peak || latestAudio.peak || 0),
        audioTranscript: activeMicAudio.transcript || latestAudio.transcript || '',
        audioAt: activeMicAudio.ts || latestAudio.ts || '',
        desktopAudioLevel: Number(activeDesktopAudio.level || 0),
        desktopAudioRms: Number(activeDesktopAudio.rms || 0),
        desktopAudioPeak: Number(activeDesktopAudio.peak || 0),
        desktopAudioAt: activeDesktopAudio.ts || ''
      }
    },
    resolveLiveStreamDurationText(obsBridgeState) {
      let obsMetrics = this.buildObsAgentMetrics(obsBridgeState)
      if (!obsMetrics.streamingActive) {
        return '未推流'
      }
      return this.formatStreamDuration(obsMetrics.streamDurationSeconds)
    },
    async addPsychSystemMessage(metrics, analysis) {
      let obsBridgeState = await this.fetchObsBridgeState()
      let obsMetrics = this.buildObsAgentMetrics(obsBridgeState)
      let metricsWithObs = {
        ...metrics,
        obs: obsMetrics
      }
      this.psychAgent.analysisCount++
      this.psychAgent.latestPsychAnalysis = {
        ts: new Date().toISOString(),
        metrics: metricsWithObs,
        analysis
      }
      let durationText = this.resolveLiveStreamDurationText(obsBridgeState)
      let distill = analysis.danmakuDistill || { label: '弹幕蒸馏', text: '暂无足够弹幕可提炼' }
      let summary = String(analysis.summary || '').trim() || '状态平稳'
      let danmakuCount = Number((metrics && metrics.textCount) || 0)
      let content = `【心理分析】直播时长: ${durationText} | 弹幕: ${danmakuCount}条 | ${distill.label}: ${distill.text} | 结论: ${summary}`
      this.onAddText(new chatModels.AddTextMsg({
        authorName: 'blivechat',
        authorType: constants.AUTHOR_TYPE_ADMIN,
        content,
        authorLevel: 60,
        id: `psych-${Date.now()}`
      }))
      await this.appendLiveArchiveRecord('mental', content)
      this.emitPsychAgentUpdate()
    },
    reportTotalGiftValue() {
      if (!this.isPsychTabEnabled('gift')) {
        return
      }
      this.psychAgent.latestGiftSummary = {
        ts: new Date().toISOString(),
        totalGiftValue: this.psychAgent.totalGiftValue
      }
      this.emitPsychAgentUpdate()
    },
    emitPsychAgentUpdate() {
      if (window.parent === window) {
        return
      }
      window.parent.postMessage({
        type: 'roomPsychAgentUpdate',
        data: {
          latestPsychAnalysis: this.psychAgent.latestPsychAnalysis,
          latestGiftSummary: this.psychAgent.latestGiftSummary,
          latestVoiceReport: this.psychAgent.latestVoiceReport,
          latestSceneReport: this.psychAgent.latestSceneReport
        }
      }, window.location.origin)
    },
    shouldRunObsMultimodalReport() {
      let state = this.obsAgent.state || {}
      return Boolean(state.streamingActive) && Boolean(this.obsAgent.monitoringActive)
    },
    hasObsAudioReady(state) {
      state = state || this.obsAgent.state || {}
      if (state.splitAudioTracks) {
        let micAudio = state.latestMicAudio || {}
        let desktopAudio = state.latestDesktopAudio || {}
        return Boolean(micAudio.audioFormat || micAudio.durationSeconds)
          && Boolean(desktopAudio.audioFormat || desktopAudio.durationSeconds)
      }
      let latestAudio = state.latestAudio || {}
      return Boolean(latestAudio.audioFormat || latestAudio.durationSeconds)
    },
    async reportObsAudioObservation() {
      if (!this.isPsychTabEnabled('voice') || this.psychAgent.obsAudioReportRunning || !this.shouldRunObsMultimodalReport()) {
        return
      }
      if (!this.hasObsAudioReady()) {
        return
      }
      this.psychAgent.obsAudioReportRunning = true
      try {
        let res = await fetch('/api/qwen/asr-report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        })
        let data = await res.json()
        if (!data.success) {
          throw new Error(data.error || 'Qwen ASR report failed')
        }
        let tokenUsage = this.recordPsychTokenUsage(data.usage)
        let report = data.report || {}
        this.psychAgent.latestVoiceReport = {
          ts: new Date().toISOString(),
          report,
          usage: tokenUsage
        }
        let obsBridgeState = await this.fetchObsBridgeState()
        let durationText = this.resolveLiveStreamDurationText(obsBridgeState)
        let content = this.formatVoiceReportContent(report, durationText)
        this.onAddText(new chatModels.AddTextMsg({
          authorName: 'blivechat',
          authorType: constants.AUTHOR_TYPE_ADMIN,
          content,
          authorLevel: 60,
          id: `voice-${Date.now()}`
        }))
        await this.appendLiveArchiveRecord('voice', content)
        this.emitPsychAgentUpdate()
      } catch (e) {
        console.warn('OBS audio report failed:', e)
      } finally {
        this.psychAgent.obsAudioReportRunning = false
      }
    },
    async reportObsVisionScene() {
      if (!this.isPsychTabEnabled('scene') || this.psychAgent.obsVisionReportRunning || !this.shouldRunObsMultimodalReport()) {
        return
      }
      let latestFrame = (this.obsAgent.state && this.obsAgent.state.latestFrame) || {}
      if (!latestFrame.imageFilePath && !latestFrame.summary && !latestFrame.ts) {
        return
      }
      this.psychAgent.obsVisionReportRunning = true
      try {
        let res = await fetch('/api/qwen/vision-report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        })
        let data = await res.json()
        if (!data.success) {
          throw new Error(data.error || 'Qwen vision report failed')
        }
        let tokenUsage = this.recordPsychTokenUsage(data.usage)
        let report = data.report || {}
        this.psychAgent.latestSceneReport = {
          ts: new Date().toISOString(),
          report,
          usage: tokenUsage
        }
        let obsBridgeState = await this.fetchObsBridgeState()
        let durationText = this.resolveLiveStreamDurationText(obsBridgeState)
        let content = this.formatSceneReportContent(report, durationText)
        this.onAddText(new chatModels.AddTextMsg({
          authorName: 'blivechat',
          authorType: constants.AUTHOR_TYPE_ADMIN,
          content,
          authorLevel: 60,
          id: `scene-${Date.now()}`
        }))
        await this.appendLiveArchiveRecord('picture', content)
      } catch (e) {
        console.warn('OBS vision report failed:', e)
      } finally {
        this.psychAgent.obsVisionReportRunning = false
      }
    },
    resetLiveArchiveSession() {
      this.liveArchive.streamStartedAt = 0
      this.liveArchive.sessionReady = false
    },
    async tryInitLiveArchiveSession() {
      let obsBridgeState = await this.fetchObsBridgeState()
      if (!obsBridgeState || !obsBridgeState.streamingActive) {
        return false
      }
      let streamStartedAt = Number(obsBridgeState.streamStartedAt || 0)
      if (streamStartedAt <= 0) {
        return false
      }
      return this.ensureLiveArchiveSession(streamStartedAt)
    },
    async ensureLiveArchiveSession(streamStartedAt) {
      let startedAt = Number(streamStartedAt || 0)
      if (startedAt <= 0) {
        return false
      }
      if (this.liveArchive.sessionReady && this.liveArchive.streamStartedAt === startedAt) {
        return true
      }
      try {
        let res = await fetch('/api/live/archive/init', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            roomId: this.getPsychRoomId(),
            streamStartedAt: startedAt
          })
        })
        let data = await res.json()
        if (!data.success) {
          throw new Error(data.error || 'init live archive failed')
        }
        this.liveArchive.streamStartedAt = startedAt
        this.liveArchive.sessionReady = true
        return true
      } catch (e) {
        console.warn('Init live archive session failed:', e)
        return false
      }
    },
    getCurrentStreamDurationSeconds() {
      let fromObs = Number(this.obsAgent.state.streamDurationSeconds || 0)
      if (fromObs > 0) {
        return fromObs
      }
      let streamStartedAt = Number(
        this.streamSession.streamStartedAt
        || this.liveArchive.streamStartedAt
        || this.obsAgent.state.streamStartedAt
        || 0
      )
      if (streamStartedAt > 0) {
        return Math.max(0, Math.floor(Date.now() / 1000) - streamStartedAt)
      }
      return 0
    },
    formatGiftReceivedTime(timestamp) {
      let ts = Number(timestamp || 0)
      if (ts <= 0) {
        ts = Math.floor(Date.now() / 1000)
      }
      let date = new Date(ts * 1000)
      let pad = n => String(n).padStart(2, '0')
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    },
    formatGiftArchiveLine(payload) {
      let receivedAt = this.formatGiftReceivedTime(payload.timestamp)
      let streamDuration = this.formatStreamDuration(this.getCurrentStreamDurationSeconds())
      let amountText = this.formatGiftValue(payload.amount)
      let parts = [
        `[${receivedAt}]`,
        `直播时长: ${streamDuration}`,
        `用户: ${payload.authorName || '未知用户'}`,
        `金额: ${amountText}`,
      ]
      if (payload.type === 'super_chat') {
        parts.push('类型: SuperChat')
        let content = String(payload.content || '').trim()
        if (content !== '') {
          parts.push(`内容: ${content}`)
        }
      } else {
        let giftName = String(payload.giftName || '未知礼物').trim()
        let num = Math.max(Number(payload.num || 1), 1)
        parts.push(`礼物: ${giftName}${num > 1 ? ` x${num}` : ''}`)
      }
      return parts.join(' | ')
    },
    appendGiftArchiveRecord(payload) {
      let content = this.formatGiftArchiveLine(payload)
      this.appendLiveArchiveRecord('gift', content).catch(() => {})
    },
    async appendLiveArchiveRecord(category, content) {
      let text = String(content || '').trim()
      if (text === '') {
        return
      }
      let streamStartedAt = Number(
        this.streamSession.streamStartedAt
        || this.liveArchive.streamStartedAt
        || 0
      )
      if (streamStartedAt <= 0) {
        let obsBridgeState = await this.fetchObsBridgeState()
        streamStartedAt = Number(
          (obsBridgeState && obsBridgeState.streamStartedAt)
          || (obsBridgeState && obsBridgeState.lastStreamStartedAt)
          || 0
        )
      }
      if (streamStartedAt <= 0) {
        return
      }
      if (!await this.ensureLiveArchiveSession(streamStartedAt)) {
        return
      }
      try {
        let res = await fetch('/api/live/archive/append', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            roomId: this.getPsychRoomId(),
            streamStartedAt,
            category,
            content: text
          })
        })
        let data = await res.json()
        if (!data.success) {
          throw new Error(data.error || 'append live archive failed')
        }
      } catch (e) {
        console.warn('Append live archive failed:', e)
      }
    },
    formatVoiceReportContent(report, durationText = '未推流') {
      let soundType = String((report && report.soundType) || '-')
      let activity = String((report && report.activity) || '-')
      let psychologicalState = String((report && report.psychologicalState) || '-')
      let summary = String((report && report.summary) || '-')
      return `【语音观察】直播时长: ${durationText} | 声音: ${soundType} | 活动: ${activity} | 状态: ${psychologicalState} | 结论: ${summary}`
    },
    formatSceneReportContent(report, durationText = '未推流') {
      let category = String((report && report.category) || '-')
      let summary = String((report && report.summary) || '-')
      return `【画面场景】直播时长: ${durationText} | 场景: ${category} | 结论: ${summary}`
    },
    exportDanmakuArchive() {
      let roomId = this.getPsychRoomId()
      let timestamp = this.formatArchiveTimestamp(new Date())
      let payload = {
        roomId,
        exportedAt: new Date().toISOString(),
        count: this.psychAgent.allDanmaku.length,
        danmaku: this.psychAgent.allDanmaku
      }
      let blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
      let url = URL.createObjectURL(blob)
      let link = document.createElement('a')
      link.href = url
      link.download = `${roomId}_${timestamp}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    },
    getPsychRoomId() {
      if (this.roomKeyValue !== null && this.roomKeyValue !== undefined && this.roomKeyValue !== '') {
        return String(this.roomKeyValue).replace(/[^\w-]/g, '_')
      }
      return 'test_room'
    },
    formatArchiveTimestamp(date) {
      let pad = n => String(n).padStart(2, '0')
      return `${[
        date.getFullYear(),
        pad(date.getMonth() + 1),
        pad(date.getDate())
      ].join('')}_${[
        pad(date.getHours()),
        pad(date.getMinutes()),
        pad(date.getSeconds())
      ].join('')}`
    },
    formatGiftValue(value) {
      return `${Number(value || 0).toFixed(2)} 元`
    },
    toPanelPercent(value) {
      let n = Number(value)
      if (!Number.isFinite(n)) {
        n = 0
      }
      return `${(Math.max(0, Math.min(1, n)) * 100).toFixed(0)}%`
    },
    formatPanelTime(ts) {
      if (!ts) {
        return '-'
      }
      let date = new Date(ts)
      if (!Number.isNaN(date.getTime())) {
        return date.toLocaleTimeString('zh-CN', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        })
      }
      let matched = String(ts).match(/(\d{2}:\d{2}:\d{2})/)
      return matched ? matched[1] : String(ts)
    },
    truncateReportText(text, maxLength) {
      text = String(text || '').trim()
      if (text.length <= maxLength) {
        return text
      }
      return `${text.slice(0, maxLength)}...`
    },
    toObjIfJson(str) {
      if (typeof str !== 'string') {
        return str
      }
      try {
        return JSON.parse(str)
      } catch {
        return {}
      }
    },
    async initChatClient() {
      if (this.roomKeyValue === null) {
        let ChatClientTest = (await import('@/api/chat/ChatClientTest')).default
        this.chatClient = new ChatClientTest()
      } else if (this.config.relayMessagesByServer) {
        let roomKey = {
          type: this.roomKeyType,
          value: this.roomKeyValue
        }
        let ChatClientRelay = (await import('@/api/chat/ChatClientRelay')).default
        this.chatClient = new ChatClientRelay(roomKey, this.config.autoTranslate)
      } else {
        if (this.roomKeyType === 1) {
          let ChatClientDirectWeb = (await import('@/api/chat/ChatClientDirectWeb')).default
          this.chatClient = new ChatClientDirectWeb(this.roomKeyValue)
        } else {
          let ChatClientDirectOpenLive = (await import('@/api/chat/ChatClientDirectOpenLive')).default
          this.chatClient = new ChatClientDirectOpenLive(this.roomKeyValue)
        }
      }

      this.chatClient.msgHandler = this
      this.chatClient.start()
    },
    async initTextEmoticons() {
      this.textEmoticons = await chat.getTextEmoticons()
    },

    sendMessageToStylegen(type, data = null) {
      if (window.parent === window) {
        return
      }
      let msg = { type, data }
      window.parent.postMessage(msg, window.location.origin)
    },
    // 处理样式生成器发送的消息
    onWindowMessage(event) {
      if (event.source !== window.parent) {
        return
      }
      if (event.origin !== window.location.origin) {
        console.warn(`消息origin错误，${event.origin} != ${window.location.origin}`)
        return
      }

      let { type, data } = event.data
      switch (type) {
      case 'roomSetCustomStyle':
        this.customStyleElement.textContent = data.css
        break
      case 'roomStartClient':
        if (this.chatClient) {
          this.chatClient.start()
        }
        break
      case 'roomStopClient':
        if (this.chatClient) {
          this.chatClient.stop()
        }
        break
      case 'roomSetPsychTabConfig':
        this.applyPsychTabConfig(data)
        break
      }
    },

    /** @param {chatModels.AddTextMsg} data */
    onAddText(data) {
      this.recordPsychText(data)
      let promise = this.doOnAddText(data).catch(() => {})
      let id = data.id
      this.pendingMsgIdToPromise.set(id, promise)
      promise.finally(() => {
        this.pendingMsgIdToPromise.delete(id)
      })
    },
    // 保证渲染器收到消息了
    async ensureMessageSent(id) {
      let promise = this.pendingMsgIdToPromise.get(id)
      if (promise !== undefined) {
        return promise
      }
    },
    /** @param {chatModels.AddTextMsg} data */
    async doOnAddText(data) {
      if (!this.config.showDanmaku || !this.filterTextMessage(data)) {
        return
      }
      let contentParts = await this.parseContentParts(data)
      // 合并要放在异步调用后面，因为异步调用后可能有新的消息，会漏合并
      if (this.mergeSimilarText(data.content)) {
        return
      }
      /** @type {typeof blcsdk.TextMsg} */
      let message = {
        id: data.id,
        type: constants.MESSAGE_TYPE_TEXT,
        avatarUrl: data.avatarUrl,
        time: new Date(data.timestamp * 1000),
        authorName: data.authorName,
        authorType: data.authorType,
        content: data.content,
        contentParts: contentParts,
        privilegeType: data.privilegeType,
        repeated: 1,
        translation: this.config.autoTranslate ? data.translation : '',
        isMirror: data.isMirror,
        // 给模板用的字段
        uid: data.uid,
        medalLevel: data.medalLevel,
        medalName: data.medalName,
      }
      this.renderer.addMessage(message)
    },
    /** @param {chatModels.AddGiftMsg} data */
    onAddGift(data) {
      this.recordPsychGift(data)
      this.appendGiftArchiveRecord({
        type: 'gift',
        timestamp: data.timestamp,
        authorName: data.authorName,
        amount: Math.max(data.totalCoin || 0, 0) / 1000,
        giftName: data.giftName,
        num: data.num || 1,
      })
      if (!this.config.showGift) {
        return
      }
      let price = data.totalCoin / 1000
      if (this.mergeSimilarGift(data.authorName, price, data.totalFreeCoin, data.giftName, data.num)) {
        return
      }
      if (price < this.config.minGiftPrice) { // 丢人
        return
      }
      /** @type {typeof blcsdk.GiftMsg} */
      let message = {
        id: data.id,
        type: constants.MESSAGE_TYPE_GIFT,
        avatarUrl: data.avatarUrl,
        time: new Date(data.timestamp * 1000),
        authorName: data.authorName,
        authorNamePronunciation: this.getPronunciation(data.authorName),
        price: price,
        giftName: data.giftName,
        num: data.num,
        // 给模板用的字段
        totalFreeCoin: data.totalFreeCoin,
        giftId: data.giftId,
        giftIconUrl: data.giftIconUrl,
        uid: data.uid,
        privilegeType: data.privilegeType,
        medalLevel: data.medalLevel,
        medalName: data.medalName,
      }
      this.renderer.addMessage(message)
    },
    /** @param {chatModels.AddMemberMsg} data */
    onAddMember(data) {
      this.recordPsychMember(data)
      if (!this.config.showGift || !this.filterNewMemberMessage(data)) {
        return
      }
      /** @type {typeof blcsdk.MemberMsg} */
      let message = {
        id: data.id,
        type: constants.MESSAGE_TYPE_MEMBER,
        avatarUrl: data.avatarUrl,
        time: new Date(data.timestamp * 1000),
        authorName: data.authorName,
        authorNamePronunciation: this.getPronunciation(data.authorName),
        privilegeType: data.privilegeType,
        title: this.$t('chat.membershipTitle'),
        // 给模板用的字段
        num: data.num,
        unit: data.unit,
        price: data.totalCoin / 1000,
        uid: data.uid,
        medalLevel: data.medalLevel,
        medalName: data.medalName,
      }
      this.renderer.addMessage(message)
    },
    /** @param {chatModels.AddSuperChatMsg} data */
    onAddSuperChat(data) {
      this.recordPsychSuperChat(data)
      this.appendGiftArchiveRecord({
        type: 'super_chat',
        timestamp: data.timestamp,
        authorName: data.authorName,
        amount: Math.max(Number(data.price || 0), 0),
        content: data.content,
      })
      if (!this.config.showGift || !this.filterSuperChatMessage(data)) {
        return
      }
      if (data.price < this.config.minGiftPrice) { // 丢人
        return
      }
      /** @type {typeof blcsdk.SuperChatMsg} */
      let message = {
        id: data.id,
        type: constants.MESSAGE_TYPE_SUPER_CHAT,
        avatarUrl: data.avatarUrl,
        authorName: data.authorName,
        authorNamePronunciation: this.getPronunciation(data.authorName),
        price: data.price,
        time: new Date(data.timestamp * 1000),
        content: data.content.trim(),
        translation: this.config.autoTranslate ? data.translation : '',
        // 给模板用的字段
        uid: data.uid,
        privilegeType: data.privilegeType,
        medalLevel: data.medalLevel,
        medalName: data.medalName,
      }
      this.renderer.addMessage(message)
    },
    /** @param {chatModels.DelSuperChatMsg} data */
    async onDelSuperChat(data) {
      await Promise.all(data.ids.map(this.ensureMessageSent))
      this.renderer.delMessages(data.ids)
    },
    /** @param {chatModels.UpdateTranslationMsg} data */
    async onUpdateTranslation(data) {
      if (!this.config.autoTranslate) {
        return
      }
      await this.ensureMessageSent(data.id)
      this.renderer.updateMessage(data.id, { translation: data.translation })
    },
    /** @param {chatModels.ChatClientFatalError} error */
    onFatalError(error) {
      this.$message.error({
        message: error.toString(),
        duration: 30 * 1000
      })
      this.onAddText(new chatModels.AddTextMsg({
        authorName: 'blivechat',
        authorType: constants.AUTHOR_TYPE_ADMIN,
        content: this.$t('room.fatalErrorOccurred'),
        authorLevel: 60,
      }))

      if (error.type === chatModels.FATAL_ERROR_TYPE_AUTH_CODE_ERROR) {
        // Read The Fucking Manual
        this.$router.push({ name: 'help' })
      }
    },
    /** @param {chatModels.DebugMsg} data */
    onDebugMsg(data) {
      if (!this.config.showDebugMessages) {
        return
      }
      this.onAddText(new chatModels.AddTextMsg({
        authorName: 'blivechat',
        authorType: constants.AUTHOR_TYPE_ADMIN,
        content: data.content,
        authorLevel: 60,
      }))
    },

    filterTextMessage(data) {
      if (this.config.blockGiftDanmaku && data.isGiftDanmaku) {
        return false
      } else if (this.config.blockMirrorMessages && data.isMirror) {
        return false
      } else if (this.config.blockLevel > 0 && data.authorLevel < this.config.blockLevel) {
        return false
      } else if (this.config.blockNewbie && data.isNewbie) {
        return false
      } else if (this.config.blockNotMobileVerified && !data.isMobileVerified) {
        return false
      } else if (this.config.blockMedalLevel > 0 && data.medalLevel < this.config.blockMedalLevel) {
        return false
      }
      return this.filterByContent(data.content) && this.filterByAuthorName(data.authorName)
    },
    filterSuperChatMessage(data) {
      return this.filterByContent(data.content) && this.filterByAuthorName(data.authorName)
    },
    filterNewMemberMessage(data) {
      return this.filterByAuthorName(data.authorName)
    },
    filterByContent(content) {
      let blockKeywordsTrie = this.blockKeywordsTrie
      for (let i = 0; i < content.length; i++) {
        let remainContent = content.substring(i)
        if (blockKeywordsTrie.lazyMatch(remainContent) !== null) {
          return false
        }
      }
      return true
    },
    filterByAuthorName(authorName) {
      return !this.blockUsersSet.has(authorName)
    },
    mergeSimilarText(content) {
      if (!this.config.mergeSimilarDanmaku) {
        return false
      }
      return this.renderer.mergeSimilarText(content)
    },
    mergeSimilarGift(authorName, price, freePrice, giftName, num) {
      if (!this.config.mergeGift) {
        return false
      }
      return this.renderer.mergeSimilarGift(authorName, price, freePrice, giftName, num)
    },
    getPronunciation(text) {
      if (this.pronunciationConverter === null) {
        return ''
      }
      return this.pronunciationConverter.getPronunciation(text)
    },
    async parseContentParts(data) {
      let contentParts = []

      // 官方的非文本表情
      if (data.emoticon !== null) {
        contentParts.push({
          type: constants.CONTENT_PART_TYPE_IMAGE,
          text: data.content,
          url: data.emoticon,
          width: 0,
          height: 0
        })
        await this.fillImageContentSizes(contentParts)
        return contentParts
      }

      // 没有文本表情，只能是纯文本
      if (this.config.emoticons.length === 0 && this.textEmoticons.length === 0) {
        contentParts.push({
          type: constants.CONTENT_PART_TYPE_TEXT,
          text: data.content
        })
        return contentParts
      }

      // 可能含有文本表情，需要解析
      let emoticonsTrie = this.emoticonsTrie
      let startPos = 0
      let pos = 0
      while (pos < data.content.length) {
        let remainContent = data.content.substring(pos)
        let matchEmoticon = emoticonsTrie.lazyMatch(remainContent)
        if (matchEmoticon === null) {
          pos++
          continue
        }

        // 加入之前的文本
        if (pos !== startPos) {
          contentParts.push({
            type: constants.CONTENT_PART_TYPE_TEXT,
            text: data.content.slice(startPos, pos)
          })
        }

        // 加入表情
        contentParts.push({
          type: constants.CONTENT_PART_TYPE_IMAGE,
          text: matchEmoticon.keyword,
          url: matchEmoticon.url,
          width: 0,
          height: 0
        })
        pos += matchEmoticon.keyword.length
        startPos = pos
      }
      // 加入尾部的文本
      if (pos !== startPos) {
        contentParts.push({
          type: constants.CONTENT_PART_TYPE_TEXT,
          text: data.content.slice(startPos, pos)
        })
      }

      await this.fillImageContentSizes(contentParts)
      return contentParts
    },
    async fillImageContentSizes(contentParts) {
      let urlSizeMap = new Map()
      for (let content of contentParts) {
        if (content.type === constants.CONTENT_PART_TYPE_IMAGE) {
          urlSizeMap.set(content.url, { width: 0, height: 0 })
        }
      }
      if (urlSizeMap.size === 0) {
        return
      }

      let promises = []
      for (let url of urlSizeMap.keys()) {
        let urlInClosure = url
        promises.push(new Promise(
          resolve => {
            let img = document.createElement('img')
            img.onload = () => {
              let size = urlSizeMap.get(urlInClosure)
              size.width = img.naturalWidth
              size.height = img.naturalHeight
              resolve()
            }
            // 获取失败了默认为0
            img.onerror = resolve
            // 超时保底
            window.setTimeout(resolve, 5000)
            img.src = urlInClosure
          }
        ))
      }
      await Promise.all(promises)

      for (let content of contentParts) {
        if (content.type === constants.CONTENT_PART_TYPE_IMAGE) {
          let size = urlSizeMap.get(content.url)
          content.width = size.width
          content.height = size.height
        }
      }
    }
  }
}
</script>

<style scoped>
.room-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 230px;
  gap: 8px;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.room-main {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.room-side-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  max-height: 100%;
  overflow: hidden;
  padding: 6px;
  box-sizing: border-box;
  color: #312b4b;
  font-size: 12px;
}

.side-section {
  flex: 0 1 24%;
  min-height: 0;
  padding: 7px 8px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(121, 100, 230, 0.16);
  box-shadow: 0 4px 16px rgba(49, 43, 75, 0.08);
  overflow: hidden;
}

.side-section--disabled {
  flex: 0 0 auto;
  padding: 5px 8px;
  opacity: 0.48;
}

.side-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 5px;
}

.side-section--disabled .side-section__header {
  margin-bottom: 0;
}

.side-section__title {
  font-weight: 700;
  color: #312b4b;
  white-space: nowrap;
}

.side-section__status {
  color: #7964e6;
  font-size: 11px;
  white-space: nowrap;
}

.side-section__body {
  overflow: hidden;
}

.side-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  line-height: 1.45;
}

.side-row__label {
  color: #7c7694;
  white-space: nowrap;
}

.side-row__value {
  color: #312b4b;
  font-weight: 600;
  text-align: right;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.side-summary {
  margin: 4px 0 0;
  color: #5b5378;
  line-height: 1.35;
  display: -webkit-box;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.template-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.template-iframe {
  width: 100%;
  height: 100%;
}
</style>

<style>
/* 前端浏览器窗口全局样式适配 (Apple 紫色调风格) */
:root {
  --yt-live-chat-background-color: transparent !important;
  --yt-live-chat-primary-text-color: #312b4b !important;
  --yt-live-chat-secondary-text-color: #7c7694 !important;
  --yt-live-chat-tertiary-text-color: #a0a0bd !important;
  --yt-live-chat-text-input-field-placeholder-color: #b0aec5 !important;
  --yt-live-chat-author-name-color: #7c7694 !important;
  --yt-live-chat-message-color: #312b4b !important;
  
  /* 紫色主题色 */
  --yt-live-chat-sponsor-color: #7964e6 !important;
  --yt-live-chat-moderator-color: #9c89ff !important;
  --yt-live-chat-owner-color: #7964e6 !important;
}

/* 弹幕容器圆角矩形风格 */
yt-live-chat-text-message-renderer {
  padding: 8px 16px !important;
  margin: 4px 8px !important;
  background-color: rgba(255, 255, 255, 0.85) !important;
  border-radius: 12px !important;
  box-shadow: 0 2px 8px rgba(121, 100, 230, 0.05) !important;
  border: 1px solid rgba(121, 100, 230, 0.1) !important;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

yt-live-chat-text-message-renderer:hover {
  transform: scale(1.02) !important;
  background-color: rgba(255, 255, 255, 0.95) !important;
}

/* 顶部礼物/SC 轨道圆角 */
#ticker.yt-live-chat-renderer {
  background-color: rgba(246, 244, 255, 0.9) !important;
  border-bottom: none !important;
  padding: 4px 0 !important;
}

yt-live-chat-ticker-paid-message-item-renderer {
  border-radius: 10px !important;
  overflow: hidden !important;
  margin: 0 4px !important;
}

/* 头像圆角 */
#author-photo.yt-live-chat-text-message-renderer,
#author-photo.yt-live-chat-paid-message-renderer {
  border-radius: 50% !important;
  border: 2px solid #fff !important;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
}

/* 滚动条 Apple 风格 */
::-webkit-scrollbar {
  width: 6px !important;
}

::-webkit-scrollbar-thumb {
  background: rgba(121, 100, 230, 0.2) !important;
  border-radius: 10px !important;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(121, 100, 230, 0.4) !important;
}

/* SC 消息圆角风格 */
yt-live-chat-paid-message-renderer {
  margin: 8px !important;
  border-radius: 16px !important;
  overflow: hidden !important;
  box-shadow: 0 4px 12px rgba(121, 100, 230, 0.1) !important;
}

#header.yt-live-chat-paid-message-renderer {
  background-color: #7964e6 !important;
}

#content.yt-live-chat-paid-message-renderer {
  background-color: #f9f8ff !important;
}

/* 隐藏不必要的分割线 */
#separator.yt-live-chat-renderer {
  display: none !important;
}
</style>
