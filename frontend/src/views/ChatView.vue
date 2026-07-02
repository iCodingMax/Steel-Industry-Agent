<template>
  <div class="chat-view">
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
          @click="chatStore.selectSession(session.id)"
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
          <el-icon class="header-icon"><ChatSquare /></el-icon>
          <span class="session-title">{{ currentSession?.title || '新对话' }}</span>
        </div>
        <div class="header-right">
          <div class="header-selectors">
            <el-select
              v-model="chatStore.selectedKnowledgeBaseId"
              placeholder="选择知识库"
              size="small"
              clearable
              @change="(val: any) => chatStore.setKnowledgeBaseId(val ?? null)"
            >
              <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
            </el-select>
            <el-select
              v-model="chatStore.selectedDatasourceId"
              placeholder="选择数据源"
              size="small"
              clearable
              @change="(val: any) => chatStore.setDatasourceId(val ?? null)"
            >
              <el-option v-for="ds in datasources" :key="ds.id" :label="ds.name" :value="ds.id" />
            </el-select>
          </div>
          <el-button size="small" @click="handleRefresh" class="refresh-btn">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>

      <div ref="messagesRef" class="chat-messages">
        <div class="welcome-banner" v-if="messages.length === 0">
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
          <h3 class="welcome-title">你好，我是贾维斯</h3>
          <p class="welcome-desc">基于大语言模型的智能助手，支持知识问答与数据查询</p>
          <div class="welcome-tips">
            <div class="tip-item">
              <el-icon><Reading /></el-icon>
              <span>选择知识库进行专业知识问答</span>
            </div>
            <div class="tip-item">
              <el-icon><DataLine /></el-icon>
              <span>选择数据源进行ChatBI数据分析</span>
            </div>
            <div class="tip-item">
              <el-icon><TrendCharts /></el-icon>
              <span>支持数据可视化与图表展示</span>
            </div>
          </div>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-item"
          :class="[msg.role, msg.type || '']"
        >
          <div v-if="msg.role === 'user'" class="message-content user">
            <div class="avatar-group">
              <div class="avatar-label">钢铁侠</div>
              <el-avatar :size="40" class="user-avatar">
                <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:24px;height:24px">
                  <path d="M20 4C12 4 8 10 8 16c0 4 1 6 2 8l2 4c1 2 2 4 4 4h8c2 0 3-2 4-4l2-4c1-2 2-4 2-8 0-6-4-12-12-12z" fill="#dc2626"/>
                  <path d="M20 6C14 6 10 11 10 16c0 3 1 5 2 7l2 4c1 1 2 3 3 3h6c1 0 2-2 3-3l2-4c1-2 2-4 2-7 0-5-4-10-10-10z" fill="#d97706"/>
                  <line x1="20" y1="6" x2="20" y2="30" stroke="#991b1b" stroke-width="1.5"/>
                  <path d="M12 15l4-2 4 2" fill="#60a5fa" stroke="#2563eb" stroke-width="0.5"/>
                  <path d="M20 15l4-2 4 2" fill="#60a5fa" stroke="#2563eb" stroke-width="0.5"/>
                  <rect x="15" y="24" width="10" height="2" rx="1" fill="#991b1b"/>
                  <circle cx="20" cy="10" r="2" fill="#93c5fd" stroke="#3b82f6" stroke-width="0.5"/>
                </svg>
              </el-avatar>
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
              <div class="avatar-label">贾维斯</div>
              <el-avatar :size="40" class="assistant-avatar">
                <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:24px;height:24px">
                  <circle cx="20" cy="20" r="16" stroke="#3b82f6" stroke-width="1.5" fill="none" opacity="0.5"/>
                  <circle cx="20" cy="20" r="12" stroke="#60a5fa" stroke-width="1.5" fill="none" stroke-dasharray="18 57" opacity="0.7"/>
                  <circle cx="20" cy="20" r="8" stroke="#93c5fd" stroke-width="1.5" fill="none" stroke-dasharray="12 38" stroke-dashoffset="-6" opacity="0.9"/>
                  <circle cx="20" cy="20" r="4" fill="#3b82f6"/>
                  <circle cx="20" cy="20" r="2" fill="#bfdbfe"/>
              </svg>
            </el-avatar>
            </div>
            <div class="message-bubble-wrap">
              <div class="thinking-process" v-if="(msg.thinkingSteps && msg.thinkingSteps.length > 0) || (msg.references && msg.references.length > 0) || (msg.sqlTraces && msg.sqlTraces.length > 0)">
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
                  <div v-if="msg.references && msg.references.length > 0" class="thinking-refs">
                    <div class="section-title">
                      <el-icon><Collection /></el-icon>
                      <span>知识引用</span>
                    </div>
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
              </div>

              <div class="message-bubble">
                <div class="bubble-arrow"></div>
                <div v-if="msg.isStreaming && !msg.content" class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <template v-else>
                  <span class="message-text">{{ stripMarkdown(msg.content) }}</span>
                  <span v-if="msg.isStreaming" class="streaming-cursor">|</span>
                </template>
              </div>

              <div v-if="msg.sqlTraces && msg.sqlTraces.length > 0" class="sql-section">
                <div class="section-header">
                  <span>SQL查询</span>
                </div>
                <div class="sql-content">
                  <pre class="sql-code">{{ msg.sqlTraces[0].sql }}</pre>
                  <div class="sql-meta">返回 {{ msg.sqlTraces[0].rows || 0 }} 行数据</div>
                </div>
              </div>

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
                      <el-icon :size="48" color="#cbd5e1">BarChart</el-icon>
                      <p>请选择 X 轴和 Y 轴字段以生成图表</p>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="msg.queryTime" class="message-meta">
                <el-icon class="meta-icon"><Clock /></el-icon>
                <span>耗时: {{ (msg.queryTime / 1000).toFixed(2) }}s</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="input-toolbar">
          <div class="toolbar-left">
            <el-button size="small" type="text" icon="Paperclip" @click="handleUpload">
              附件
            </el-button>
            <el-button size="small" type="text" icon="Picture" @click="handleImage">
              图片
            </el-button>
          </div>
        </div>
        <div class="input-wrapper">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入您的问题，如：展示转炉炼钢数据..."
            resize="none"
            @keydown.enter.exact="handleEnterKey"
            class="chat-input"
          />
          <div class="input-actions">
            <el-button type="primary" :loading="isSending" @click="handleSend" class="send-btn">
              <el-icon><Right /></el-icon>
              发送
            </el-button>
          </div>
        </div>
        <div class="input-tips">
          <span>Enter 发送 · Ctrl+Enter 换行</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, reactive, watch } from 'vue'
