<template>
  <div class="ai-assistant-view">
    <!-- 侧边栏 -->
    <aside class="chat-sidebar">
      <div class="sidebar-header">
        <h2 class="sidebar-title">对话历史</h2>
        <el-button type="primary" size="small" @click="handleNewChat" class="new-chat-btn">
          <el-icon><Plus /></el-icon>
          新对话
        </el-button>
      </div>
      <div class="sidebar-search">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索历史对话..."
          size="small"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <div class="sidebar-sessions">
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="selectSession(session.id)"
        >
          <div class="session-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <div class="session-info">
            <div v-if="editingSessionId === session.id" class="session-rename" @click.stop>
              <el-input
                v-model="renameValue"
                size="small"
                placeholder="输入新名称"
                @keyup.enter="confirmRename(session.id)"
                @keyup.escape="cancelRename"
                @blur="confirmRename(session.id)"
              />
            </div>
            <div v-else class="session-name">{{ session.title || '新对话' }}</div>
            <div class="session-time">{{ formatTime(session.updatedAt) }}</div>
          </div>
          <div v-if="editingSessionId !== session.id" class="session-actions" @click.stop>
            <el-dropdown trigger="click" @command="(cmd: string) => handleSessionCommand(cmd, session)">
              <el-button text size="small" class="action-btn">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename">
                    <el-icon><Edit /></el-icon>
                    重命名
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" divided>
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
        <div v-if="filteredSessions.length === 0" class="empty-sessions">
          <p>暂无对话记录</p>
        </div>
      </div>
      <!-- 侧边栏底部用户区域 -->
      <div class="sidebar-footer">
        <el-dropdown
          v-if="chatUser"
          trigger="click"
          @command="handleUserMenu"
        >
          <div class="user-info">
            <AvatarImage type="user" />
            <div class="user-detail">
              <div class="user-name">{{ chatUser.name || chatUser.username }}</div>
              <div class="user-username">{{ chatUser.username }}</div>
            </div>
            <el-icon class="user-arrow"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>
                <div class="dropdown-user-info">
                  <div class="dropdown-username">用户名: {{ chatUser.username }}</div>
                  <div v-if="chatUser.name" class="dropdown-name">姓名: {{ chatUser.name }}</div>
                </div>
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <div v-else class="user-info login-prompt" @click="goToLogin">
          <AvatarImage type="user" />
          <div class="user-detail">
            <div class="user-name">点击登录</div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主对话区 -->
    <div class="chat-main">
      <div class="chat-header">
        <div class="header-left">
          <span class="session-title">{{ currentSession?.title || appName }}</span>
        </div>
        <div class="header-right">
          <el-select
            v-model="knowledgeBaseId"
            placeholder="选择知识库"
            size="small"
            clearable
            style="width: 180px"
          >
            <el-option
              v-for="kb in knowledgeBases"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            />
          </el-select>
        </div>
      </div>

      <ChatPanel
        v-if="!isLoading"
        :messages="messages"
        v-model="inputText"
        :isSending="isSending"
        :welcomeTitle="appName"
        :welcomeDesc="greetingMessage || '你好，有什么我可以帮你的吗？'"
        inputPlaceholder="输入您的问题，按 Enter 发送，Ctrl+Enter 换行"
        sendButtonText="发送"
        size="md"
        @send="handleSend"
        @suggestion="handleSuggestion"
        @copy="copyMessageContent"
        @regenerate="regenerateMessage"
        @edit="handleEdit"
        @sql="showSqlDialog"
        @reference="showReferenceDetail"
        @export="handleExport"
      />
      <div v-else class="chat-loading">
        <el-icon class="loading-icon" :size="40"><Loading /></el-icon>
        <p>加载中...</p>
      </div>

      <!-- SQL查看弹窗 -->
      <el-dialog v-model="sqlDialogVisible" title="SQL查询语句" width="70%" top="10vh">
        <div class="sql-dialog-content">
          <pre class="sql-dialog-code">{{ currentSql }}</pre>
        </div>
        <template #footer>
          <el-button @click="sqlDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="copySql(currentSql)">复制SQL</el-button>
        </template>
      </el-dialog>

      <!-- 知识引用详情弹窗 -->
      <el-dialog v-model="referenceDetailVisible" title="知识引用详情" width="60%" max-width="90%" top="10vh">
        <div class="reference-detail-content">
          <div class="reference-detail-header">
            <el-icon :size="24" color="#6366f1"><Document /></el-icon>
            <span class="reference-detail-title">{{ currentReference?.documentName }}</span>
            <span v-if="currentReference?.score" class="reference-detail-score">{{ (currentReference.score * 100).toFixed(1) }}%</span>
          </div>
          <div class="reference-detail-body">
            <div class="reference-detail-content-text">{{ currentReference?.content }}</div>
          </div>
        </div>
        <template #footer>
          <el-button @click="referenceDetailVisible = false">关闭</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, triggerRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  ChatDotRound,
  Edit,
  Delete,
  MoreFilled,
  ArrowDown,
  Loading,
  SwitchButton,
  Document,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import * as XLSX from 'xlsx'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import AvatarImage from '@/components/AvatarImage.vue'
