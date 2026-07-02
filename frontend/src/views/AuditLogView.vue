<template>
  <div class="audit-log-view">
    <div class="page-header">
      <h2 class="page-title">审计日志</h2>
      <el-button type="primary" @click="handleCollect" :loading="collecting">
        <el-icon><RefreshRight /></el-icon>
        采集日志
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card total">
        <div class="stat-icon">
          <el-icon><Notebook /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">日志总数</div>
        </div>
      </div>
      <div class="stat-card success">
        <div class="stat-icon">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.successCount }}</div>
          <div class="stat-label">成功</div>
        </div>
      </div>
      <div class="stat-card failed">
        <div class="stat-icon">
          <el-icon><CircleClose /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.failedCount }}</div>
          <div class="stat-label">失败</div>
        </div>
      </div>
      <div class="stat-card rate">
        <div class="stat-icon">
          <el-icon><TrendCharts /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.successRate }}%</div>
          <div class="stat-label">成功率</div>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        size="default"
        style="width: 280px"
        @change="handleFilter"
      />
      <el-select v-model="filterAction" placeholder="操作类型" clearable size="default" style="width: 140px" @change="handleFilter">
        <el-option label="创建" value="create" />
        <el-option label="更新" value="update" />
        <el-option label="删除" value="delete" />
        <el-option label="登录" value="login" />
        <el-option label="查询" value="query" />
      </el-select>
      <el-select v-model="filterResourceType" placeholder="资源类型" clearable size="default" style="width: 140px" @change="handleFilter">
        <el-option label="知识库" value="knowledge_base" />
        <el-option label="文档" value="document" />
        <el-option label="数据源" value="datasource" />
        <el-option label="会话" value="session" />
        <el-option label="指标" value="metric" />
        <el-option label="维度" value="dimension" />
        <el-option label="术语" value="term" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="状态" clearable size="default" style="width: 120px" @change="handleFilter">
        <el-option label="成功" value="success" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-input
        v-model="filterKeyword"
        placeholder="搜索用户/资源名/路径"
        clearable
        size="default"
        style="width: 220px"
        @clear="handleFilter"
        @keyup.enter="handleFilter"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
    </div>

    <!-- 日志列表 -->
    <el-table :data="logs" style="width: 100%" v-loading="loading" row-key="id">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand-content">
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">请求路径</span>
                <span class="detail-value">{{ row.path || '-' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">HTTP方法</span>
                <span class="detail-value">
                  <el-tag v-if="row.method" size="small" :type="methodTagType(row.method)">{{ row.method }}</el-tag>
                  <span v-else>-</span>
                </span>
              </div>
              <div class="detail-item">
                <span class="detail-label">IP地址</span>
                <span class="detail-value">{{ row.ipAddress || '-' }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">操作用户ID</span>
                <span class="detail-value">{{ row.userId || '-' }}</span>
              </div>
            </div>
            <div v-if="row.errorMessage" class="detail-error">
              <span class="detail-label">错误信息</span>
              <span class="detail-value error-text">{{ row.errorMessage }}</span>
            </div>
            <div v-if="row.detail && Object.keys(row.detail).length > 0" class="detail-json">
              <span class="detail-label">操作详情</span>
              <pre class="json-content">{{ JSON.stringify(row.detail, null, 2) }}</pre>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.createdAt) }}
        </template>
      </el-table-column>
      <el-table-column prop="username" label="操作人" width="120">
        <template #default="{ row }">
          {{ row.username || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="action" label="操作" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="actionTagType(row.action)">{{ actionText[row.action] || row.action }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="resourceType" label="资源类型" width="120">
        <template #default="{ row }">
          {{ resourceTypeText[row.resourceType] || row.resourceType }}
        </template>
      </el-table-column>
      <el-table-column prop="resourceName" label="资源名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'success' ? 'success' : 'danger'" effect="plain">
            {{ row.status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="handlePageChange"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Notebook,
  CircleCheck,
  CircleClose,
  TrendCharts,
  RefreshRight,
  Search,
} from '@element-plus/icons-vue'
import { getAuditStats, getAuditLogs, collectAuditLogs, type AuditLogStats, type AuditLogItem } from '@/api/audit_log'

const loading = ref(false)
const collecting = ref(false)
const logs = ref<AuditLogItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const stats = reactive<AuditLogStats>({
  total: 0,
  successCount: 0,
  failedCount: 0,
  successRate: 0,
  actionStats: [],
  resourceStats: [],
})

// 筛选条件
const dateRange = ref<string[]>([])
const filterAction = ref('')
const filterResourceType = ref('')
const filterStatus = ref('')
const filterKeyword = ref('')

// 文本映射
const actionText: Record<string, string> = {
  create: '创建',
  update: '更新',
  delete: '删除',
  login: '登录',
  query: '查询',
}

const resourceTypeText: Record<string, string> = {
  knowledge_base: '知识库',
  document: '文档',
  datasource: '数据源',
  session: '会话',
  metric: '指标',
  dimension: '维度',
  term: '术语',
  llm_config: 'LLM配置',
}

const actionTagType = (action: string) => {
  const map: Record<string, string> = { create: 'success', update: 'warning', delete: 'danger', login: 'info', query: '' }
  return map[action] || ''
}

const methodTagType = (method: string) => {
  const map: Record<string, string> = { GET: 'info', POST: 'success', PUT: 'warning', DELETE: 'danger' }
  return map[method] || ''
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function loadStats() {
  try {
    const params: any = {}
    if (dateRange.value?.length === 2) {
      params.startDate = dateRange.value[0]
      params.endDate = dateRange.value[1]
    }
    const res = await getAuditStats(params) as any
    if (res.code === 0 && res.data) {
      Object.assign(stats, res.data)
    }
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

async function loadLogs() {
  loading.value = true
  try {
    const params: any = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (filterAction.value) params.action = filterAction.value
    if (filterResourceType.value) params.resourceType = filterResourceType.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (dateRange.value?.length === 2) {
      params.startDate = dateRange.value[0]
      params.endDate = dateRange.value[1]
    }
    const res = await getAuditLogs(params) as any
    if (res.code === 0 && res.data) {
      logs.value = res.data.list || []
      total.value = res.data.total || 0
    }
  } catch (e) {
    console.error('加载审计日志失败', e)
  } finally {
    loading.value = false
  }
}

function handleFilter() {
  currentPage.value = 1
  loadStats()
  loadLogs()
}

function handlePageChange() {
  loadLogs()
}

async function handleCollect() {
  collecting.value = true
  try {
    const res = await collectAuditLogs() as any
    if (res.code === 0) {
      ElMessage.success(res.message || '采集完成')
      await loadStats()
      await loadLogs()
    }
  } catch (e) {
    ElMessage.error('采集失败')
  } finally {
    collecting.value = false
  }
}

onMounted(() => {
  loadStats()
  loadLogs()
})
</script>

<style lang="scss" scoped>
.audit-log-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
  margin: 0;
}

// 统计卡片
.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border: 1px solid $card-border;
  border-radius: $card-radius;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.2s;

  &:hover {
    box-shadow: $card-shadow;
    transform: translateY(-2px);
  }

  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;

    .el-icon {
      font-size: 24px;
    }
  }

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.2;
  }

  .stat-label {
    font-size: 13px;
    color: $text-secondary;
    margin-top: 4px;
  }

  &.total .stat-icon {
    background: rgba(59, 130, 246, 0.1);
    .el-icon { color: #3b82f6; }
  }
  &.total .stat-value { color: #3b82f6; }

  &.success .stat-icon {
    background: rgba(16, 185, 129, 0.1);
    .el-icon { color: #10b981; }
  }
  &.success .stat-value { color: #10b981; }

  &.failed .stat-icon {
    background: rgba(239, 68, 68, 0.1);
    .el-icon { color: #ef4444; }
  }
  &.failed .stat-value { color: #ef4444; }

  &.rate .stat-icon {
    background: rgba(245, 158, 11, 0.1);
    .el-icon { color: #f59e0b; }
  }
  &.rate .stat-value { color: #f59e0b; }
}

// 筛选栏
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  padding: 16px;
  background: #fff;
  border-radius: $card-radius;
  border: 1px solid $card-border;
}

// 展开详情
.expand-content {
  padding: 16px 24px;
  background-color: #f8fafc;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px 24px;
  margin-bottom: 12px;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-label {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
  min-width: 80px;
}

.detail-value {
  font-size: 13px;
  color: #1e293b;
}

.detail-error {
  margin-bottom: 12px;

  .error-text {
    color: #ef4444;
  }
}

.detail-json {
  .json-content {
    margin-top: 8px;
    padding: 12px;
    background: #0f172a;
    color: #e2e8f0;
    border-radius: 8px;
    font-size: 12px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    line-height: 1.6;
    overflow-x: auto;
  }
}

// 分页
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0;
}
</style>
