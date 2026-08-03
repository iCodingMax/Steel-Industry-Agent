<template>
  <div class="app-login-view">
    <div class="login-container">
      <div class="login-header">
        <div class="logo-container">
          <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="20" cy="20" r="18" stroke="#3b82f6" stroke-width="2" fill="none" opacity="0.6"/>
            <circle cx="20" cy="20" r="14" stroke="#3b82f6" stroke-width="1.5" fill="none" stroke-dasharray="22 66" stroke-dashoffset="0" opacity="0.8"/>
            <circle cx="20" cy="20" r="10" stroke="#60a5fa" stroke-width="1.5" fill="none" stroke-dasharray="16 47" stroke-dashoffset="-8" opacity="0.9"/>
            <circle cx="20" cy="20" r="4" fill="#3b82f6"/>
            <circle cx="20" cy="20" r="2" fill="#93c5fd"/>
          </svg>
        </div>
        <h1 class="login-title">{{ appName }}</h1>
        <p class="login-subtitle">请登录以使用智能助手</p>
      </div>

      <div class="login-tabs">
        <div 
          class="tab-item" 
          :class="{ active: activeTab === 'account' }"
          @click="activeTab = 'account'"
        >
          <el-icon><User /></el-icon>
          账号登录
        </div>
        <div 
          class="tab-item" 
          :class="{ active: activeTab === 'oauth' }"
          @click="handleOauthLogin"
        >
          <el-icon><Lock /></el-icon>
          统一身份认证
        </div>
      </div>

      <div v-if="activeTab === 'account'" class="login-form">
        <el-form ref="formRef" :model="formData" :rules="formRules" label-position="top">
          <el-form-item prop="username">
            <el-input 
              v-model="formData.username" 
              placeholder="请输入用户名"
              size="large"
              clearable
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item prop="password">
            <el-input 
              v-model="formData.password" 
              type="password" 
              placeholder="请输入密码"
              size="large"
              show-password
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          <el-button 
            type="primary" 
            size="large" 
            :loading="isLoading"
            class="login-btn"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form>
      </div>

      <div v-else class="oauth-login">
        <p class="oauth-desc">点击下方按钮跳转到统一身份认证中心登录</p>
        <el-button 
          type="primary" 
          size="large" 
          :loading="oauthLoading"
          class="oauth-btn"
          @click="handleOauthLogin"
        >
          <el-icon><Link /></el-icon>
          使用统一身份认证登录
        </el-button>
      </div>

      <div class="login-footer">
        <span>© {{ currentYear }} 钢铁行业智能助手平台</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Link } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const route = useRoute()
const router = useRouter()

// 检测是否为弹窗模式（仅在通过window.open打开时为true）
// 使用URL参数 popup=1 来明确标记弹窗模式，避免window.opener的不确定性
const isPopupMode = computed(() => {
  return route.query.popup === '1'
})

const activeTab = ref('account')
const isLoading = ref(false)
const oauthLoading = ref(false)
const formRef = ref<FormInstance>()
const appName = ref('智能助手')
const oauthEnabled = ref(false)
const oauthLoginUrl = ref('')

const formData = reactive({
  username: '',
  password: '',
})

const formRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const currentYear = computed(() => new Date().getFullYear())

// 获取应用名称
function getAppName() {
  const query = route.query
  if (query.appName) {
    appName.value = decodeURIComponent(query.appName as string)
  }
}

// 获取redirect路径
function getRedirectPath(): string {
  // 优先级1: 从URL参数获取
  const redirect = route.query.redirect as string | undefined
  if (redirect) {
    // 尝试解码（如果已经是解码后的路径，decodeURIComponent不会有副作用）
    try {
      const decoded = decodeURIComponent(redirect)
      // 确保redirect是有效的应用访问路径
      if (decoded.startsWith('/chat')) {
        return decoded
      }
    } catch {
      // 解码失败，可能已经是原始路径
      if (redirect.startsWith('/chat')) {
        return redirect
      }
    }
  }
  
  // 优先级2: 从sessionStorage获取embed_redirect（适用于嵌入页面场景）
  const embedRedirect = sessionStorage.getItem('embed_redirect')
  if (embedRedirect && embedRedirect.startsWith('/chat')) {
    return embedRedirect
  }
  
  // 优先级3: 从sessionStorage获取chat_redirect（适用于公开访问链接场景）
  const chatRedirect = sessionStorage.getItem('chat_redirect')
  if (chatRedirect && chatRedirect.startsWith('/chat')) {
    return chatRedirect
  }
  
  // 优先级4: 从sessionStorage获取oauth_redirect（适用于OAuth登录场景）
  const oauthRedirect = sessionStorage.getItem('oauth_redirect')
  if (oauthRedirect && oauthRedirect.startsWith('/chat')) {
    return oauthRedirect
  }
  
  // 默认跳转到chat页面
  return '/chat'
}

