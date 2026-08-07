<template>
  <div class="chat-embed-view" :class="{ 'floating-mode': isFloatingMode, 'expanded-mode': isFloatingMode && isExpandedMode }">
    <!-- 遮罩层 - 侧边栏显示时出现 -->
    <div class="sidebar-overlay" v-if="sidebarVisible" @click="sidebarVisible = false"></div>
    
    <!-- 侧边栏 - 浮层模式 -->
    <div class="chat-sidebar" :class="{ 'sidebar-visible': sidebarVisible }">
      <div class="sidebar-close-btn" v-if="isFloatingMode" @click="sidebarVisible = false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </div>
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
          prefix-icon="Search"
        />
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
            <el-button text size="small" class="action-btn" @click="startRename(session)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button text size="small" class="action-btn delete-btn" @click="handleDeleteSession(session)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <div v-if="currentSessionId === session.id && editingSessionId !== session.id" class="session-active-indicator"></div>
        </div>
      </div>
      <!-- 侧边栏底部用户区域 -->
          <div class="sidebar-footer">
            <!-- 游客模式：只显示头像，无任何交互 -->
            <div v-if="isGuestMode" class="user-info guest-mode">
              <AvatarImage type="user" />
            </div>
            <!-- 身份验证模式 -->
            <template v-else>
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
            </template>
          </div>
    </div>

    <div class="chat-main">
      <div class="chat-header">
        <div class="header-left">
          <!-- 浮窗模式下的菜单按钮 -->
          <button v-if="isFloatingMode" class="header-menu-btn" @click="sidebarVisible = !sidebarVisible" title="会话管理">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="3" y1="12" x2="21" y2="12"/>
              <line x1="3" y1="6" x2="21" y2="6"/>
              <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>
          <span class="session-title">{{ currentSession?.title || appName }}</span>
        </div>
        <!-- 浮窗模式控制按钮 -->
        <div class="header-actions" v-if="isFloatingMode">
          <!-- 新建对话 -->
          <button class="header-action-btn" @click="handleNewChat" title="新建对话">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </button>
          <!-- 展开/缩小（中等大小） -->
          <button class="header-action-btn" @click="handleResizeToggle" :title="isExpandedMode ? '缩小' : '展开'">
            <svg v-if="!isExpandedMode" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <polyline points="16,3 21,3 21,8"/>
              <line x1="8" y1="16" x2="16" y2="16"/>
            </svg>
          </button>
          <!-- 关闭 -->
          <button class="header-action-btn close" @click="sendMessageToParent('chat-close')" title="关闭">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      <ChatPanel
        v-if="!isLoading"
        :messages="messages"
        v-model="inputText"
        :isSending="isSending"
        :welcomeTitle="appName"
        :welcomeDesc="greetingMessage || '你好，有什么我可以帮你的吗？'"
        inputPlaceholder="输入您的问题..."
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
  ArrowDown,
  Loading,
  CopyDocument,
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

// 清除对话用户信息
function clearChatUser() {
  chatUser.value = null
  chatToken.value = null
  localStorage.removeItem('chat_token')
  localStorage.removeItem('chat_user')
}

// 退出登录
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
      // 刷新页面
      window.location.reload()
    } catch {
      // 用户取消
    }
  }
}

// 检测是否在iframe中运行
const isInIframe = computed(() => {
  try {
    return window.self !== window.top
  } catch (e) {
    return true  // 跨域iframe时默认为true
  }
})

// 检测是否为浮窗模式（通过URL参数mode=float）
const isFloatingMode = computed(() => {
  return route.query.mode === 'float'
})

// 展开模式状态（中等大小，由父页面chat-embed.js控制）
const isExpandedMode = ref(false)

// 侧边栏可见性（浮窗模式下控制会话管理面板显示）
const sidebarVisible = ref(false)

// 切换展开/缩小模式
function handleResizeToggle() {
  if (isExpandedMode.value) {
    // 缩小回小窗口
    sendMessageToParent('chat-toggle-expanded')
  } else {
    // 展开为中等大小
    sendMessageToParent('chat-toggle-expanded')
  }
}