import * as echarts from 'echarts'
import { useChatStore } from '@/stores/chat'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  ChatDotRound,
  User,
  Cpu,
  Refresh,
  TrendCharts,
  Document,
  ArrowRight,
  Right,
  Loading,
  CircleCheck,
  ChatSquare,
  DataLine,
  List,
  Clock,
  Paperclip,
  Edit,
  Delete,
  Reading,
  Collection,
} from '@element-plus/icons-vue'
import { getKnowledgeBases } from '@/api/knowledge'
import { getDatasources } from '@/api/datasource'
import ChartCard from '@/components/chart/ChartCard.vue'

const chatStore = useChatStore()
const messagesRef = ref<HTMLElement>()

const searchKeyword = ref('')
const inputText = ref('')
const isSending = ref(false)
const knowledgeBases = ref<any[]>([])
const datasources = ref<any[]>([])

const dataViewMode = reactive<Record<string, string>>({})
const chartConfig = reactive<Record<string, {
  chartType: string
  xField: string
  yField: string
  option: any
}>>({})
const thinkingExpanded = reactive<Record<string, boolean>>({})

// 会话重命名状态
const editingSessionId = ref<string | null>(null)
const renameValue = ref('')

const sessions = computed(() => chatStore.sessions)
const currentSessionId = computed(() => chatStore.currentSessionId)
const messages = computed(() => chatStore.messages)
const currentSession = computed(() => chatStore.currentSession)

