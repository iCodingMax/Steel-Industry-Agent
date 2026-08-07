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
                  <el-form-item label="应用名称" prop="name">
                    <el-input v-model="appForm.name" placeholder="请输入应用名称" />
                  </el-form-item>
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
                    <div class="textarea-wrapper">
                      <el-input 
                        ref="systemPromptRef"
                        v-model="appForm.systemPrompt" 
                        type="textarea" 
                        :rows="5" 
                        placeholder="请输入系统提示词，定义AI助手的角色和行为准则"
                        @focus="systemPromptFocused = true"
                        @blur="systemPromptFocused = false"
                        @input="checkPromptOverflow"
                      />
                      <div class="textarea-ellipsis" v-if="appForm.systemPrompt && !systemPromptFocused && isPromptOverflow">...</div>
                    </div>
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
                    <p class="form-tip">选择后，智能助手将基于这些知识库的内容进行回答</p>
                  </el-form-item>
                  <el-form-item label="关联数据库">
                    <el-select v-model="appForm.datasourceIds" multiple placeholder="请选择数据源" style="width: 100%">
                      <el-option v-for="ds in datasources" :key="ds.id" :label="ds.name" :value="ds.id" />
                    </el-select>
                    <p class="form-tip">选择后，智能助手将基于数据库中的数据进行问答</p>
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

                <el-card shadow="never" class="form-card">
                  <template #header>
                    <span class="card-title">集成设置</span>
                  </template>
                  <el-form-item label="公开访问">
                    <div class="integration-content">
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
                          <span>第三方集成</span>
                        </el-button>
                      </div>
                    </div>
                  </el-form-item>
                  <el-form-item label="身份验证">
                    <div class="auth-config">
                      <el-switch
                        v-model="authConfig.requireAuth"
                        active-text="开启"
                        inactive-text="关闭"
                        @change="handleAuthToggle"
                      />
                      <p class="form-tip" v-if="authConfig.requireAuth">
                        开启后，应用发布的智能助手支持账号登录
                      </p>
                      <p class="form-tip" v-else>
                        关闭后，应用发布的智能助手支持访客模式
                      </p>
                    </div>
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
                  <ChatPanel
                    :messages="debugMessages"
                    v-model="debugInput"
                    :isSending="debugSending"
                    welcomeTitle=""
                    :welcomeDesc="appForm.greetingMessage || '你好，有什么我可以帮你的吗？'"
                    size="sm"
                    @send="handleDebugSend"
                    @copy="copyMessageContent"
                    @regenerate="regenerateDebugMessage"
                    @edit="submitDebugEdit"
                    @sql="handleSql"
                    @reference="handleReference"
                    @export="handleDebugExport"
                  />
                </div>
              </el-card>
            </div>
          </div>
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

    <el-dialog v-model="showEmbedModal" title="第三方集成" width="700px" destroy-on-close>
      <div class="embed-modal-content">
        <div class="embed-mode-tabs">
          <div 
            class="embed-mode" 
            :class="{ active: embedMode === 'fullscreen' }"
            @click="embedMode = 'fullscreen'"
          >
            <div class="mode-icon full-icon">
              <img src="@/assets/embedMode-fullscreen.png" alt="网页嵌入" />
            </div>
            <div class="mode-name">网页嵌入</div>
          </div>
          <div 
            class="embed-mode" 
            :class="{ active: embedMode === 'floating' }"
            @click="embedMode = 'floating'"
          >
            <div class="mode-icon float-icon">
              <img src="@/assets/embedMode-floating.png" alt="浮窗助手" />
            </div>
            <div class="mode-name">浮窗助手</div>
          </div>
        </div>

        <div class="embed-code-section">
          <div class="code-header">
            <span>{{ embedMode === 'fullscreen' ? '复制以下代码进行嵌入' : '复制以下代码进行嵌入' }}</span>
            <el-button type="text" @click="copyEmbedCode" class="copy-code-btn">
              <el-icon><CopyDocument /></el-icon>
              复制代码
            </el-button>
          </div>
          <pre class="embed-code-block"><code>{{ currentEmbedCode }}</code></pre>
          <div class="embed-tip" v-if="embedMode === 'fullscreen'">
            <p>💡 网页嵌入说明：</p>
            <ul>
              <li>将参考代码复制到业务系统前端项目中，作为独立页面路由文件</li>
            </ul>
          </div>
          <div class="embed-tip" v-if="embedMode === 'floating'">
            <p>💡 浮窗模式说明：</p>
            <ul>
              <li>嵌入后右下角会显示机器人图标</li>
              <li>点击图标可展开小窗口进行对话</li>
              <li>支持小窗口展开模式</li>
            </ul>
          </div>
        </div>
      </div>
    </el-dialog>

    
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import * as XLSX from 'xlsx'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import { copyToClipboard } from '@/utils/clipboard'
import {
  Plus,
  Setting,
  Monitor,
  CopyDocument,
  Link,
  RefreshLeft,
  ArrowLeft,
  View,
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

const systemPromptFocused = ref(false)
const systemPromptRef = ref<any>()
const isPromptOverflow = ref(false)

function checkPromptOverflow() {
  nextTick(() => {
    // 优先通过 ref 获取
    let textarea = systemPromptRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement
    // 如果 ref 方式失败，使用 document.querySelector 兜底
    if (!textarea) {
      textarea = document.querySelector('.textarea-wrapper textarea') as HTMLTextAreaElement
    }
    if (textarea) {
      isPromptOverflow.value = textarea.scrollHeight > textarea.clientHeight + 10
    }
  })
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

const publicAccessEnabled = ref(true)
const showEmbedModal = ref(false)
const embedMode = ref<'fullscreen' | 'floating'>('fullscreen')

const authConfig = reactive({
  requireAuth: true,
})

const publicAccessUrl = computed(() => {
  if (!currentApp.value) return ''
  return `${window.location.origin}/chat/${currentApp.value.accessHash}`
})

const currentEmbedCode = computed(() => {
  if (!currentApp.value) return ''
  const origin = window.location.origin

  if (embedMode.value === 'fullscreen') {
    // 网页嵌入模式：使用业务系统的 app-iframe 组件嵌入（单行格式）
    const baseUrl = `${origin}/chat/${currentApp.value.accessHash}`
    return '<route lang="json5">{ meta: { label: \'智能助手\', isSkip403Check: true } }</'
      + 'route><'
      + 'script lang="ts" setup>const iframeSrc = `' + baseUrl + '`;</'
      + 'script><'
      + 'template> <app-iframe class="app-iframe" :src="iframeSrc" allow="microphone" /> </'
      + 'template><'
      + 'style lang="scss"></'
      + 'style>'
  } else {
    // 浮窗模式：script嵌入
    const token = currentApp.value.accessHash
    const protocol = window.location.protocol.replace(':', '')
    const host = window.location.host
    const scriptTag = '<script async defer src="' + origin + '/chat-embed.js?token=' + token + '&protocol=' + protocol + '&host=' + host + '"></' + 'script>'
    return scriptTag
  }
})

function stripMarkdown(text: string): string {
  return text.replace(/\*\*/g, '')
}

interface DebugMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  type?: 'text' | 'data'
  isStreaming?: boolean
  thinkingSteps?: Array<{
    step: number
    title: string
    description: string
  }>
  sqlTraces?: Array<{
    sql: string
    rows: number
  }>
  dataResult?: any[]
  columnMeta?: any[]
  chartType?: string
  references?: Array<{
    documentName: string
    content: string
    score: number
  }>
  elapsedTime?: number
  queryTime?: number
}

const debugInput = ref('')
const debugSending = ref(false)
const debugMessages = ref<DebugMessage[]>([])

function getFieldAlias(fieldName: string, columnMeta?: any[]): string | null {
  if (!columnMeta || columnMeta.length === 0) return null
  // 兼容不同的字段名格式：name（后端返回）或 columnName（其他来源）
  const meta = columnMeta.find((m: any) => (m.name || m.columnName) === fieldName)
  // 兼容不同的别名字段：comment（后端返回）或 columnAlias（其他来源）
  return meta?.comment || meta?.columnAlias || null
}

async function copyMessageContent(content: string) {
  const ok = await copyToClipboard(content)
  ok ? ElMessage.success('已复制') : ElMessage.error('复制失败')
}

async function handleSql(sql: string) {
  const ok = await copyToClipboard(sql)
  ok ? ElMessage.success('SQL已复制到剪贴板') : ElMessage.error('复制失败，请手动复制')
}

function handleReference(_reference: any) {
}

// 提交编辑（调试预览）
function submitDebugEdit(msg: any, content: string) {
  if (!content.trim()) {
    ElMessage.warning('请输入内容')
    return
  }
  msg.content = content.trim()
  msg.isStreaming = false
  debugInput.value = msg.content
  handleDebugSend()
}

// 重新生成调试消息
function regenerateDebugMessage(msg: any) {
  const msgIndex = debugMessages.value.findIndex((m) => m.id === msg.id)
  if (msgIndex <= 0) {
    ElMessage.error('无法重新生成此消息')
    return
  }

  const prevMsg = debugMessages.value[msgIndex - 1]
  if (!prevMsg || prevMsg.role !== 'user') {
    ElMessage.error('无法重新生成此消息')
    return
  }

  debugInput.value = prevMsg.content
  handleDebugSend()
}

function getTableName(sqlTraces: any[]) {
  if (!sqlTraces || sqlTraces.length === 0) return ''
  const sql = sqlTraces[0].sql
  const match = sql.match(/FROM\s+(\w+)/i)
  return match ? match[1] : ''
}

function getDataColumns(data: any[], columnMeta?: any[]) {
  if (!data || data.length === 0) return []
  const keys = Object.keys(data[0])
  return keys.map((key) => ({
    prop: key,
    label: getFieldAlias(key, columnMeta) || key,
    minWidth: 120,
  }))
}

function getNumericColumns(data: any[], columnMeta?: any[]) {
  if (!data || data.length === 0) return []
  const keys = Object.keys(data[0])
  return keys
    .filter((key) => {
      const val = data[0][key]
      return typeof val === 'number' || (!isNaN(Number(val)) && val !== null && val !== '')
    })
    .map((key) => ({
      prop: key,
      label: getFieldAlias(key, columnMeta) || key,
      minWidth: 120,
    }))
}

async function copySql(sql: string) {
  const ok = await copyToClipboard(sql)
  ok ? ElMessage.success('SQL已复制到剪贴板') : ElMessage.error('复制失败，请手动复制')
}

// 导出Excel
function exportToExcel(data: any[], columnMeta?: any[], fileName?: string) {
  if (!data || data.length === 0) {
    ElMessage.warning('没有数据可导出')
    return
  }

  const cols = getDataColumns(data, columnMeta)
  const headers = cols.map((c) => c.label)
  const rows = data.map((row) => cols.map((col) => String(row[col.prop] ?? '')))

  const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows])
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, '数据')

  const name = fileName || `数据导出_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}`
  XLSX.writeFile(workbook, `${name}.xlsx`)
}