import { copyToClipboard } from '@/utils/clipboard'
import { getApplication, getApplicationByHash } from '@/api/application'
import type { Application } from '@/api/application'
import { getLLMConfigs } from '@/api/llmConfig'
import { getKnowledgeBases } from '@/api/knowledge'

const route = useRoute()
const router = useRouter()

// 对话用户认证相关
const chatUser = ref<any>(null)
const chatToken = ref<string | null>(localStorage.getItem('chat_token'))

interface Session {
  id: string
  title: string
  messages: DebugMessage[]
  updatedAt: string
}

interface DebugMessage {
  id: number | string
  role: string
  content: string
  type?: 'text' | 'data'
  isStreaming?: boolean
  thinkingSteps?: Array<{ step: number; title: string; description: string }>
  sqlTraces?: Array<{ sql: string; rows: number }>
  dataResult?: any[]
  columnMeta?: any[]
  chartType?: string
  chartOption?: any
  references?: Array<{ documentName: string; content: string; score: number }>
  elapsedTime?: number
  queryTime?: number
}

const inputText = ref('')
const isSending = ref(false)
const isLoading = ref(true)
const knowledgeBaseId = ref<number | null>(null)
const knowledgeBases = ref<any[]>([])

// 初始化对话用户信息
function initChatUser() {
  const savedUser = localStorage.getItem('chat_user')
  const savedToken = localStorage.getItem('chat_token')
  if (savedUser && savedToken) {
    try {
      chatUser.value = JSON.parse(savedUser)
      chatToken.value = savedToken
    } catch (e) {
      console.error('解析用户信息失败', e)
      clearChatUser()
    }
  }
}

function clearChatUser() {
  chatUser.value = null
  chatToken.value = null
  localStorage.removeItem('chat_token')
  localStorage.removeItem('chat_user')
}

async function handleUserMenu(command: string) {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm(
        '确定要退出登录吗？',
        '退出登录',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
      )
      clearChatUser()
      ElMessage.success('已退出登录')
      window.location.reload()
    } catch {
      // 用户取消
    }
  }
}

const isInIframe = computed(() => {
  try {
    return window.self !== window.top
  } catch (e) {
    return true
  }
})

function goToLogin() {
  const currentPath = route.fullPath
  sessionStorage.setItem('embed_redirect', currentPath)
  sessionStorage.setItem('chat_redirect', currentPath)

  if (isInIframe.value) {
    const loginPath = `/app-login?redirect=${encodeURIComponent(currentPath)}&popup=1`
    window.parent?.postMessage({
      type: 'steel_auth_required',
      loginUrl: loginPath,
      redirect: currentPath
    }, '*')
    const loginUrl = window.location.origin + loginPath
    window.open(loginUrl, '_blank', 'width=480,height=600')
    ElMessage.info('请在新窗口中完成登录')
  } else {
    const loginPath = `/app-login?redirect=${encodeURIComponent(currentPath)}`
    router.push(loginPath)
  }
}

// 应用配置：支持 appId（query参数）、accessHash（URL路径）两种方式
const isHashMode = computed(() => route.name === 'AiAssistantByHash')
const accessHash = computed(() => route.params.accessHash as string)
const appId = computed(() => {
  if (route.query.appId) {
    return parseInt(route.query.appId as string)
  }
  if (isHashMode.value && app.value) {
    return app.value.id
  }
  // 默认应用ID
  return 1
})
const appName = ref('钢铁行业智能助手')
const greetingMessage = ref('')
const app = ref<Application | null>(null)
const llmConfigs = ref<any[]>([])