// 向父页面发送消息（浮窗模式通信）
function sendMessageToParent(type: string) {
  if (window.parent && window.parent !== window) {
    window.parent.postMessage({ type }, '*')
  }
}

// 跳转到登录页
function goToLogin() {
  const currentPath = route.fullPath
  
  // 保存当前路径到localStorage（持久存储），确保OAuth流程中不会丢失
  // OAuth跳转会离开当前页面，sessionStorage可能丢失，必须用localStorage兜底
  localStorage.setItem('embed_redirect', currentPath)
  localStorage.setItem('chat_redirect', currentPath)
  
  // 如果在iframe中，需要用window.open打开登录页
  if (isInIframe.value) {
    // 通过postMessage通知父窗口打开登录页
    window.parent?.postMessage({
      type: 'steel_auth_required',
      loginUrl: '/app-login?redirect=' + encodeURIComponent(currentPath),
      redirect: currentPath
    }, '*')
    
    // 同时也打开一个新窗口作为备选
    const loginUrl = `/app-login?redirect=${encodeURIComponent(currentPath)}&popup=1`
    const fullLoginUrl = window.location.origin + loginUrl
    window.open(fullLoginUrl, '_blank', 'width=480,height=600')
    ElMessage.info('请在新窗口中完成登录')
  } else {
    // 非iframe模式（公开访问链接），直接在当前页面跳转
    // 使用对象形式传递参数，避免URL编码问题
    router.push({
      path: '/app-login',
      query: {
        redirect: currentPath
      }
    })
  }
}

// 支持两种访问方式：通过appId（/chat/embed/:appId）或通过accessHash（/chat/:accessHash 或 /ai-assistant/:accessHash）
// 通过判断路由参数中是否存在 accessHash 来识别模式，不依赖具体路由名称
const isHashMode = computed(() => !!route.params.accessHash)
const accessHash = computed(() => route.params.accessHash as string)
const appId = computed(() => {
  if (isHashMode.value && app.value) {
    return app.value.id
  }
  return parseInt(route.params.appId as string)
})
const appName = ref('工业智能助手平台')
const greetingMessage = ref('')
const app = ref<Application | null>(null)
const llmConfigs = ref<any[]>([])

const requireAuth = computed(() => app.value?.requireAuth ?? true)
const isGuestMode = computed(() => !requireAuth.value)

async function loadLLMConfigs() {
  try {
    const res = await getLLMConfigs()
    const configs = (res.data as any) || []
    llmConfigs.value = configs.filter((c: any) => c.modelType === 'llm')
  } catch (error) {
    llmConfigs.value = []
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
    // 兼容不同的字段名格式：name（后端返回）或 columnName（其他来源）
    const meta = columnMeta?.find((m: any) => (m.name || m.columnName) === key)
    // 兼容不同的别名字段：comment（后端返回）或 columnAlias（其他来源）
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

// 重新生成消息
function regenerateMessage(msg: any) {
  const session = currentSession.value
  if (!session) {
    ElMessage.error('无法重新生成此消息')
    return
  }
  
  // 找到消息在会话中的位置
  const msgIndex = session.messages.findIndex((m) => m.id === msg.id)
  if (msgIndex <= 0) {
    ElMessage.error('无法重新生成此消息')
    return
  }
  
  // 查找父消息（用户消息）
  const prevMsg = session.messages[msgIndex - 1]
  if (!prevMsg || prevMsg.role !== 'user') {
    ElMessage.error('无法重新生成此消息')
    return
  }
  
  // 重新发送用户消息
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
      // 通过hash访问，使用公开接口
      const res = await getApplicationByHash(accessHash.value)
      appData = res.data as unknown as Application
    } else {
      // 通过appId访问
      const res = await getApplication(appId.value)
      appData = res.data as unknown as Application
    }
    
    app.value = appData
    appName.value = appData.name || '工业智能助手平台'
    greetingMessage.value = appData.greetingMessage || ''
  } catch (error) {
    console.error('加载应用配置失败', error)
  }
}

