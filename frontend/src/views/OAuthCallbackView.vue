<template>
  <div class="oauth-callback-page">
    <div class="callback-container">
      <div class="loading-icon" v-if="!error">
        <el-icon class="is-loading" :size="48"><Loading /></el-icon>
      </div>
      <div class="success-icon" v-else-if="success">
        <el-icon :size="48" color="#67c23a"><SuccessFilled /></el-icon>
      </div>
      <div class="error-icon" v-else>
        <el-icon :size="48" color="#f56c6c"><CircleCloseFilled /></el-icon>
      </div>
      <p class="callback-message">{{ message }}</p>
      <el-button
        v-if="error"
        type="primary"
        @click="goToLogin"
      >
        返回登录
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, SuccessFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { handleOAuthCallback } from '@/api/oauth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const message = ref('正在处理认证回调...')
const error = ref(false)
const success = ref(false)

async function processCallback() {
  const code = route.query.code as string
  const state = route.query.state as string

  if (!code) {
    error.value = true
    message.value = '认证回调失败：缺少授权码'
    return
  }

  try {
    message.value = '正在验证授权信息...'
    const res: any = await handleOAuthCallback(code, state)
    
    if (res.code === 0 && res.data) {
      // 保存token
      authStore.token = res.data.token
      localStorage.setItem('token', res.data.token)
      
      // 更新用户信息
      if (res.data.user) {
        authStore.userInfo = res.data.user
      }
      
      success.value = true
      message.value = '认证成功，正在跳转...'
      
      // 跳转到目标页面
      // 优先级: URL参数 > oauth_redirect（主登录流程设置） > 默认/app-management
      // chat_redirect/embed_redirect 仅在 oauth_redirect 未设置时使用，且必须是chat相关路径
      // 这样避免之前访问对话页面残留的redirect值干扰主登录流程
      setTimeout(() => {
        const urlRedirect = route.query.redirect as string
        const oauthRedirect = localStorage.getItem('oauth_redirect')
        let redirect = urlRedirect || oauthRedirect || '/app-management'
        
        // 如果 oauth_redirect 未设置，尝试使用 chat/embed_redirect
        // 但前提是它们必须是有效的chat路径（防止残留的非chat路径被误用）
        if (!urlRedirect && !oauthRedirect) {
          const chatRedirect = localStorage.getItem('chat_redirect')
          const embedRedirect = localStorage.getItem('embed_redirect')
          const chatOrEmbed = chatRedirect || embedRedirect
          if (chatOrEmbed && (chatOrEmbed.startsWith('/chat') || chatOrEmbed.startsWith('/ai-assistant'))) {
            redirect = chatOrEmbed
          }
        }

        // 确保redirect是有效的路径（必须以/开头，且是允许的路径前缀）
        const validPrefixes = ['/chat', '/ai-assistant', '/app', '/admin']
        if (!redirect.startsWith('/') || !validPrefixes.some(p => redirect.startsWith(p))) {
          redirect = '/app-management'
        }
        
        // 清理使用后的redirect存储
        localStorage.removeItem('oauth_redirect')
        localStorage.removeItem('chat_redirect')
        localStorage.removeItem('embed_redirect')
        
        router.replace(redirect)
      }, 1000)
    } else {
      error.value = true
      message.value = res.message || '认证失败'
    }
  } catch (e: any) {
    error.value = true
    message.value = e?.message || '认证处理失败'
  }
}

function goToLogin() {
  router.replace('/login')
}

onMounted(() => {
  processCallback()
})
</script>

<style lang="scss" scoped>
.oauth-callback-page {
  height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0a1628 0%, #1a237e 50%, #3b82f6 100%);
}

.callback-container {
  background: #fff;
  padding: 48px 64px;
  border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  text-align: center;
  min-width: 320px;
}

.loading-icon,
.success-icon,
.error-icon {
  margin-bottom: 20px;
}

.callback-message {
  font-size: 16px;
  color: #606266;
  margin-bottom: 24px;
}
</style>
