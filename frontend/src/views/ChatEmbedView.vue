<template>
  <div class="chat-embed-view">
    <div class="chat-sidebar">
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
    </div>

    <div class="chat-main">
      <div class="chat-header">
        <div class="header-left">
          <div class="header-logo">
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="20" cy="20" r="18" stroke="#3b82f6" stroke-width="2" fill="none" opacity="0.6"/>
              <circle cx="20" cy="20" r="14" stroke="#3b82f6" stroke-width="1.5" fill="none" stroke-dasharray="22 66" stroke-dashoffset="0" opacity="0.8"/>
              <circle cx="20" cy="20" r="10" stroke="#60a5fa" stroke-width="1.5" fill="none" stroke-dasharray="16 47" stroke-dashoffset="-8" opacity="0.9"/>
              <circle cx="20" cy="20" r="4" fill="#3b82f6"/>
              <circle cx="20" cy="20" r="2" fill="#93c5fd"/>
            </svg>
          </div>
          <span class="session-title">{{ currentSession?.title || appName }}</span>
        </div>
      </div>

      <div ref="messagesRef" class="chat-messages">
        <div v-if="isLoading" class="loading-container">
          <el-icon class="loading-icon" :size="40"><Loading /></el-icon>
          <p>加载中...</p>
        </div>
        
        <template v-else>
        <div v-if="messages.length === 0" class="welcome-banner">
          <div class="welcome-icon">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              <line x1="32" y1="4" x2="32" y2="14" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
              <circle cx="32" cy="4" r="3" fill="#fbbf24"/>
              <rect x="14" y="14" width="36" height="24" rx="6" fill="#e2e8f0"/>
              <rect x="14" y="14" width="36" height="24" rx="6" stroke="#fff" stroke-width="1.5"/>
              <circle cx="24" cy="26" r="4" fill="#3b82f6"/>
              <circle cx="40" cy="26" r="4" fill="#3b82f6"/>
              <circle cx="24" cy="25" r="1.5" fill="#fff"/>
              <circle cx="40" cy="25" r="1.5" fill="#fff"/>
              <rect x="26" y="32" width="12" height="2.5" rx="1.25" fill="#3b82f6"/>
              <rect x="18" y="40" width="28" height="16" rx="4" fill="#cbd5e1"/>
              <rect x="18" y="40" width="28" height="16" rx="4" stroke="#fff" stroke-width="1.5"/>
              <circle cx="32" cy="48" r="3" fill="#3b82f6"/>
              <circle cx="32" cy="48" r="1.2" fill="#fff"/>
            </svg>
          </div>
          <p class="welcome-desc">{{ greetingMessage || '你好，有什么我可以帮你的吗？' }}</p>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-item"
          :class="[msg.role]"
        >
          <div v-if="msg.role === 'user'" class="message-content user">
            <div class="avatar-group">
              <AvatarImage type="user" />
            </div>
            <div class="message-bubble-wrap">
              <div class="message-bubble">
                <div class="bubble-arrow"></div>
                <div class="bubble-content">{{ msg.content }}</div>
              </div>
            </div>
          </div>
          <div v-else class="message-content assistant">
            <div class="avatar-group">
              <AvatarImage type="assistant" />
            </div>
            <div class="message-bubble-wrap">
              <!-- Thinking Process -->
              <div class="thinking-process" v-if="(msg.thinkingSteps && msg.thinkingSteps.length > 0) || (msg.sqlTraces && msg.sqlTraces.length > 0)">
                <div class="thinking-header" @click="toggleThinking(msg.id)">
                  <el-icon :class="{ 'rotated': thinkingExpanded[msg.id] }"><ArrowRight /></el-icon>
                  <span class="thinking-title">思考过程</span>
                  <span class="thinking-count">{{ msg.thinkingSteps?.length || 0 }} 步</span>
                  <span class="thinking-action">{{ thinkingExpanded[msg.id] ? '收起' : '展开' }}</span>
                </div>
                <div v-show="thinkingExpanded[msg.id]" class="thinking-content">
                  <div v-if="msg.thinkingSteps && msg.thinkingSteps.length > 0" class="thinking-steps">
                    <div class="section-title">
                      <el-icon><List /></el-icon>
                      <span>执行步骤</span>
                    </div>
                    <div class="steps-timeline">
                      <div v-for="(step, idx) in msg.thinkingSteps" :key="idx" class="step-item">
                        <div class="step-connector">
                          <div class="connector-line" :class="{ last: idx === msg.thinkingSteps!.length - 1 }"></div>
                          <div class="step-dot" :class="{ active: idx === msg.thinkingSteps!.length - 1 && msg.isStreaming, completed: idx < msg.thinkingSteps!.length - 1 || !msg.isStreaming }">
                            <el-icon v-if="idx === msg.thinkingSteps!.length - 1 && msg.isStreaming"><Loading class="step-loading" /></el-icon>
                            <el-icon v-else-if="idx < msg.thinkingSteps!.length - 1 || !msg.isStreaming"><CircleCheck class="step-check" /></el-icon>
                            <span v-else class="step-number-text">{{ step.step }}</span>
                          </div>
                        </div>
                        <div class="step-content">
                          <div class="step-title">{{ step.title }}</div>
                          <div class="step-desc">{{ step.description }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Message Bubble -->
              <div class="message-bubble">
                <div class="bubble-arrow"></div>
                <!-- 打字指示器：仅在流式中且内容为空时显示 -->
                <div v-if="msg.isStreaming && !msg.content" class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <!-- 消息内容：始终渲染，确保流式内容实时更新 -->
                <template v-else>
                  <span class="message-text">{{ stripMarkdown(msg.content) }}</span>
                  <span v-if="msg.isStreaming" class="streaming-cursor">|</span>
                </template>
              </div>

              <!-- SQL Section -->
              <div v-if="msg.sqlTraces && msg.sqlTraces.length > 0" class="sql-section">
                <div class="section-header">
                  <span>SQL查询</span>
                  <el-button text size="small" class="sql-copy-btn" @click="copySql(msg.sqlTraces[0].sql)">
                    <el-icon><CopyDocument /></el-icon>
                    复制
                  </el-button>
                </div>
                <div class="sql-content">
                  <pre class="sql-code">{{ msg.sqlTraces[0].sql }}</pre>
                  <div class="sql-meta">返回 {{ msg.sqlTraces[0].rows || 0 }} 行数据</div>
                </div>
              </div>

              <!-- Data Visualization -->
              <div v-if="msg.dataResult && msg.dataResult.length > 0" class="chart-section">
                <div class="section-header">
                  <el-icon><TrendCharts /></el-icon>
                  <span>数据可视化</span>
                  <div class="table-name-badge">表名：{{ getTableName(msg.sqlTraces || []) }}</div>
                  <div class="chart-view-toggle">
                    <el-radio-group v-model="dataViewMode[msg.id]" size="small">
                      <el-radio-button value="table">表格</el-radio-button>
                      <el-radio-button value="chart">图表</el-radio-button>
                    </el-radio-group>
                  </div>
                  <el-dropdown trigger="click" @command="(cmd: string) => handleExport(cmd, msg)">
                    <el-button type="text" size="small" class="export-btn">
                      <el-icon><Download /></el-icon>
                      <span>导出</span>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="excel">Excel</el-dropdown-item>
                        <el-dropdown-item v-if="dataViewMode[msg.id] === 'chart'" command="image">图片</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
                <div class="chart-body">
                  <div v-if="dataViewMode[msg.id] !== 'chart'" class="table-wrapper">
                    <el-table
                      :data="msg.dataResult.slice(0, 100)"
                      size="small"
                      border
                      max-height="400"
                      stripe
                      class="data-table"
                    >
                      <el-table-column
                        v-for="col in getDataColumns(msg.dataResult, msg.columnMeta)"
                        :key="col.prop"
                        :prop="col.prop"
                        :label="col.label"
                        :min-width="col.minWidth"
                        show-overflow-tooltip
                      />
                    </el-table>
                    <div v-if="msg.dataResult.length > 100" class="table-footer">
                      仅展示前 100 行，共 {{ msg.dataResult.length }} 行
                    </div>
                  </div>
                  <div v-else class="chart-wrapper">
                    <div class="chart-controls">
                      <el-select v-model="chartConfig[msg.id].chartType" placeholder="图表类型" size="small" @change="updateChartOption(msg.id, msg.columnMeta)">
                        <el-option label="柱状图" value="bar" />
                        <el-option label="折线图" value="line" />
                        <el-option label="饼图" value="pie" />
                      </el-select>
                      <el-select v-model="chartConfig[msg.id].xField" placeholder="X轴" size="small" @change="updateChartOption(msg.id, msg.columnMeta)">
                        <el-option v-for="col in getDataColumns(msg.dataResult, msg.columnMeta)" :key="col.prop" :label="col.label" :value="col.prop" />
                      </el-select>
                      <el-select v-model="chartConfig[msg.id].yField" placeholder="Y轴" size="small" @change="updateChartOption(msg.id, msg.columnMeta)">
                        <el-option v-for="col in getNumericColumns(msg.dataResult, msg.columnMeta)" :key="col.prop" :label="col.label" :value="col.prop" />
                      </el-select>
                    </div>
                    <div v-if="chartConfig[msg.id]?.option" class="chart-container">
                      <ChartCard :option="chartConfig[msg.id].option" />
                    </div>
                    <div v-else class="chart-placeholder">
                      <el-icon :size="48" color="#cbd5e1">TrendCharts</el-icon>
                      <p>请选择 X 轴和 Y 轴字段以生成图表</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- References -->
              <div v-if="msg.references && msg.references.length > 0" class="references-section">
                <div class="references-header" @click="toggleReferences(msg.id)">
                  <el-icon :class="{ 'rotated': refsExpanded[msg.id] }"><ArrowRight /></el-icon>
                  <span class="references-title">知识引用</span>
                  <span class="references-count">{{ msg.references.length }} 条</span>
                  <span class="references-action">{{ refsExpanded[msg.id] ? '收起' : '展开' }}</span>
                </div>
                <div v-show="refsExpanded[msg.id]" class="references-content">
                  <div class="ref-cards">
                    <div v-for="(ref, idx) in msg.references" :key="idx" class="ref-card">
                      <div class="ref-header">
                        <span class="ref-name">{{ ref.documentName }}</span>
                        <span class="ref-score">{{ (ref.score * 100).toFixed(1) }}%</span>
                      </div>
                      <div class="ref-content">{{ ref.content.slice(0, 200) }}...</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Elapsed Time -->
              <div v-if="msg.elapsedTime" class="message-meta">
                <span>耗时: {{ msg.elapsedTime.toFixed(2) }}s</span>
              </div>
            </div>
          </div>
        </div>
        </template>
      </div>

      <div class="chat-input-area">
        <div class="input-wrapper">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入您的问题..."
            resize="none"
            @keydown.enter.exact="handleEnterKey"
            class="chat-input"
          />
          <div class="input-actions">
            <el-button type="primary" :loading="isSending" @click="handleSend" class="send-btn">
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, reactive, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  ChatDotRound,
  Edit,
  Delete,
  ArrowRight,
  List,
  Loading,
  CircleCheck,
  CopyDocument,
  TrendCharts,
  Download,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import * as XLSX from 'xlsx'
import ChartCard from '@/components/chart/ChartCard.vue'
import AvatarImage from '@/components/AvatarImage.vue'
import { getApplication, getApplicationByHash } from '@/api/application'
import type { Application } from '@/api/application'
import { getLLMConfigs } from '@/api/llmConfig'

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
  isStreaming?: boolean
  thinkingSteps?: Array<{ step: number; title: string; description: string }>
  sqlTraces?: Array<{ sql: string; rows: number }>
  dataResult?: any[]
  columnMeta?: any[]
  chartType?: string
  references?: Array<{ documentName: string; content: string; score: number }>
  elapsedTime?: number
}

