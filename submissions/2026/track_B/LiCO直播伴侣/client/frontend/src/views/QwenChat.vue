<template>
  <div class="qwen-chat-container">
    <el-card>
      <div slot="header">
        <span>千问AI对话</span>
        <el-button
          size="small"
          style="float: right; margin-left: 8px"
          icon="el-icon-top-right"
          @click="openPopup"
        >
          弹窗模式
        </el-button>
        <el-tag
          v-if="apiConfigured"
          type="success"
          size="small"
          style="float: right"
        >
          API已配置
        </el-tag>
        <el-tag
          v-else
          type="warning"
          size="small"
          style="float: right"
        >
          API未配置
        </el-tag>
      </div>

      <div v-if="!apiConfigured" class="auth-section">
        <el-alert
          title="请先配置千问AI"
          type="warning"
          :closable="false"
          show-icon
        >
          <div>请在服务端配置文件（开发环境 <code>data/config.ini</code>，安装版 <code>%ProgramData%\blivechat\data\config.ini</code>）中添加千问 API 密钥：</div>
          <pre style="margin-top: 10px; background: #f5f5f5; padding: 10px; border-radius: 4px;">
[qwen]
api_key = 你的DASHSCOPE_API_KEY
base_url = https://dashscope.aliyuncs.com/compatible-mode/v1
model = qwen-turbo</pre>
        </el-alert>
      </div>

      <div v-else class="chat-section">
        <div class="messages-container" ref="messagesContainer">
          <div
            v-for="(msg, index) in messages"
            :key="`msg-${index}-${msg.time}`"
            :class="['message', msg.role]"
          >
            <div class="message-content">
              <div class="message-role">{{ msg.role === 'user' ? '我' : '千问' }}</div>
              <div class="message-text">{{ msg.content }}</div>
              <div class="message-time">{{ msg.time }}</div>
            </div>
          </div>
          <div v-if="isLoading" class="message assistant">
            <div class="message-content">
              <div class="message-role">千问</div>
              <div class="message-text">
                <i class="el-icon-loading"></i> 正在思考...
              </div>
            </div>
          </div>
        </div>

        <div class="input-section">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="3"
            placeholder="输入消息..."
            @keydown.enter.ctrl.prevent="sendMessage"
          ></el-input>
          <div class="input-actions">
            <el-button
              type="primary"
              @click="sendMessage"
              :disabled="!inputMessage.trim() || isLoading"
            >
              发送 (Ctrl+Enter)
            </el-button>
            <el-button @click="clearMessages">清空对话</el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: 'QwenChat',
  data() {
    return {
      apiConfigured: false,
      messages: [],
      inputMessage: '',
      isLoading: false
    }
  },
  mounted() {
    // 检查API是否配置
    this.checkApiConfiguration()
  },
  methods: {
    openPopup() {
      window.open('/qwen/popup', 'qwen-chat', 'width=480,height=680,menubar=0,toolbar=0,location=0,scrollbars=0,resizable=1')
    },

    async checkApiConfiguration() {
      try {
        const response = await fetch('/api/qwen/status')
        const data = await response.json()
        this.apiConfigured = Boolean(data.configured && data.connected)
      } catch (error) {
        console.error('API configuration check error:', error)
        this.apiConfigured = false
      }
    },

    async sendMessage() {
      if (!this.inputMessage.trim() || this.isLoading) {
        return
      }

      // 检查API配置状态
      if (!this.apiConfigured) {
        this.$message.warning('请先在服务端配置千问API密钥')
        return
      }

      const userMessage = {
        role: 'user',
        content: this.inputMessage.trim(),
        time: this.getCurrentTime()
      }

      this.messages.push(userMessage)
      this.inputMessage = ''
      this.isLoading = true

      // 滚动到底部
      this.$nextTick(() => {
        this.scrollToBottom()
      })

      try {
        // 构建历史消息（只发送最近10条）
        const history = this.messages
          .slice(-11, -1) // 排除刚添加的当前消息
          .map(msg => ({
            role: msg.role,
            content: msg.content
          }))

        // 调用后端API
        const response = await fetch('/api/qwen/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            message: userMessage.content,
            history: history
          })
        })

        const data = await response.json()

        if (!data.success) {
          throw new Error(data.error || 'API调用失败')
        }
        
        const assistantMessage = {
          role: 'assistant',
          content: data.response,
          time: this.getCurrentTime()
        }

        this.messages.push(assistantMessage)
      } catch (error) {
        console.error('Qwen API error:', error)
        this.$message.error(`发送消息失败: ${error.message}`)

        // 添加错误消息
        this.messages.push({
          role: 'assistant',
          content: `抱歉, 我现在无法回复: ${error.message}`,
          time: this.getCurrentTime()
        })
      } finally {
        this.isLoading = false
        this.$nextTick(() => {
          this.scrollToBottom()
        })
      }
    },

    clearMessages() {
      this.$confirm('确定要清空所有对话记录吗?', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.messages = []
        this.$message.success('对话已清空')
      }).catch(() => {})
    },

    getCurrentTime() {
      const now = new Date()
      // 使用 ES6 模板字符串，符合 prefer-template 规则
      return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
    },

    scrollToBottom() {
      const container = this.$refs.messagesContainer
      if (container) {
        container.scrollTop = container.scrollHeight
      }
    }
  }
}
</script>

<style scoped>
.qwen-chat-container {
  max-width: 1200px;
  margin: 20px auto;
  padding: 0 20px;
}

.auth-section {
  padding: 40px 0;
  text-align: center;
}

.chat-section {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 250px);
  min-height: 500px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 20px;
}

.message {
  margin-bottom: 20px;
  display: flex;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.message.user .message-content {
  background-color: #409EFF;
  color: white;
}

.message.assistant .message-content {
  background-color: white;
  color: #333;
}

.message-role {
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 4px;
  opacity: 0.8;
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.message-time {
  font-size: 11px;
  margin-top: 4px;
  opacity: 0.6;
  text-align: right;
}

.input-section {
  border-top: 1px solid #ddd;
  padding-top: 20px;
}

.input-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 滚动条样式 */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>

