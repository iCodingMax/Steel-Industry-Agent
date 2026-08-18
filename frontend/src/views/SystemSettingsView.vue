<template>
  <div class="user-manage-view">
    <div class="page-header">
      <h1 class="page-title">系统设置</h1>
    </div>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <el-tab-pane label="用户列表" name="list">
        <div class="tab-content">
          <div class="tab-toolbar">
            <div class="toolbar-left">
              <el-input
                v-model="searchKeyword"
                placeholder="搜索用户名/姓名/邮箱"
                style="width: 240px"
                clearable
                @keyup.enter="handleSearch"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
              <el-select
                v-model="statusFilter"
                placeholder="状态筛选"
                style="width: 120px"
                clearable
              >
                <el-option label="已启用" value="active" />
                <el-option label="已禁用" value="disabled" />
              </el-select>
              <el-button type="primary" @click="handleSearch">
                <el-icon><Search /></el-icon>
                查询
              </el-button>
            </div>
            <el-button type="success" @click="handleAddUser">
              <el-icon><Plus /></el-icon>
              创建用户
            </el-button>
          </div>

          <el-table :data="users" style="width: 100%" v-loading="loading" class="user-table" stripe border>
            <el-table-column prop="name" label="姓名" min-width="120" align="center">
              <template #default="{ row }">
                <span>{{ row.name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="username" label="用户名" min-width="120" align="center" />
            <el-table-column label="状态" min-width="100" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 'active' ? 'success' : 'danger'"
                  effect="plain"
                >
                  {{ row.status === 'active' ? '已启用' : '已禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="email" label="邮箱" min-width="160" align="center">
              <template #default="{ row }">
                <span>{{ row.email || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="phone" label="手机号" min-width="120" align="center">
              <template #default="{ row }">
                <span>{{ row.phone || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="role" label="角色" min-width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'primary' : 'info'" effect="plain">
                  {{ row.role === 'admin' ? '管理员' : '普通用户' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="用户来源" min-width="120" align="center">
              <template #default="{ row }">
                <el-tag :type="row.userSource === 'oauth2' ? 'primary' : 'info'" effect="plain">
                  {{ row.userSource === 'oauth2' ? 'OAuth2' : '本地创建' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" min-width="160" align="center">
              <template #default="{ row }">
                {{ formatDate(row.createdAt) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <div class="action-btns">
                  <el-switch
                    v-model="row.status"
                    active-value="active"
                    inactive-value="disabled"
                    @change="handleToggleStatus(row)"
                    :disabled="row.username === 'admin'"
                  />
                  <el-button link type="primary" @click="handleEditUser(row)">编辑</el-button>
                  <el-button link type="warning" @click="handleResetPassword(row)">重置密码</el-button>
                  <el-button
                    link
                    type="danger"
                    @click="handleDeleteUser(row)"
                    :disabled="row.username === 'admin' || row.id === currentUserId"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-container">
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="total"
              layout="total, sizes, prev, pager, next, jumper"
              background
              @size-change="loadUsers"
              @current-change="loadUsers"
            />
          </div>
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

    <!-- 创建/编辑用户对话框 -->
    <el-dialog
      v-model="userDialogVisible"
      :title="isEditUser ? '编辑用户' : '创建用户'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="userForm" label-width="100px" :rules="userRules" ref="userFormRef">
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="userForm.username"
            placeholder="请输入用户名"
            :disabled="isEditUser"
          />
        </el-form-item>
        <el-form-item v-if="!isEditUser" label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" show-password placeholder="请输入密码(至少6位)" />
        </el-form-item>
        <el-form-item v-if="!isEditUser" label="确认密码" prop="confirmPassword">
          <el-input v-model="userForm.confirmPassword" type="password" show-password placeholder="请再次输入密码" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="userForm.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="userForm.phone" placeholder="请输入手机号（选填）" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="userForm.role" style="width: 100%">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveUser" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog
      v-model="pwdDialogVisible"
      title="重置密码"
      width="420px"
      destroy-on-close
    >
      <el-form :model="pwdForm" label-width="100px" :rules="pwdRules" ref="pwdFormRef">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="pwdForm.password" type="password" show-password placeholder="请输入新密码(至少6位)" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="请再次输入密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSavePassword" :loading="pwdSaving">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Search, Plus, Key } from '@element-plus/icons-vue'
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  resetUserPassword,
  toggleUserStatus,
  type UserInfo,
  type UserCreateForm,
  type UserUpdateForm,
} from '@/api/user'
import { getUserInfoApi } from '@/api/auth'
import { getOAuthConfig, saveOAuthConfig } from '@/api/oauth'

const activeTab = ref('list')
const loading = ref(false)
const saving = ref(false)
const pwdSaving = ref(false)
const oauthSaving = ref(false)

const searchKeyword = ref('')
const statusFilter = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const users = ref<UserInfo[]>([])
const currentUserId = ref(0)

const userDialogVisible = ref(false)
const pwdDialogVisible = ref(false)

const isEditUser = ref(false)
const editUserId = ref<number | null>(null)
const pwdUserId = ref<number | null>(null)

const userFormRef = ref<FormInstance>()
const pwdFormRef = ref<FormInstance>()
const oauthFormRef = ref<FormInstance>()

const userForm = reactive<UserCreateForm & { confirmPassword?: string }>({
  username: '',
  password: '',
  confirmPassword: '',
  name: '',
  email: '',
  phone: '',
  role: 'user',
})

const pwdForm = reactive({
  password: '',
  confirmPassword: '',
})

const oauthForm = reactive({
  authorizationUrl: '',
  tokenUrl: '',
  userInfoUrl: '',
  scope: '',
  clientId: '',
  clientSecret: '',
  fieldMapping: '',
  redirectUrl: 'http://localhost:5173/admin/api/oauth2',
  enabled: false,
})

const userRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== userForm.password) {
          callback(new Error('两次密码输入不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

const pwdRules: FormRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== pwdForm.password) {
          callback(new Error('两次密码输入不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

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

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

async function loadCurrentUser() {
  try {
    const res: any = await getUserInfoApi()
    if (res.code === 0 && res.data) {
      currentUserId.value = res.data.id
    }
  } catch (e) {
    console.error('获取当前用户信息失败', e)
  }
}

async function loadUsers() {
  loading.value = true
  try {
    const params: any = {
      page: page.value,
      pageSize: pageSize.value,
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const res: any = await getUsers(params)
    if (res.code === 0 && res.data) {
      users.value = res.data.list || []
      total.value = res.data.total || 0
    }
  } catch (e) {
    console.error('加载用户列表失败', e)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  loadUsers()
}

function handleAddUser() {
  isEditUser.value = false
  editUserId.value = null
  Object.assign(userForm, {
    username: '',
    password: '',
    confirmPassword: '',
    name: '',
    email: '',
    phone: '',
    role: 'user',
  })
  userDialogVisible.value = true
}

function handleEditUser(row: UserInfo) {
  isEditUser.value = true
  editUserId.value = row.id
  Object.assign(userForm, {
    username: row.username,
    name: row.name || '',
    email: row.email || '',
    phone: row.phone || '',
    role: row.role,
  })
  userDialogVisible.value = true
}

async function handleSaveUser() {
  if (!userFormRef.value) return
  await userFormRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      if (isEditUser.value && editUserId.value) {
        const updateData: UserUpdateForm = {
          name: userForm.name,
          email: userForm.email,
          phone: userForm.phone,
          role: userForm.role,
        }
        const res: any = await updateUser(editUserId.value, updateData)
        if (res.code === 0) {
          ElMessage.success('更新成功')
          userDialogVisible.value = false
          await loadUsers()
        }
      } else {
        const createData: UserCreateForm = {
          username: userForm.username,
          password: userForm.password,
          name: userForm.name,
          email: userForm.email,
          phone: userForm.phone,
          role: userForm.role,
        }
        const res: any = await createUser(createData)
        if (res.code === 0) {
          ElMessage.success('创建成功')
          userDialogVisible.value = false
          await loadUsers()
        }
      }
    } catch (e: any) {
      if (e?.message) {
        ElMessage.error(e.message)
      }
    } finally {
      saving.value = false
    }
  })
}

async function handleToggleStatus(row: UserInfo) {
  try {
    const res: any = await toggleUserStatus(row.id)
    if (res.code === 0) {
      ElMessage.success(row.status === 'active' ? '已启用' : '已禁用')
      await loadUsers()
    }
  } catch (e: any) {
    if (e?.message) {
      ElMessage.error(e.message)
    }
  }
}

function handleResetPassword(row: UserInfo) {
  pwdUserId.value = row.id
  pwdForm.password = ''
  pwdForm.confirmPassword = ''
  pwdDialogVisible.value = true
}

async function handleSavePassword() {
  if (!pwdFormRef.value) return
  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return
    pwdSaving.value = true
    try {
      if (pwdUserId.value) {
        const res: any = await resetUserPassword(pwdUserId.value, {
          password: pwdForm.password,
        })
        if (res.code === 0) {
          ElMessage.success('密码重置成功')
          pwdDialogVisible.value = false
        }
      }
    } catch (e: any) {
      if (e?.message) {
        ElMessage.error(e.message)
      }
    } finally {
      pwdSaving.value = false
    }
  })
}

async function handleDeleteUser(row: UserInfo) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.username}」吗？删除后不可恢复！`,
      '删除确认',
      {
        type: 'warning',
      }
    )
    const res: any = await deleteUser(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadUsers()
    }
  } catch {
    // 用户取消
  }
}

async function handleSaveOAuth() {
  if (!oauthFormRef.value) return
  await oauthFormRef.value.validate(async (valid) => {
    if (!valid) return
    oauthSaving.value = true
    try {
      // 解析字段映射
      let fieldMappingObj: Record<string, string> = {}
      if (typeof oauthForm.fieldMapping === 'string') {
        try {
          fieldMappingObj = JSON.parse(oauthForm.fieldMapping)
        } catch {
          ElMessage.error('字段映射JSON格式错误')
          return
        }
      } else {
        fieldMappingObj = oauthForm.fieldMapping as Record<string, string>
      }

      const configData = {
        configType: 'system',
        authorizationUrl: oauthForm.authorizationUrl,
        tokenUrl: oauthForm.tokenUrl,
        userInfoUrl: oauthForm.userInfoUrl,
        scope: oauthForm.scope,
        clientId: oauthForm.clientId,
        clientSecret: oauthForm.clientSecret,
        fieldMapping: fieldMappingObj,
        redirectUrl: oauthForm.redirectUrl,
        enabled: oauthForm.enabled,
      }

      const res: any = await saveOAuthConfig(configData)
      if (res.code === 0) {
        ElMessage.success('OAuth2配置保存成功')
      } else {
        ElMessage.error(res.message || '保存失败')
      }
    } catch (e: any) {
      console.error('保存OAuth2配置失败', e)
      ElMessage.error(e?.message || '保存OAuth2配置失败，请重试')
    } finally {
      oauthSaving.value = false
    }
  })
}

async function loadOAuthConfig() {
  try {
    const res: any = await getOAuthConfig('system')
    if (res.code === 0 && res.data) {
      const data = res.data
      oauthForm.authorizationUrl = data.authorizationUrl || ''
      oauthForm.tokenUrl = data.tokenUrl || ''
      oauthForm.userInfoUrl = data.userInfoUrl || ''
      oauthForm.scope = data.scope || ''
      oauthForm.clientId = data.clientId || ''
      oauthForm.clientSecret = data.clientSecret || ''
      oauthForm.redirectUrl = data.redirectUrl || ''
      oauthForm.enabled = data.enabled || false
      // 字段映射处理
      if (data.fieldMapping && typeof data.fieldMapping === 'object') {
        oauthForm.fieldMapping = JSON.stringify(data.fieldMapping)
      } else if (typeof data.fieldMapping === 'string') {
        oauthForm.fieldMapping = data.fieldMapping
      }
    }
  } catch (e) {
    console.error('加载OAuth配置失败', e)
  }
}

onMounted(() => {
  loadCurrentUser()
  loadUsers()
  loadOAuthConfig()
})
</script>

<style lang="scss" scoped>
.user-manage-view {
  height: 100%;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
  margin: 0;
}

.settings-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 24px;
  }
}

.tab-content {
  .tab-toolbar {
    display: flex;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .toolbar-left {
    display: flex;
    gap: 12px;
  }

  .pagination-container {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}

.action-btns {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  white-space: nowrap;
  gap: 4px;
}

.user-table {
  margin-bottom: 16px;
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
</style>