const route = useRoute()
const messagesRef = ref<HTMLElement>()
const inputText = ref('')
const isSending = ref(false)
const isLoading = ref(true)

// 支持两种访问方式：通过appId（/chat/embed/:appId）或通过accessHash（/chat/:accessHash）
const isHashMode = computed(() => route.name === 'ChatEmbedByHash')
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

// 使用reactive替代ref，确保Vue能正确检测状态变化
const thinkingExpanded = reactive<Record<string | number, boolean>>({})
const refsExpanded = reactive<Record<string | number, boolean>>({})
const dataViewMode = reactive<Record<string | number, string>>({})
const chartConfig = reactive<Record<string | number, {
  chartType: string
  xField: string
  yField: string
  option: any
}>>({})

const currentSession = computed(() => sessions.value.find(s => s.id === currentSessionId.value))
const messages = computed(() => currentSession.value?.messages || [])

const filteredSessions = computed(() => {
  if (!searchKeyword.value) return sessions.value
  const keyword = searchKeyword.value.toLowerCase()
  return sessions.value.filter((s) =>
    (s.title || '新对话').toLowerCase().includes(keyword)
  )
})

const fieldAliasMap: Record<string, string> = {
  HEAT_ID: '炉号',
  BLOW_COUNT: '吹炼次数',
  PRODUCE_DATE: '生产日期',
  STEEL_GRADE: '钢种',
  STEEL_GRADE_DESC: '钢种描述',
  IRON_WGT: '铁水重量',
  SCRAP_WGT: '废钢重量',
  STEEL_WGT: '钢水重量',
  TAP_TEMP: '出钢温度',
  END_C: '终点碳',
  BLOW_O2_VOL: '吹氧量',
}

