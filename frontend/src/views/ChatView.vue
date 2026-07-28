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
            <el-select
              v-model="chatStore.selectedLLMConfigId"
              placeholder="选择模型"
              size="small"
              @change="(val: any) => chatStore.setLLMConfigId(val ?? null)"
            >
              <el-option 
                v-for="llm in chatStore.llmConfigs" 
                :key="llm.id" 
                :label="llm.name + (llm.isDefault ? ' (默认)' : '')" 
                :value="llm.id" 
              />
            </el-select>
          </div>
        </div>
      </div>

      <div ref="messagesRef" class="chat-messages" @scroll="handleScroll">
        <!-- 加载状态 -->
        <div class="welcome-banner" v-if="chatStore.isLoadingMessages">
          <div class="loading-wrapper">
            <el-spinner class="loading-spinner" size="60" />
            <p class="loading-text">加载中...</p>
          </div>
        </div>

        <!-- 空状态 -->
        <div class="welcome-banner" v-else-if="messages.length === 0">
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
          <h3 class="welcome-title">你好，我是钢铁行业智能助手</h3>
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
          <div v-if="msg.role === 'user'" class="message-content user" :class="{ editing: editingMessageId[msg.id] }">
            <div class="avatar-group">
              <AvatarImage type="user" />
            </div>
            <div class="message-bubble-wrap" :class="{ editing: editingMessageId[msg.id] }">
              <div class="message-bubble" v-if="!editingMessageId[msg.id]">
                <div class="bubble-arrow"></div>
                <div class="bubble-content">{{ msg.content }}</div>
              </div>
              <!-- 编辑模式 -->
              <div v-else class="message-bubble edit-mode">
                <div class="edit-input-wrap">
                  <el-input
                    v-model="editMessageContent[msg.id]"
                    class="edit-input"
                    placeholder="输入您的问题..."
                  />
                  <div class="edit-actions">
                    <el-button size="small" @click="cancelEdit(msg.id)">取消</el-button>
                    <el-button size="small" type="primary" class="edit-send-btn" @click="submitEdit(msg)">发送</el-button>
                  </div>
                </div>
              </div>
              <!-- 用户消息操作：复制、编辑 -->
              <div class="user-message-actions">
                <el-icon class="meta-action-icon" @click="copyMessageContent(msg.content)" title="复制">
                  <CopyDocument />
                </el-icon>
                <el-icon class="meta-action-icon" @click="startEdit(msg)" title="编辑">
                  <Edit />
                </el-icon>
              </div>
            </div>
          </div>
          <div v-else class="message-content assistant">
            <div class="avatar-group">
              <AvatarImage type="assistant" />
            </div>
            <div class="message-bubble-wrap">
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

              <!-- 消息气泡：始终显示，确保流式内容能实时展示 -->
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

                <!-- 知识引用 - 放入AI回答框的底部 -->
                <div v-if="msg.references && msg.references.length > 0" class="references-section">
                  <div class="references-header">
                    <el-icon><Document /></el-icon>
                    <span class="references-title">引用</span>
                  </div>
                  <div class="references-files">
                    <div
                      v-for="(ref, idx) in msg.references"
                      :key="idx"
                      class="ref-file"
                      @click="showReferenceDetail(ref)"
                    >
                      <el-icon><Document /></el-icon>
                      <span class="ref-file-name">{{ ref.documentName }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="msg.dataResult && msg.dataResult.length > 0" class="chart-section">
                <div class="section-header">
                  <div class="header-left">
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
                  <div class="header-right">
                    <!-- 查看SQL按钮 -->
                    <el-button v-if="msg.sqlTraces && msg.sqlTraces.length > 0" type="text" size="small" class="sql-view-btn" @click="showSqlDialog(msg.sqlTraces[0].sql)">
                      <el-icon><Document /></el-icon>
                      <span>查看SQL</span>
                    </el-button>
                    <!-- 导出按钮 -->
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

              <!-- 消息元数据：复制、重新生成、耗时 -->
              <div v-if="msg.role === 'assistant' && !msg.isStreaming" class="message-meta">
                <span class="meta-actions">
                  <el-icon class="meta-action-icon" @click="copyMessageContent(msg.content)" title="复制">
                    <CopyDocument />
                  </el-icon>
                  <el-icon class="meta-action-icon" @click="regenerateMessage(msg)" title="重新生成">
                    <Refresh />
                  </el-icon>
                </span>
                <el-icon class="meta-icon"><Clock /></el-icon>
                <span>耗时: {{ msg.queryTime ? (msg.queryTime / 1000).toFixed(2) : '--' }}s</span>
              </div>
            </div>
          </div>
        </div>
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
              <el-icon><Right /></el-icon>
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>
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
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, reactive, watch } from 'vue'
import * as echarts from 'echarts'
import * as XLSX from 'xlsx'
import { saveAs } from 'file-saver'
import { useChatStore } from '@/stores/chat'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  ChatDotRound,
  User,
  Cpu,
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
  CopyDocument,
  Download,
  Monitor,
  Refresh,
} from '@element-plus/icons-vue'
import { getKnowledgeBases } from '@/api/knowledge'
import { getDatasources } from '@/api/datasource'
import ChartCard from '@/components/chart/ChartCard.vue'
import AvatarImage from '@/components/AvatarImage.vue'

