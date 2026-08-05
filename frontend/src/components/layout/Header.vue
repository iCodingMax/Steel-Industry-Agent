<template>
  <div class="header">
    <div class="header-left">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item>{{ currentPageTitle }}</el-breadcrumb-item>
      </el-breadcrumb>
    </div>
    <div class="header-right">
      <el-dropdown trigger="click" @command="handleCommand">
        <div class="user-info">
          <el-avatar :size="32" style="background-color: #3b82f6">
            <el-icon><User /></el-icon>
          </el-avatar>
          <span class="username">{{ username }}</span>
          <el-icon class="arrow-down"><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon>个人信息
            </el-dropdown-item>
            <el-dropdown-item command="password">
              <el-icon><Lock /></el-icon>修改密码
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon>退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <img src="@/assets/company-logo-light.png" alt="公司标志" class="company-logo" />
    </div>

    <el-dialog v-model="pwdDialogVisible" title="修改密码" width="400px">
      <el-form :model="pwdForm" label-width="100px" :rules="pwdRules" ref="pwdFormRef">
        <el-form-item label="当前密码" prop="oldPassword">
          <el-input v-model="pwdForm.oldPassword" type="password" show-password placeholder="请输入当前密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="pwdForm.newPassword" type="password" show-password placeholder="请输入新密码(至少6位)" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleChangePwd">确认修改</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="profileDialogVisible" title="个人信息" width="450px">
      <el-descriptions :column="1" border class="config-desc">
        <el-descriptions-item label="用户名">
          <span class="config-value">{{ authStore.userInfo?.username || '-' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag type="primary" effect="plain">{{ authStore.userInfo?.role === 'admin' ? '管理员' : authStore.userInfo?.role || '-' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          <span class="config-value">{{ formatDate(authStore.userInfo?.createdAt) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="最后登录">
          <span class="config-value">{{ formatDate(authStore.userInfo?.lastLoginAt) }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="profileDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  User,
  ArrowDown,
  Lock,
  SwitchButton,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const username = computed(() => authStore.username || 'admin')
const currentPageTitle = computed(() => (route.meta.title as string) || '')

const pwdDialogVisible = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const pwdRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== pwdForm.newPassword) {
          callback(new Error('两次密码输入不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

const profileDialogVisible = ref(false)

function formatDate(dateStr: string | undefined) {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

function handleCommand(command: string) {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
    ElMessage.success('已退出登录')
  } else if (command === 'password') {
    pwdDialogVisible.value = true
  } else if (command === 'profile') {
    profileDialogVisible.value = true
  }
}

async function handleChangePwd() {
  if (!pwdFormRef.value) return
  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      await authStore.changePassword(pwdForm.oldPassword, pwdForm.newPassword)
      ElMessage.success('密码修改成功')
      pwdDialogVisible.value = false
      pwdForm.oldPassword = ''
      pwdForm.newPassword = ''
      pwdForm.confirmPassword = ''
    } catch (e) {
      // error handled by interceptor
    }
  })
}
</script>

<style lang="scss" scoped>
.header {
  height: $header-height;
  background-color: #fff;
  border-bottom: 1px solid $card-border;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.header-left {
  flex: 1;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;

  .company-logo {
    height: 36px;
    object-fit: contain;
    margin-left: 16px;
    padding-left: 16px;
    border-left: 1px solid $card-border;
  }
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: $border-radius;
  transition: background-color 0.2s;

  &:hover {
    background-color: $main-bg;
  }

  .username {
    font-size: 14px;
    font-weight: 500;
    color: $text-primary;
  }

  .arrow-down {
    font-size: 12px;
    color: $text-secondary;
  }
}

.config-desc {
  margin: 0;

  :deep(.el-descriptions__label) {
    font-weight: 500;
    color: $text-secondary;
  }

  :deep(.el-descriptions__content) {
    color: $text-primary;
  }
}

.config-value {
  font-weight: 500;
  color: $text-primary;
}
</style>