async function loadLLMConfigs() {
  try {
    const res = await getLLMConfigs()
    const configs = (res.data as any) || []
    llmConfigs.value = configs.filter((c: any) => c.modelType === 'llm')
  } catch (error) {
    llmConfigs.value = []
  }
}

async function loadKnowledgeBases() {
  try {
    const res = await getKnowledgeBases()
    knowledgeBases.value = res.data || []
  } catch (error) {
    knowledgeBases.value = []
  }
}

const sessions = ref<Session[]>([])
const currentSessionId = ref<string>('')
const searchKeyword = ref('')
const editingSessionId = ref<string | null>(null)
const renameValue = ref('')

const sqlDialogVisible = ref(false)
const currentSql = ref('')
const referenceDetailVisible = ref(false)
const currentReference = ref<any>(null)

const currentSession = computed(() => sessions.value.find(s => s.id === currentSessionId.value))
const messages = computed(() => currentSession.value?.messages || [])

const filteredSessions = computed(() => {
  if (!searchKeyword.value) return sessions.value
  const keyword = searchKeyword.value.toLowerCase()
  return sessions.value.filter((s) =>
    (s.title || '新对话').toLowerCase().includes(keyword)
  )
})

function formatTime(date: Date | string) {
  const d = new Date(date)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function handleSuggestion(suggestion: string) {
  inputText.value = suggestion
  handleSend(suggestion)
}

function handleEdit(message: any, content: string) {
  inputText.value = content
  handleSend(content)
}

function getTableName(sqlTraces: any[]) {
  if (!sqlTraces || sqlTraces.length === 0) return '-'
  const sql = sqlTraces[0].sql || ''
  const match = sql.match(/FROM\s+(\w+)/i)
  return match ? match[1] : '-'
}

function getDataColumns(data: any[], columnMeta?: any[]) {
  if (!data || data.length === 0) return []
  const keys = Object.keys(data[0])
  return keys.map((key) => {
    const meta = columnMeta?.find((m: any) => (m.name || m.columnName) === key)
    const label = meta?.comment || meta?.columnAlias || key
    return {
      prop: key,
      label,
      minWidth: 120,
    }
  })
}

function generateChartOption(data: any[], msg: DebugMessage, chartType: string): any {
  if (!data || data.length === 0) return null

  const allCols = getDataColumns(data, msg.columnMeta)
  const numCols = allCols.filter((c) => {
    const val = data[0][c.prop]
    return typeof val === 'number' || (!isNaN(Number(val)) && val !== null && val !== '')
  })

  if (allCols.length === 0 || numCols.length === 0) return null

  const xCol = allCols.find((c) => !numCols.some((n) => n.prop === c.prop))?.prop || allCols[0].prop
  const yCol = numCols[0].prop

  const xData = data.map((row: any) => String(row[xCol] ?? ''))
  const yData = data.map((row: any) => Number(row[yCol]) || 0)

  if (chartType === 'pie') {
    return {
      tooltip: { trigger: 'item' },
      legend: {
        type: 'scroll',
        orient: 'horizontal',
        bottom: 10,
        itemGap: 16,
        textStyle: { fontSize: 12 },
      },
      grid: { top: 20, bottom: 60, left: '3%', right: '3%', containLabel: true },
      series: [{
        type: 'pie',
        radius: ['25%', '55%'],
        center: ['50%', '40%'],
        data: xData.map((name, i) => ({ name, value: yData[i] })),
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
        label: { fontSize: 12, formatter: '{b}: {d}%' },
        labelLine: { length: 15, length2: 20, smooth: true },
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
      }],
    }
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: chartType === 'bar' ? 'shadow' : 'line' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: { rotate: 30, fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 12 },
    },
    series: [{
      type: chartType,
      data: yData,
      smooth: chartType === 'line',
      barMaxWidth: 50,
      itemStyle: {
        borderRadius: chartType === 'bar' ? [4, 4, 0, 0] : undefined,
      },
    }],
  }
}

