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

      <ChatPanel
        ref="chatPanelRef"
        :messages="messages"
        v-model="inputText"
        :isSending="isSending"
        welcomeTitle="你好，我是钢铁行业智能助手"
        welcomeDesc="基于大语言模型的智能助手，支持知识问答与数据查询"
        size="lg"
        @send="handleSend"
        @suggestion="handleSuggestion"
        @copy="copyMessageContent"
        @regenerate="regenerateMessage"
        @edit="handleEdit"
        @sql="showSqlDialog"
        @reference="showReferenceDetail"
        @export="handleExport"
      />
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
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import * as XLSX from 'xlsx'
import * as echarts from 'echarts'
import { useChatStore } from '@/stores/chat'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  ChatDotRound,
  Document,
  Edit,
  Delete,
} from '@element-plus/icons-vue'
import { getKnowledgeBases } from '@/api/knowledge'
import { getDatasources } from '@/api/datasource'
import ChatPanel from '@/components/chat/ChatPanel.vue'
import { copyToClipboard } from '@/utils/clipboard'

const chatStore = useChatStore()
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)

const searchKeyword = ref('')
const inputText = ref('')
const isSending = ref(false)
const knowledgeBases = ref<any[]>([])
const datasources = ref<any[]>([])

// SQL弹窗状态
const sqlDialogVisible = ref(false)
const currentSql = ref('')

// 知识引用详情弹窗状态
const referenceDetailVisible = ref(false)
const currentReference = ref<any>(null)

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

// 导出图表为图片（兜底逻辑：当页面实例不可用时重新渲染）
function exportChartToImage(msg: any, chartOption?: any) {
  if (!chartOption) {
    ElMessage.warning('没有图表可导出')
    return
  }

  try {
    const W = 1200
    const H = 700
    const canvas = document.createElement('canvas')
    canvas.width = W
    canvas.height = H
    // 屏幕外定位（非 display:none），确保 ECharts 能读取真实尺寸
    canvas.style.cssText = `position:fixed;left:-9999px;top:0;width:${W}px;height:${H}px;z-index:-9999;`
    document.body.appendChild(canvas)

    const chart = echarts.init(canvas, undefined, { renderer: 'canvas', width: W, height: H })
    // 深拷贝 + 修复配置，确保兜底渲染完整数据
    const clonedOption = JSON.parse(JSON.stringify(chartOption))

    // === 修复百分比布局和 containLabel 导致的绘图区压缩、数据点被截断 ===
    clonedOption.animation = false
    clonedOption.animationDuration = 0
    clonedOption.animationDurationUpdate = 0
    if (clonedOption.grid) {
      const g = Array.isArray(clonedOption.grid) ? clonedOption.grid[0] : clonedOption.grid
      // 用固定像素替代百分比，避免小尺寸下压缩绘图区
      g.containLabel = false
      g.left = 70
      g.right = 40
      g.top = 50
      g.bottom = 120
      if (clonedOption.xAxis && clonedOption.xAxis.name) {
        g.bottom = 130
      }
    }
    // 饼图：调整 grid 和 radius 避免边缘扇区被裁切
    if (Array.isArray(clonedOption.series)) {
      clonedOption.series.forEach((s: any) => {
        if (s.type === 'pie') {
          s.radius = ['35%', '65%']
          s.center = ['50%', '52%']
          if (!s.itemStyle) s.itemStyle = {}
          s.itemStyle.borderWidth = 2
        }
        if ((s.type === 'bar' || s.type === 'line') && clonedOption.xAxis) {
          clonedOption.xAxis.axisLabel = clonedOption.xAxis.axisLabel || {}
          clonedOption.xAxis.axisLabel.interval = 0
          clonedOption.xAxis.boundaryGap = s.type === 'bar' ? true : false
        }
      })
    }

    // notMerge=true 避免默认配置残留干扰
    chart.setOption(clonedOption, true)
    // 强制 resize 以确保所有元素按新尺寸布局
    chart.resize({ width: W, height: H })

    // 等待完全渲染
    setTimeout(() => {
      const url = chart.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff',
        excludeComponents: ['toolbox'],
      })

      chart.dispose()
      document.body.removeChild(canvas)

      const tableName = getTableNameFromMsg(msg)
      const link = document.createElement('a')
      link.download = `图表导出_${tableName}_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.png`
      link.href = url
      link.click()
      ElMessage.success('图表导出成功')
    }, 600)
  } catch (error) {
    console.error('图表导出失败:', error)
    ElMessage.error('图表导出失败，请重试')
  }
}

