<template>
  <div class="callback-container">
    <el-card>
      <div class="callback-content">
        <i v-if="loading" class="el-icon-loading" style="font-size: 48px; color: #409EFF;"></i>
        <i v-else-if="success" class="el-icon-success" style="font-size: 48px; color: #67C23A;"></i>
        <i v-else class="el-icon-error" style="font-size: 48px; color: #F56C6C;"></i>

        <h2 v-if="loading">正在处理认证...</h2>
        <h2 v-else-if="success">认证成功！</h2>
        <h2 v-else>认证失败</h2>

        <p v-if="!loading">{{ message }}</p>

        <el-button v-if="!loading" type="primary" @click="closeWindow">
          关闭窗口
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: 'QwenCallback',
  data() {
    return {
      loading: true,
      success: false,
      message: ''
    }
  },
  mounted() {
    this.handleCallback()
  },
  methods: {
    async handleCallback() {
      try {
        // 获取URL参数
        const urlParams = new URLSearchParams(window.location.search)
        const code = urlParams.get('code')
        const userCode = urlParams.get('user_code')

        if (!code && !userCode) {
          throw new Error('缺少认证参数')
        }

        // 调用后端完成认证
        const response = await fetch('/api/qwen/auth/callback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            code: code,
            user_code: userCode
          })
        })

        if (!response.ok) {
          throw new Error('认证失败')
        }

        const data = await response.json()

        // 认证成功
        this.success = true
        this.message = '您已成功连接千问AI，窗口将自动关闭'

        // 通知父窗口
        if (window.opener) {
          window.opener.postMessage({
            type: 'qwen-auth-success',
            token: data.token
          }, '*')
        }

        // 3秒后自动关闭
        setTimeout(() => {
          window.close()
        }, 3000)
      } catch (error) {
        console.error('Callback error:', error)
        this.success = false
        this.message = error.message || '认证过程中出现错误'
      } finally {
        this.loading = false
      }
    },

    closeWindow() {
      window.close()
    }
  }
}
</script>

<style scoped>
.callback-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f5f5;
  padding: 20px;
}

.callback-content {
  text-align: center;
  padding: 40px;
}

.callback-content i {
  display: block;
  margin-bottom: 20px;
}

.callback-content h2 {
  margin: 20px 0;
  color: #333;
}

.callback-content p {
  margin: 20px 0;
  color: #666;
  font-size: 14px;
}
</style>