function formatTime(date: Date | string) {
  const d = new Date(date)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function stripMarkdown(content: string) {
  return content.replace(/\*\*/g, '')
}

function scrollToBottom(force = false) {
  if (messagesRef.value) {
    // 获取最后一条消息
    const lastMessage = messages.value[messages.value.length - 1]
    
    // 如果强制滚动或最后一条消息正在流式输出，则强制滚动到底部
    if (force || lastMessage?.isStreaming) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
      return
    }
    
    // 否则，只有在用户在底部附近时才自动滚动
    if (shouldAutoScroll()) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  }
}

// 检查是否需要自动滚动（用户是否在底部附近）
function shouldAutoScroll() {
  if (!messagesRef.value) return true
  const container = messagesRef.value
  const scrollTop = container.scrollTop
  const scrollHeight = container.scrollHeight
  const clientHeight = container.clientHeight
  // 如果用户滚动位置在底部50px范围内，则视为在底部
  return scrollTop >= scrollHeight - clientHeight - 50
}

function handleEnterKey(e: KeyboardEvent) {
  if (!e.ctrlKey && !e.shiftKey && !e.altKey) {
    e.preventDefault()
    handleSend()
  }
}

function toggleThinking(msgId: string | number) {
  thinkingExpanded[msgId] = !thinkingExpanded[msgId]
}

