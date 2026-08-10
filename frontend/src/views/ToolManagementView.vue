<template>
  <div class="tool-management-view">
    <div class="page-header">
      <h2 class="page-title">工具管理</h2>
    </div>

    <el-tabs v-model="activeTab" class="config-tabs">
      <!-- MCP 管理 -->
      <el-tab-pane label="MCP 管理" name="mcp">
        <div class="tab-content">
          <div class="tab-toolbar">
            <div class="toolbar-left">
              <el-input
                v-model="mcpSearch"
                placeholder="搜索MCP..."
                style="width: 240px"
                clearable
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>
            <el-button type="primary" @click="handleAddMCP">
              <el-icon><Plus /></el-icon>
              新增 MCP
            </el-button>
          </div>

          <el-table :data="filteredMCPs" style="width: 100%" v-loading="mcpLoading">
            <el-table-column prop="name" label="MCP名称" min-width="160" />
            <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'danger'" effect="plain">
                  {{ row.status === 'active' ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <div class="action-btns">
                  <el-button link type="primary" @click="handleTestMCP(row)">测试连接</el-button>
                  <el-button link type="primary" @click="handleEditMCP(row)">编辑</el-button>
                  <el-button link type="danger" @click="handleDeleteMCP(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Skills 管理 -->
      <el-tab-pane label="Skills 管理" name="skill">
        <div class="tab-content">
          <div class="tab-toolbar">
            <div class="toolbar-left">
              <el-input
                v-model="skillSearch"
                placeholder="搜索Skill..."
                style="width: 240px"
                clearable
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </div>
            <el-button type="primary" @click="handleAddSkill">
              <el-icon><Plus /></el-icon>
              新增 Skill
            </el-button>
          </div>

          <el-table :data="filteredSkills" style="width: 100%" v-loading="skillLoading">
            <el-table-column prop="name" label="Skill名称" min-width="160" />
            <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
            <el-table-column prop="skill_file_name" label="文件名" min-width="160" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'danger'" effect="plain">
                  {{ row.status === 'active' ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <div class="action-btns">
                  <el-button link type="primary" @click="handleEditSkill(row)">编辑</el-button>
                  <el-button link type="danger" @click="handleDeleteSkill(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- MCP 创建/编辑对话框 -->
    <el-dialog v-model="mcpDialogVisible" :title="isEditMCP ? '编辑 MCP' : '创建 MCP'" width="600px" destroy-on-close>
      <el-form :model="mcpForm" label-width="160px" :rules="mcpRules" ref="mcpFormRef">
        <div class="form-section-title">基础信息</div>
        <el-form-item label="名称" prop="name">
          <el-input v-model="mcpForm.name" placeholder="请输入 MCP 名称" maxlength="64" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="mcpForm.description" type="textarea" :rows="3" placeholder="请输入描述" maxlength="128" show-word-limit />
        </el-form-item>
        <div class="form-section-title">MCP 服务</div>
        <el-form-item label="MCP Server Config" prop="mcp_config_json">
          <div class="config-editor-wrapper">
            <el-input
              v-model="mcpForm.mcp_config_json"
              type="textarea"
              :rows="6"
              placeholder='请输入 MCP Server 配置 (MaxKB格式)&#10;{&#10;  "服务名": {&#10;    "url": "http://xxx/sse?key=xxx",&#10;    "transport": "sse"&#10;  }&#10;}'
              @blur="validateMCPConfig"
            />
            <div class="config-tip">仅支持 SSE、Streamable HTTP 协议</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mcpDialogVisible = false">取消</el-button>
        <el-button type="success" @click="handleTestMCPConfig" :loading="testing">测试连接</el-button>
        <el-button type="primary" @click="handleSaveMCP" :loading="saving">创建</el-button>
      </template>
    </el-dialog>

    <!-- Skill 创建/编辑对话框 -->
    <el-dialog v-model="skillDialogVisible" :title="isEditSkill ? '编辑 Skill' : '创建 Skill'" width="600px" destroy-on-close>
      <el-form :model="skillForm" label-width="120px" :rules="skillRules" ref="skillFormRef">
        <div class="form-section-title">基础信息</div>
        <el-form-item label="名称" prop="name">
          <el-input v-model="skillForm.name" placeholder="请输入 Skills 名称" maxlength="64" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="skillForm.description" type="textarea" :rows="3" placeholder="请输入描述" maxlength="128" show-word-limit />
        </el-form-item>
        <div class="form-section-title">Skills 文件</div>
        <el-form-item :label="isEditSkill ? 'Skill 文件' : 'Skill 文件'" :prop="isEditSkill ? '' : 'file'">
          <el-upload
            class="skill-uploader"
            drag
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :file-list="skillFileList"
            :limit="1"
            accept=".zip"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">拖拽文件至上传或 <em>选择文件</em></div>
            <template #tip>
              <div class="el-upload__tip">
                <span v-if="isEditSkill && !skillForm.file">未选择新文件时保留原文件</span>
                <span v-else>支持格式：ZIP，大小不超过 100 MB</span>
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <div v-if="isEditSkill && currentSkillFileName && !skillForm.file" class="current-file-tip">
          <template v-if="!removeExistingFile">
            <el-icon><Document /></el-icon>
            <span class="file-name">当前文件：{{ currentSkillFileName }}</span>
            <el-icon class="remove-file-icon" @click="handleRemoveExistingFile" title="删除文件">
              <Close />
            </el-icon>
          </template>
          <template v-else>
            <el-icon><Warning /></el-icon>
            <span class="file-name removed">文件已标记删除，保存后生效</span>
            <el-button link type="primary" size="small" @click="handleRestoreFile">恢复</el-button>
          </template>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="skillDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveSkill" :loading="saving">{{ isEditSkill ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, UploadFilled, Document, Close, Warning } from '@element-plus/icons-vue'
import {
  getTools,
  createMCP,
  updateMCP,
  deleteTool,
  createSkill,
  updateSkill,
  testMCPConnection
} from '@/api/tool'

// === 状态变量 ===
const activeTab = ref('mcp')
const mcpSearch = ref('')
const skillSearch = ref('')
const mcpLoading = ref(false)
const skillLoading = ref(false)
const saving = ref(false)
const testing = ref(false)

// 数据列表
const mcpList = ref<any[]>([])
const skillList = ref<any[]>([])

// 过滤后的数据
const filteredMCPs = computed(() => {
  if (!mcpSearch.value) return mcpList.value
  const search = mcpSearch.value.toLowerCase()
  return mcpList.value.filter(item =>
    item.name.toLowerCase().includes(search) ||
    item.description?.toLowerCase().includes(search)
  )
})

const filteredSkills = computed(() => {
  if (!skillSearch.value) return skillList.value
  const search = skillSearch.value.toLowerCase()
  return skillList.value.filter(item =>
    item.name.toLowerCase().includes(search) ||
    item.description?.toLowerCase().includes(search)
  )
})

// === MCP 对话框 ===
const mcpDialogVisible = ref(false)
const isEditMCP = ref(false)
const editingMCPId = ref<number | null>(null)
const mcpFormRef = ref()

const defaultMCPConfig = {
  "mcp-service": {
    "url": "http://example.com/sse?key=xxx",
    "transport": "sse"
  }
}

const mcpForm = reactive({
  name: '',
  description: '',
  mcp_config_json: JSON.stringify(defaultMCPConfig, null, 2)
})

const mcpRules = {
  name: [{ required: true, message: '请输入MCP名称', trigger: 'blur' }],
  mcp_config_json: [{ required: true, message: '请输入MCP Server配置', trigger: 'blur' }]
}

// === Skill 对话框 ===
const skillDialogVisible = ref(false)
const isEditSkill = ref(false)
const editingSkillId = ref<number | null>(null)
const currentSkillFileName = ref('')
const removeExistingFile = ref(false)
const skillFormRef = ref()

const skillForm = reactive({
  name: '',
  description: '',
  file: null as File | null
})

const skillFileList = ref<any[]>([])

const skillRules = {
  name: [{ required: true, message: '请输入Skill名称', trigger: 'blur' }],
  file: [{
    required: true,
    validator: (_rule: any, value: any, callback: any) => {
      if (!isEditSkill.value && !value) {
        callback(new Error('请上传Skill文件'))
      } else {
        callback()
      }
    },
    trigger: 'change'
  }]
}

// === 方法 ===
function formatDate(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function loadMCPs() {
  mcpLoading.value = true
  try {
    const res: any = await getTools('mcp')
    mcpList.value = res.data || []
  } catch (e) {
    console.error('加载MCP列表失败', e)
  } finally {
    mcpLoading.value = false
  }
}

async function loadSkills() {
  skillLoading.value = true
  try {
    const res: any = await getTools('skill')
    skillList.value = res.data || []
  } catch (e) {
    console.error('加载Skill列表失败', e)
  } finally {
    skillLoading.value = false
  }
}

function resetMCPForm() {
  mcpForm.name = ''
  mcpForm.description = ''
  mcpForm.mcp_config_json = JSON.stringify(defaultMCPConfig, null, 2)
  editingMCPId.value = null
  isEditMCP.value = false
}

function handleAddMCP() {
  resetMCPForm()
  mcpDialogVisible.value = true
}

async function handleEditMCP(row: any) {
  isEditMCP.value = true
  editingMCPId.value = row.id
  mcpForm.name = row.name
  mcpForm.description = row.description || ''
  mcpForm.mcp_config_json = JSON.stringify(row.mcp_config || defaultMCPConfig, null, 2)
  mcpDialogVisible.value = true
}

function validateMCPConfig(): boolean {
  try {
    const config = JSON.parse(mcpForm.mcp_config_json)
    // 验证 MaxKB 格式: {"服务名": {"url": "...", "transport": "sse"}}
    if (typeof config !== 'object' || Array.isArray(config)) {
      ElMessage.error('MCP配置必须是对象格式')
      return false
    }
    const keys = Object.keys(config)
    if (keys.length !== 1) {
      ElMessage.error('MCP配置必须包含且仅包含一个服务配置')
      return false
    }
    const [serviceName] = keys
    const serviceConfig = config[serviceName]
    if (typeof serviceConfig !== 'object' || !serviceConfig.url) {
      ElMessage.error(`服务 "${serviceName}" 必须包含 url 字段`)
      return false
    }
    if (serviceConfig.transport && !['sse', 'streamable-http'].includes(serviceConfig.transport)) {
      ElMessage.error(`服务 "${serviceName}" 传输协议仅支持 sse 或 streamable-http`)
      return false
    }
    return true
  } catch {
    ElMessage.error('MCP配置必须是有效的JSON格式')
    return false
  }
}

async function handleTestMCPConfig() {
  if (!validateMCPConfig()) return
  
  testing.value = true
  try {
    const config = JSON.parse(mcpForm.mcp_config_json)
    const res: any = await testMCPConnection(config)
    if (res.code === 0) {
      ElMessage.success('MCP连接测试成功')
    } else {
      ElMessage.error(res.message || '连接测试失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '连接测试失败')
  } finally {
    testing.value = false
  }
}

async function handleTestMCP(row: any) {
  testing.value = true
  try {
    const res: any = await testMCPConnection(row.mcp_config)
    if (res.code === 0) {
      ElMessage.success('MCP连接测试成功')
    } else {
      ElMessage.error(res.message || '连接测试失败')
    }
  } catch (e: any) {
    ElMessage.error('连接测试失败')
  } finally {
    testing.value = false
  }
}

async function handleSaveMCP() {
  try {
    await mcpFormRef.value.validate()
  } catch {
    return
  }
  
  if (!validateMCPConfig()) return
  
  saving.value = true
  try {
    const config = JSON.parse(mcpForm.mcp_config_json)
    
    if (isEditMCP.value && editingMCPId.value) {
      const res: any = await updateMCP(editingMCPId.value, {
        name: mcpForm.name,
        description: mcpForm.description,
        mcp_config: config
      })
      if (res.code === 0) {
        ElMessage.success('MCP更新成功')
        mcpDialogVisible.value = false
        await loadMCPs()
      } else {
        ElMessage.error(res.message || '更新失败')
      }
    } else {
      const res: any = await createMCP({
        name: mcpForm.name,
        description: mcpForm.description,
        mcp_config: config
      })
      if (res.code === 0) {
        ElMessage.success('MCP创建成功')
        mcpDialogVisible.value = false
        await loadMCPs()
      } else {
        ElMessage.error(res.message || '创建失败')
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteMCP(row: any) {
  try {
    await ElMessageBox.confirm(`确定要删除 MCP "${row.name}" 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res: any = await deleteTool(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadMCPs()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// === Skill 方法 ===
function resetSkillForm() {
  skillForm.name = ''
  skillForm.description = ''
  skillForm.file = null
  skillFileList.value = []
  isEditSkill.value = false
  editingSkillId.value = null
  currentSkillFileName.value = ''
  removeExistingFile.value = false
}

function handleAddSkill() {
  resetSkillForm()
  skillDialogVisible.value = true
}

function handleEditSkill(row: any) {
  isEditSkill.value = true
  editingSkillId.value = row.id
  skillForm.name = row.name
  skillForm.description = row.description || ''
  skillForm.file = null
  skillFileList.value = []
  currentSkillFileName.value = row.skill_file_name || ''
  removeExistingFile.value = false
  skillDialogVisible.value = true
}

function handleRemoveExistingFile() {
  ElMessageBox.confirm('确定要删除当前已上传的文件吗？', '删除确认', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    removeExistingFile.value = true
    ElMessage.success('文件已标记删除，保存后生效')
  }).catch(() => {})
}

function handleRestoreFile() {
  removeExistingFile.value = false
  ElMessage.success('已恢复文件')
}

function handleFileChange(file: any) {
  if (file.size > 100 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 100 MB')
    return false
  }
  if (!file.name.endsWith('.zip')) {
    ElMessage.error('只支持 ZIP 格式文件')
    return false
  }
  skillForm.file = file.raw
  // 选择新文件时重置删除标志
  removeExistingFile.value = false
}

function handleFileRemove() {
  skillForm.file = null
}

async function handleSaveSkill() {
  try {
    await skillFormRef.value.validate()
  } catch {
    return
  }
  
  if (!isEditSkill.value && !skillForm.file) {
    // 创建模式必须上传文件
    ElMessage.error('请上传 Skill 文件')
    return
  }
  
  if (isEditSkill.value && !skillForm.file && !currentSkillFileName && !removeExistingFile.value) {
    // 编辑模式：原文件不存在且未上传新文件，也未标记删除
    ElMessage.warning('请上传 Skill 文件')
    return
  }
  
  saving.value = true
  try {
    const formData = new FormData()
    formData.append('name', skillForm.name)
    formData.append('description', skillForm.description || '')
    
    if (isEditSkill.value && editingSkillId.value) {
      if (skillForm.file) {
        // 上传了新文件，替换原文件
        formData.append('file', skillForm.file)
        formData.append('remove_file', 'false')
      } else if (removeExistingFile.value) {
        // 标记删除文件
        formData.append('remove_file', 'true')
      }
      const res: any = await updateSkill(editingSkillId.value, formData)
      if (res.code === 0) {
        ElMessage.success('Skill更新成功')
        skillDialogVisible.value = false
        await loadSkills()
      } else {
        ElMessage.error(res.message || '更新失败')
      }
    } else {
      formData.append('file', skillForm.file!)
      const res: any = await createSkill(formData)
      if (res.code === 0) {
        ElMessage.success('Skill创建成功')
        skillDialogVisible.value = false
        await loadSkills()
      } else {
        ElMessage.error(res.message || '创建失败')
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteSkill(row: any) {
  try {
    await ElMessageBox.confirm(`确定要删除 Skill "${row.name}" 吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const res: any = await deleteTool(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadSkills()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// === 生命周期 ===
onMounted(() => {
  loadMCPs()
  loadSkills()
})
</script>

<style scoped>
.tool-management-view {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
}

.tab-content {
  padding: 20px 0;
}

.tab-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar-left {
  display: flex;
  gap: 12px;
}

.action-btns {
  display: flex;
  gap: 4px;
}

.form-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin: 16px 0 12px;
  padding-left: 8px;
  border-left: 3px solid #409eff;
}

.config-editor-wrapper {
  width: 100%;
}

.config-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.skill-uploader {
  width: 100%;
}

.skill-uploader :deep(.el-upload-dragger) {
  padding: 40px;
}

.current-file-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  margin-top: 8px;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 6px;
  font-size: 13px;
  color: #67c23a;
}

.current-file-tip .file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  
  &.removed {
    color: #f56c6c;
    text-decoration: line-through;
  }
}

.current-file-tip .remove-file-icon {
  cursor: pointer;
  font-size: 16px;
  color: #909399;
  margin-left: auto;
  padding: 2px;
  border-radius: 4px;
  transition: all 0.2s;
  
  &:hover {
    color: #f56c6c;
    background: #fef0f0;
  }
}
</style>
