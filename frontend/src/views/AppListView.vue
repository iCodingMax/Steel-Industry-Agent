<template>
  <div class="app-list-view">
    <template v-if="!currentApp">
      <div class="page-header">
        <h2 class="page-title">应用管理</h2>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新建应用
        </el-button>
      </div>

      <div class="app-grid">
        <div v-for="app in applications" :key="app.id" class="app-card" @click="handleDetail(app)">
          <div class="app-icon">
            <el-icon :size="28"><Setting /></el-icon>
          </div>
          <div class="app-info">
            <h3 class="app-name">{{ app.name }}</h3>
            <p class="app-desc">{{ app.description || '暂无描述' }}</p>
            <div class="app-meta">
              <span class="app-model">
                <el-icon><Monitor /></el-icon>
                {{ app.modelName }}
              </span>
              <span class="app-status" :class="app.status">
                {{ statusText[app.status] || app.status }}
              </span>
            </div>
          </div>
          <div class="app-actions">
            <el-button text type="primary" @click.stop="handleDetail(app)">
              <el-icon><View /></el-icon>
              管理
            </el-button>
          </div>
        </div>

        <div class="app-card add-app" @click="handleCreate">
          <el-icon :size="48" class="add-icon"><Plus /></el-icon>
          <span>新建应用</span>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="app-detail-view">
        <div class="page-header">
          <div class="header-left">
            <el-button text @click="backToList">
              <el-icon><ArrowLeft /></el-icon>
              返回列表
            </el-button>
            <h2 class="page-title">{{ currentApp?.name }}</h2>
        </div>
        <div class="header-actions">
          <el-button @click="handleDeleteApp">删除应用</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
          <el-button type="success" @click="handlePublish">发布</el-button>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="app-tabs">
        <el-tab-pane label="应用设置" name="settings">
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
                <span class="card-title">关联设置</span>
              </template>
              <el-form-item label="关联知识库">
                <el-select v-model="appForm.knowledgeBaseIds" multiple placeholder="请选择知识库" style="width: 100%">
                  <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
                </el-select>
                <p class="form-tip">选择后，AI将基于这些知识库的内容进行回答</p>
              </el-form-item>
              <el-form-item label="关联数据库">
                <el-select v-model="appForm.datasourceIds" multiple placeholder="请选择数据源" style="width: 100%">
                  <el-option v-for="ds in datasources" :key="ds.id" :label="ds.name" :value="ds.id" />
                </el-select>
                <p class="form-tip">选择后，AI将基于数据库中的数据进行问答</p>
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
        </el-tab-pane>

        <el-tab-pane label="集成设置" name="integration">
          <el-card shadow="never" class="embed-card">
            <template #header>
              <span class="card-title">iFrame嵌入代码</span>
            </template>
            <el-form :model="integrationForm" label-width="120px">
              <el-row :gutter="20">
                <el-col :span="8">
                  <el-form-item label="嵌入宽度">
                    <el-input v-model="integrationForm.iframeWidth" placeholder="例如：400px 或 100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="嵌入高度">
                    <el-input v-model="integrationForm.iframeHeight" placeholder="例如：600px" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item label="边框样式">
                    <el-select v-model="integrationForm.iframeBorder" placeholder="选择边框">
                      <el-option label="无边框" value="0" />
                      <el-option label="细边框" value="1px solid #ccc" />
                      <el-option label="圆角边框" value="1px solid #ccc; border-radius: 8px" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>

            <div class="code-section">
              <div class="code-header">
                <span>嵌入代码</span>
                <el-button type="text" @click="copyEmbedCode">
                  <el-icon><CopyDocument /></el-icon>
                  复制代码
                </el-button>
              </div>
              <pre class="code-block"><code>{{ embedCode }}</code></pre>
            </div>

            <div class="preview-section">
              <div class="preview-header">
                <span>预览效果</span>
              </div>
              <div class="preview-container">
                <iframe :src="previewUrl" :width="integrationForm.iframeWidth" :height="integrationForm.iframeHeight" :style="{ border: integrationForm.iframeBorder === '0' ? 'none' : integrationForm.iframeBorder }" title="智能助手嵌入预览"></iframe>
              </div>
            </div>
          </el-card>

          <el-card shadow="never" class="api-card">
            <template #header>
              <span class="card-title">API密钥管理</span>
            </template>
            <div class="api-key-section">
              <div class="api-key-row">
                <label>API密钥</label>
                <div class="api-key-value">
                  <span class="key-masked">{{ maskedApiKey }}</span>
                  <el-button type="text" @click="toggleApiKeyVisibility" size="small">
                    {{ showApiKey ? '隐藏' : '显示' }}
                  </el-button>
                </div>
              </div>
              <div class="api-key-actions">
                <el-button type="warning" @click="handleRegenerateApiKey">重新生成密钥</el-button>
                <el-button type="primary" @click="copyApiKey">复制密钥</el-button>
              </div>
              <p class="api-tip">
                <el-icon><InfoFilled /></el-icon>
                密钥用于验证嵌入请求的合法性。重新生成后，旧密钥将立即失效。
              </p>
            </div>
          </el-card>

          <el-card shadow="never" class="security-card">
            <template #header>
              <span class="card-title">安全设置</span>
            </template>
            <el-form :model="integrationForm" label-width="120px">
              <el-form-item label="允许的来源">
                <el-input v-model="allowedOriginsText" type="textarea" :rows="3" placeholder="输入允许嵌入的域名，每行一个，如：https://example.com" />
                <p class="form-tip">留空则允许所有来源，建议限制为具体域名以提高安全性</p>
              </el-form-item>
              <el-form-item label="自定义域名">
                <el-input v-model="integrationForm.customDomain" placeholder="如：https://chat.example.com" />
                <p class="form-tip">设置后可使用自定义域名访问嵌入页面</p>
              </el-form-item>
            </el-form>
            <el-button type="primary" @click="handleSaveIntegration">保存设置</el-button>
          </el-card>

          <el-card shadow="never" class="usage-card">
            <template #header>
              <span class="card-title">使用说明</span>
            </template>
            <div class="usage-steps">
              <h4>嵌入到业务系统</h4>
              <ol>
                <li>复制上方的iFrame代码</li>
                <li>将代码粘贴到业务系统页面的HTML中</li>
                <li>根据需要调整宽度和高度</li>
                <li>确保业务系统域名已添加到"允许的来源"列表中</li>
              </ol>
              <h4>API调用方式</h4>
              <pre class="code-block small"><code>POST /api/v1/sessions/embed/chat