function exportToExcel(msg: DebugMessage) {
  if (!msg.dataResult || msg.dataResult.length === 0) {
    ElMessage.warning('没有数据可导出')
    return
  }

  const cols = getDataColumns(msg.dataResult, msg.columnMeta)
  const headers = cols.map((c) => c.label)
  const rows = msg.dataResult.map((row) => cols.map((col) => String(row[col.prop] ?? '')))

  const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows])
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, '数据')

  const name = `数据导出_${getTableName(msg.sqlTraces || [])}_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}`
  XLSX.writeFile(workbook, `${name}.xlsx`)
  ElMessage.success('导出成功')
}

function exportChartToImage(msg: DebugMessage) {
  const option = (msg as any).chartOption
  if (!option) {
    ElMessage.warning('没有图表可导出')
    return
  }

  try {
    const canvas = document.createElement('canvas')
    canvas.width = 800
    canvas.height = 400
    canvas.style.display = 'none'
    document.body.appendChild(canvas)

    const chart = echarts.init(canvas, undefined, { renderer: 'canvas' })
    chart.setOption(option)

    setTimeout(() => {
      const url = chart.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff',
      })

      chart.dispose()
      document.body.removeChild(canvas)

      const link = document.createElement('a')
      link.download = `图表导出_${getTableName(msg.sqlTraces || [])}_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.png`
      link.href = url
      link.click()
      ElMessage.success('导出成功')
    }, 500)
  } catch (error) {
    console.error('图表导出失败:', error)
    ElMessage.error('图表导出失败，请重试')
  }
}

function handleExport(cmd: string, msg: DebugMessage) {
  if (cmd === 'excel') {
    exportToExcel(msg)
  } else if (cmd === 'image') {
    exportChartToImage(msg)
  }
}

async function copySql(sql: string) {
  const ok = await copyToClipboard(sql)
  ok ? ElMessage.success('SQL已复制') : ElMessage.error('复制失败')
}

function showSqlDialog(sql: string) {
  currentSql.value = sql
  sqlDialogVisible.value = true
}

function showReferenceDetail(ref: any) {
  currentReference.value = ref
  referenceDetailVisible.value = true
}

async function copyMessageContent(content: string) {
  const ok = await copyToClipboard(content)
  ok ? ElMessage.success('已复制') : ElMessage.error('复制失败')
}

function regenerateMessage(msg: any) {
  const session = currentSession.value
  if (!session) {
    ElMessage.error('无法重新生成此消息')
    return
  }

  const msgIndex = session.messages.findIndex((m) => m.id === msg.id)
  if (msgIndex <= 0) {
    ElMessage.error('无法重新生成此消息')
    return
  }

  const prevMsg = session.messages[msgIndex - 1]
  if (!prevMsg || prevMsg.role !== 'user') {
    ElMessage.error('无法重新生成此消息')
    return
  }

  const content = prevMsg.content
  inputText.value = content
  handleSend(content)
}

function loadFromQueryParams() {
  const query = route.query
  if (query.appName) {
    appName.value = decodeURIComponent(query.appName as string) || '钢铁行业智能助手'
  }
  if (query.greetingMessage) {
    greetingMessage.value = decodeURIComponent(query.greetingMessage as string) || ''
  }
}

async function loadAppConfig() {
  loadFromQueryParams()

  if (route.query.appName) {
    return
  }

  try {
    let appData: Application

    if (isHashMode.value) {
      const res = await getApplicationByHash(accessHash.value)
      appData = res.data as unknown as Application
    } else {
      const res = await getApplication(appId.value)
      appData = res.data as unknown as Application
    }

    app.value = appData
    appName.value = appData.name || '钢铁行业智能助手'
    greetingMessage.value = appData.greetingMessage || ''

    // 设置默认知识库
    if (appData.knowledgeBaseIds && appData.knowledgeBaseIds.length > 0) {
      knowledgeBaseId.value = appData.knowledgeBaseIds[0]
    }
  } catch (error) {
    console.error('加载应用配置失败', error)
  }
}

function createNewSession() {
  const newSession: Session = {
    id: `ai-assistant-${Date.now()}`,
    title: '新对话',
    messages: [],
    updatedAt: new Date().toISOString(),
  }
  sessions.value.unshift(newSession)
  currentSessionId.value = newSession.id
  saveSessions()
}