function toggleReferences(msgId: string | number) {
  refsExpanded[msgId] = !refsExpanded[msgId]
}

function getFieldAlias(fieldName: string, columnMeta?: any[]) {
  if (columnMeta && columnMeta.length > 0) {
    const meta = columnMeta.find((m: any) => m.name === fieldName)
    if (meta?.comment) {
      return meta.comment
    }
  }
  return fieldAliasMap[fieldName] || null
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

function autoSuggestChart(data: any[], msgId: string | number, suggestedChartType?: string, columnMeta?: any[]) {
  const allCols = getDataColumns(data, columnMeta)
  const numCols = getNumericColumns(data, columnMeta)
  if (allCols.length === 0 || numCols.length === 0) return

  const xCol = allCols.find((c) => !numCols.some((n) => n.prop === c.prop))?.prop || allCols[0].prop
  const yCol = numCols[0].prop

  const chartType = suggestedChartType || 'bar'

  chartConfig[msgId] = {
    chartType,
    xField: xCol,
    yField: yCol,
    option: null,
  }
  if (suggestedChartType && suggestedChartType !== 'table') {
    dataViewMode[msgId] = 'chart'
  } else {
    dataViewMode[msgId] = 'chart'
  }
  updateChartOption(msgId, columnMeta)
}

function updateChartOption(msgId: string | number, columnMeta?: any[]) {
  const config = chartConfig[msgId]
  if (!config || !config.xField || !config.yField) return

  const msg = messages.value.find((m) => m.id === msgId)
  if (!msg?.dataResult) return

  const meta = columnMeta || msg.columnMeta
  const data = msg.dataResult
  const xData = data.map((row: any) => String(row[config.xField] ?? ''))
  const yData = data.map((row: any) => Number(row[config.yField]) || 0)

  const xAxisName = getFieldAlias(config.xField, meta) || config.xField
  const yAxisName = getFieldAlias(config.yField, meta) || config.yField

  if (config.chartType === 'pie') {
    config.option = {
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
  } else {
    config.option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: config.chartType === 'bar' ? 'shadow' : 'line' },
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
        name: xAxisName,
        axisLabel: { rotate: 30, fontSize: 12 },
        nameTextStyle: { fontSize: 12 },
      },
      yAxis: {
        type: 'value',
        name: yAxisName,
        axisLabel: { fontSize: 12 },
        nameTextStyle: { fontSize: 12 },
      },
      series: [{
        name: yAxisName,
        type: config.chartType,
        data: yData,
        smooth: config.chartType === 'line',
        barMaxWidth: 50,
        itemStyle: {
          borderRadius: config.chartType === 'bar' ? [4, 4, 0, 0] : undefined,
        },
      }],
    }
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
  const config = chartConfig[msg.id]
  if (!config?.option) {
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
    chart.setOption(config.option)

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

function copySql(sql: string) {
  navigator.clipboard.writeText(sql).then(() => {
    ElMessage.success('SQL已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
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
      appData = (res.data as unknown as { data: Application }).data
    } else {
      // 通过appId访问
      const res = await getApplication(appId.value)
      appData = (res.data as unknown as { data: Application }).data
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
  // 切换会话后滚动到最新消息
  nextTick(() => scrollToBottom(true))
}

function saveSessions() {
  try {
    localStorage.setItem(`embed_sessions_${appId.value}`, JSON.stringify(sessions.value))
  } catch (e) {
    console.error('保存会话失败', e)
  }
}

function loadSessions() {
  try {
    const saved = localStorage.getItem(`embed_sessions_${appId.value}`)
    if (saved) {
      sessions.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('加载会话失败', e)
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

async function handleSend() {
  if (!inputText.value.trim()) {
    return
  }

  const userMsg: DebugMessage = {
    id: Date.now(),
    role: 'user',
    content: inputText.value.trim(),
  }
  
  const session = currentSession.value
  if (session) {
    session.messages.push(userMsg)
    session.updatedAt = new Date().toISOString()
    if (!session.title || session.title === '新对话') {
      session.title = inputText.value.trim().substring(0, 20) + (inputText.value.length > 20 ? '...' : '')
    }
    saveSessions()
  }
  
  inputText.value = ''
  nextTick(() => scrollToBottom())

  isSending.value = true

  const aiMsgId = Date.now() + 1
  const aiMsg: DebugMessage = {
    id: aiMsgId,
    role: 'assistant',
    content: '',
    isStreaming: true,
  }
  if (session) {
    session.messages.push(aiMsg)
    saveSessions()
  }
  nextTick(() => scrollToBottom())

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
            if (aiMsg) {
              aiMsg.content += data.content
              aiMsg.isStreaming = true
            }
            saveSessions()
            nextTick(() => scrollToBottom())
          } else if (data.type === 'thinking') {
              if (aiMsg) {
                // 后端发送的thinking消息包含顶层字段：step, total_steps, title, description
                if (!aiMsg.thinkingSteps) {
                  aiMsg.thinkingSteps = []
                }
                aiMsg.thinkingSteps.push({
                  step: data.step,
                  title: data.title,
                  description: data.description
                })
                thinkingExpanded[aiMsgId] = true
              }
              saveSessions()
            } else if (data.type === 'sql_traces') {
              if (aiMsg) {
                aiMsg.sqlTraces = data.data
              }
              saveSessions()
            } else if (data.type === 'data_result') {
              if (aiMsg) {
                aiMsg.dataResult = data.data
                // 后端将columnMeta和chartType放在data_result消息中
                if (data.columnMeta) {
                  aiMsg.columnMeta = data.columnMeta
                }
                // 自动生成图表
                if (aiMsg.dataResult && aiMsg.dataResult.length > 0) {
                  autoSuggestChart(aiMsg.dataResult, aiMsgId, data.chartType || 'bar', aiMsg.columnMeta)
                }
              }
              saveSessions()
            } else if (data.type === 'column_meta') {
              if (aiMsg) {
                aiMsg.columnMeta = data.data
                if (aiMsg.dataResult && aiMsg.dataResult.length > 0) {
                  autoSuggestChart(aiMsg.dataResult, aiMsgId, data.suggested_chart_type || 'bar', aiMsg.columnMeta)
                }
              }
              saveSessions()
          } else if (data.type === 'references') {
            if (aiMsg) {
              aiMsg.references = data.data
            }
            saveSessions()
          } else if (data.type === 'done') {
            if (aiMsg) {
              aiMsg.isStreaming = false
              const elapsedTime = data.elapsed_time || data.elapsedTime
              if (elapsedTime !== undefined) {
                aiMsg.elapsedTime = Math.round(elapsedTime * 1000)
              }
            }
            saveSessions()
          } else if (data.type === 'error') {
            if (aiMsg) {
              aiMsg.content += `\n\n[错误] ${data.message}`
              aiMsg.isStreaming = false
            }
            saveSessions()
          }
        } catch (e) {
          console.error('解析SSE消息失败', e)
        }
      }
    }
  } catch (error: any) {
    const currentMsgs = currentSession.value?.messages || []
    const aiMsg = currentMsgs.find(m => m.id === aiMsgId)
    if (aiMsg) {
      aiMsg.content = aiMsg.content || '抱歉，消息发送失败，请稍后重试。'
      aiMsg.isStreaming = false
    }
    saveSessions()
  } finally {
    isSending.value = false
    nextTick(() => scrollToBottom())
  }
}

// 监听messages变化，自动初始化图表（用于从localStorage加载会话时）
watch(
  () => messages.value.map((m) => m.dataResult),
  (results) => {
    messages.value.forEach((msg) => {
      if (msg.dataResult && msg.dataResult.length > 0 && !chartConfig[msg.id]) {
        autoSuggestChart(msg.dataResult, msg.id, msg.chartType, msg.columnMeta)
      }
    })
    nextTick(() => scrollToBottom())
  },
  { deep: true }
)

// 监听消息内容变化，在流式输出时自动滚动到底部
watch(
  () => messages.value.map((m) => m.content),
  () => {
    nextTick(() => scrollToBottom())
  },
  { deep: true }
)

onMounted(async () => {
  await loadAppConfig()
  await loadLLMConfigs()
  loadSessions()
  if (sessions.value.length === 0) {
    createNewSession()
  } else {
    currentSessionId.value = sessions.value[0].id
  }
  // 加载完成后强制滚动到最新消息
  nextTick(() => {
    scrollToBottom(true)
    isLoading.value = false
  })
})
</script>

<style lang="scss" scoped>
.chat-embed-view {
  display: flex;
  height: 100vh;
  background-color: #f1f5f9;
  overflow: hidden; /* 防止页面整体滚动 */
}

.chat-sidebar {
  width: 280px;
  background-color: #f8fafc;
  display: flex;
  flex-direction: column;
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
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;

    .header-logo {
      svg {
        width: 20px;
        height: 20px;
      }
    }

    .session-title {
      font-size: 14px;
      font-weight: 600;
      color: #fff;
      white-space: nowrap;
    }
  }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px;
  padding-right: 24px; /* 给滚动条留出空间 */
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  scrollbar-gutter: stable; /* 保持滚动条占位稳定 */

  .loading-container {
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

  .welcome-banner {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    text-align: center;
  }

  .welcome-icon {
    width: 64px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
    border-radius: 16px;
    margin-bottom: 16px;
    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);

    svg {
      width: 40px;
      height: 40px;
    }
  }

  .welcome-desc {
    font-size: 14px;
    color: #64748b;
    margin: 0;
    max-width: 300px;
  }

  .message-item {
    display: flex;
    margin-bottom: 16px;

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
    gap: 10px;

    &.user {
      flex-direction: row-reverse;

      .avatar-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        flex-shrink: 0;
      }

      .message-bubble-wrap {
        display: flex;
        flex-direction: column;
        gap: 8px;
        flex: 0 1 auto;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        align-items: flex-end;
      }

      .message-bubble {
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        color: #ffffff;
        border-radius: 12px 12px 4px 12px;
        position: relative;
        padding: 12px 16px;
        font-size: 14px;
        line-height: 1.6;
        word-break: break-word;
        overflow-wrap: break-word;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        width: auto;
        max-width: 100%;

        .bubble-arrow {
          position: absolute;
          width: 0;
          height: 0;
          top: 12px;
          border: 6px solid transparent;
          right: -12px;
          border-left-color: #6366f1;
        }
      }
    }

    &.assistant {
      flex-direction: row;

      .avatar-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        flex-shrink: 0;
      }

      .message-bubble-wrap {
        display: flex;
        flex-direction: column;
        gap: 8px;
        flex: 1;
        min-width: 0;
        align-items: stretch;
        overflow: hidden;
      }

      .message-bubble {
        background-color: #ffffff;
        color: #1e293b;
        border-radius: 12px 12px 12px 4px;
        position: relative;
        padding: 12px 16px;
        font-size: 14px;
        line-height: 1.6;
        word-break: break-word;
        overflow-wrap: break-word;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        width: 100%;

        .bubble-arrow {
          position: absolute;
          width: 0;
          height: 0;
          top: 12px;
          border: 6px solid transparent;
          left: -12px;
          border-right-color: #ffffff;
        }
      }

      .thinking-process {
        background-color: #fff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        margin-top: 4px;

        .thinking-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          cursor: pointer;
          transition: background-color 0.2s;

          &:hover {
            background-color: #f8fafc;
          }

          .thinking-title {
            font-size: 12px;
            font-weight: 600;
            color: #3b82f6;
          }

          .thinking-count {
            font-size: 11px;
            color: #94a3b8;
            margin-left: auto;
          }

          .thinking-action {
            font-size: 11px;
            color: #64748b;
            margin-left: 8px;
          }
        }

        .thinking-content {
          padding: 12px 14px;
          border-top: 1px solid #e2e8f0;
        }

        .thinking-steps {
          .section-title {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12px;

            .el-icon {
              font-size: 12px;
            }
          }

          .steps-timeline {
            display: flex;
            flex-direction: column;
            gap: 0;
          }

          .step-item {
            display: flex;
            gap: 12px;
            padding-bottom: 14px;
            position: relative;

            &:last-child {
              padding-bottom: 0;
            }

            .step-connector {
              display: flex;
              flex-direction: column;
              align-items: center;
              width: 20px;
              flex-shrink: 0;

              .connector-line {
                width: 2px;
                flex: 1;
                min-height: 30px;
                background-color: #e2e8f0;
                margin-top: 4px;

                &.last {
                  display: none;
                }
              }

              .step-dot {
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background-color: #e2e8f0;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
                border: 2px solid #fff;
                box-shadow: 0 0 0 2px #e2e8f0;
                transition: all 0.3s;

                &.active {
                  background-color: #3b82f6;
                  box-shadow: 0 0 0 2px #93c5fd;
                }

                &.completed {
                  background-color: #10b981;
                  box-shadow: 0 0 0 2px #6ee7b7;
                }

                .step-loading {
                  font-size: 10px;
                  color: #fff;
                }

                .step-check {
                  font-size: 10px;
                  color: #fff;
                }

                .step-number-text {
                  font-size: 9px;
                  font-weight: 600;
                  color: #64748b;
                }
              }
            }

            .step-content {
              flex: 1;
              padding-top: 2px;

              .step-title {
                font-size: 12px;
                font-weight: 600;
                color: #1e293b;
                margin-bottom: 2px;
              }

              .step-desc {
                font-size: 11px;
                color: #64748b;
                line-height: 1.5;
              }
            }
          }
        }
      }

      .sql-section {
        background-color: #1e293b;
        border-radius: 10px;
        overflow: hidden;
        margin-top: 4px;

        .section-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          background-color: #334155;
          border-bottom: 1px solid #475569;

          span {
            font-size: 11px;
            font-weight: 600;
            color: #94a3b8;
          }

          .sql-copy-btn {
            margin-left: auto;
            font-size: 10px;
            color: #94a3b8;

            &:hover {
              color: #fff;
            }
          }
        }

        .sql-content {
          padding: 10px 12px;

          .sql-code {
            font-family: 'Fira Code', 'Consolas', monospace;
            font-size: 11px;
            color: #e2e8f0;
            line-height: 1.6;
            margin: 0;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
          }

          .sql-meta {
            font-size: 10px;
            color: #64748b;
            margin-top: 6px;
            text-align: right;
          }
        }
      }

      .chart-section {
        background-color: #fff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        margin-top: 4px;

        .section-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          border-bottom: 1px solid #e2e8f0;
          flex-wrap: wrap;

          .el-icon {
            font-size: 14px;
            color: #3b82f6;
          }

          span {
            font-size: 12px;
            font-weight: 600;
            color: #475569;
          }

          .table-name-badge {
            font-size: 10px;
            padding: 2px 8px;
            background-color: #eff6ff;
            color: #3b82f6;
            border-radius: 4px;
            margin-left: auto;
          }

          .chart-view-toggle {
            margin-left: 12px;
          }

          .export-btn {
            margin-left: 8px;
            font-size: 11px;
            color: #64748b;

            &:hover {
              color: #3b82f6;
            }
          }
        }

        .chart-body {
          padding: 12px;
        }

        .table-wrapper {
          overflow-x: auto;

          .data-table {
            font-size: 11px;

            :deep(.el-table__header th) {
              font-size: 11px;
              font-weight: 600;
            }

            :deep(.el-table__body td) {
              font-size: 11px;
            }
          }

          .table-footer {
            text-align: center;
            font-size: 10px;
            color: #94a3b8;
            margin-top: 8px;
          }
        }

        .chart-wrapper {
          .chart-controls {
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            flex-wrap: wrap;

            :deep(.el-select) {
              width: auto;
            }

            :deep(.el-select__wrapper) {
              font-size: 11px;
            }
          }

          .chart-container {
            height: 300px;
            min-height: 200px;
          }

          .chart-placeholder {
            height: 300px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: #cbd5e1;

            p {
              margin-top: 12px;
              font-size: 12px;
            }
          }
        }
      }

      .references-section {
        background-color: #fff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        margin-top: 4px;

        .references-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 14px;
          cursor: pointer;
          transition: background-color 0.2s;

          &:hover {
            background-color: #f8fafc;
          }

          .references-title {
            font-size: 12px;
            font-weight: 600;
            color: #3b82f6;
          }

          .references-count {
            font-size: 11px;
            color: #94a3b8;
            margin-left: auto;
          }

          .references-action {
            font-size: 11px;
            color: #64748b;
            margin-left: 8px;
          }
        }

        .references-content {
          padding: 12px 14px;
          border-top: 1px solid #e2e8f0;
        }

        .ref-cards {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .ref-card {
          padding: 10px;
          background-color: #f8fafc;
          border-radius: 6px;
          border: 1px solid #e2e8f0;

          .ref-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;

            .ref-name {
              font-size: 11px;
              font-weight: 600;
              color: #1e293b;
            }

            .ref-score {
              font-size: 10px;
              padding: 1px 5px;
              background-color: #dcfce7;
              color: #16a34a;
              border-radius: 4px;
              font-weight: 500;
            }
          }

          .ref-content {
            font-size: 11px;
            color: #64748b;
            line-height: 1.5;
          }
        }
      }
    }

    .avatar-label {
      font-size: 10px;
      font-weight: 600;
      color: #1e293b;
      white-space: nowrap;
    }

    .user-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, #fde8e8 0%, #fef3c7 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 6px rgba(220, 38, 38, 0.15);
    }

    .assistant-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: white;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    }

    .message-text {
      white-space: pre-wrap;
    }

    .streaming-cursor {
      animation: blink 1s infinite;
      font-weight: bold;
    }

    .typing-indicator {
      display: flex;
      gap: 6px;
      padding: 8px 0;

      span {
        width: 8px;
        height: 8px;
        background-color: #cbd5e1;
        border-radius: 50%;
        animation: typing 1.4s infinite ease-in-out both;

        &:nth-child(1) { animation-delay: -0.32s; }
        &:nth-child(2) { animation-delay: -0.16s; }
      }
    }

    .message-meta {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 6px;
      margin-top: 4px;

      span {
        font-size: 11px;
        color: #94a3b8;
      }
    }
  }
}

.chat-input-area {
  background-color: #ffffff;
  border-top: 1px solid #e2e8f0;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);

  .input-wrapper {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    padding: 10px 16px;

    .chat-input {
      flex: 1;

      :deep(.el-textarea__inner) {
        border-radius: 10px;
        padding: 10px 14px;
        font-size: 13px;
        border: 1px solid #e2e8f0;
        transition: all 0.2s;

        &:focus {
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
      }
    }

    .input-actions {
      flex-shrink: 0;
    }

    .send-btn {
      background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
      border: none;
      border-radius: 8px;
      padding: 8px 20px;
      font-weight: 500;
      font-size: 13px;
      box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);

      &:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(59, 130, 246, 0.4);
      }

      &:disabled {
        opacity: 0.7;
      }
    }
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.rotated {
  transform: rotate(90deg);
  transition: transform 0.2s ease;
}
</style>