<template>
  <div class="settings-view">
    <div class="page-header">
      <h2 class="page-title">系统设置</h2>
    </div>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <el-tab-pane label="用户管理" name="user">
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
      </el-tab-pane>

      <el-tab-pane label="登录认证" name="oauth">
        <div class="config-section">
          <h3 class="section-title">
            <el-icon><Key /></el-icon>
            OAuth2 认证配置
          </h3>
          <el-form :model="oauthForm" label-width="120px" :rules="oauthRules" ref="oauthFormRef">
            <el-form-item label="授权端地址*" prop="authorizationUrl">
              <el-input v-model="oauthForm.authorizationUrl" placeholder="请输入授权端地址" />
            </el-form-item>
            <el-form-item label="Token端地址*" prop="tokenUrl">
              <el-input v-model="oauthForm.tokenUrl" placeholder="请输入Token端地址" />
            </el-form-item>
            <el-form-item label="用户信息端地址*" prop="userInfoUrl">
              <el-input v-model="oauthForm.userInfoUrl" placeholder="请输入用户信息端地址" />
            </el-form-item>
            <el-form-item label="连接范围*" prop="scope">
              <el-input v-model="oauthForm.scope" placeholder="请输入连接范围，如 user,email" />
            </el-form-item>
            <el-form-item label="客户端ID*" prop="clientId">
              <el-input v-model="oauthForm.clientId" placeholder="请输入客户端ID" />
            </el-form-item>
            <el-form-item label="客户端密钥*" prop="clientSecret">
              <el-input v-model="oauthForm.clientSecret" type="password" show-password placeholder="请输入客户端密钥" />
            </el-form-item>
            <el-form-item label="字段映射*" prop="fieldMapping">
              <el-input v-model="oauthForm.fieldMapping" type="textarea" :rows="3" placeholder='请输入字段映射JSON，如 {"username":"login","nick_name":"name","email":"email"}' />
            </el-form-item>
            <el-form-item label="回调地址*" prop="redirectUrl">
              <el-input v-model="oauthForm.redirectUrl" placeholder="请输入回调地址" />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="oauthForm.enabled">启用 OAuth2 认证</el-checkbox>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSaveOAuth" :loading="oauthSaving">保存</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Key } from '@element-plus/icons-vue'
import { getUserInfoApi, changePasswordApi, type UserInfo } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const activeTab = ref('user')

const pwdChanging = ref(false)
const pwdFormRef = ref<FormInstance>()

const oauthSaving = ref(false)
const oauthFormRef = ref<FormInstance>()

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

const oauthForm = reactive({
  authorizationUrl: '',
  tokenUrl: '',
  userInfoUrl: '',
  scope: '',
  clientId: '',
  clientSecret: '',
  fieldMapping: '',
  redirectUrl: '',
  enabled: false,
})

const oauthRules: FormRules = {
  authorizationUrl: [{ required: true, message: '请输入授权端地址', trigger: 'blur' }],
  tokenUrl: [{ required: true, message: '请输入Token端地址', trigger: 'blur' }],
  userInfoUrl: [{ required: true, message: '请输入用户信息端地址', trigger: 'blur' }],
  scope: [{ required: true, message: '请输入连接范围', trigger: 'blur' }],
  clientId: [{ required: true, message: '请输入客户端ID', trigger: 'blur' }],
  clientSecret: [{ required: true, message: '请输入客户端密钥', trigger: 'blur' }],
  fieldMapping: [{ required: true, message: '请输入字段映射', trigger: 'blur' }],
  redirectUrl: [{ required: true, message: '请输入回调地址', trigger: 'blur' }],
}

watch(() => route.path, (newPath) => {
  if (newPath.includes('oauth')) {
    activeTab.value = 'oauth'
  } else {
    activeTab.value = 'user'
  }
})

watch(activeTab, (newTab) => {
  if (newTab === 'oauth') {
    router.push('/system-settings/oauth')
  } else {
    router.push('/system-settings/user')
  }
})

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

async function handleSaveOAuth() {
  if (!oauthFormRef.value) return
  await oauthFormRef.value.validate(async (valid) => {
    if (!valid) return
    oauthSaving.value = true
    try {
      const res: any = await fetch('/api/v1/system-settings/oauth', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(oauthForm),
      })
      const data = await res.json()
      if (data.code === 0) {
        ElMessage.success('OAuth2配置保存成功')
      }
    } catch (e) {
      console.error('保存OAuth2配置失败', e)
    } finally {
      oauthSaving.value = false
    }
  })
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadUserInfo()
  if (route.path.includes('oauth')) {
    activeTab.value = 'oauth'
  }
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

.settings-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 24px;
  }
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