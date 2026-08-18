<template>
  <div class="chat-user-view">
    <div class="page-header">
      <h1 class="page-title">对话用户</h1>
    </div>

    <el-tabs v-model="activeTab" class="user-tabs">
      <el-tab-pane label="用户列表" name="list">
        <div class="tab-content">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-input
                v-model="searchKeyword"
                placeholder="搜索用户名、姓名或邮箱"
                clearable
                class="search-input"
                @keyup.enter="handleSearch"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
              <el-select
                v-model="searchStatus"
                placeholder="状态筛选"
                clearable
                class="status-select"
              >
                <el-option label="已启用" value="active" />
                <el-option label="已禁用" value="disabled" />
              </el-select>
              <el-button type="primary" @click="handleSearch">
                <el-icon><Search /></el-icon>
                查询
              </el-button>
            </div>
            <div class="toolbar-right">
              <el-button type="success" @click="openCreateDialog">
                <el-icon><Plus /></el-icon>
                创建用户
              </el-button>
            </div>
          </div>

          <el-table
            v-loading="loading"
            :data="userList"
            class="user-table"
            stripe
            border
          >
            <el-table-column prop="name" label="姓名" min-width="120" align="center" />
            <el-table-column prop="username" label="用户名" min-width="120" align="center" />
            <el-table-column label="状态" min-width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'danger'" effect="light">
                  {{ row.status === 'active' ? '已启用' : '已禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="email" label="邮箱" min-width="160" align="center">
              <template #default="{ row }">
                {{ row.email || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="phone" label="手机号" min-width="120" align="center">
              <template #default="{ row }">
                {{ row.phone || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="用户来源" min-width="120" align="center">
              <template #default="{ row }">
                <el-tag :type="row.userSource === 'oauth2' ? 'primary' : 'info'" effect="light">
                  {{ row.userSource === 'oauth2' ? 'OAuth2' : '本地创建' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="createdAt" label="创建时间" min-width="160" align="center">
              <template #default="{ row }">
                {{ formatDate(row.createdAt) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <el-switch
                  v-model="row.status"
                  active-value="active"
                  inactive-value="disabled"
                  @change="handleToggleStatus(row)"
                />
                <el-button link type="primary" size="small" @click="openEditDialog(row)">
                  编辑
                </el-button>
                <el-button link type="warning" size="small" @click="handleResetPassword(row)">
                  重置密码
                </el-button>
                <el-button link type="danger" size="small" @click="handleDelete(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :total="total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
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
          <el-form :model="oauthForm" label-width="140px" :rules="oauthRules" ref="oauthFormRef">
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
              <el-input v-model="oauthForm.scope" placeholder="请输入连接范围，如 profile" />
            </el-form-item>
            <el-form-item label="客户端ID*" prop="clientId">
              <el-input v-model="oauthForm.clientId" placeholder="请输入客户端ID" />
            </el-form-item>
            <el-form-item label="客户端密钥*" prop="clientSecret">
              <el-input v-model="oauthForm.clientSecret" type="password" show-password placeholder="请输入客户端密钥" />
            </el-form-item>
            <el-form-item label="字段映射*" prop="fieldMapping">
              <el-input v-model="oauthForm.fieldMapping" type="textarea" :rows="3" placeholder='请输入字段映射JSON，如 {"username":"preferred_username","nick_name":"nickname","email":"email"}' />
            </el-form-item>
            <el-form-item label="回调地址*" prop="redirectUrl">
              <el-input v-model="oauthForm.redirectUrl" placeholder="请输入回调地址" />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="oauthForm.enabled">启用 OAuth2 认证</el-checkbox>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSaveOAuth" :loading="oauthSaving">保存配置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建/编辑用户弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingUser ? '编辑对话用户' : '创建对话用户'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="formData.username"
            :disabled="!!editingUser"
            placeholder="请输入用户名"
          />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="formData.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="formData.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="formData.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="formData.status">
            <el-radio value="active">已启用</el-radio>
            <el-radio value="disabled">已禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog
      v-model="pwdDialogVisible"
      title="重置密码"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="pwdFormRef"
        :model="pwdForm"
        :rules="pwdRules"
        label-width="100px"
      >
        <el-form-item label="新密码" prop="newPassword">
          <el-select
            v-model="pwdForm.newPassword"
            style="width: 100%"
            placeholder="选择新密码"
          >
            <el-option label="默认密码 123456" value="123456" />
            <el-option label="自定义密码" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="pwdForm.newPassword === 'custom'" label="自定义密码" prop="customPassword">
          <el-input
            v-model="pwdForm.customPassword"
            type="password"
            show-password
            placeholder="请输入新密码(至少6位)"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResetPassword" :loading="pwdSaving">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Search, Plus, Key } from '@element-plus/icons-vue'
import {
  getChatUserList,
  createChatUser,
  updateChatUser,
  deleteChatUser,
  toggleChatUserStatus,
  resetChatUserPassword,
  type ChatUser,
} from '@/api/chatUser'
import { getOAuthConfig, saveOAuthConfig } from '@/api/oauth'

const activeTab = ref('list')
const loading = ref(false)
const oauthSaving = ref(false)
const pwdSaving = ref(false)
const userList = ref<ChatUser[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const searchStatus = ref('')

const dialogVisible = ref(false)
const pwdDialogVisible = ref(false)
const editingUser = ref<ChatUser | null>(null)
const pwdUserId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const pwdFormRef = ref<FormInstance>()
const oauthFormRef = ref<FormInstance>()

const formData = reactive({
  username: '',
  name: '',
  email: '',
  phone: '',
  status: 'active',
})

const pwdForm = reactive({
  newPassword: '123456',
  customPassword: '',
})

const oauthForm = reactive({
  authorizationUrl: '',
  tokenUrl: '',
  userInfoUrl: '',
  scope: '',
  clientId: '',
  clientSecret: '',
  fieldMapping: '',
  redirectUrl: 'http://localhost:5173/chat/api/auth/oauth2',
  enabled: false,
})

const formRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
}

const pwdRules: FormRules = {
  newPassword: [{ required: true, message: '请选择新密码', trigger: 'change' }],
  customPassword: [
    {
      validator: (_rule, value, callback) => {
        if (pwdForm.newPassword === 'custom' && (!value || value.length < 6)) {
          callback(new Error('密码长度不能少于6位'))
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

function handleResetPassword(row: ChatUser) {
  pwdUserId.value = row.id
  pwdForm.newPassword = '123456'
  pwdForm.customPassword = ''
  pwdDialogVisible.value = true
}

async function submitResetPassword() {
  if (!pwdFormRef.value || !pwdUserId.value) return
  
  try {
    await pwdFormRef.value.validate()
  } catch {
    return
  }
  
  pwdSaving.value = true
  try {
    const newPassword = pwdForm.newPassword === 'custom' ? pwdForm.customPassword : '123456'
    const res: any = await resetChatUserPassword(pwdUserId.value, { newPassword })
    if (res.code === 0) {
      ElMessage.success(res.message || '密码修改成功')
      pwdDialogVisible.value = false
    } else {
      ElMessage.error(res.message || '密码修改失败')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.message || '密码修改失败')
  } finally {
    pwdSaving.value = false
  }
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

async function loadUsers() {
  loading.value = true
  try {
    const res: any = await getChatUserList({
      keyword: searchKeyword.value || undefined,
      status: searchStatus.value || undefined,
      page: currentPage.value,
      pageSize: pageSize.value,
    })
    if (res.code === 0 && res.data) {
      userList.value = res.data.items || []
      total.value = res.data.total || 0
    }
  } catch (error: any) {
    console.error('获取用户列表失败', error)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  loadUsers()
}

function openCreateDialog() {
  editingUser.value = null
  Object.assign(formData, {
    username: '',
    name: '',
    email: '',
    phone: '',
    status: 'active',
  })
  dialogVisible.value = true
}

function openEditDialog(row: ChatUser) {
  editingUser.value = row
  Object.assign(formData, {
    username: row.username,
    name: row.name || '',
    email: row.email || '',
    phone: row.phone || '',
    status: row.status,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      if (editingUser.value) {
        const res: any = await updateChatUser(editingUser.value.id, formData)
        if (res.code === 0) {
          ElMessage.success('更新成功')
          dialogVisible.value = false
          loadUsers()
        }
      } else {
        const res: any = await createChatUser(formData)
        if (res.code === 0) {
          ElMessage.success('创建成功')
          dialogVisible.value = false
          loadUsers()
        }
      }
    } catch (error: any) {
      console.error('操作失败', error)
    }
  })
}

async function handleToggleStatus(row: ChatUser) {
  try {
    const res: any = await toggleChatUserStatus(row.id)
    if (res.code === 0) {
      ElMessage.success('状态更新成功')
      loadUsers()
    }
  } catch (error: any) {
    console.error('状态更新失败', error)
  }
}

async function handleDelete(row: ChatUser) {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${row.username}" 吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
    const res: any = await deleteChatUser(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      loadUsers()
    }
  } catch (e) {
    // 用户取消
  }
}

async function handleSaveOAuth() {
  if (!oauthFormRef.value) return
  await oauthFormRef.value.validate(async (valid) => {
    if (!valid) return
    oauthSaving.value = true
    try {
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
        configType: 'chat',
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
    const res: any = await getOAuthConfig('chat')
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

watch(activeTab, (newVal) => {
  if (newVal === 'oauth') {
    loadOAuthConfig()
  }
})

onMounted(() => {
  loadUsers()
})
</script>

<style lang="scss" scoped>
.chat-user-view {
  .page-header {
    margin-bottom: 20px;

    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #1f2937;
      margin: 0 0 8px;
    }

    .page-desc {
      font-size: 14px;
      color: #6b7280;
      margin: 0;
    }
  }

  .user-tabs {
    .tab-content {
      padding-top: 16px;
    }
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .toolbar-left {
      display: flex;
      gap: 12px;

      .search-input {
        width: 280px;
      }

      .status-select {
        width: 140px;
      }
    }
  }

  .user-table {
    margin-bottom: 16px;
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
  }

  .config-section {
    padding: 24px;
    background: #fff;
    border-radius: 8px;

    .section-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 18px;
      font-weight: 600;
      color: #1f2937;
      margin: 0 0 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #e5e7eb;
    }
  }
}
</style>