function selectSession(sessionId: string) {
  currentSessionId.value = sessionId
}

const sessionStorageKey = computed(() => {
  const userId = chatUser.value?.id || 'anonymous'
  return `ai_assistant_sessions_${appId.value}_${userId}`
})

function saveSessions() {
  try {
    localStorage.setItem(sessionStorageKey.value, JSON.stringify(sessions.value))
  } catch (e) {
    console.error('保存会话失败', e)
  }
}

let saveTimer: any = null
function throttledSaveSessions() {
  if (saveTimer) return
  saveTimer = setTimeout(() => {
    saveTimer = null
    saveSessions()
  }, 500)
}

function loadSessions() {
  try {
    const saved = localStorage.getItem(sessionStorageKey.value)
    if (saved) {
      sessions.value = JSON.parse(saved)
      let needsFix = false
      for (const session of sessions.value) {
        if (session.messages && Array.isArray(session.messages)) {
          for (const msg of session.messages) {
            if (msg.isStreaming) {
              msg.isStreaming = false
              needsFix = true
            }
          }
        }
      }
      if (needsFix) {
        saveSessions()
      }
    } else {
      sessions.value = []
    }
  } catch (e) {
    console.error('加载会话失败', e)
    sessions.value = []
  }
}

function handleNewChat() {
  editingSessionId.value = null
  renameValue.value = ''
  createNewSession()
}

function startRename(session: Session) {
  editingSessionId.value = session.id
  renameValue.value = session.title || '新对话'
}

function cancelRename() {
  editingSessionId.value = null
  renameValue.value = ''
}

function confirmRename(sessionId: string) {
  if (!editingSessionId.value) return
  const title = renameValue.value.trim()
  if (!title) {
    cancelRename()
    return
  }
  const session = sessions.value.find(s => s.id === sessionId)
  if (session) {
    session.title = title
    session.updatedAt = new Date().toISOString()
    saveSessions()
  }
  editingSessionId.value = null
  renameValue.value = ''
}

function handleSessionCommand(command: string, session: Session) {
  if (command === 'rename') {
    startRename(session)
  } else if (command === 'delete') {
    handleDeleteSession(session)
  }
}

async function handleDeleteSession(session: Session) {
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${session.title || '新对话'}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const index = sessions.value.findIndex(s => s.id === session.id)
    if (index !== -1) {
      sessions.value.splice(index, 1)
      saveSessions()
      if (currentSessionId.value === session.id) {
        if (sessions.value.length > 0) {
          currentSessionId.value = sessions.value[0].id
        } else {
          createNewSession()
        }
      }
    }
    ElMessage.success('会话已删除')
  } catch {
    // 用户取消
  }
}

