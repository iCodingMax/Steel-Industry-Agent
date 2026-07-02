<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-left">
        <div class="brand-info">
          <div class="brand-logo">
            <el-icon :size="48"><Cpu /></el-icon>
          </div>
          <h1 class="brand-title">Steel Industry AI Assistant</h1>
          <p class="brand-desc">钢铁行业智能问答系统</p>
          <p class="brand-sub">RAG知识问答 · ChatBI智能问数 · 融合推理</p>
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
                @keyup.enter="handleLogin"
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
          <div class="login-tip">
            <el-icon><InfoFilled /></el-icon>
            默认账号：admin / admin
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
import {
  Cpu,
  User,
  Lock,
  Document,
  DataAnalysis,
  MagicStick,
  InfoFilled,
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loginFormRef = ref<FormInstance>()
const loading = ref(false)

const loginForm = reactive({
  username: 'admin',
  password: '',
})

const loginRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
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
      const redirect = (route.query.redirect as string) || '/chat'
      router.push(redirect)
    } catch (e) {
      // error handled by interceptor
    } finally {
      loading.value = false
    }
  })
}

onMounted(() => {
  if (authStore.isLoggedIn) {
    router.push('/chat')
  }
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
  .brand-logo {
    width: 72px;
    height: 72px;
    background: rgba(59, 130, 246, 0.2);
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 24px;
    color: $primary-color;
  }

  .brand-title {
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 8px;
    line-height: 1.3;
  }

  .brand-desc {
    font-size: 18px;
    color: rgba(255, 255, 255, 0.85);
    margin-bottom: 12px;
  }

  .brand-sub {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
  }
}

.features {
  display: flex;
  flex-direction: column;
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