// 从消息中获取表名
function getTableNameFromMsg(msg: any): string {
  if (!msg?.sqlTraces || msg.sqlTraces.length === 0) return '数据'
  const sql = msg.sqlTraces[0].sql || ''
  const match = sql.match(/FROM\s+(\w+)/i)
  return match ? match[1] : '数据'
}

// 处理导出命令（兼容 ChatPanel 与 ChatMessage 的事件签名）
function handleExport(cmd: string, msg: any, chartOption?: any, _dataViewMode?: string) {
  if (!msg) return
  if (cmd === 'excel') {
    exportToExcel(msg.dataResult, msg.columnMeta)
  } else if (cmd === 'image') {
    // 兼容两种情况：直接传入chartOption 或 从msg中动态生成
    let option = chartOption
    if (!option && msg.dataResult && msg.dataResult.length > 0) {
      // 当chartOption未传入但有数据时，动态生成图表配置
      option = buildChartOption(msg)
    }
    exportChartToImage(msg, option)
  }
}

// 根据消息内容动态生成图表配置（用于chartOption未传入的情况）
function buildChartOption(msg: any): any {
  const rawData = msg.dataResult
  if (!rawData || rawData.length === 0) return null

  const allKeys = Object.keys(rawData[0])
  const isNumeric = (val: any) => typeof val === 'number' || (!isNaN(Number(val)) && val !== null && val !== '')
  const numKeys = allKeys.filter((key) => isNumeric(rawData[0][key]))
  if (allKeys.length === 0 || numKeys.length === 0) return null

  // 智能选择列
  const categoryKeywords = ['班次', '类型', '名称', '日期', '时间', '代码', '编号', '项目', '评分', '等级']
  const excludeKeywords = ['报告', '备注', '说明', '描述', '内容', '信息', '消息']
  const valueKeywords = ['得分', '评分', '数量', '次数', '金额', '率', '值', '数']

  function getAlias(key: string): string {
    const meta = msg.columnMeta?.find((m: any) => (m.name || m.columnName) === key)
    return meta?.comment || meta?.columnAlias || key
  }

  // 智能选择xField
  let xField = allKeys.find((key) => {
    const label = getAlias(key) || key
    const val = rawData[0][key]
    if (isNumeric(val)) return false
    if (excludeKeywords.some((kw) => label.includes(kw))) return false
    if (String(val ?? '').length > 50) return false
    return categoryKeywords.some((kw) => label.includes(kw))
  })
  if (!xField) {
    const nonTextKeys = allKeys.filter((key) => {
      const label = getAlias(key) || key
      const val = rawData[0][key]
      if (isNumeric(val)) return false
      if (excludeKeywords.some((kw) => label.includes(kw))) return false
      if (String(val ?? '').length > 50) return false
      return true
    })
    xField = nonTextKeys[0] || allKeys[0]
  }
  // 智能选择yField
  let yField = numKeys.find((key) => {
    const label = getAlias(key) || key
    return valueKeywords.some((kw) => label.includes(kw))
  })
  if (!yField) yField = numKeys[0]

  // 自动聚合
  let data = rawData
  if (rawData.length > 10 && xField && yField) {
    const groups = new Map<string, any[]>()
    for (const row of rawData) {
      const key = String(row[xField] ?? '')
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(row)
    }
    if (rawData.length / Math.max(groups.size, 1) > 1.5 && groups.size < rawData.length * 0.7) {
      data = Array.from(groups.entries()).map(([key, rows]) => ({
        [xField]: key,
        [yField]: Math.round(rows.reduce((s, r) => s + (Number(r[yField]) || 0), 0) / rows.length * 100) / 100,
        count: rows.length,
      }))
      if (data.length > 20) {
        const top = data.slice(0, 19)
        const rest = data.slice(19).reduce((s, r) => s + (r.count || 0), 0)
        const restAvg = data.slice(19).reduce((s, r) => s + (Number(r[yField]) || 0) * (r.count || 1), 0) / Math.max(rest, 1)
        top.push({ [xField]: '其他', [yField]: Math.round(restAvg * 100) / 100, count: rest })
        data = top
      }
    }
  }

  // 推荐的图表类型（优先使用msg中的设置）
  let chartType = msg.chartType || 'bar'
  if (!['bar', 'line', 'pie'].includes(chartType)) chartType = 'bar'

  const xLabel = getAlias(xField)
  const yLabel = getAlias(yField)
  const dataLength = data.length
  const needRotate = dataLength > 6
  const needDataZoom = dataLength > 20
  const colors = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#6366f1', '#f43f5e', '#84cc16', '#0ea5e9']
  const barColors = ['#3b82f6', '#2563eb', '#1d4ed8', '#1e40af', '#1e3a8a']
  const lineColor = '#3b82f6'

  const option: any = {
    color: colors,
    tooltip: {
      trigger: chartType === 'pie' ? 'item' : 'axis',
      axisPointer: chartType === 'pie' ? undefined : { type: 'shadow' },
      confine: true,
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#1e293b', fontSize: 11 },
      padding: [8, 12],
    },
  }

  if (chartType === 'bar') {
    option.grid = { left: '8%', right: needDataZoom ? '12%' : '5%', bottom: needDataZoom ? '25%' : (needRotate ? '20%' : '15%'), top: '10%', containLabel: true }
    if (needDataZoom) {
      option.dataZoom = [{ type: 'slider', show: true, xAxisIndex: 0, start: 0, end: Math.min(50, (20 / dataLength) * 100), bottom: 5, height: 15, borderColor: '#e2e8f0', fillerColor: 'rgba(59, 130, 246, 0.15)', handleStyle: { color: '#3b82f6' } }, { type: 'inside', xAxisIndex: 0, start: 0, end: Math.min(50, (20 / dataLength) * 100) }]
    }
    option.xAxis = {
      type: 'category',
      name: xLabel,
      nameLocation: 'middle',
      nameGap: needRotate ? 25 : 15,
      nameTextStyle: { fontSize: 12, color: '#64748b' },
      axisLabel: {
        rotate: needRotate ? 45 : 0,
        fontSize: 11,
        color: '#64748b',
        interval: dataLength > 10 ? Math.ceil(dataLength / 10) - 1 : 0,
        hideOverlap: true,
      },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
      data: data.map((d: any) => d[xField]),
    }
    option.yAxis = {
      type: 'value',
      name: yLabel,
      nameLocation: 'middle',
      nameGap: 35,
      nameTextStyle: { fontSize: 12, color: '#64748b' },
      axisLabel: { fontSize: 11, color: '#64748b' },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    }
    option.series = [{
      type: 'bar',
      barMaxWidth: 40,
      barMinHeight: 4,
      data: data.map((d: any, idx: number) => ({
        value: d[yField],
        itemStyle: { color: barColors[idx % barColors.length], borderRadius: [4, 4, 0, 0] },
      })),
    }]
  } else if (chartType === 'line') {
    option.grid = { left: '8%', right: '5%', bottom: needRotate ? '20%' : '15%', top: '10%', containLabel: true }
    option.xAxis = {
      type: 'category',
      name: xLabel,
      nameLocation: 'middle',
      nameGap: needRotate ? 25 : 15,
      nameTextStyle: { fontSize: 12, color: '#64748b' },
      axisLabel: {
        rotate: needRotate ? 45 : 0,
        fontSize: 11,
        color: '#64748b',
        interval: dataLength > 10 ? Math.ceil(dataLength / 10) - 1 : 0,
      },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
      boundaryGap: false,
      data: data.map((d: any) => d[xField]),
    }
    option.yAxis = {
      type: 'value',
      name: yLabel,
      nameLocation: 'middle',
      nameGap: 35,
      nameTextStyle: { fontSize: 12, color: '#64748b' },
      axisLabel: { fontSize: 11, color: '#64748b' },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    }
    option.series = [{
      type: 'line',
      data: data.map((d: any) => d[yField]),
      smooth: true,
      showSymbol: dataLength <= 20,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { width: 2, color: lineColor },
      itemStyle: { color: lineColor },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.02)' },
          ],
        },
      },
    }]
  } else if (chartType === 'pie') {
    option.grid = { top: '5%', bottom: '5%', left: '5%', right: '5%' }
    option.tooltip.formatter = '{b}: {c} ({d}%)'
    let pieData = data.map((d: any) => ({ name: d[xField], value: d[yField] }))
    if (pieData.length > 15) {
      pieData.sort((a: any, b: any) => b.value - a.value)
      const top = pieData.slice(0, 10)
      const rest = pieData.slice(10).reduce((s: number, i: any) => s + Number(i.value || 0), 0)
      if (rest > 0) top.push({ name: '其他', value: rest })
      pieData = top
    }
    option.series = [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { show: pieData.length <= 10, fontSize: 11, color: '#64748b', formatter: '{b}: {c}' },
      labelLine: { show: pieData.length <= 10, length: 10, length2: 10, lineStyle: { color: '#e2e8f0' } },
      data: pieData,
    }]
  }

  return option
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
async function copySql(sql: string) {
  const ok = await copyToClipboard(sql)
  ok ? ElMessage.success('SQL已复制到剪贴板') : ElMessage.error('复制失败')
}

