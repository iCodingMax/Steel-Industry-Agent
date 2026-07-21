<template>
  <div class="app-settings-view">
    <div class="view-container">
      <div class="app-sidebar">
        <div class="sidebar-header">
          <h3 class="sidebar-title">应用列表</h3>
          <el-button type="primary" size="small" @click="handleCreateApp">
            <el-icon><Plus /></el-icon>
            新建应用
          </el-button>
        </div>

        <el-input v-model="searchKeyword" placeholder="搜索应用" class="search-input" @keyup.enter="loadApplications" />

        <div class="app-list">
          <div
            v-for="app in applications"
            :key="app.id"
            class="app-item"
            :class="{ active: selectedAppId === app.id }"
            @click="selectApp(app)"
          >
            <div class="app-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </div>
            <div class="app-info">
              <div class="app-name">{{ app.name }}</div>
              <div class="app-model">{{ app.modelName }}</div>
            </div>
            <el-tag :type="app.status === 'active' ? 'success' : 'danger'" size="small">
              {{ app.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </div>

          <div v-if="applications.length === 0" class="empty-app-list">
            <el-empty description="暂无应用，点击新建创建" />
          </div>
        </div>
      </div>

      <div class="app-detail">
        <template v-if="currentApp">
          <div class="detail-header">
            <div class="detail-title">
              <h2>{{ currentApp.name }}</h2>
              <span class="detail-desc">{{ currentApp.description || '暂无描述' }}</span>
            </div>
            <div class="detail-actions">
              <el-button @click="handleDeleteApp">删除应用</el-button>
              <el-button type="success" @click="handleSaveAndPublish">保存并发布</el-button>
              <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
            </div>
          </div>

          <el-form :model="appForm" label-width="120px" :rules="appRules" ref="appFormRef" class="app-form">
            <el-card shadow="never" class="form-card">
              <template #header>
                <span class="card-title">基本信息</span>
              </template>
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="应用名称" prop="name">
                    <el-input v-model="appForm.name" placeholder="请输入应用名称" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="应用状态">
                    <el-switch v-model="appForm.status" active-value="active" inactive-value="inactive" active-text="启用" inactive-text="停用" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="应用描述">
                <el-input v-model="appForm.description" type="textarea" :rows="2" placeholder="请输入应用描述" />
              </el-form-item>
            </el-card>

            <el-card shadow="never" class="form-card">
              <template #header>
                <span class="card-title">AI模型设置</span>
              </template>
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="LLM模型">
                    <el-select v-model="appForm.modelName" placeholder="请选择模型">
                      <el-option v-for="model in llmModels" :key="model.id" :label="model.modelName" :value="model.modelName" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="嵌入模型">
                    <el-select v-model="appForm.embeddingModel" placeholder="请选择模型">
                      <el-option v-for="model in embeddingModels" :key="model.id" :label="model.modelName" :value="model.modelName" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="重排模型">
                    <el-select v-model="appForm.rerankModel" placeholder="请选择模型">
                      <el-option v-for="model in rerankModels" :key="model.id" :label="model.modelName" :value="model.modelName" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="最大输出Token">
                    <el-input-number v-model="appForm.maxTokens" :min="1024" :max="100000" style="width: 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="温度参数">
                    <el-slider v-model="appForm.temperature" :min="0" :max="2" :step="0.1" />
                    <span class="slider-value">{{ appForm.temperature }}</span>
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="Top-P参数">
                    <el-slider v-model="appForm.topP" :min="0" :max="1" :step="0.05" />
                    <span class="slider-value">{{ appForm.topP }}</span>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-card>

            <el-card shadow="never" class="form-card">
              <template #header>
                <span class="card-title">提示词设置</span>
              </template>
              <el-form-item label="系统提示词">
                <el-input v-model="appForm.systemPrompt" type="textarea" :rows="5" placeholder="请输入系统提示词，定义AI助手的角色和行为准则" />
              </el-form-item>
              <el-form-item label="用户提示词模板">
                <el-input v-model="appForm.userPromptTemplate" type="textarea" :rows="3" placeholder="用户输入会被填充到这个模板中，例如：请基于以下知识回答问题：{{question}}" />
              </el-form-item>
            </el-card>

            <el-card shadow="never" class="form-card">
              <template #header>
                <span class="card-title">关联知识库</span>
              </template>
              <el-form-item label="关联知识库">
                <el-select v-model="appForm.knowledgeBaseIds" multiple placeholder="请选择知识库" style="width: 100%">
                  <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
                </el-select>
                <p class="form-tip">选择后，AI将基于这些知识库的内容进行回答</p>
              </el-form-item>
            </el-card>

            <el-card shadow="never" class="form-card">
              <template #header>
                <span class="card-title">开场白设置</span>
              </template>
              <el-form-item label="开场白消息">
                <el-input v-model="appForm.greetingMessage" type="textarea" :rows="3" placeholder="用户首次进入对话时显示的欢迎消息" />
              </el-form-item>
            </el-card>
          </el-form>
        </template>

        <div v-else class="empty-detail">
          <el-empty description="请选择一个应用进行配置" />
        </div>
      </div>
    </div>

    <el-dialog v-model="createDialogVisible" title="新建应用" width="500px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" :rules="createRules" ref="createFormRef">
        <el-form-item label="应用名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入应用名称" />
        </el-form-item>
        <el-form-item label="应用描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="请输入应用描述" />
        </el-form-item>
        <el-form-item label="LLM模型">
          <el-select v-model="createForm.modelName" placeholder="请选择模型">
            <el-option v-for="model in llmModels" :key="model.id" :label="model.modelName" :value="model.modelName" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getApplications,
  createApplication,
  updateApplication,
  deleteApplication,
  type Application,
  type ApplicationCreateForm,
  type ApplicationUpdateForm,
} from '@/api/application'
import { getKnowledgeBases } from '@/api/knowledge'
import { getLLMConfigs, type LLMConfigForm } from '@/api/llmConfig'

const loading = ref(false)
const saving = ref(false)
const creating = ref(false)
const searchKeyword = ref('')
const applications = ref<Application[]>([])
const knowledgeBases = ref<any[]>([])
const llmModels = ref<LLMConfigForm[]>([])
const embeddingModels = ref<LLMConfigForm[]>([])
const rerankModels = ref<LLMConfigForm[]>([])

const selectedAppId = ref<number | null>(null)
const currentApp = ref<Application | null>(null)

const appFormRef = ref<FormInstance>()
const appForm = reactive<ApplicationUpdateForm>({
  name: '',
  description: '',
  status: 'active',
  modelName: 'glm-5.1-fp8',
  embeddingModel: 'bge-m3',
  rerankModel: 'bge-reranker-large',
  systemPrompt: '',
  userPromptTemplate: '',
  greetingMessage: '',
  knowledgeBaseIds: [],
  maxTokens: 8192,
  temperature: 0.7,
  topP: 0.9,
})

const appRules: FormRules = {
  name: [{ required: true, message: '请输入应用名称', trigger: 'blur' }],
}

const createDialogVisible = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive<ApplicationCreateForm>({
  name: '',
  description: '',
  modelName: 'glm-5.1-fp8',
  embeddingModel: 'bge-m3',
  rerankModel: 'bge-reranker-large',
  knowledgeBaseIds: [],
  maxTokens: 8192,
  temperature: 0.7,
  topP: 0.9,
})

const createRules: FormRules = {
  name: [{ required: true, message: '请输入应用名称', trigger: 'blur' }],
}

async function loadApplications() {
  loading.value = true
  try {
    const res = await getApplications({
      page: 1,
      pageSize: 100,
      keyword: searchKeyword.value,
    })
    applications.value = (res.data as any).data || []
    if (applications.value.length > 0 && !selectedAppId.value) {
      selectApp(applications.value[0])
    }
  } catch (error) {
    ElMessage.error('加载应用列表失败')
  } finally {
    loading.value = false
  }
}

async function loadKnowledgeBases() {
  try {
    const res = await getKnowledgeBases()
    knowledgeBases.value = (res.data as any) || []
  } catch (error) {
    knowledgeBases.value = []
  }
}

async function loadModels() {
  try {
    const res = await getLLMConfigs()
    const configs = (res.data as any) || []
    llmModels.value = configs.filter((c: LLMConfigForm) => c.modelType === 'llm')
    embeddingModels.value = configs.filter((c: LLMConfigForm) => c.modelType === 'embedding')
    rerankModels.value = configs.filter((c: LLMConfigForm) => c.modelType === 'rerank')
  } catch (error) {
    llmModels.value = []
    embeddingModels.value = []
    rerankModels.value = []
  }
}

function selectApp(app: Application) {
  selectedAppId.value = app.id
  currentApp.value = app
  Object.assign(appForm, {
    name: app.name,
    description: app.description || '',
    status: app.status,
    modelName: app.modelName,
    embeddingModel: app.embeddingModel,
    rerankModel: app.rerankModel,
    systemPrompt: app.systemPrompt || '',
    userPromptTemplate: app.userPromptTemplate || '',
    greetingMessage: app.greetingMessage || '',
    knowledgeBaseIds: [...app.knowledgeBaseIds],
    maxTokens: app.maxTokens,
    temperature: app.temperature,
    topP: app.topP,
  })
}

function handleCreateApp() {
  Object.assign(createForm, {
    name: '',
    description: '',
    modelName: 'glm-5.1-fp8',
    embeddingModel: 'bge-m3',
    rerankModel: 'bge-reranker-large',
    knowledgeBaseIds: [],
    maxTokens: 8192,
    temperature: 0.7,
    topP: 0.9,
  })
  createDialogVisible.value = true
}

async function handleSubmitCreate() {
  if (!createFormRef.value) return
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }

  creating.value = true
  try {
    await createApplication({ ...createForm })
    ElMessage.success('应用创建成功')
    createDialogVisible.value = false
    await loadApplications()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleSave() {
  if (!appFormRef.value || !currentApp.value) return
  try {
    await appFormRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    await updateApplication(currentApp.value.id, { ...appForm })
    ElMessage.success('应用保存成功')
    await loadApplications()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleSaveAndPublish() {
  if (!appFormRef.value || !currentApp.value) return
  try {
    await appFormRef.value.validate()
  } catch {
    return
  }

  appForm.status = 'active'
  saving.value = true
  try {
    await updateApplication(currentApp.value.id, { ...appForm })
    ElMessage.success('应用已保存并发布')
    await loadApplications()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteApp() {
  if (!currentApp.value) return
  try {
    await ElMessageBox.confirm(`确定要删除应用「${currentApp.value.name}」吗？`, '提示', {
      type: 'warning',
    })
    await deleteApplication(currentApp.value.id)
    ElMessage.success('删除成功')
    selectedAppId.value = null
    currentApp.value = null
    await loadApplications()
  } catch {
  }
}

onMounted(() => {
  loadApplications()
  loadKnowledgeBases()
  loadModels()
})
</script>

<style lang="scss" scoped>
.app-settings-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.view-container {
  flex: 1;
  display: flex;
  gap: 20px;
  overflow: hidden;
}

.app-sidebar {
  width: 320px;
  background: #f8fafc;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e2e8f0;
}

.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

.search-input {
  margin: 12px;
}

.app-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.app-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
  border: 1px solid #e2e8f0;

  &:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
  }

  &.active {
    background: #eff6ff;
    border-color: #3b82f6;

    .app-icon {
      color: #3b82f6;
    }
  }

  .app-icon {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #94a3b8;
    flex-shrink: 0;
  }

  .app-info {
    flex: 1;
    min-width: 0;

    .app-name {
      font-size: 14px;
      font-weight: 500;
      color: #1e293b;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .app-model {
      font-size: 12px;
      color: #64748b;
      margin-top: 2px;
    }
  }
}

.empty-app-list {
  padding: 40px 20px;
}

.app-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;

  .detail-title {
    h2 {
      font-size: 20px;
      font-weight: 600;
      margin: 0;
      color: #1a1a2e;
    }

    .detail-desc {
      font-size: 14px;
      color: #64748b;
      margin-top: 4px;
      display: block;
    }
  }

  .detail-actions {
    display: flex;
    gap: 8px;
  }
}

.app-form {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

.form-card {
  margin-bottom: 16px;

  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: #1e293b;
  }
}

.form-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.slider-value {
  font-size: 13px;
  color: #64748b;
  margin-left: 8px;
}

.empty-detail {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  border-radius: 8px;
}
</style>