// 检查OAuth是否启用
async function checkOauthEnabled() {
  try {
    const res = await fetch('/api/v1/chat-auth/oauth-config')
    const data = await res.json()
    if (data.code === 0 && data.data) {
      oauthEnabled.value = data.data.enabled || false
      if (oauthEnabled.value) {
        activeTab.value = 'oauth'
      }
    }
  } catch (e) {
    console.error('检查OAuth配置失败', e)
  }
}

// 账号登录
async function handleLogin() {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    isLoading.value = true
    try {
      const res = await fetch('/api/v1/chat-auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })
      
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.message || '登录失败')
      }
      
      const data = await res.json()
      if (data.code === 0 && data.data) {
        // 存储token（使用chat_token区分）
        localStorage.setItem('chat_token', data.data.token)
        localStorage.setItem('chat_user', JSON.stringify(data.data.user))
        
        // 如果是弹窗模式（从iframe打开），通知父窗口并关闭
        if (isPopupMode.value) {
          ElMessage.success('登录成功')
          // 通知父窗口（iframe）登录状态
          try {
            window.opener?.postMessage({
              type: 'steel_login_success',
              token: data.data.token,
              user: data.data.user
            }, '*')
          } catch (e) {
            console.warn('无法通知父窗口', e)
          }
          // 清理弹窗标记
          sessionStorage.removeItem('is_popup')
          // 延迟关闭窗口
          setTimeout(() => {
            window.close()
            // 如果无法关闭（非脚本打开的窗口），显示提示
            ElMessage.info('登录成功，请返回原页面')
          }, 500)
          return
        }
        
        ElMessage.success('登录成功')
        
        // 跳转到原页面（使用replace避免在历史记录中留下登录页）
        const redirect = getRedirectPath()
        router.replace(redirect)
      } else {
        ElMessage.error(data.message || '登录失败')
      }
    } catch (error: any) {
      ElMessage.error(error.message || '登录失败，请检查用户名和密码')
    } finally {
      isLoading.value = false
    }
  })
}

// OAuth登录
async function handleOauthLogin() {
  if (!oauthEnabled.value) {
    ElMessage.warning('统一身份认证尚未启用')
    return
  }
  
  oauthLoading.value = true
  try {
    const res = await fetch('/api/v1/oauth/chat-login-url')
    const data = await res.json()
    
    if (data.code === 0 && data.data) {
      // 保存redirect信息供回调后使用
      const redirect = getRedirectPath()
      sessionStorage.setItem('oauth_redirect', redirect)
      sessionStorage.setItem('chat_redirect', redirect)
      // 传递弹窗模式标记给OAuth回调页
      if (isPopupMode.value) {
        sessionStorage.setItem('is_popup', '1')
      } else {
        sessionStorage.removeItem('is_popup')
      }
      
      // 跳转到OAuth授权页面
      window.location.href = data.data.loginUrl
    } else {
      ElMessage.error(data.message || '获取授权地址失败')
    }
  } catch (error: any) {
    ElMessage.error('登录失败，请重试')
  } finally {
    oauthLoading.value = false
  }
}

onMounted(() => {
  getAppName()
  checkOauthEnabled()
})
</script>

<style lang="scss" scoped>
.app-login-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-container {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  overflow: hidden;
}

.login-header {
  padding: 40px 32px 24px;
  text-align: center;
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  
  .logo-container {
    width: 64px;
    height: 64px;
    margin: 0 auto 16px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    
    svg {
      width: 40px;
      height: 40px;
    }
  }
  
  .login-title {
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    margin: 0 0 8px;
  }
  
  .login-subtitle {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.85);
    margin: 0;
  }
}

.login-tabs {
  display: flex;
  border-bottom: 1px solid #e5e7eb;
  margin: 0 32px;
  
  .tab-item {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 16px 0;
    font-size: 14px;
    font-weight: 500;
    color: #6b7280;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.3s;
    
    &:hover {
      color: #3b82f6;
    }
    
    &.active {
      color: #3b82f6;
      border-bottom-color: #3b82f6;
    }
    
    .el-icon {
      font-size: 16px;
    }
  }
}

.login-form {
  padding: 32px;
  
  .login-btn {
    width: 100%;
    height: 44px;
    font-size: 16px;
    font-weight: 600;
    margin-top: 8px;
  }
  
  :deep(.el-form-item) {
    margin-bottom: 20px;
  }
  
  :deep(.el-input__wrapper) {
    height: 44px;
  }
}

.oauth-login {
  padding: 32px;
  
  .oauth-desc {
    text-align: center;
    color: #6b7280;
    font-size: 14px;
    margin: 0 0 24px;
  }
  
  .oauth-btn {
    width: 100%;
    height: 44px;
    font-size: 15px;
    font-weight: 500;
  }
}

.login-footer {
  padding: 16px 32px 24px;
  text-align: center;
  border-top: 1px solid #f3f4f6;
  
  span {
    font-size: 12px;
    color: #9ca3af;
  }
}
</style>