const chatStore = useChatStore()
const messagesRef = ref<HTMLElement>()

const searchKeyword = ref('')
const inputText = ref('')
const isSending = ref(false)
const knowledgeBases = ref<any[]>([])
const datasources = ref<any[]>([])

// 滚动状态：用于判断是否需要自动滚动到底部
const isUserScrolling = ref(false)

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

// SQL弹窗状态
const sqlDialogVisible = ref(false)
const currentSql = ref('')

// 知识引用详情弹窗状态
const referenceDetailVisible = ref(false)
const currentReference = ref<any>(null)

// 消息编辑状态
const editingMessageId = ref<Record<string, boolean>>({})
const editMessageContent = ref<Record<string, string>>({})

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
function exportChartToImage(msgId: string) {
  const config = chartConfig[msgId]
  if (!config?.option) {
    ElMessage.warning('没有图表可导出')
    return
  }

  try {
    // 创建隐藏的canvas元素
    const canvas = document.createElement('canvas')
    canvas.width = 800
    canvas.height = 400
    canvas.style.display = 'none'
    document.body.appendChild(canvas)

    // 创建图表实例
    const chart = echarts.init(canvas, undefined, {
      renderer: 'canvas',
    })
    chart.setOption(config.option)

    // 等待图表渲染完成
    setTimeout(() => {
      const url = chart.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff',
      })

      chart.dispose()
      document.body.removeChild(canvas)

      // 将base64转换为Blob并下载
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
function handleExport(cmd: string, msg: any) {
  if (cmd === 'excel') {
    exportToExcel(msg.dataResult, msg.columnMeta)
  } else if (cmd === 'image') {
    exportChartToImage(msg.id)
  }
}

// 显示SQL弹窗
function showSqlDialog(sql: string) {
  currentSql.value = sql
  sqlDialogVisible.value = true
}

// 显示知识引用详情弹窗
function showReferenceDetail(ref: any) {
  currentReference.value = ref
  referenceDetailVisible.value = true
}

// 复制SQL
function copySql(sql: string) {
  navigator.clipboard.writeText(sql).then(() => {
    ElMessage.success('SQL已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

// 复制消息内容
function copyMessageContent(content: string) {
  navigator.clipboard.writeText(content).then(() => {
    ElMessage.success('内容已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

// 开始编辑消息
function startEdit(msg: any) {
  editingMessageId.value[msg.id] = true
  editMessageContent.value[msg.id] = msg.content
}

// 取消编辑
function cancelEdit(msgId: string) {
  editingMessageId.value[msgId] = false
  editMessageContent.value[msgId] = ''
}

// 提交编辑（作为新消息发送）
function submitEdit(msg: any) {
  const content = editMessageContent.value[msg.id]
  if (!content || !content.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }
  // 关闭编辑模式
  editingMessageId.value[msg.id] = false
  editMessageContent.value[msg.id] = ''
  // 发送新消息
  chatStore.sendUserMessage(content.trim())
}

// 重新生成消息
function regenerateMessage(msg: any) {
  // 优先使用消息自带的问题
  if (msg.question) {
    chatStore.sendUserMessage(msg.question)
    return
  }
  
  // 尝试通过消息ID查找父消息（用户消息）
  const msgIndex = messages.value.findIndex((m) => m.id === msg.id)
  if (msgIndex > 0) {
    const prevMsg = messages.value[msgIndex - 1]
    if (prevMsg && prevMsg.role === 'user') {
      chatStore.sendUserMessage(prevMsg.content)
      return
    }
  }
  
  ElMessage.error('无法重新生成此消息')
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
      grid: { top: 40, right: 20, bottom: 60, left: 20, containLabel: true },
      xAxis: {
        type: 'category',
        name: xAxisName,
        data: xData,
        axisLabel: { rotate: xData.length > 10 ? 45 : 0, fontSize: 11, interval: 0 },
        nameTextStyle: { fontSize: 12, padding: [10, 0, 0, 0] },
        nameLocation: 'middle',
        nameGap: 30,
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

function handleEnterKey(e: KeyboardEvent) {
  if (!e.ctrlKey && !e.shiftKey && !e.altKey) {
    e.preventDefault()
    handleSend()
  }
}

function scrollToBottom(force = false) {
  if (messagesRef.value) {
    // 获取最后一条消息
    const lastMessage = messages.value[messages.value.length - 1]
    
    // 如果最后一条消息正在流式输出，或强制滚动，则强制滚动到底部
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

// 处理滚动事件
function handleScroll() {
  // 滚动事件处理，用于更新shouldAutoScroll的判断
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
      // 兼容分页格式：新接口返回 {total, list}，旧接口直接返回数组
      if (res.data && Array.isArray(res.data.list)) {
        datasources.value = res.data.list
      } else if (Array.isArray(res.data)) {
        datasources.value = res.data
      } else {
        datasources.value = []
      }
    }
  } catch (e) {
    console.error('加载数据源失败', e)
    datasources.value = []
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
  // 立即设置loading状态，防止旧消息闪烁
  chatStore.isLoadingMessages = true
  chatStore.messages = []
  
  await chatStore.fetchSessions()
  await loadKnowledgeBases()
  await loadDatasources()
  await chatStore.fetchLLMConfigs()
  await chatStore.fetchDefaultLLMConfig()
  
  if (sessions.value.length === 0) {
    await chatStore.createNewSession()
  } else {
    await chatStore.selectSession(sessions.value[0].id)
  }
  
  // 加载完成后强制滚动到最新消息
  nextTick(() => scrollToBottom(true))
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

// 监听消息内容变化，在流式输出时自动滚动到底部
watch(
  () => messages.value.map((m) => m.content),
  () => {
    nextTick(() => scrollToBottom())
  },
  { deep: true }
)
</script>

<style lang="scss" scoped>
.chat-view {
  display: flex;
  height: 100%;
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
  min-width: 0;
  overflow: hidden;

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

  }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 24px;
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);

    .welcome-banner {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 60px 40px;
      text-align: center;

      .loading-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 16px;
      }

      .loading-spinner {
        color: #3b82f6;
      }

      .loading-text {
        font-size: 16px;
        color: #64748b;
        margin: 0;
      }
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
      min-width: 0;
      overflow: hidden;
      gap: 12px;

      &.user {
        flex-direction: row-reverse;

        // 编辑模式下，消息区域宽度占满，保持头像在右边
        &.editing {
          max-width: 100%;
          width: 100%;
        }

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
          flex: 0 1 auto;
          min-width: 0;
          max-width: 100%;
          overflow: hidden;
          align-items: flex-end;

          // 编辑模式下占满可用宽度，与AI回复框对齐
          &.editing {
            flex: 1;
            align-items: stretch;
            width: 100%;
            max-width: calc(85% - 50px); // 减去头像宽度，与AI回复框对齐
          }
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
        background: white;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
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
        align-items: center;
        gap: 4px;
        padding: 4px 0;
        
        span {
          width: 6px;
          height: 6px;
          background-color: rgba(255, 255, 255, 0.8);
          border-radius: 50%;
          animation: typing 1.4s infinite ease-in-out both;
          
          &:nth-child(1) {
            animation-delay: -0.32s;
          }
          
          &:nth-child(2) {
            animation-delay: -0.16s;
          }
        }
      }

      @keyframes typing {
        0%, 80%, 100% {
          transform: scale(0);
          opacity: 0.5;
        }
        40% {
          transform: scale(1);
          opacity: 1;
        }
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
        margin-top: 8px;

        .sql-view-btn {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          color: #64748b;
          font-size: 12px;
          padding: 4px 12px;
          border-radius: 4px;
          background-color: #f1f5f9;
          border: 1px solid #e2e8f0;

          &:hover {
            color: #3b82f6;
            background-color: #e0f2fe;
            border-color: #bae6fd;
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
          justify-content: space-between;
          padding: 14px 16px;
          background: linear-gradient(90deg, #ecfdf5 0%, #ffffff 100%);
          border-bottom: 1px solid #d1fae5;

          .header-left {
            display: flex;
            align-items: center;
            gap: 10px;

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
            }

            .chart-view-toggle {
              margin-left: 10px;
            }
          }

          .header-right {
            display: flex;
            align-items: center;
            gap: 8px;

            .sql-view-btn {
              color: #64748b;
              font-size: 13px;
              padding: 4px 10px;

              &:hover {
                color: #f59e0b;
                background-color: #fffbeb;
              }
            }

            .export-btn {
              color: #64748b;
              font-size: 13px;
              padding: 4px 10px;

              &:hover {
                color: #3b82f6;
                background-color: #eff6ff;
              }
            }
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
        gap: 12px;
        margin-top: 8px;

        .meta-actions {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .meta-action-icon {
          font-size: 14px;
          color: #94a3b8;
          cursor: pointer;
          transition: color 0.2s;

          &:hover {
            color: #3b82f6;
          }
        }

        .meta-icon {
          font-size: 12px;
          color: #94a3b8;
        }

        span {
          font-size: 12px;
          color: #94a3b8;
        }
      }

      .references-section {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 8px;
        flex-wrap: wrap;

        .references-header {
          display: flex;
          align-items: center;
          gap: 4px;

          .el-icon {
            font-size: 14px;
            color: #64748b;
          }

          .references-title {
            font-size: 12px;
            color: #64748b;
          }
        }

        .references-files {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }

        .ref-file {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 4px 10px;
          background-color: #f1f5f9;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s;

          .el-icon {
            font-size: 14px;
            color: #6366f1;
          }

          .ref-file-name {
            font-size: 12px;
            color: #475569;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          &:hover {
            background-color: #e0e7ff;

            .ref-file-name {
              color: #6366f1;
            }
          }
        }
      }

      // 用户消息操作按钮
      .user-message-actions {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 4px;

        .meta-action-icon {
          font-size: 14px;
          color: #94a3b8;
          cursor: pointer;
          transition: color 0.2s;

          &:hover {
            color: #3b82f6;
          }
        }
      }

      // 编辑模式样式
      .message-bubble.edit-mode {
        background: #ffffff !important;
        background-image: none !important;
        color: #1e293b !important;
        border-radius: 12px !important;
        position: relative;
        padding: 4px !important;
        font-size: 14px;
        line-height: 1.7;
        word-break: break-word;
        overflow-wrap: break-word;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06) !important;
        width: 100% !important;
        max-width: 100% !important;
        border: 1px solid #e2e8f0;
        flex: 1;

        .edit-input-wrap {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 0;
          width: 100%;
        }

        .edit-input {
          flex: 1;

          :deep(.el-input__wrapper) {
            border-radius: 10px;
            padding: 8px 12px;
            font-size: 14px;
            border: none;
            background-color: transparent;
            box-shadow: none;

            &:focus {
              box-shadow: none;
            }
          }

          :deep(.el-input__inner) {
            padding: 0;
            font-size: 14px;
          }
        }

        .edit-actions {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .edit-actions .el-button {
          border-radius: 8px;
          padding: 6px 14px;
          height: auto;
          font-size: 13px;
        }

        .edit-send-btn {
          background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
          border: none !important;
          border-radius: 10px;
          padding: 6px 18px !important;
          font-weight: 500;
          box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
        }
      }
    }
  }

  .chat-input-area {
    background-color: #ffffff;
    border-top: 1px solid #e2e8f0;
    box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.04);
    flex-shrink: 0;

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
          resize: vertical;
          min-height: 44px;
          max-height: 180px;

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
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* SQL弹窗样式 */
.sql-dialog-content {
  max-height: 60vh;
  overflow-y: auto;

  .sql-dialog-code {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 13px;
    color: #e2e8f0;
    background-color: #0f172a;
    padding: 16px;
    border-radius: 8px;
    line-height: 1.8;
    margin: 0;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

/* 知识引用详情弹窗样式 */
.reference-detail-content {
  .reference-detail-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px;
    background-color: #f8fafc;
    border-radius: 8px;
    margin-bottom: 16px;

    .reference-detail-title {
      font-size: 14px;
      font-weight: 600;
      color: #1e293b;
      flex: 1;
    }

    .reference-detail-score {
      font-size: 12px;
      padding: 4px 10px;
      background-color: #dcfce7;
      color: #16a34a;
      border-radius: 6px;
      font-weight: 500;
    }
  }

  .reference-detail-body {
    max-height: 50vh;
    overflow-y: auto;
  }

  .reference-detail-content-text {
    font-size: 13px;
    color: #334155;
    line-height: 1.8;
    white-space: pre-wrap;
    word-break: break-all;
  }
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
  70% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}
</style>