<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-left">
        <div class="brand-info">
          <div class="brand-logo">
            <img src="@/assets/login-logo-dark.png" alt="工业智能助手平台" class="logo-image" />
          </div>
          <h1 class="brand-title">工业智能助手平台</h1>
          <p class="brand-desc">Industrial Intelligent Assistant Platform</p>
        </div>
        <div class="features">
          <div class="feature-item">
            <el-icon :size="20"><Document /></el-icon>
            <span>工艺知识智能检索</span>
          </div>
          <div class="feature-item">
            <el-icon :size="20"><DataAnalysis /></el-icon>
            <span>生产数据智能分析</span>
          </div>
          <div class="feature-item">
            <el-icon :size="20"><MagicStick /></el-icon>
            <span>自然语言交互对话</span>
          </div>
        </div>
      </div>
      <div class="login-right">
        <div class="login-card">
          <h2 class="login-title">欢迎登录</h2>
          <p class="login-subtitle">请输入您的账号信息</p>
          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            class="login-form"
            @keyup.enter="handleLogin"
          >
            <el-form-item prop="username">
              <el-input
                v-model="loginForm.username"
                placeholder="请输入用户名"
                size="large"
                :prefix-icon="User"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                size="large"
                show-password
                :prefix-icon="Lock"
              />
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form>
          
          <!-- OAuth2登录入口 -->
          <div v-if="oauthEnabled" class="oauth-section">
            <div class="divider">
              <span>或使用统一认证登录</span>
            </div>
            <el-button
              class="oauth-btn"
              size="large"
              :loading="oauthLoading"
              @click="handleOAuthLogin"
            >
              <el-icon class="oauth-icon"><User /></el-icon>
              统一身份认证登录
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getOAuthConfig, getOAuthLoginUrl } from '@/api/oauth'
import {
  User,
  Lock,
  Document,
  DataAnalysis,
  MagicStick,
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loginFormRef = ref<FormInstance>()
const loading = ref(false)
const oauthEnabled = ref(false)
const oauthLoading = ref(false)

const loginForm = reactive({
  username: 'admin',
  password: '',
})

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function checkOAuthStatus() {
  try {
    const res: any = await getOAuthConfig()
    if (res.code === 0 && res.data) {
      oauthEnabled.value = res.data.enabled
    }
  } catch (e) {
    console.error('获取OAuth配置失败', e)
  }
}

async function handleLogin() {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await authStore.login({
        username: loginForm.username,
        password: loginForm.password,
      })
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || '/app-management'
      router.push(redirect)
    } catch (e) {
      // error handled by interceptor
    } finally {
      loading.value = false
    }
  })
}

async function handleOAuthLogin() {
  oauthLoading.value = true
  try {
    const res: any = await getOAuthLoginUrl()
    if (res.code === 0 && res.data) {
      // 存储state到sessionStorage用于回调验证
      sessionStorage.setItem('oauth_state', res.data.state)

      // 计算正确的跳转路径
      // 从URL参数获取redirect，如果没有则默认为/app-management
      const redirect = (route.query.redirect as string) || '/app-management'
      localStorage.setItem('oauth_redirect', redirect)

      // 清除chat_redirect和embed_redirect，避免之前访问对话页面时残留的跳转地址干扰
      // 这两个值仅在AppLoginView（应用内登录）流程中使用
      localStorage.removeItem('chat_redirect')
      localStorage.removeItem('embed_redirect')

      // 跳转到OAuth2授权页面
      window.location.href = res.data.loginUrl
    } else {
      ElMessage.error(res.message || '获取OAuth登录地址失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || 'OAuth登录失败')
  } finally {
    oauthLoading.value = false
  }
}

onMounted(() => {
  if (authStore.isLoggedIn) {
    router.push('/app-management')
    return
  }
  checkOAuthStatus()
})
</script>

<style lang="scss" scoped>
.login-page {
  height: 100vh;
  width: 100%;
  background: linear-gradient(135deg, #0a1628 0%, #1a237e 50%, #3b82f6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.login-container {
  width: 900px;
  max-width: 100%;
  height: 560px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  display: flex;
  overflow: hidden;
}

.login-left {
  width: 50%;
  background: linear-gradient(160deg, #0a1628 0%, #1a237e 100%);
  color: #fff;
  padding: 60px 50px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.brand-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;

  .brand-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 28px;

    .logo-image {
      width: 160px;
      height: 100px;
      object-fit: contain;
    }
  }

  .brand-title {
    font-size: 42px;
    font-weight: 700;
    margin-bottom: 12px;
    line-height: 1.2;
    white-space: nowrap;
  }

  .brand-desc {
    font-size: 22px;
    color: rgba(255, 255, 255, 0.85);
    margin-bottom: 16px;
    white-space: nowrap;
  }

  .brand-sub {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
  }
}

.features {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);

  .el-icon {
    color: $primary-color;
  }
}

.login-right {
  width: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 50px;
  border-radius: 0 16px 16px 0;
}

.login-card {
  width: 100%;
  max-width: 340px;
}

.login-title {
  font-size: 24px;
  font-weight: 600;
  color: $text-primary;
  margin-bottom: 8px;
}

.login-subtitle {
  font-size: 14px;
  color: $text-secondary;
  margin-bottom: 32px;
}

.login-form {
  margin-bottom: 20px;
}

.login-btn {
  width: 100%;
  font-weight: 500;
  letter-spacing: 4px;
  border-radius: $border-radius;
}

.login-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  color: $text-placeholder;

  .el-icon {
    color: $primary-color;
  }
}

.oauth-section {
  margin-top: 20px;
}

.divider {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  
  &::before,
  &::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #e4e7ed;
  }
  
  span {
    padding: 0 12px;
    font-size: 13px;
    color: #909399;
  }
}

.oauth-btn {
  width: 100%;
  background: #1a237e;
  border-color: #1a237e;
  color: #fff;
  
  &:hover {
    background: #283593;
    border-color: #283593;
  }
  
  .oauth-icon {
    margin-right: 6px;
  }
}

@media (max-width: 768px) {
  .login-container {
    flex-direction: column;
    height: auto;
  }

  .login-left,
  .login-right {
    width: 100%;
  }

  .login-left {
    padding: 40px 30px;
  }

  .login-right {
    padding: 40px 30px;
  }
}
</style>
