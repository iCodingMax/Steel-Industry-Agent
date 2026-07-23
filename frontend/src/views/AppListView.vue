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
          <div class="settings-layout">
            <div class="settings-left">
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
                    <el-col :span="12">
                      <el-form-item label="LLM模型">
                        <el-select v-model="appForm.modelName" placeholder="请选择模型">
                          <el-option v-for="model in llmModels" :key="model.id" :label="model.modelName" :value="model.modelName" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="最大输出Token">
                        <el-input-number v-model="appForm.maxTokens" :min="1024" :max="100000" style="width: 100%" />
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="温度参数">
                        <el-slider v-model="appForm.temperature" :min="0" :max="2" :step="0.1" />
                        <span class="slider-value">{{ appForm.temperature }}</span>
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
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
            </div>

            <div class="settings-right">
              <el-card shadow="never" class="preview-card">
                <template #header>
                  <div class="preview-header">
                    <span class="card-title">调试预览</span>
                    <el-button class="refresh-btn" @click="clearMessages" title="清理历史记录">
                      <el-icon><RefreshLeft /></el-icon>
                      <span>清理</span>
                    </el-button>
                  </div>
                </template>
                <div class="chat-container">
                  <div ref="chatMessagesRef" class="chat-messages">
                    <div v-if="debugMessages.length === 0" class="chat-welcome">
                      <div class="welcome-icon">
                        <svg class="robot-icon" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <!-- 天线 -->
                          <line x1="32" y1="4" x2="32" y2="14" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
                          <circle cx="32" cy="4" r="3" fill="#fbbf24"/>
                          <!-- 头部 -->
                          <rect x="14" y="14" width="36" height="24" rx="6" fill="#e2e8f0"/>
                          <rect x="14" y="14" width="36" height="24" rx="6" stroke="#fff" stroke-width="1.5"/>
                          <!-- 眼睛 -->
                          <circle cx="24" cy="26" r="4" fill="#3b82f6"/>
                          <circle cx="40" cy="26" r="4" fill="#3b82f6"/>
                          <circle cx="24" cy="25" r="1.5" fill="#fff"/>
                          <circle cx="40" cy="25" r="1.5" fill="#fff"/>
                          <!-- 嘴巴 -->
                          <rect x="26" y="32" width="12" height="2.5" rx="1.25" fill="#3b82f6"/>
                          <!-- 身体 -->
                          <rect x="18" y="40" width="28" height="16" rx="4" fill="#cbd5e1"/>
                          <rect x="18" y="40" width="28" height="16" rx="4" stroke="#fff" stroke-width="1.5"/>
                          <!-- 身体按钮 -->
                          <circle cx="32" cy="48" r="3" fill="#3b82f6"/>
                          <circle cx="32" cy="48" r="1.2" fill="#fff"/>
                          <!-- 手臂 -->
                          <rect x="6" y="42" width="10" height="6" rx="3" fill="#94a3b8"/>
                          <rect x="48" y="42" width="10" height="6" rx="3" fill="#94a3b8"/>
                          <!-- 钢铁火花装饰 -->
                          <circle cx="10" cy="38" r="1" fill="#fbbf24"/>
                          <circle cx="54" cy="38" r="1" fill="#fbbf24"/>
                          <circle cx="8" cy="50" r="0.8" fill="#fb923c"/>
                          <circle cx="56" cy="50" r="0.8" fill="#fb923c"/>
                        </svg>
                      </div>
                      <p>{{ appForm.greetingMessage || '你好，有什么我可以帮你的吗？' }}</p>
                    </div>
                    <div
                      v-for="msg in debugMessages"
                      :key="msg.id"
                      class="message-item"
                      :class="msg.role"
                    >
                      <div class="message-content" :class="msg.role">
                        <div class="avatar-group">
                          <div class="avatar" :class="msg.role === 'user' ? 'user-avatar' : 'assistant-avatar'">
                            <template v-if="msg.role === 'user'">
                              <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:20px;height:20px">
                                <path d="M20 4C12 4 8 10 8 16c0 4 1 6 2 8l2 4c1 2 2 4 4 4h8c2 0 3-2 4-4l2-4c1-2 2-4 2-8 0-6-4-12-12-12z" fill="#dc2626"/>
                              </svg>
                            </template>
                            <template v-else>
                              <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:20px;height:20px">
                                <circle cx="20" cy="20" r="16" stroke="#60a5fa" stroke-width="1.5" fill="none"/>
                                <circle cx="20" cy="20" r="8" fill="#60a5fa"/>
                              </svg>
                            </template>
                          </div>
                          <span class="avatar-label">{{ msg.role === 'user' ? '我' : '助手' }}</span>
                        </div>
                        <div class="message-bubble-wrap">
                          <div class="message-bubble">
                            <template v-if="msg.isStreaming">
                              <span>{{ stripMarkdown(msg.content) }}</span>
                              <span class="typing-cursor">|</span>
                            </template>
                            <template v-else>{{ stripMarkdown(msg.content) }}</template>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="chat-input-area">
                    <el-input
                      v-model="debugInput"
                      placeholder="请输入问题"
                      @keydown.enter.exact="handleDebugSend"
                      class="debug-input"
                    >
                      <template #append>
                        <el-button type="primary" :loading="debugSending" @click="handleDebugSend">
                          <el-icon><Message /></el-icon>
                        </el-button>
                      </template>
                    </el-input>
                  </div>
                </div>
              </el-card>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="集成设置" name="integration">
          <el-card shadow="never" class="integration-card">
            <div class="integration-header">
              <div class="app-info">
                <div class="app-icon">
                  <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="6" y="10" width="36" height="30" rx="4" fill="#3b82f6"/>
                    <rect x="12" y="16" width="8" height="16" rx="2" fill="#fff"/>
                    <rect x="28" y="16" width="8" height="16" rx="2" fill="rgba(255,255,255,0.6)"/>
                  </svg>
                </div>
                <div class="app-name">{{ currentApp?.name }}</div>
              </div>
            </div>

            <div class="public-link-section">
              <div class="link-row">
                <span class="link-label">公开访问链接</span>
                <el-switch v-model="publicAccessEnabled" active-text="开启" inactive-text="关闭" />
              </div>
              <div class="link-display" v-if="publicAccessEnabled">
                <input type="text" :value="publicAccessUrl" readonly class="link-input" />
                <el-button type="text" @click="copyPublicLink" class="copy-btn">
                  <el-icon><CopyDocument /></el-icon>
                </el-button>
                <el-button type="text" @click="openPublicLink" class="open-btn">
                  <el-icon><View /></el-icon>
                </el-button>
              </div>
            </div>

            <div class="action-buttons">
              <el-button class="action-btn" @click="openChat">
                <el-icon><Message /></el-icon>
                <span>去对话</span>
              </el-button>
              <el-button class="action-btn" @click="showEmbedModal = true">
                <el-icon><Monitor /></el-icon>
                <span>嵌入第三方</span>
              </el-button>
              <el-button class="action-btn" @click="showAccessModal = true">
                <el-icon><Setting /></el-icon>
                <span>访问限制</span>
              </el-button>
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

    <el-dialog v-model="showEmbedModal" title="嵌入第三方" width="700px" destroy-on-close>
      <div class="embed-modal-content">
        <div class="embed-mode-tabs">
          <div class="embed-mode active">
            <div class="mode-icon full-icon">
              <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="4" y="8" width="40" height="32" rx="4" fill="#f1f5f9" stroke="#e2e8f0" stroke-width="2"/>
                <rect x="8" y="12" width="32" height="6" rx="2" fill="#cbd5e1"/>
                <rect x="8" y="22" width="28" height="14" rx="2" fill="#e2e8f0"/>
                <rect x="8" y="26" width="20" height="4" rx="1" fill="#cbd5e1"/>
              </svg>
            </div>
            <div class="mode-name">页面嵌入</div>
          </div>
        </div>

        <div class="embed-code-section">
          <div class="code-header">
            <span>复制以下代码进行嵌入</span>
            <el-button type="text" @click="copyEmbedCode" class="copy-code-btn">
              <el-icon><CopyDocument /></el-icon>
              复制代码
            </el-button>
          </div>
          <pre class="embed-code-block"><code>{{ currentEmbedCode }}</code></pre>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="showAccessModal" title="访问限制" width="500px" destroy-on-close>
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
      <template #footer>
        <el-button @click="showAccessModal = false">取消</el-button>
        <el-button type="primary" @click="handleSaveAccessSettings">保存设置</el-button>
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
  RefreshLeft,
  Message,
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