// 搜索过滤后的会话列表
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

function stripMarkdown(content: string) {
  return content.replace(/\*\*/g, '')
}

function toggleThinking(msgId: string) {
  thinkingExpanded[msgId] = !thinkingExpanded[msgId]
}

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

function getFieldAlias(fieldName: string, columnMeta?: any[]) {
  // 优先从 columnMeta（数据库字段注释）获取中文名
  if (columnMeta && columnMeta.length > 0) {
    const meta = columnMeta.find((m: any) => m.name === fieldName)
    if (meta?.comment) {
      return meta.comment
    }
  }
  // 兜底使用硬编码映射
  return fieldAliasMap[fieldName] || null
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

function autoSuggestChart(data: any[], msgId: string, suggestedChartType?: string, columnMeta?: any[]) {
  const allCols = getDataColumns(data, columnMeta)
  const numCols = getNumericColumns(data, columnMeta)
  if (allCols.length === 0 || numCols.length === 0) return

  const xCol = allCols.find((c) => !numCols.some((n) => n.prop === c.prop))?.prop || allCols[0].prop
  const yCol = numCols[0].prop

  // 使用后端推荐的图表类型，默认柱状图
  const chartType = suggestedChartType || 'bar'

  chartConfig[msgId] = {
    chartType,
    xField: xCol,
    yField: yCol,
    option: null,
  }
  // 默认展示图表视图（当有推荐图表类型时）
  if (suggestedChartType && suggestedChartType !== 'table') {
    dataViewMode[msgId] = 'chart'
  }
  updateChartOption(msgId, columnMeta)
}

function updateChartOption(msgId: string, columnMeta?: any[]) {
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
      tooltip: { trigger: 'axis' },
      grid: { top: 40, right: 20, bottom: 40, left: 20, containLabel: true },
      xAxis: {
        type: 'category',
        name: xAxisName,
        data: xData,
        axisLabel: { rotate: xData.length > 10 ? 45 : 0, fontSize: 11 },
        nameTextStyle: { fontSize: 12, padding: [8, 0, 0, 0] },
      },
      yAxis: {
        type: 'value',
        name: yAxisName,
        nameTextStyle: { fontSize: 12, padding: [0, 0, 0, 40] },
        axisLabel: { fontSize: 11 },
      },
      series: [{
        type: config.chartType,
        data: yData,
        barMaxWidth: 40,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#409eff' },
            { offset: 1, color: '#79bbff' },
          ]),
          borderRadius: [4, 4, 0, 0],
        },
        smooth: config.chartType === 'line',
        areaStyle: config.chartType === 'line' ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.02)' },
          ]),
        } : undefined,
        lineStyle: config.chartType === 'line' ? { width: 2.5, color: '#409eff' } : undefined,
        symbol: config.chartType === 'line' ? 'circle' : undefined,
        symbolSize: config.chartType === 'line' ? 6 : undefined,
      }],
    }
  }
}

async function handleNewChat() {
  await chatStore.createNewSession()
}

async function handleRefresh() {
  if (currentSessionId.value) {
    await chatStore.fetchMessages(currentSessionId.value)
  }
}

function handleEnterKey(e: KeyboardEvent) {
  if (!e.ctrlKey && !e.shiftKey && !e.altKey) {
    e.preventDefault()
    handleSend()
  }
}

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

async function loadKnowledgeBases() {
  try {
    const res = await getKnowledgeBases() as any
    if (res.code === 0) {
      knowledgeBases.value = res.data
    }
  } catch (e) {
    console.error('加载知识库失败', e)
  }
}

async function loadDatasources() {
  try {
    const res = await getDatasources() as any
    if (res.code === 0) {
      datasources.value = res.data
    }
  } catch (e) {
    console.error('加载数据源失败', e)
  }
}

function handleUpload() {
  ElMessage.info('附件上传功能开发中')
}