async function handleSend(content?: string) {
  const sendContent = (content ?? inputText.value).trim()
  if (!sendContent) {
    return
  }

  let session = currentSession.value
  if (!session) {
    createNewSession()
    session = currentSession.value
    if (!session) {
      ElMessage.error('会话创建失败，请刷新页面重试')
      return
    }
  }

  const userMsg: DebugMessage = {
    id: Date.now(),
    role: 'user',
    content: sendContent,
  }

  session.messages.push(userMsg)
  session.updatedAt = new Date().toISOString()
  if (!session.title || session.title === '新对话') {
    session.title = sendContent.substring(0, 20) + (sendContent.length > 20 ? '...' : '')
  }
  saveSessions()

  inputText.value = ''
  isSending.value = true

  const aiMsgId = Date.now() + 1
  const aiMsg: DebugMessage = {
    id: aiMsgId,
    role: 'assistant',
    content: '',
    isStreaming: true,
  }
  session.messages.push(aiMsg)
  saveSessions()

  const aiMsgRef = session.messages.find(m => m.id === aiMsgId)
  if (!aiMsgRef) {
    console.error('无法在会话中找到AI消息')
    isSending.value = false
    return
  }

  try {
    const datasourceId = app.value?.datasourceIds?.[0] || null
    const llmConfig = llmConfigs.value.find((m) => m.modelName === app.value?.modelName)
    const llmConfigId = llmConfig?.id || null

    const requestBody: any = {
      sessionId: currentSessionId.value,
      question: userMsg.content,
      applicationId: appId.value,
    }

    if (chatUser.value) {
      requestBody.chatUserId = chatUser.value.id
      requestBody.chatUsername = chatUser.value.username
    }

    // 优先使用用户选择的知识库
    const effectiveKbId = knowledgeBaseId.value ?? app.value?.knowledgeBaseIds?.[0] ?? null
    if (effectiveKbId !== null) {
      requestBody.knowledgeBaseId = effectiveKbId
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
        'Authorization': chatToken.value ? `Bearer ${chatToken.value}` : '',
      },
      body: JSON.stringify(requestBody),
    })

    if (!response.ok) {
      throw new Error('请求失败')
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
            if (aiMsgRef) {
              aiMsgRef.content += data.content
              aiMsgRef.isStreaming = true
              triggerRef(sessions)
            }
          } else if (data.type === 'thinking') {
            if (aiMsgRef) {
              if (!aiMsgRef.thinkingSteps) {
                aiMsgRef.thinkingSteps = []
              }
              aiMsgRef.thinkingSteps.push({
                step: data.step,
                title: data.title,
                description: data.description
              })
              triggerRef(sessions)
              saveSessions()
            }
          } else if (data.type === 'sql_traces') {
            if (aiMsgRef) {
              aiMsgRef.sqlTraces = data.data
              triggerRef(sessions)
              saveSessions()
            }
          } else if (data.type === 'data_result') {
            if (aiMsgRef) {
              aiMsgRef.dataResult = data.data
              if (data.columnMeta) {
                aiMsgRef.columnMeta = data.columnMeta
              }
              if (data.chartType) {
                aiMsgRef.chartType = data.chartType
                // 自动生成图表配置
                aiMsgRef.chartOption = generateChartOption(data.data, aiMsgRef, data.chartType)
              }
              aiMsgRef.type = 'data'
              triggerRef(sessions)
              saveSessions()
            }
          } else if (data.type === 'column_meta') {
            if (aiMsgRef) {
              aiMsgRef.columnMeta = data.data
              triggerRef(sessions)
              saveSessions()
            }
          } else if (data.type === 'references') {
            if (aiMsgRef) {
              aiMsgRef.references = data.data
              triggerRef(sessions)
              saveSessions()
            }
          } else if (data.type === 'done') {
            if (aiMsgRef) {
              aiMsgRef.isStreaming = false
              const elapsedTime = data.elapsed_time || data.elapsedTime
              if (elapsedTime !== undefined) {
                aiMsgRef.elapsedTime = Math.round(elapsedTime * 1000)
                aiMsgRef.queryTime = Math.round(elapsedTime * 1000)
              }
              triggerRef(sessions)
            }
            if (saveTimer) {
              clearTimeout(saveTimer)
              saveTimer = null
            }
            saveSessions()
          } else if (data.type === 'error') {
            if (aiMsgRef) {
              aiMsgRef.content += `\n\n[错误] ${data.message}`
              aiMsgRef.isStreaming = false
              triggerRef(sessions)
            }
            saveSessions()
          }
        } catch (e) {
          console.error('解析SSE消息失败', e)
        }
      }
    }
  } catch (error: any) {
    if (aiMsgRef) {
      aiMsgRef.content = aiMsgRef.content || '抱歉，消息发送失败，请稍后重试。'
      aiMsgRef.isStreaming = false
      triggerRef(sessions)
    }
    saveSessions()
  } finally {
    isSending.value = false
  }
}

function setupMessageListener() {
  window.addEventListener('message', (event) => {
    const data = event.data
    if (!data || typeof data !== 'object') return

    if (data.type === 'steel_login_success' && data.token) {
      localStorage.setItem('chat_token', data.token)
      localStorage.setItem('chat_user', JSON.stringify(data.user))
      initChatUser()
      ElMessage.success('登录成功')
      loadSessions()
    }
  })
}

onMounted(async () => {
  initChatUser()
  setupMessageListener()
  await loadAppConfig()
  loadLLMConfigs().catch(() => {})
  loadKnowledgeBases().catch(() => {})
  loadSessions()
  if (sessions.value.length === 0) {
    createNewSession()
  } else {
    currentSessionId.value = sessions.value[0].id
  }
  isLoading.value = false
})
</script>

