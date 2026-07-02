<template>
  <div class="settings-view">
    <div class="page-header">
      <h2 class="page-title">系统设置</h2>
    </div>

    <div class="config-section">
      <h3 class="section-title">
        <el-icon><User /></el-icon>
        个人信息
      </h3>
      <el-descriptions :column="1" border class="config-desc">
        <el-descriptions-item label="用户名">
          <span class="config-value">{{ userInfo.username }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag type="primary" effect="plain">{{ userInfo.role === 'admin' ? '管理员' : userInfo.role }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          <span class="config-value">{{ formatDate(userInfo.createdAt) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="最后登录">
          <span class="config-value">{{ formatDate(userInfo.lastLoginAt) }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="config-section">
      <h3 class="section-title">
        <el-icon><Lock /></el-icon>
        修改密码
      </h3>
      <el-form :model="pwdForm" label-width="100px" style="max-width: 400px" :rules="pwdRules" ref="pwdFormRef">
        <el-form-item label="当前密码" prop="oldPassword">
          <el-input v-model="pwdForm.oldPassword" type="password" show-password placeholder="请输入当前密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="pwdForm.newPassword" type="password" show-password placeholder="请输入新密码(至少6位)" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleChangePwd" :loading="pwdChanging">确认修改</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { getUserInfoApi, changePasswordApi, type UserInfo } from '@/api/auth'

const pwdChanging = ref(false)
const pwdFormRef = ref<FormInstance>()

const userInfo = ref<UserInfo>({
  id: 0,
  username: '',
  role: '',
  createdAt: '',
  lastLoginAt: '',
  forceChangePassword: false,
})

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

async function loadUserInfo() {
  try {
    const res: any = await getUserInfoApi()
    if (res.code === 0 && res.data) {
      userInfo.value = res.data
    }
  } catch (e) {
    console.error('加载用户信息失败', e)
  }
}

async function handleChangePwd() {
  if (!pwdFormRef.value) return
  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return
    pwdChanging.value = true
    try {
      const res: any = await changePasswordApi({
        oldPassword: pwdForm.oldPassword,
        newPassword: pwdForm.newPassword,
      })
      if (res.code === 0) {
        ElMessage.success('密码修改成功')
        pwdForm.oldPassword = ''
        pwdForm.newPassword = ''
        pwdForm.confirmPassword = ''
      }
    } catch (e) {
      console.error('修改密码失败', e)
    } finally {
      pwdChanging.value = false
    }
  })
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadUserInfo()
})
</script>

<style lang="scss" scoped>
.settings-view {
  height: 100%;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
}

.config-section {
  background: #fff;
  border: 1px solid $card-border;
  border-radius: $card-radius;
  padding: 24px;
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
  margin-bottom: 16px;

  .el-icon {
    color: $primary-color;
    font-size: 18px;
  }
}

.config-desc {
  margin-bottom: 16px;
}

.config-value {
  font-family: 'Courier New', monospace;
  color: $text-primary;
}
</style>