// 导出图表为图片
function exportChartToImage(chartOption: any) {
  if (!chartOption) {
    ElMessage.warning('没有图表可导出')
    return
  }

  try {
    const canvas = document.createElement('canvas')
    canvas.width = 800
    canvas.height = 400
    canvas.style.display = 'none'
    document.body.appendChild(canvas)

    const chart = echarts.init(canvas, undefined, {
      renderer: 'canvas',
    })
    chart.setOption(chartOption)

    setTimeout(() => {
      const url = chart.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff',
      })

      chart.dispose()
      document.body.removeChild(canvas)

      const link = document.createElement('a')
      link.download = `图表导出_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.png`
      link.href = url
      link.click()
    }, 500)
  } catch (error) {
    console.error('图表导出失败:', error)
    ElMessage.error('图表导出失败，请重试')
  }
}

// 处理导出命令
function handleDebugExport(cmd: string, msg: DebugMessage, chartOption?: any, dataViewMode?: string) {
  if (cmd === 'excel') {
    exportToExcel(msg.dataResult || [], msg.columnMeta)
  } else if (cmd === 'image') {
    exportChartToImage(chartOption)
  }
}

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
  return `/chat/${currentApp.value.accessHash}?${params.toString()}`
})

const embedCode = computed(() => {
  if (!currentApp.value) return ''
  const origin = window.location.origin
  const url = `${origin}/chat/${currentApp.value.accessHash}`
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
      // 兼容分页格式：新接口返回 {total, list}，旧接口直接返回数组
      if (res.data && Array.isArray(res.data.list)) {
        datasources.value = res.data.list
      } else if (Array.isArray(res.data)) {
        datasources.value = res.data
      } else {
        datasources.value = []
      }
    }
  } catch (error) {
    console.error('加载数据源失败', error)
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
  authConfig.requireAuth = app.requireAuth ?? true
  // 检测系统提示词是否溢出
  checkPromptOverflow()
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
  const ok = await copyToClipboard(currentEmbedCode.value)
  ok ? ElMessage.success('嵌入代码已复制') : ElMessage.error('复制失败')
}

