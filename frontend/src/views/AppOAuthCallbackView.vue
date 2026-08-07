<template>
  <div class="app-oauth-callback">
    <div class="callback-container">
      <div v-if="isLoading" class="loading-state">
        <el-icon class="loading-icon" :size="48"><Loading /></el-icon>
        <p class="loading-text">正在登录中...</p>
        <p class="loading-desc">请稍候，正在处理您的身份认证</p>
      </div>
      <div v-else class="success-state">
        <el-icon class="success-icon" :size="64"><CircleCheckFilled /></el-icon>
        <p class="success-text">登录成功！</p>
        <p class="success-desc">正在跳转到应用页面...</p>
      </div>
      <div v-if="errorMessage" class="error-state">
        <el-icon class="error-icon" :size="64"><CircleCloseFilled /></el-icon>
        <p class="error-text">登录失败</p>
        <p class="error-desc">{{ errorMessage }}</p>
        <el-button type="primary" @click="goToLogin">返回登录页</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loading, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

// 检测是否为弹窗模式（仅在通过window.open打开时为true）
// 使用sessionStorage中的popup标记，由登录页在OAuth跳转前设置
const isPopupMode = computed(() => {
  return sessionStorage.getItem('is_popup') === '1'
})

const isLoading = ref(true)
const errorMessage = ref('')
const userInfo = ref<any>(null)

async function handleCallback() {
  const code = route.query.code as string
  const state = route.query.state as string
  
  if (!code) {
    isLoading.value = false
    errorMessage.value = '缺少授权码，请重新登录'
    return
  }
  
  try {
    isLoading.value = true
    errorMessage.value = ''
    
    const res = await fetch('/api/v1/oauth/chat-callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, state }),
    })
    
    if (!res.ok) {
      throw new Error('登录请求失败')
    }
    
    const data = await res.json()
    
    if (data.code === 0 && data.data) {
      // 存储对话用户token
      localStorage.setItem('chat_token', data.data.token)
      localStorage.setItem('chat_user', JSON.stringify(data.data.user))
      userInfo.value = data.data.user
      
      // 等待一下再跳转，显示成功状态
      await new Promise(resolve => setTimeout(resolve, 1500))
      
      // 如果是弹窗模式，通知父窗口并关闭
      if (isPopupMode.value) {
        const loginSuccessData = {
          type: 'steel_login_success',
          token: data.data.token,
          user: data.data.user
        }
        
        // 方法1: 尝试通过 window.opener 通知（最可靠）
        let notified = false
        try {
          if (window.opener && !window.opener.closed) {
            window.opener.postMessage(loginSuccessData, '*')
            notified = true
          }
        } catch (e) {
          console.warn('通过opener通知失败', e)
        }
        
        // 方法2: 使用localStorage广播（作为备选方案）
        if (!notified) {
          try {
            localStorage.setItem('steel_login_result', JSON.stringify(loginSuccessData))
            // 触发storage事件
            window.dispatchEvent(new Event('storage'))
          } catch (e) {
            console.warn('通过localStorage通知失败', e)
          }
        }
        
        // 清理弹窗标记
        sessionStorage.removeItem('is_popup')
        // 尝试关闭窗口
        try {
          window.close()
        } catch (e) {
          // 如果无法关闭，显示提示
        }
        
        // 如果无法关闭窗口，显示返回登录的链接
        setTimeout(() => {
          if (!window.closed) {
            ElMessage.info('登录成功，请返回原页面')
          }
        }, 500)
        return
      }
      
      // 获取保存的redirect路径（按优先级获取）
      // 优先级: URL参数 > oauth_redirect > chat_redirect > embed_redirect > 默认/chat
      // 使用localStorage持久存储，确保OAuth跨页面跳转后redirect不丢失
      const urlRedirect = route.query.redirect as string
      const oauthRedirect = localStorage.getItem('oauth_redirect')
      const chatRedirect = localStorage.getItem('chat_redirect')
      const embedRedirect = localStorage.getItem('embed_redirect')
      let redirect = urlRedirect || oauthRedirect || chatRedirect || embedRedirect || '/chat'
      
      // 确保redirect是有效的路径（必须以/开头，且是允许的路径前缀）
      const validPrefixes = ['/chat', '/ai-assistant']
      if (!redirect.startsWith('/') || !validPrefixes.some(p => redirect.startsWith(p))) {
        redirect = '/chat'
      }

      // 清理临时存储（使用后清除，避免残留数据干扰后续登录）
      localStorage.removeItem('oauth_redirect')
      localStorage.removeItem('chat_redirect')
      localStorage.removeItem('embed_redirect')

      // 跳转到原页面
      router.replace(redirect)
    } else {
      throw new Error(data.message || '登录失败')
    }
  } catch (error: any) {
    isLoading.value = false
    errorMessage.value = error.message || '登录失败，请重试'
  }
}

function goToLogin() {
  // 返回登录页，保留当前路径信息
  const currentPath = route.fullPath
  const loginPath = `/app-login${currentPath ? '?redirect=' + encodeURIComponent(currentPath) : ''}`
  router.replace(loginPath)
}

onMounted(() => {
  handleCallback()
})
</script>

<style lang="scss" scoped>
.app-oauth-callback {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.callback-container {
  background: #fff;
  border-radius: 16px;
  padding: 60px 48px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  max-width: 360px;
}

.loading-state,
.success-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.loading-icon {
  color: #3b82f6;
  animation: rotate 1.5s linear infinite;
}

.loading-text {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.loading-desc {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.success-icon {
  color: #10b981;
}

.success-text {
  font-size: 24px;
  font-weight: 700;
  color: #10b981;
  margin: 0;
}

.success-desc {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.error-icon {
  color: #ef4444;
}

.error-text {
  font-size: 24px;
  font-weight: 700;
  color: #ef4444;
  margin: 0;
}

.error-desc {
  font-size: 14px;
  color: #6b7280;
  margin: 0 0 16px;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