function createNewSession() {
  const newSession: Session = {
    id: `embed-${Date.now()}`,
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

// 计算会话存储key，实现用户数据隔离
const sessionStorageKey = computed(() => {
  const userId = chatUser.value?.id || 'anonymous'
  return `embed_sessions_${appId.value}_${userId}`
})

function saveSessions() {
  try {
    // 直接保存当前 sessions 引用的数据，不重新赋值，避免破坏响应式
    localStorage.setItem(sessionStorageKey.value, JSON.stringify(sessions.value))
  } catch (e) {
    console.error('保存会话失败', e)
  }
}

// 节流保存：用于流式内容更新，避免频繁保存导致性能问题
let saveTimer: any = null
function throttledSaveSessions() {
  if (saveTimer) return
  saveTimer = setTimeout(() => {
    saveTimer = null
    saveSessions()
  }, 500) // 500ms 节流
}

function loadSessions() {
  try {
    const saved = localStorage.getItem(sessionStorageKey.value)
    if (saved) {
      sessions.value = JSON.parse(saved)
      // 修复加载的会话中残留的 isStreaming 状态
      // 如果之前的对话在流式输出中中断，消息可能保持 isStreaming: true
      // 导致 UI 一直显示"正在输入"状态
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

  // 确保存在当前会话，如果不存在则自动创建
  let session = currentSession.value
  if (!session) {
    console.warn('当前会话不存在，自动创建新会话')
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
  // 关键：从数组中重新获取响应式代理对象，确保Vue能检测到属性变化
  saveSessions()

  // 获取响应式代理对象的引用，用于后续流式更新
  // 这样可以确保Vue能正确追踪所有属性变化
  const aiMsgRef = session.messages.find(m => m.id === aiMsgId)
  if (!aiMsgRef) {
    // 理论上不应该发生，但作为安全回退
    console.error('无法在会话中找到AI消息')
    isSending.value = false
    return
  }

  try {
    const knowledgeBaseId = app.value?.knowledgeBaseIds?.[0] || null
    const datasourceId = app.value?.datasourceIds?.[0] || null
    // 根据modelName查找llmConfigId
    const llmConfig = llmConfigs.value.find((m) => m.modelName === app.value?.modelName)
    const llmConfigId = llmConfig?.id || null
    
    const requestBody: any = {
      sessionId: currentSessionId.value,
      question: userMsg.content,
      applicationId: appId.value,
    }
    
    // 添加对话用户信息，实现数据隔离
    if (chatUser.value) {
      requestBody.chatUserId = chatUser.value.id
      requestBody.chatUsername = chatUser.value.username
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
          
          if (data.type === 'start') {
            // 会话开始事件，记录sessionId
          } else if (data.type === 'intent') {
            // 意图识别结果
          } else if (data.type === 'content') {
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
            // 确保最终保存
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
    } else {
      const currentMsgs = currentSession.value?.messages || []
      const msg = currentMsgs.find(m => m.id === aiMsgId)
      if (msg) {
        msg.content = msg.content || '抱歉，消息发送失败，请稍后重试。'
        msg.isStreaming = false
        triggerRef(sessions)
      }
    }
    saveSessions()
  } finally {
    isSending.value = false
  }
}

// 监听来自登录弹窗的消息
function setupMessageListener() {
  // 监听 postMessage（主通道）
  window.addEventListener('message', (event) => {
    const data = event.data
    if (!data || typeof data !== 'object') return
    
    // 接收登录成功消息
    if (data.type === 'steel_login_success' && data.token) {
      localStorage.setItem('chat_token', data.token)
      localStorage.setItem('chat_user', JSON.stringify(data.user))
      initChatUser()
      ElMessage.success('登录成功')
      // 重新加载会话
      loadSessions()
    }
    
    // 展开状态变化（浮窗模式）
    if (data.type === 'chat-toggle-expanded') {
      isExpandedMode.value = !isExpandedMode.value
      // 切换展开时，重置侧边栏状态
      sidebarVisible.value = false
    }
    if (data.type === 'chat-expanded-enter') {
      isExpandedMode.value = true
      sidebarVisible.value = false
    }
    if (data.type === 'chat-expanded-exit') {
      isExpandedMode.value = false
      sidebarVisible.value = false
    }
  })
  
  // 监听 localStorage 变化（备选通道，用于弹窗 postMessage 失败时）
  window.addEventListener('storage', (event) => {
    if (event.key === 'steel_login_result' && event.newValue) {
      try {
        const data = JSON.parse(event.newValue)
        if (data.type === 'steel_login_success' && data.token) {
          localStorage.setItem('chat_token', data.token)
          localStorage.setItem('chat_user', JSON.stringify(data.user))
          initChatUser()
          ElMessage.success('登录成功')
          loadSessions()
          // 清理临时存储
          localStorage.removeItem('steel_login_result')
        }
      } catch (e) {
        console.error('解析登录结果失败', e)
      }
    }
  })
}

onMounted(async () => {
  initChatUser()
  
  setupMessageListener()
  
  await loadAppConfig()
  // LLM配置加载为非阻塞，后端会从应用配置中自动解析LLM配置
  // 这里仅用于前端显示，失败不影响对话功能
  loadLLMConfigs().catch(() => {})
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
.chat-embed-view {
  display: flex;
  height: 100vh;
  background-color: #f1f5f9;
  overflow: hidden;
  position: relative;

  // 遮罩层
  .sidebar-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.3);
    z-index: 100;
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  &.floating-mode {
    height: 100%;
    border-radius: 16px 0 0 0;
    overflow: hidden;

    .chat-main {
      border-radius: 16px 0 0 0;
    }

    .chat-header {
      padding: 10px 12px;
      
      .header-left {
        .session-title {
          font-size: 13px;
        }
      }
    }

    // 浮窗模式下侧边栏改为浮层
    .chat-sidebar {
      position: absolute;
      top: 0;
      left: 0;
      width: 240px;
      height: 100%;
      background: white;
      z-index: 101;
      transform: translateX(-100%);
      transition: transform 0.3s ease;
      display: flex;
      flex-direction: column;
      
      &.sidebar-visible {
        transform: translateX(0);
      }
      
      .sidebar-close-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        position: absolute;
        top: 8px;
        right: 8px;
        border-radius: 6px;
        background: rgba(0, 0, 0, 0.05);
        color: #6b7280;
        cursor: pointer;
        border: none;
        transition: all 0.2s;
        z-index: 10;
        
        &:hover {
          background: rgba(239, 68, 68, 0.1);
          color: #ef4444;
        }
        
        svg {
          width: 14px;
          height: 14px;
        }
      }
      
      .sidebar-header {
        padding: 12px 44px 12px 12px;
        flex-shrink: 0;

        .sidebar-title {
          font-size: 14px;
        }

        .new-chat-btn {
          padding: 6px 10px;
          font-size: 12px;
        }
      }
      
      .sidebar-search {
        padding: 0 12px;
        flex-shrink: 0;
      }
      
      .sidebar-sessions {
        flex: 1;
        overflow-y: auto;
        padding: 8px;
      }
      
      .sidebar-footer {
        padding: 10px;
        flex-shrink: 0;
      }
    }

    // 菜单按钮
    .header-menu-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border-radius: 8px;
      border: none;
      background: rgba(0, 0, 0, 0.05);
      color: #374151;
      cursor: pointer;
      margin-right: 8px;
      transition: all 0.2s;
      
      &:hover {
        background: rgba(139, 92, 246, 0.1);
        color: #8b5cf6;
      }
      
      svg {
        width: 18px;
        height: 18px;
      }
    }
  }

  // 展开模式（右侧全高度）
  &.expanded-mode {
    border-radius: 0;
    min-height: 100vh;
    
    .chat-main {
      border-radius: 0;
    }
    
    .chat-header {
      padding: 12px 16px;
      border-bottom: 1px solid #e5e7eb;
      
      .header-left {
        .session-title {
          font-size: 14px;
        }
      }
    }
    
    .chat-messages {
      padding: 20px;
    }
    
    .chat-input {
      padding: 16px 20px;
    }
  }
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid #e5e7eb;
  background: #f8fafc;
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
    border-color: #c7d2fe;
  }

  &.guest-mode {
    justify-content: flex-start;
    padding: 10px 12px;
    cursor: default;
    border: none;
    background: #fff;
    width: 100%;
    height: auto;
    min-height: 44px;

    &:hover {
      background: #fff;
    }

    .user-detail {
      display: none;
    }
  }

  &.login-prompt {
    justify-content: center;
    padding: 12px;
    border: 1px dashed #d1d5db;

    &:hover {
      border-color: #3b82f6;
      background: #eff6ff;

      .user-name {
        color: #3b82f6;
      }
    }
  }
}

/* AvatarImage 组件在侧边栏中的样式适配 */
.sidebar-footer :deep(.avatar-image) {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.sidebar-footer :deep(.avatar-image .avatar-img) {
  border-radius: 50%;
}

.user-detail {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-username {
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-arrow {
  font-size: 12px;
  color: #94a3b8;
}

.dropdown-user-info {
  padding: 4px 0;

  .dropdown-username {
    font-size: 13px;
    font-weight: 600;
    color: #1e293b;
  }

  .dropdown-name {
    font-size: 12px;
    color: #64748b;
    margin-top: 2px;
  }
}

.chat-sidebar {
  width: 280px;
  background-color: #f8fafc;
  display: flex;
  flex-direction: column;
  height: 100%;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;

  .sidebar-header {
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid #e2e8f0;
  }

  .sidebar-title {
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
    white-space: nowrap;
  }

  .new-chat-btn {
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 500;
  }

  .sidebar-search {
    padding: 12px 16px;
  }

  .sidebar-sessions {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    min-height: 0;
  }

  .session-item {
    display: flex;
    align-items: center;
    padding: 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;

    &:hover {
      background-color: #f1f5f9;
    }

    &.active {
      background-color: #eff6ff;
      border-left: 3px solid #3b82f6;
    }

    .session-icon {
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: #ecfdf5;
      border-radius: 8px;
      margin-right: 10px;
      flex-shrink: 0;

      .el-icon {
        font-size: 16px;
        color: #10b981;
      }
    }

    .session-info {
      flex: 1;
      min-width: 0;

      .session-name {
        font-size: 13px;
        font-weight: 500;
        color: #1e293b;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .session-time {
        font-size: 11px;
        color: #94a3b8;
        margin-top: 2px;
      }

      .session-rename {
        :deep(.el-input__inner) {
          font-size: 13px;
          padding: 4px 8px;
        }
      }
    }

    .session-actions {
      display: flex;
      gap: 4px;
      opacity: 0;
      transition: opacity 0.2s;

      .action-btn {
        color: #94a3b8;

        &:hover {
          color: #3b82f6;
        }

        &.delete-btn:hover {
          color: #ef4444;
        }
      }
    }

    &:hover .session-actions {
      opacity: 1;
    }

    .session-active-indicator {
      position: absolute;
      right: 12px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: #3b82f6;
    }
  }
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header {
  padding: 12px 16px;
  background: #3b82f6;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;

  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;

    .session-title {
      font-size: 14px;
      font-weight: 600;
      color: #fff;
      white-space: nowrap;
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  .header-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .header-action-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: none;
    background: rgba(255, 255, 255, 0.15);
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;

    &:hover {
      background: rgba(255, 255, 255, 0.25);
    }

    &.close:hover {
      background: rgba(239, 68, 68, 0.8);
    }

    svg {
      width: 16px;
      height: 16px;
    }
  }
}

.chat-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
  color: #64748b;
  gap: 12px;
}

.loading-icon {
  animation: rotate 1s linear infinite;
  color: #3b82f6;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.sql-dialog-content {
  max-height: 400px;
  overflow: auto;

  .sql-dialog-code {
    background: #1e293b;
    color: #e2e8f0;
    padding: 16px;
    border-radius: 8px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    white-space: pre-wrap;
    margin: 0;
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
      font-size: 16px;
      font-weight: 600;
      color: #1e293b;
    }

    .reference-detail-score {
      margin-left: auto;
      font-size: 14px;
      color: #3b82f6;
      font-weight: 500;
    }
  }

  .reference-detail-body {
    max-height: 400px;
    overflow: auto;

    .reference-detail-content-text {
      font-size: 14px;
      line-height: 1.6;
      color: #334155;
      white-space: pre-wrap;
    }
  }
}
</style>