function handleImage() {
  ElMessage.info('图片上传功能开发中')
}

async function handleSend() {
  if (!inputText.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }

  isSending.value = true
  try {
    await chatStore.sendUserMessage(inputText.value.trim())
    inputText.value = ''
    nextTick(() => scrollToBottom())
  } catch (e) {
    console.error('发送消息失败', e)
  } finally {
    isSending.value = false
  }
}

function startRename(session: any) {
  editingSessionId.value = session.id
  renameValue.value = session.title || '新对话'
}

function cancelRename() {
  editingSessionId.value = null
  renameValue.value = ''
}

async function confirmRename(sessionId: string) {
  if (!editingSessionId.value) return
  const title = renameValue.value.trim()
  if (!title) {
    cancelRename()
    return
  }
  await chatStore.renameSession(sessionId, title)
  editingSessionId.value = null
  renameValue.value = ''
}

async function handleDeleteSession(session: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${session.title || '新对话'}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await chatStore.removeSession(session.id)
    ElMessage.success('会话已删除')
  } catch {
    // 用户取消
  }
}

onMounted(async () => {
  await chatStore.fetchSessions()
  if (sessions.value.length === 0) {
    await chatStore.createNewSession()
  } else {
    chatStore.selectSession(sessions.value[0].id)
  }
  await loadKnowledgeBases()
  await loadDatasources()
})

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
</script>

