import { ensureBaseUrlInited, getBaseUrl } from '@/api/base'

export async function fetchObsBridgeState() {
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
}

export function createEmptyObsAgentState() {
  return {
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
}

export class ObsAgentConnection {
  constructor(onStateChange) {
    this.onStateChange = onStateChange
    this.websocket = null
    this.reconnectTimerId = null
    this.shouldReconnect = false
    this.state = createEmptyObsAgentState()
  }

  start() {
    if (this.websocket !== null || this.reconnectTimerId !== null) {
      return
    }
    this.shouldReconnect = true
    this.connectObsAgent()
  }

  stop() {
    this.shouldReconnect = false
    if (this.reconnectTimerId !== null) {
      window.clearTimeout(this.reconnectTimerId)
      this.reconnectTimerId = null
    }
    if (this.websocket !== null) {
      this.websocket.onopen = null
      this.websocket.onmessage = null
      this.websocket.onclose = null
      this.websocket.close()
      this.websocket = null
    }
  }

  async connectObsAgent() {
    if (!this.shouldReconnect) {
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
      this.websocket = websocket
      websocket.onopen = () => {
        this.updateObsAgentState({ connected: true })
      }
      websocket.onmessage = this.onObsAgentMessage.bind(this)
      websocket.onclose = this.onObsAgentClose.bind(this)
    } catch (e) {
      console.warn('OBS agent connect failed:', e)
      this.scheduleObsAgentReconnect()
    }
  }

  onObsAgentClose() {
    this.websocket = null
    this.updateObsAgentState({ connected: false })
    this.scheduleObsAgentReconnect()
  }

  scheduleObsAgentReconnect() {
    if (!this.shouldReconnect || this.reconnectTimerId !== null) {
      return
    }
    this.reconnectTimerId = window.setTimeout(() => {
      this.reconnectTimerId = null
      this.connectObsAgent()
    }, 3000)
  }

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
  }

  updateObsAgentState(nextState) {
    this.state = { ...this.state, ...nextState }
    if (typeof this.onStateChange === 'function') {
      this.onStateChange(this.state)
    }
  }

  async refreshFromHttp() {
    let bridgeState = await fetchObsBridgeState()
    if (!bridgeState) {
      return this.state
    }
    this.updateObsAgentState({
      connected: Boolean(bridgeState.connected),
      streamingActive: Boolean(bridgeState.streamingActive),
      splitAudioTracks: Boolean(bridgeState.splitAudioTracks),
      streamStartedAt: Number(bridgeState.streamStartedAt || 0),
      streamDurationSeconds: Number(bridgeState.streamDurationSeconds || 0),
      recordingFilePath: String(bridgeState.recordingFilePath || ''),
      lastEvent: bridgeState.lastEvent || null,
      latestFrame: bridgeState.latestFrame || null,
      latestAudio: bridgeState.latestAudio || null,
      latestMicAudio: bridgeState.latestMicAudio || null,
      latestDesktopAudio: bridgeState.latestDesktopAudio || null,
      updatedAt: bridgeState.updatedAt || null
    })
    return this.state
  }
}