const publicAccessEnabled = ref(true)
const showEmbedModal = ref(false)
const showAccessModal = ref(false)

const publicAccessUrl = computed(() => {
  if (!currentApp.value) return ''
  return `${window.location.origin}/chat/embed/${currentApp.value.id}`
})

const currentEmbedCode = computed(() => {
  if (!currentApp.value) return ''
  const origin = window.location.origin
  const baseUrl = `${origin}/chat/embed/${currentApp.value.id}`
  return '<iframe src="' + baseUrl + '" style="width: 100%; height: 100%;" frameborder="0" allow="microphone"></iframe>'
})

function stripMarkdown(text: string): string {
  return text.replace(/\*\*/g, '')
}

interface DebugMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
}

const debugInput = ref('')
const debugSending = ref(false)
const debugMessages = ref<DebugMessage[]>([])
const chatMessagesRef = ref<HTMLElement>()

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
    await navigator.clipboard.writeText(currentEmbedCode.value)
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

function openChat() {
  if (!currentApp.value) return
  window.open(`/chat/embed/${currentApp.value.id}`, '_blank')
}

async function copyPublicLink() {
  try {
    await navigator.clipboard.writeText(publicAccessUrl.value)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

function openPublicLink() {
  if (!currentApp.value) return
  window.open(publicAccessUrl.value, '_blank')
}

async function handleSaveAccessSettings() {
  if (!currentApp.value) return
  saving.value = true
  try {
    const allowedOrigins = allowedOriginsText.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line)

    await updateApplication(currentApp.value.id, {
      iframeAllowedOrigins: allowedOrigins,
      customDomain: integrationForm.customDomain,
    })
    showAccessModal.value = false
    ElMessage.success('访问限制已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function scrollToBottom() {
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
  }
}

function clearMessages() {
  debugMessages.value = []
}

async function handleDebugSend() {
  if (!debugInput.value.trim() || !currentApp.value) return

  const userMsg: DebugMessage = {
    id: Date.now(),
    role: 'user',
    content: debugInput.value.trim(),
  }
  debugMessages.value.push(userMsg)
  debugInput.value = ''
  scrollToBottom()

  debugSending.value = true
  const aiMsg = reactive<DebugMessage>({
    id: Date.now() + 1,
    role: 'assistant',
    content: '',
    isStreaming: true,
  })
  debugMessages.value.push(aiMsg)
  scrollToBottom()

  try {
    const knowledgeBaseId = appForm.knowledgeBaseIds?.[0] || null
    const response = await fetch(`/api/v1/sessions/embed/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify({
        sessionId: `debug-${currentApp.value.id}-${Date.now()}`,
        question: userMsg.content,
        knowledgeBaseId,
        applicationId: currentApp.value.id,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`请求失败: ${response.status} - ${errorText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法读取响应')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmedLine = line.trim()
        if (!trimmedLine.startsWith('data: ')) continue

        try {
          const jsonStr = trimmedLine.substring(6)
          const data = JSON.parse(jsonStr)

          if (data.type === 'content') {
            aiMsg.content += data.content
            aiMsg.isStreaming = true
            scrollToBottom()
          } else if (data.type === 'done') {
            aiMsg.isStreaming = false
          } else if (data.type === 'error') {
            aiMsg.content = `错误: ${data.message}`
            aiMsg.isStreaming = false
          }
        } catch (e) {
          console.warn('解析SSE消息失败:', e)
        }
      }
    }
  } catch (error: any) {
    console.error('调试对话失败:', error)
    aiMsg.content = `发送失败: ${error.message || '未知错误'}`
    aiMsg.isStreaming = false
  } finally {
    debugSending.value = false
    scrollToBottom()
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

.integration-card {
  max-width: 600px;
  margin: 0 auto;

  :deep(.el-card__body) {
    padding: 24px;
  }

  .integration-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid $card-border;

    .app-info {
      display: flex;
      align-items: center;
      gap: 12px;

      .app-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 0;

        svg {
          width: 24px;
          height: 24px;
        }
      }

      .app-name {
        font-size: 18px;
        font-weight: 600;
        color: $text-primary;
        margin-bottom: 0;
      }
    }

    .public-access-badge {
      font-size: 12px;
      padding: 4px 12px;
      background: rgba(59, 130, 246, 0.1);
      color: $primary-color;
      border-radius: 12px;
      font-weight: 500;
    }
  }

  .public-link-section {
    margin-bottom: 24px;
    padding: 16px;
    background: #f8fafc;
    border-radius: 12px;

    .link-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      .link-label {
        font-size: 14px;
        font-weight: 500;
        color: $text-primary;
      }
    }

    .link-display {
      display: flex;
      align-items: center;
      gap: 8px;

      .link-input {
        flex: 1;
        padding: 8px 12px;
        border: 1px solid $card-border;
        border-radius: 8px;
        font-size: 13px;
        font-family: monospace;
        color: $text-secondary;
        background: #fff;

        &:focus {
          outline: none;
          border-color: $primary-color;
        }
      }

      .copy-btn,
      .open-btn {
        padding: 8px;
        color: $text-secondary;

        &:hover {
          color: $primary-color;
        }
      }
    }
  }

  .action-buttons {
    display: flex;
    gap: 12px;

    .action-btn {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      padding: 16px 12px;
      border: 1px solid $card-border;
      border-radius: 12px;
      background: #fff;
      color: $text-primary;
      transition: all 0.2s;

      :deep(.el-icon) {
        font-size: 20px;
        color: $primary-color;
      }

      span {
        font-size: 13px;
        font-weight: 500;
      }

      &:hover {
        border-color: $primary-color;
        background: rgba(59, 130, 246, 0.05);
      }
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

.settings-layout {
  display: flex;
  gap: 24px;
  height: calc(100vh - 180px);

  .settings-left {
    width: 50%;
    flex-shrink: 0;
    overflow-y: auto;
    padding-right: 8px;
    display: flex;
    flex-direction: column;
    gap: 16px;

    :deep(.el-card) {
      margin-bottom: 0;
    }
  }

  .settings-right {
    width: 50%;
    flex-shrink: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .preview-card {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-radius: 12px;

    :deep(.el-card__body) {
      padding: 0;
      flex: 1;
      display: flex;
      flex-direction: column;
    }

    .preview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 24px;
      background-color: #ffffff;
      border-bottom: 1px solid #e2e8f0;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);

      .card-title {
        font-size: 16px;
        font-weight: 600;
        color: #1e293b;
      }

      .refresh-btn {
        border-radius: 8px;
        padding: 6px 14px;
        display: flex;
        align-items: center;
        gap: 4px;
        border: 1px solid #e2e8f0;
        color: #475569;
        transition: all 0.2s;

        &:hover {
          color: #3b82f6;
          border-color: #3b82f6;
          background-color: #eff6ff;
        }
      }
    }
  }

  .chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    background-color: #f1f5f9;
  }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 24px;
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);

    .chat-welcome {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 60px 40px;
      text-align: center;

      .welcome-icon {
        width: 100px;
        height: 100px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        border-radius: 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px rgba(59, 130, 246, 0.3);

        svg {
          width: 64px;
          height: 64px;
        }
      }

      p {
        font-size: 14px;
        color: #64748b;
        margin: 0;
        max-width: 300px;
        line-height: 1.6;
      }
    }

    .message-item {
      display: flex;
      margin-bottom: 24px;

      &.user {
        justify-content: flex-end;
      }

      &.assistant {
        justify-content: flex-start;
      }
    }

    .message-content {
      display: flex;
      max-width: 85%;
      min-width: 0;
      overflow: hidden;
      gap: 12px;

      &.user {
        flex-direction: row-reverse;

        .message-bubble-wrap {
          display: flex;
          flex-direction: column;
          gap: 4px;
          flex: 0 1 auto;
          min-width: 0;
          max-width: 100%;
          overflow: hidden;
          align-items: flex-end;
        }

        .message-bubble {
          background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
          color: #ffffff;
          border-radius: 16px 16px 4px 16px;
          position: relative;
          padding: 16px 20px;
          font-size: 14px;
          line-height: 1.7;
          word-break: break-word;
          overflow-wrap: break-word;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
          width: auto;
          max-width: 100%;
        }
      }

      &.assistant {
        flex-direction: row;

        .message-bubble-wrap {
          display: flex;
          flex-direction: column;
          gap: 4px;
          flex: 1;
          min-width: 0;
          align-items: stretch;
          overflow: hidden;
        }

        .message-bubble {
          background-color: #ffffff;
          color: #1e293b;
          border-radius: 16px 16px 16px 4px;
          position: relative;
          padding: 16px 20px;
          font-size: 14px;
          line-height: 1.7;
          word-break: break-word;
          overflow-wrap: break-word;
          overflow: hidden;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
          width: 100%;

          .typing-cursor {
            animation: blink 1s infinite;
          }
        }
      }

      .avatar-label {
        font-size: 12px;
        font-weight: 600;
        color: #1e293b;
        white-space: nowrap;
      }

      .avatar-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        flex-shrink: 0;
      }

      .avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;

        &.user-avatar {
          background: linear-gradient(135deg, #fde8e8 0%, #fef3c7 100%);
          box-shadow: 0 2px 8px rgba(220, 38, 38, 0.15);
        }

        &.assistant-avatar {
          background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
          box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
        }
      }
    }
  }

  .chat-input-area {
    background-color: #ffffff;
    border-top: 1px solid #e2e8f0;
    box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.04);
    padding: 12px 20px;

    .debug-input {
      :deep(.el-input__wrapper) {
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 0 0 1px #e2e8f0 inset;
        transition: all 0.2s;

        &:hover {
          box-shadow: 0 0 0 1px #3b82f6 inset;
        }

        &.is-focus {
          border-color: #3b82f6;
          box-shadow: 0 0 0 1px #3b82f6 inset, 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
      }

      :deep(.el-input__inner) {
        padding: 12px 16px;
        font-size: 14px;
      }
    }

    :deep(.el-button) {
      &.el-button--primary {
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        border: none;
        border-radius: 10px;
        padding: 10px 24px;
        font-weight: 500;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);

        &:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        }

        &:disabled {
          opacity: 0.7;
        }
      }
    }
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.embed-modal-content {
  .embed-mode-tabs {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;

    .embed-mode {
      flex: 1;
      padding: 16px;
      border: 2px solid $card-border;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.2s;
      text-align: center;

      &.active {
        border-color: $primary-color;
        background: rgba(59, 130, 246, 0.05);
      }

      .mode-icon {
        width: 64px;
        height: 64px;
        margin: 0 auto 12px;
        display: flex;
        align-items: center;
        justify-content: center;

        svg {
          width: 48px;
          height: 48px;
        }
      }

      .mode-name {
        font-size: 14px;
        font-weight: 600;
        color: $text-primary;
      }
    }
  }

  .embed-code-section {
    background: #f8fafc;
    border-radius: 12px;
    padding: 16px;

    .code-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      span {
        font-size: 14px;
        font-weight: 500;
        color: $text-primary;
      }

      .copy-code-btn {
        color: $primary-color;
      }
    }

    .embed-code-block {
      background: #0f172a;
      color: #e2e8f0;
      padding: 16px;
      border-radius: 8px;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 12px;
      line-height: 1.6;
      overflow-x: auto;
      margin: 0;

      code {
        background: none;
        padding: 0;
        font-family: inherit;
      }
    }
  }
}

.display-settings {
  padding: 20px;
  text-align: center;

  p {
    color: $text-secondary;
    font-size: 14px;
  }
}
</style>