<style lang="scss" scoped>
.chat-view {
  display: flex;
  height: 100vh;
  background-color: #f1f5f9;
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
    border-bottom: 1px solid #e2e8f0;
  }

  .sidebar-title {
    font-size: 16px;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
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
        margin-top: 3px;
      }

      .session-rename {
        :deep(.el-input__wrapper) {
          background-color: #ffffff;
          box-shadow: 0 0 0 1px #3b82f6 inset;
          border-radius: 6px;
        }

        :deep(.el-input__inner) {
          color: #1e293b;
          font-size: 13px;
        }
      }
    }

    .session-actions {
      display: none;
      align-items: center;
      gap: 2px;
      flex-shrink: 0;
      margin-left: 4px;

      .action-btn {
        color: #94a3b8;
        padding: 4px;
        border-radius: 6px;

        &:hover {
          color: #475569;
          background-color: #e2e8f0;
        }

        &.delete-btn:hover {
          color: #ef4444;
          background-color: #fef2f2;
        }
      }
    }

    &:hover .session-actions {
      display: flex;
    }

    .session-active-indicator {
      width: 6px;
      height: 6px;
      background-color: #3b82f6;
      border-radius: 50%;
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
    }

    // 当操作按钮显示时，隐藏活跃指示器避免重叠
    &:hover .session-active-indicator {
      display: none;
    }
  }
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #f1f5f9;

  .chat-header {
    padding: 16px 24px;
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);

    .header-left {
      display: flex;
      align-items: center;
      gap: 10px;

      .header-icon {
        font-size: 20px;
        color: #3b82f6;
      }

      .session-title {
        font-size: 16px;
        font-weight: 600;
        color: #1e293b;
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .header-selectors {
      display: flex;
      align-items: center;
      gap: 8px;

      :deep(.el-select) {
        width: 160px;

        .el-input__wrapper {
          border-radius: 8px;
          box-shadow: 0 0 0 1px #e2e8f0 inset;
          transition: all 0.2s;

          &:hover {
            box-shadow: 0 0 0 1px #3b82f6 inset;
          }
        }

        .el-input__wrapper.is-focus {
          box-shadow: 0 0 0 1px #3b82f6 inset, 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
      }
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

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);

    .welcome-banner {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 60px 40px;
      text-align: center;
    }

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

      .robot-icon {
        width: 64px;
        height: 64px;
      }
    }

    .welcome-title {
      font-size: 24px;
      font-weight: 700;
      color: #1e293b;
      margin: 0 0 8px 0;
    }

    .welcome-desc {
      font-size: 14px;
      color: #64748b;
      margin: 0 0 32px 0;
    }

    .welcome-tips {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 24px;
    }

    .tip-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 20px;
      background-color: #ffffff;
      border-radius: 12px;
      border: 1px solid #e2e8f0;
      font-size: 13px;
      color: #475569;

      .el-icon {
        font-size: 16px;
        color: #3b82f6;
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
      gap: 12px;

      &.user {
        flex-direction: row-reverse;

        .avatar-group {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          flex-shrink: 0;
        }

        .message-bubble-wrap {
          display: flex;
          flex-direction: column;
          gap: 12px;
          flex: 1;
          min-width: 0;
          max-width: 100%;
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
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
          width: auto;
          max-width: 100%;

          .bubble-arrow {
            position: absolute;
            width: 0;
            height: 0;
            top: 16px;
            border: 8px solid transparent;
            right: -16px;
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
          gap: 4px;
          flex-shrink: 0;
        }

        .message-bubble-wrap {
          display: flex;
          flex-direction: column;
          gap: 12px;
          flex: 1;
          min-width: 0;
          max-width: 100%;
          align-items: flex-start;
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
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
          width: auto;
          max-width: 100%;

          .bubble-arrow {
            position: absolute;
            width: 0;
            height: 0;
            top: 16px;
            border: 8px solid transparent;
            left: -16px;
            border-right-color: #ffffff;
          }
        }
      }

      .avatar-label {
        font-size: 12px;
        font-weight: 600;
        color: #1e293b;
        white-space: nowrap;
      }

      .user-avatar {
        background: linear-gradient(135deg, #fde8e8 0%, #fef3c7 100%);
        box-shadow: 0 2px 8px rgba(220, 38, 38, 0.15);
      }

      .assistant-avatar {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
      }

      .message-text {
        white-space: pre-wrap;
      }

      .streaming-cursor {
        animation: blink 1s infinite;
        font-weight: bold;
      }

      .thinking-process {
        background-color: #ffffff;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        width: 100%;

        .thinking-header {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 16px;
          cursor: pointer;
          background: linear-gradient(90deg, #f1f5f9 0%, #ffffff 100%);
          transition: background-color 0.2s;

          &:hover {
            background: linear-gradient(90deg, #e2e8f0 0%, #f1f5f9 100%);
          }

          .el-icon {
            font-size: 14px;
            color: #64748b;
            transition: transform 0.25s;

            &.rotated {
              transform: rotate(90deg);
            }
          }

          .thinking-title {
            font-size: 13px;
            font-weight: 600;
            color: #475569;
          }

          .thinking-count {
            font-size: 11px;
            padding: 2px 8px;
            background-color: #e0e7ff;
            color: #6366f1;
            border-radius: 10px;
            font-weight: 500;
          }

          .thinking-action {
            margin-left: auto;
            font-size: 12px;
            color: #94a3b8;
          }
        }

        .thinking-content {
          padding: 16px;
        }

        .section-title {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          font-weight: 600;
          color: #475569;
          margin-bottom: 14px;
          padding-left: 8px;
          border-left: 3px solid #3b82f6;

          .el-icon {
            font-size: 14px;
            color: #3b82f6;
          }
        }

        .thinking-steps {
          margin-bottom: 20px;
        }

        .steps-timeline {
          display: flex;
          flex-direction: column;
          gap: 0;
        }

        .step-item {
          display: flex;
          gap: 14px;
          padding-bottom: 20px;

          &:last-child {
            padding-bottom: 0;

            .step-connector {
              .connector-line {
                display: none;
              }
            }
          }
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
            background-color: #e2e8f0;
            margin-top: 4px;

            &.last {
              display: none;
            }
          }

          .step-dot {
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #e2e8f0;
            border-radius: 50%;
            border: 3px solid #ffffff;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
            flex-shrink: 0;
            font-size: 10px;

            &.active {
              background-color: #3b82f6;
              animation: pulse 2s infinite;
            }

            &.completed {
              background-color: #10b981;
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
              color: #64748b;
              font-weight: 600;
            }
          }
        }

        .step-content {
          flex: 1;
          padding-top: 2px;

          .step-title {
            font-size: 13px;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 4px;
          }

          .step-desc {
            font-size: 12px;
            color: #64748b;
            line-height: 1.6;
          }
        }

        .thinking-refs {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px dashed #e2e8f0;
        }

        .ref-cards {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .ref-card {
          padding: 12px;
          background-color: #f8fafc;
          border-radius: 8px;
          border: 1px solid #e2e8f0;

          .ref-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;

            .ref-name {
              font-size: 12px;
              font-weight: 600;
              color: #1e293b;
            }

            .ref-score {
              font-size: 11px;
              padding: 2px 6px;
              background-color: #dcfce7;
              color: #16a34a;
              border-radius: 6px;
              font-weight: 500;
            }
          }

          .ref-content {
            font-size: 12px;
            color: #64748b;
            line-height: 1.6;
          }
        }
      }

      .sql-section {
        background-color: #0f172a;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
        width: 100%;

        .section-header {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 16px;
          background-color: #1e293b;
          border-bottom: 1px solid #334155;

          span {
            font-size: 13px;
            font-weight: 600;
            color: #f1f5f9;
          }
        }

        .sql-content {
          padding: 16px;

          .sql-code {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 12px;
            color: #e2e8f0;
            line-height: 1.8;
            margin: 0;
            overflow-x: auto;
          }

          .sql-meta {
            margin-top: 10px;
            font-size: 11px;
            color: #64748b;
            text-align: right;
          }
        }
      }

      .chart-section {
        background-color: #ffffff;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        width: 100%;

        .section-header {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 14px 16px;
          background: linear-gradient(90deg, #ecfdf5 0%, #ffffff 100%);
          border-bottom: 1px solid #d1fae5;

          .el-icon {
            font-size: 16px;
            color: #10b981;
          }

          span {
            font-size: 14px;
            font-weight: 600;
            color: #065f46;
          }

          .table-name-badge {
            font-size: 12px;
            padding: 4px 10px;
            background-color: #e0e7ff;
            color: #6366f1;
            border-radius: 6px;
            margin-left: auto;
          }

          .chart-view-toggle {
            margin-left: 10px;
          }
        }

        .chart-body {
          padding: 12px 16px 16px;
        }

        .table-wrapper {
          :deep(.data-table) {
            font-size: 12px;
            border-radius: 8px;
            overflow: hidden;
          }
        }

        .table-footer {
          margin-top: 10px;
          text-align: center;
          font-size: 12px;
          color: #94a3b8;
        }

        .chart-wrapper {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .chart-controls {
          display: flex;
          gap: 10px;
          justify-content: flex-end;
          padding: 0 4px;
        }

        .chart-container {
          width: 100%;
          min-height: 360px;
        }

        .chart-placeholder {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 40px;
          background-color: #f8fafc;
          border-radius: 8px;

          p {
            margin-top: 12px;
            font-size: 13px;
            color: #94a3b8;
          }
        }
      }

      .message-meta {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 6px;
        margin-top: 8px;

        .meta-icon {
          font-size: 12px;
          color: #94a3b8;
        }

        span {
          font-size: 12px;
          color: #94a3b8;
        }
      }
    }
  }

  .chat-input-area {
    background-color: #ffffff;
    border-top: 1px solid #e2e8f0;
    box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.04);

    .input-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 20px;
      border-bottom: 1px solid #f1f5f9;

      .toolbar-left,
      .toolbar-right {
        display: flex;
        gap: 8px;
      }
    }

    .input-wrapper {
      display: flex;
      align-items: flex-end;
      gap: 12px;
      padding: 12px 20px;

      .chat-input {
        flex: 1;

        :deep(.el-textarea__inner) {
          border-radius: 12px;
          padding: 12px 16px;
          font-size: 14px;
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

    .input-tips {
      padding: 6px 20px 12px;
      text-align: center;

      span {
        font-size: 11px;
        color: #94a3b8;
      }
    }
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
  70% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}
</style>