// 复制消息内容
async function copyMessageContent(content: string) {
  const ok = await copyToClipboard(content)
  ok ? ElMessage.success('已复制') : ElMessage.error('复制失败')
}

// 处理 ChatMessage 的编辑提交事件
function handleEdit(message: any, content: string) {
  if (!content || !content.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }
  chatStore.sendUserMessage(content.trim())
}

// 重新生成消息
function regenerateMessage(msg: any) {
  if (msg?.question) {
    chatStore.sendUserMessage(msg.question)
    return
  }

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

// 处理欢迎提示点击后的建议词
function handleSuggestion(suggestion: string) {
  inputText.value = suggestion
  handleSend()
}

async function handleNewChat() {
  await chatStore.createNewSession()
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

async function handleSend() {
  const content = inputText.value.trim()
  if (!content) {
    ElMessage.warning('请输入问题')
    return
  }

  isSending.value = true
  try {
    await chatStore.sendUserMessage(content)
    inputText.value = ''
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

// 会话重命名状态
const editingSessionId = ref<string | null>(null)
const renameValue = ref('')

// 在setup阶段同步清空状态（渲染前执行），防止旧消息闪现
chatStore.isLoadingMessages = true
chatStore.messages = []
chatStore.currentSessionId = ''

onMounted(async () => {
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
})

// 监听消息内容变化，在流式输出时通知 ChatPanel 滚动
watch(
  () => messages.value.map((m) => m.content),
  () => {
    nextTick(() => {
      chatPanelRef.value?.scrollToBottom?.()
    })
  },
  { deep: true }
)

// 监听思考过程步骤变化，在执行过程时通知 ChatPanel 滚动
watch(
  () => messages.value.map((m) => m.thinkingSteps?.length || 0),
  () => {
    nextTick(() => {
      chatPanelRef.value?.scrollToBottom?.()
    })
  }
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

    .header-left {
      display: flex;
      align-items: center;
      gap: 10px;

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

  // ChatPanel 撑满剩余空间
  :deep(.chat-panel) {
    flex: 1;
    min-height: 0;
    background: transparent;
    border-radius: 0;
  }

  :deep(.chat-panel .chat-messages) {
    background: #f8fafc;
  }
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
</style>