<style lang="scss" scoped>
.ai-assistant-view {
  display: flex;
  height: 100%;
  width: 100%;
  background-color: #f1f5f9;
  overflow: hidden;
}

.chat-sidebar {
  width: 260px;
  background: white;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;

  .sidebar-header {
    padding: 16px;
    flex-shrink: 0;
    border-bottom: 1px solid #e2e8f0;

    .sidebar-title {
      font-size: 15px;
      font-weight: 600;
      color: #1e293b;
      margin: 0 0 12px 0;
    }

    .new-chat-btn {
      width: 100%;
    }
  }

  .sidebar-search {
    padding: 12px 16px;
    flex-shrink: 0;
  }

  .sidebar-sessions {
    flex: 1;
    overflow-y: auto;
    padding: 8px;

    .empty-sessions {
      text-align: center;
      padding: 40px 20px;
      color: #94a3b8;
      font-size: 14px;
    }
  }

  .session-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
    margin-bottom: 4px;

    &:hover {
      background: #f1f5f9;
    }

    &.active {
      background: #eff6ff;

      .session-name {
        color: #3b82f6;
        font-weight: 500;
      }
    }

    .session-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: #f1f5f9;
      color: #64748b;
      flex-shrink: 0;

      .active & {
        background: #dbeafe;
        color: #3b82f6;
      }
    }

    .session-info {
      flex: 1;
      min-width: 0;

      .session-name {
        font-size: 14px;
        color: #1e293b;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .session-time {
        font-size: 12px;
        color: #94a3b8;
        margin-top: 2px;
      }

      .session-rename {
        .el-input {
          padding: 0;
        }
      }
    }

    .session-actions {
      flex-shrink: 0;
      opacity: 0;
      transition: opacity 0.2s;

      .session-item:hover & {
        opacity: 1;
      }
    }

    .session-active-indicator {
      width: 3px;
      height: 20px;
      background: #3b82f6;
      border-radius: 2px;
      flex-shrink: 0;
    }
  }

  .sidebar-footer {
    padding: 12px;
    border-top: 1px solid #e2e8f0;
    background: #f8fafc;
    flex-shrink: 0;
  }
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #fff;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: #f0f4ff;
  }

  &.login-prompt {
    justify-content: center;
    background: #f8fafc;
    border: 1px dashed #cbd5e1;

    &:hover {
      background: #eff6ff;
      border-color: #3b82f6;
    }
  }

  .user-detail {
    flex: 1;
    min-width: 0;

    .user-name {
      font-size: 14px;
      font-weight: 500;
      color: #1e293b;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .user-username {
      font-size: 12px;
      color: #94a3b8;
      margin-top: 2px;
    }
  }

  .user-arrow {
    font-size: 12px;
    color: #94a3b8;
  }
}

.dropdown-user-info {
  .dropdown-username,
  .dropdown-name {
    font-size: 13px;
    color: #374151;
    padding: 2px 0;
  }
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f8fafc;
}

.chat-header {
  padding: 12px 20px;
  background: #3b82f6;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;

  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;

    .session-title {
      font-size: 15px;
      font-weight: 600;
      color: #fff;
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.chat-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;

  .loading-icon {
    color: #3b82f6;
    animation: rotate 1s linear infinite;
  }

  p {
    margin-top: 12px;
    font-size: 14px;
  }
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.sql-dialog-content {
  .sql-dialog-code {
    background: #f1f5f9;
    padding: 16px;
    border-radius: 8px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 400px;
    overflow-y: auto;
  }
}

.reference-detail-content {
  .reference-detail-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #e2e8f0;

    .reference-detail-title {
      font-size: 15px;
      font-weight: 600;
      color: #1e293b;
      flex: 1;
    }

    .reference-detail-score {
      font-size: 13px;
      color: #3b82f6;
      font-weight: 500;
    }
  }

  .reference-detail-body {
    .reference-detail-content-text {
      font-size: 14px;
      line-height: 1.8;
      color: #475569;
      white-space: pre-wrap;
    }
  }
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;

  &:hover {
    background: #94a3b8;
  }
}
</style>
