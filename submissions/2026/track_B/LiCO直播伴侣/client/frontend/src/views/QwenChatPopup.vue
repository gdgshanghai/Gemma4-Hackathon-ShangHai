<template>
  <div class="popup-root">
    <div class="popup-header">
      <span class="popup-title">千问 AI 对话</span>
      <span :class="['status-dot', apiConfigured ? 'ok' : 'warn']"></span>
      <span class="status-text">{{ apiConfigured ? 'API 已就绪' : 'API 未配置' }}</span>
      <button class="clear-btn" @click="clearMessages" title="清空对话">清空</button>
    </div>

    <div v-if="!apiConfigured" class="unconfigured">
      <p>加载中，请稍等...</p>
    </div>

    <div v-else class="chat-body">
      <div class="messages" ref="messages">
        <template v-for="(msg, i) in messages">
          <div :key="i" :class="['bubble-row', msg.role]">
            <div class="bubble">
              <div class="bubble-text">{{ msg.content }}</div>
              <div class="bubble-time">{{ msg.time }}</div>
            </div>
          </div>
        </template>
        <div v-if="isLoading" class="bubble-row assistant">
          <div class="bubble loading-bubble">
            <span class="loading-text">加载中，请稍等...</span>
          </div>
        </div>
      </div>

      <div class="input-bar">
        <textarea
          v-model="inputMessage"
          class="input-textarea"
          placeholder="输入消息，Ctrl+Enter 发送…"
          @keydown.enter.ctrl.prevent="sendMessage"
          rows="3"
        ></textarea>
        <button
          class="send-btn"
          :disabled="!inputMessage.trim() || isLoading"
          @click="sendMessage"
        >
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'QwenChatPopup',
  data() {
    return {
      apiConfigured: false,
      messages: [],
      inputMessage: '',
      isLoading: false
    }
  },
  mounted() {
    this.checkApiConfiguration()
  },
  methods: {
    async checkApiConfiguration() {
      try {
        const res = await fetch('/api/qwen/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: 'ping', history: [] })
        })
        const data = await res.json()
        this.apiConfigured = !(data.error && data.error.includes('未配置'))
      } catch {
        this.apiConfigured = true
      }
    },

    async sendMessage() {
      const text = this.inputMessage.trim()
      if (!text || this.isLoading) {
        return
      }

      this.messages.push({ role: 'user', content: text, time: this.now() })
      this.inputMessage = ''
      this.isLoading = true
      this.$nextTick(() => this.scrollToBottom())

      try {
        const history = this.messages
          .slice(-11, -1)
          .map(m => ({ role: m.role, content: m.content }))

        const res = await fetch('/api/qwen/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, history })
        })
        const data = await res.json()
        if (!data.success) {
          throw new Error(data.error || '调用失败')
        }

        this.messages.push({ role: 'assistant', content: data.response, time: this.now() })
      } catch (e) {
        this.messages.push({
          role: 'assistant',
          content: `出错了：${e.message}`,
          time: this.now()
        })
      } finally {
        this.isLoading = false
        this.$nextTick(() => this.scrollToBottom())
      }
    },

    clearMessages() {
      if (this.messages.length === 0) {
        return
      }
      if (window.confirm('确定要清空所有对话记录吗？')) {
        this.messages = []
      }
    },

    now() {
      const d = new Date()
      return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    },

    scrollToBottom() {
      const el = this.$refs.messages
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    }
  }
}
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

html, body, #app {
  height: 100%;
  background: #f5f6f7;
}

body {
  font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
</style>

<style scoped>
.popup-root {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f6f7;
  color: #333;
}

/* ── Header ── */
.popup-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #e4e6e9;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.popup-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a73e8;
  flex: 1;
  letter-spacing: 0.3px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.ok   { background: #34a853; box-shadow: 0 0 5px rgba(52,168,83,0.5); }
.status-dot.warn { background: #fbbc04; box-shadow: 0 0 5px rgba(251,188,4,0.5); }

.status-text {
  font-size: 12px;
  color: #888;
}

.clear-btn {
  background: none;
  border: 1px solid #ddd;
  color: #888;
  padding: 3px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all .2s;
}
.clear-btn:hover {
  border-color: #1a73e8;
  color: #1a73e8;
}

/* ── Unconfigured notice ── */
.unconfigured {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 32px;
  color: #666;
  text-align: center;
}
.unconfigured code {
  color: #d93025;
  background: #fce8e6;
  padding: 2px 6px;
  border-radius: 3px;
}
.unconfigured pre {
  background: #f8f9fa;
  border: 1px solid #e4e6e9;
  border-radius: 6px;
  padding: 12px 16px;
  font-size: 13px;
  color: #444;
  text-align: left;
  line-height: 1.7;
}

/* ── Chat body ── */
.chat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f5f6f7;
}

/* scrollbar */
.messages::-webkit-scrollbar { width: 4px; }
.messages::-webkit-scrollbar-track { background: transparent; }
.messages::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }
.messages::-webkit-scrollbar-thumb:hover { background: #aaa; }

/* ── Bubbles ── */
.bubble-row {
  display: flex;
}
.bubble-row.user      { justify-content: flex-end; }
.bubble-row.assistant { justify-content: flex-start; }

.bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 14px;
  line-height: 1.6;
  font-size: 14px;
  word-break: break-word;
  white-space: pre-wrap;
}

.bubble-row.user .bubble {
  background: #1a73e8;
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 1px 4px rgba(26,115,232,0.25);
}

.bubble-row.assistant .bubble {
  background: #fff;
  color: #333;
  border: 1px solid #e4e6e9;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.bubble-time {
  font-size: 10px;
  margin-top: 4px;
  opacity: 0.45;
  text-align: right;
}

/* ── Loading text ── */
.loading-bubble {
  background: #fff;
  border: 1px solid #e4e6e9;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.loading-text {
  font-size: 13px;
  color: #888;
  font-style: italic;
}

/* ── Input bar ── */
.input-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #e4e6e9;
  flex-shrink: 0;
  box-shadow: 0 -1px 3px rgba(0,0,0,0.04);
}

.input-textarea {
  flex: 1;
  resize: none;
  background: #f8f9fa;
  border: 1px solid #e4e6e9;
  border-radius: 8px;
  color: #333;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color .2s, box-shadow .2s;
  line-height: 1.5;
}
.input-textarea:focus {
  border-color: #1a73e8;
  box-shadow: 0 0 0 3px rgba(26,115,232,0.12);
  background: #fff;
}
.input-textarea::placeholder {
  color: #bbb;
}

.send-btn {
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 0 20px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background .2s, transform .1s, box-shadow .2s;
  align-self: flex-end;
  height: 40px;
  box-shadow: 0 1px 4px rgba(26,115,232,0.3);
}
.send-btn:hover:not(:disabled) {
  background: #1557b0;
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(26,115,232,0.35);
}
.send-btn:disabled {
  background: #e8eaed;
  cursor: not-allowed;
  color: #aaa;
  box-shadow: none;
}
</style>