Content-Type: application/json
X-API-Key: {{ currentApp?.apiKey }}

{
  "applicationId": {{ currentApp?.id }},
  "question": "用户问题",
  "sessionId": "可选，用于保持对话上下文"
}</code></pre>
            </div>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>
    </template>

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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  Plus,
  Setting,
  Monitor,
  View,
  ArrowLeft,
  CopyDocument,
  InfoFilled,
} from '@element-plus/icons-vue'
import {
  getApplications,
  createApplication,
  updateApplication,
  deleteApplication,
  regenerateApiKey,
  type Application,
  type ApplicationCreateForm,
  type ApplicationUpdateForm,
} from '@/api/application'
import { getKnowledgeBases } from '@/api/knowledge'
import { getLLMConfigs, type LLMConfigForm } from '@/api/llmConfig'
import { getDatasources } from '@/api/datasource'

const loading = ref(false)
const saving = ref(false)
const creating = ref(false)
const applications = ref<Application[]>([])
const knowledgeBases = ref<any[]>([])
const datasources = ref<any[]>([])
const llmModels = ref<LLMConfigForm[]>([])
const embeddingModels = ref<LLMConfigForm[]>([])
const rerankModels = ref<LLMConfigForm[]>([])

const currentApp = ref<Application | null>(null)
const activeTab = ref('settings')
const showApiKey = ref(false)

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
  datasourceIds: [],
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

const integrationForm = reactive({
  iframeWidth: '400px',
  iframeHeight: '600px',
  iframeBorder: '0',
  customDomain: '',
})

const allowedOriginsText = ref('')

const statusText: Record<string, string> = {
  active: '启用',
  inactive: '停用',
}

const maskedApiKey = computed(() => {
  if (!currentApp.value?.apiKey) return ''
  if (showApiKey.value) return currentApp.value.apiKey
  return currentApp.value.apiKey.substring(0, 8) + '****************'
})

const previewUrl = computed(() => {
  if (!currentApp.value) return ''
  const params = new URLSearchParams()
  params.set('appName', encodeURIComponent(currentApp.value.name || ''))
  params.set('greetingMessage', encodeURIComponent(currentApp.value.greetingMessage || ''))
  return `/chat/embed/${currentApp.value.id}?${params.toString()}`
})

const embedCode = computed(() => {
  if (!currentApp.value) return ''
  const origin = window.location.origin
  const url = `${origin}/chat/embed/${currentApp.value.id}`
  const borderStyle = integrationForm.iframeBorder === '0' ? 'none' : integrationForm.iframeBorder
  return `<iframe src="${url}" width="${integrationForm.iframeWidth}" height="${integrationForm.iframeHeight}" style="border: ${borderStyle}" frameborder="0" title="智能助手"></iframe>`
})