async function copyApiKey() {
  if (!currentApp.value?.apiKey) return
  const ok = await copyToClipboard(currentApp.value.apiKey)
  ok ? ElMessage.success('API密钥已复制') : ElMessage.error('复制失败')
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
    await updateApplication(currentApp.value.id, {
      iframeWidth: '100%',
      iframeHeight: 600,
      requireAuth: authConfig.requireAuth,
    })
    ElMessage.success('集成设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function handleAuthToggle(val: boolean) {
  if (!currentApp.value) return
  updateApplication(currentApp.value.id, {
    requireAuth: val,
  }).catch(() => {
    ElMessage.error('保存失败')
  })
}

function openChat() {
  if (!currentApp.value) return
  window.open(`/chat/${currentApp.value.accessHash}`, '_blank')
}

async function copyPublicLink() {
  const ok = await copyToClipboard(publicAccessUrl.value)
  ok ? ElMessage.success('链接已复制') : ElMessage.error('复制失败')
}

function openPublicLink() {
  if (!currentApp.value) return
  window.open(publicAccessUrl.value, '_blank')
}

function scrollToBottom() {
  nextTick(() => {
    const el = document.querySelector('.preview-card .chat-panel .chat-messages') as HTMLElement
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function clearMessages() {
  debugMessages.value = []
}

async function handleDebugSend(content?: string) {
  const messageContent = (content ?? debugInput.value).trim()
  if (!messageContent || !currentApp.value) return

  const userMsg: DebugMessage = {
    id: Date.now(),
    role: 'user',
    content: messageContent,
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
    const datasourceId = appForm.datasourceIds?.[0] || null
    // 根据modelName查找llmConfigId
    const llmConfig = llmModels.value.find((m) => m.modelName === appForm.modelName)
    const llmConfigId = llmConfig?.id || null
    
    const requestBody: any = {
      sessionId: `debug-${currentApp.value.id}-${Date.now()}`,
      question: userMsg.content,
      applicationId: currentApp.value.id,
    }
    
    if (knowledgeBaseId !== null) {
      requestBody.knowledgeBaseId = knowledgeBaseId
    }
    if (datasourceId !== null) {
      requestBody.datasourceId = datasourceId
    }
    if (llmConfigId !== null) {
      requestBody.llmConfigId = llmConfigId
    }
    
    const response = await fetch(`/api/v1/sessions/embed/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(requestBody),
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

          if (data.type === 'start') {
            // 会话开始事件
          } else if (data.type === 'intent') {
            // 意图识别结果
          } else if (data.type === 'content') {
            aiMsg.content += data.content
            aiMsg.isStreaming = true
            scrollToBottom()
          } else if (data.type === 'thinking') {
            if (!aiMsg.thinkingSteps) {
              aiMsg.thinkingSteps = []
            }
            aiMsg.thinkingSteps.push({
              step: data.step,
              title: data.title,
              description: data.description,
            })
            scrollToBottom()
          } else if (data.type === 'references') {
            aiMsg.references = data.data
            scrollToBottom()
          } else if (data.type === 'sql_traces') {
            aiMsg.sqlTraces = data.data
            scrollToBottom()
          } else if (data.type === 'data_result') {
            aiMsg.dataResult = data.data
            if (data.columnMeta) {
              aiMsg.columnMeta = data.columnMeta
            }
            if (data.chartType) {
              aiMsg.chartType = data.chartType
            }
            aiMsg.type = 'data'
            scrollToBottom()
          } else if (data.type === 'column_meta') {
            aiMsg.columnMeta = data.data
            scrollToBottom()
          } else if (data.type === 'done') {
            aiMsg.isStreaming = false
            const elapsedTime = data.elapsed_time || data.elapsedTime
            if (elapsedTime !== undefined) {
              aiMsg.elapsedTime = Math.round(elapsedTime * 1000)
              aiMsg.queryTime = Math.round(elapsedTime * 1000)
            }
          } else if (data.type === 'error') {
            aiMsg.content += `\n\n[错误] ${data.message}`
            aiMsg.isStreaming = false
          }
        } catch (e) {
          console.warn('解析SSE消息失败:', e)
        }
      }
    }
  } catch (error: any) {
    console.error('调试对话失败:', error)
    aiMsg.content = aiMsg.content || '抱歉，消息发送失败，请稍后重试。'
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
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px); /* Header 60px + content-area padding 40px */
  min-height: 0;
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
  display: flex;
  flex-direction: column;
  height: 100%;

  .app-tabs {
    background: #fff;
    border-radius: 0 $card-radius $card-radius $card-radius;
    min-height: 0;
    flex: 1;
    display: flex;
    flex-direction: column;

    :deep(.el-tabs__header) {
      flex-shrink: 0;
    }

    :deep(.el-tabs__content) {
      padding: 20px;
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    :deep(.el-tab-pane) {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
  }
}

.integration-content {
  width: 100%;

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
    gap: 20px;
    align-items: stretch;
    flex: 1;
    min-height: 0;

    .settings-left {
        width: 40%;
        flex-shrink: 0;
        overflow-y: auto;
        max-height: 100%;

      :deep(.el-card) {
        margin-bottom: 0;
        border-radius: 10px;
      }

      :deep(.el-card__body) {
        padding: 24px;
      }

      :deep(.el-card__body .el-row) {
        margin-bottom: 24px;

        &:last-child {
          margin-bottom: 0;
        }
      }

      :deep(.el-card__header) {
        padding: 10px 16px;
        border-bottom: 1px solid #e2e8f0;
      }

      .card-title {
        font-size: 14px;
        font-weight: 600;
        color: #1e293b;
      }

      :deep(.el-form) {
        label-width: 90px;
      }

      :deep(.el-form-item) {
        margin-bottom: 24px;

        &:last-child {
          margin-bottom: 0;
        }

        // 应用描述等textarea与上一行保持足够间距
        &:has(.el-textarea__inner) {
          margin-top: 8px;
        }
      }

      :deep(.el-form-item__label) {
        font-size: 13px;
        font-weight: 500;
        color: #475569;
      }

      :deep(.el-input__wrapper) {
        border-radius: 8px;
        padding: 4px 8px;
        width: 100%;
        height: 36px;
        box-sizing: border-box;
      }

      :deep(.el-input__inner) {
        font-size: 12px;
        padding: 8px 10px;
        width: 100%;
        min-width: 0;
        height: 28px;
        line-height: 28px;
      }

      :deep(.el-select__wrapper) {
        border-radius: 8px;
        padding: 4px 8px;
        width: 100%;
        height: 36px;
        box-sizing: border-box;
      }

      :deep(.el-select__inner) {
        font-size: 12px;
        padding: 8px 10px;
        width: 100%;
        height: 28px;
        line-height: 28px;
      }

      :deep(.el-input-number) {
        width: 100%;
        min-width: 0;
      }

      :deep(.el-input-number .el-input__wrapper) {
        border-radius: 8px;
        width: 100%;
        padding: 4px 8px;
        box-sizing: border-box;
        height: 36px;
      }

      :deep(.el-input-number .el-input__inner) {
        font-size: 12px;
        width: 100%;
        padding-right: 30px;
        height: 28px;
        line-height: 28px;
      }

      :deep(.el-input-number__decrease),
      :deep(.el-input-number__increase) {
        width: 24px;
        height: 36px;
        line-height: 36px;

        .el-icon {
          font-size: 12px;
        }
      }

      :deep(.el-textarea__inner) {
        font-size: 12px;
        padding: 10px;
        border-radius: 8px;
        width: 100%;
        min-width: 0;
        resize: none;
      }

      .textarea-wrapper {
        position: relative;
        width: 100%;

        .textarea-ellipsis {
          position: absolute;
          bottom: 12px;
          right: 14px;
          background: #fff;
          padding: 0 8px;
          color: #94a3b8;
          font-size: 12px;
          pointer-events: none;
        }
      }

      :deep(.el-slider) {
        margin-bottom: 6px;
      }

      :deep(.el-switch) {
        font-size: 12px;
        padding: 0 8px;
      }

      :deep(.el-switch__core) {
        width: 32px;
        height: 18px;
      }

      :deep(.el-switch__button) {
        width: 16px;
        height: 16px;
      }

      :deep(.el-switch__label) {
        font-size: 12px;
        padding: 0 4px;
        line-height: normal;
        overflow: visible;
        height: auto;
      }

      .slider-value {
        font-size: 11px;
        color: #64748b;
        margin-left: 6px;
      }

      .form-tip {
        margin-top: 6px;
        font-size: 11px;
        color: #94a3b8;
      }
    }

    .settings-right {
      width: 60%;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
      box-sizing: border-box;
    }

    .preview-card {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border-radius: 10px;
      min-height: 0;
      border: 1px solid #e2e8f0 !important;

      :deep(.el-card__body) {
        padding: 0 !important;
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        margin: 0 !important;
        min-height: 0;
      }

    .preview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 16px;
      background-color: #ffffff;
      border-bottom: 1px solid #e2e8f0;

      .card-title {
        font-size: 14px;
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
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes typing {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
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

      &:hover {
        border-color: #8b5cf6;
        background: rgba(139, 92, 246, 0.05);
      }

      &.active {
        border-color: #8b5cf6;
        background: rgba(139, 92, 246, 0.05);
      }

      .mode-icon {
        width: 80px;
        height: 64px;
        margin: 0 auto 8px;
        display: flex;
        align-items: center;
        justify-content: center;

        img {
          max-width: 100%;
          max-height: 100%;
          object-fit: contain;
        }
      }

      .mode-name {
        font-size: 14px;
        font-weight: 600;
        color: $text-primary;
      }
    }
  }

  .embed-tip {
    margin-top: 12px;
    padding: 12px 16px;
    background: #f5f3ff;
    border-radius: 8px;
    border: 1px solid #ddd6fe;
    
    p {
      margin: 0 0 8px 0;
      font-weight: 600;
      color: #5b21b6;
      font-size: 13px;
    }
    
    ul {
      margin: 0;
      padding-left: 20px;
      color: #6b7280;
      font-size: 12px;
      
      li {
        margin-bottom: 4px;
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