async function loadApplications() {
  loading.value = true
  try {
    const res = await getApplications({
      page: 1,
      page_size: 100,
    })
    applications.value = (res.data as any).data || []
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

async function loadDatasources() {
  try {
    const res = await getDatasources() as any
    if (res.code === 0) {
      datasources.value = res.data
    }
  } catch (error) {
    datasources.value = []
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

function handleCreate() {
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

function handleDetail(app: Application) {
  currentApp.value = app
  activeTab.value = 'settings'
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
    datasourceIds: [...app.datasourceIds],
    maxTokens: app.maxTokens,
    temperature: app.temperature,
    topP: app.topP,
  })
  integrationForm.iframeWidth = app.iframeWidth || '400px'
  integrationForm.iframeHeight = String(app.iframeHeight) || '600px'
  integrationForm.customDomain = app.customDomain || ''
  allowedOriginsText.value = (app.iframeAllowedOrigins || []).join('\n')
}

function backToList() {
  currentApp.value = null
  activeTab.value = 'settings'
  loadApplications()
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

async function handlePublish() {
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
    ElMessage.success('应用已发布')
    await loadApplications()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '发布失败')
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
    currentApp.value = null
    await loadApplications()
  } catch {
  }
}

function toggleApiKeyVisibility() {
  showApiKey.value = !showApiKey.value
}

async function copyEmbedCode() {
  try {
    await navigator.clipboard.writeText(embedCode.value)
    ElMessage.success('嵌入代码已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function copyApiKey() {
  if (!currentApp.value?.apiKey) return
  try {
    await navigator.clipboard.writeText(currentApp.value.apiKey)
    ElMessage.success('API密钥已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function handleRegenerateApiKey() {
  if (!currentApp.value) return
  try {
    await ElMessageBox.confirm('重新生成API密钥后，旧密钥将立即失效，是否继续？', '确认', {
      type: 'warning',
    })
    const res = await regenerateApiKey(currentApp.value.id)
    currentApp.value.apiKey = (res.data.data as { apiKey: string }).apiKey
    showApiKey.value = true
    ElMessage.success('API密钥已重新生成')
  } catch {
  }
}

async function handleSaveIntegration() {
  if (!currentApp.value) return
  saving.value = true
  try {
    const allowedOrigins = allowedOriginsText.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line)

    await updateApplication(currentApp.value.id, {
      iframeWidth: integrationForm.iframeWidth,
      iframeHeight: parseInt(integrationForm.iframeHeight) || 600,
      iframeAllowedOrigins: allowedOrigins,
      customDomain: integrationForm.customDomain,
    })
    ElMessage.success('集成设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadApplications()
  loadKnowledgeBases()
  loadDatasources()
  loadModels()
})
</script>

<style lang="scss" scoped>
.app-list-view {
  height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .page-title {
    font-size: 20px;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }
}

.app-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.app-card {
  background: #fff;
  border: 1px solid $card-border;
  border-radius: $card-radius;
  padding: 24px;
  transition: all 0.3s ease;
  cursor: pointer;

  &:hover {
    box-shadow: $card-shadow;
    transform: translateY(-2px);
  }
}

.app-icon {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(59, 130, 246, 0.2));
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $primary-color;
  margin-bottom: 16px;
}

.app-info {
  margin-bottom: 16px;
}

.app-name {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
  margin-bottom: 6px;
}

.app-desc {
  font-size: 13px;
  color: $text-secondary;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.app-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.app-model {
  display: flex;
  align-items: center;
  gap: 4px;
  color: $text-secondary;
}

.app-status {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;

  &.active {
    background: rgba(16, 185, 129, 0.1);
    color: $success-color;
  }

  &.inactive {
    background: rgba(239, 68, 68, 0.1);
    color: $danger-color;
  }
}

.app-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid $card-border;
}

.add-app {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 2px dashed $card-border;
  color: $text-placeholder;
  min-height: 200px;
  gap: 12px;
  font-size: 14px;

  &:hover {
    border-color: $primary-color;
    color: $primary-color;
    background: rgba(59, 130, 246, 0.02);
  }
}

.add-icon {
  color: inherit;
}

.app-detail-view {
  height: 100%;
  display: flex;
  flex-direction: column;

  .app-tabs {
    flex: 1;
    overflow: hidden;
    background: #fff;
    border-radius: 0 $card-radius $card-radius $card-radius;

    :deep(.el-tabs__content) {
      height: calc(100% - 55px);
      overflow: auto;
      padding: 20px;
    }
  }
}

.app-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-card {
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

.embed-card,
.api-card,
.security-card,
.usage-card {
  margin-bottom: 16px;

  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: #1e293b;
  }
}

.code-section {
  margin-top: 16px;

  .code-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 13px;
    color: #64748b;
  }

  .code-block {
    background: #1e293b;
    color: #e2e8f0;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 13px;
    margin: 0;

    &.small {
      font-size: 12px;
      padding: 10px;
    }
  }
}

.preview-section {
  margin-top: 16px;

  .preview-header {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 8px;
  }

  .preview-container {
    border: 1px dashed #cbd5e1;
    border-radius: 8px;
    padding: 16px;
    background: #f8fafc;

    iframe {
      display: block;
      margin: 0 auto;
      background: #fff;
      border-radius: 4px;
    }
  }
}

.api-key-section {
  .api-key-row {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 12px;

    label {
      font-size: 14px;
      color: #374151;
      font-weight: 500;
    }

    .api-key-value {
      flex: 1;
      display: flex;
      align-items: center;
      gap: 8px;
      background: #f3f4f6;
      padding: 8px 12px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 14px;
      color: #1f2937;
    }
  }

  .api-key-actions {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
  }

  .api-tip {
    font-size: 12px;
    color: #6b7280;
    margin: 0;
    padding-left: 20px;
  }
}

.usage-steps {
  h4 {
    font-size: 14px;
    font-weight: 600;
    color: #374151;
    margin: 16px 0 8px;
  }

  ol {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
    color: #4b5563;
    line-height: 1.8;
  }
}
</style>