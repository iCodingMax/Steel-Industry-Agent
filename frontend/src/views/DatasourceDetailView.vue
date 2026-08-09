<template>
  <div class="datasource-detail-view">
    <div class="detail-header">
      <el-button @click="goBack" class="back-btn">
        <el-icon><ArrowLeft /></el-icon>
        返回列表
      </el-button>
      <div class="header-info" v-if="datasource">
        <el-tag :type="dbTypeColor[datasource.type] || 'primary'" effect="plain" size="small">
          {{ datasource.type?.toUpperCase() }}
        </el-tag>
        <h2 class="detail-title">{{ datasource.name }}</h2>
        <span class="detail-sub">{{ datasource.host }}:{{ datasource.port }} / {{ datasource.database }}</span>
      </div>
      <div class="header-actions" v-if="datasource">
        <el-button size="small" @click="handleSync" :loading="syncing">
          <el-icon><Refresh /></el-icon>
          同步Schema
        </el-button>
      </div>
    </div>

    <div class="detail-body" v-loading="loading">
      <!-- 左侧：数据表列表 -->
      <div class="table-sidebar">
        <div class="sidebar-header">
          <h3 class="sidebar-title">数据表 ({{ tables.length }})</h3>
          <el-input v-model="tableSearch" placeholder="搜索表名..." size="small" clearable style="width: 160px">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        <div class="table-list">
          <div
            v-for="table in filteredTables"
            :key="table.id"
            class="table-item"
            :class="{ active: selectedTable?.id === table.id }"
            @click="selectTable(table)"
          >
            <svg class="table-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/>
            </svg>
            <div class="table-info">
              <div class="table-name">{{ table.tableName }}</div>
              <div class="table-comment" v-if="table.tableComment && table.tableComment !== table.tableName">{{ table.tableComment }}</div>
            </div>
            <el-tag size="small" type="info" effect="plain">{{ (table.columns || []).length }}列</el-tag>
          </div>
          <div v-if="tables.length === 0" class="empty-state">
            <p>暂无表结构数据</p>
            <el-button type="primary" size="small" @click="handleSync">同步Schema</el-button>
          </div>
        </div>
      </div>

      <!-- 右侧：字段结构详情 -->
      <div class="table-detail">
        <div v-if="!selectedTable" class="detail-empty">
          <svg viewBox="0 0 64 64" fill="none" style="width:64px;height:64px;opacity:0.3">
            <rect x="8" y="8" width="48" height="48" rx="4" stroke="#94a3b8" stroke-width="2"/>
            <line x1="8" y1="22" x2="56" y2="22" stroke="#94a3b8" stroke-width="2"/>
            <line x1="8" y1="36" x2="56" y2="36" stroke="#94a3b8" stroke-width="2"/>
            <line x1="8" y1="50" x2="56" y2="50" stroke="#94a3b8" stroke-width="2"/>
            <line x1="24" y1="8" x2="24" y2="56" stroke="#94a3b8" stroke-width="2"/>
          </svg>
          <p>请从左侧选择一张数据表查看字段结构</p>
        </div>
        <template v-else>
          <div class="detail-content-header">
            <div class="content-title-area">
              <h3 class="content-title">{{ selectedTable.tableName }}</h3>
              <span v-if="selectedTable.tableComment && selectedTable.tableComment !== selectedTable.tableName" class="content-comment">{{ selectedTable.tableComment }}</span>
            </div>
            <el-tag type="info" effect="plain">{{ (selectedTable.columns || []).length }} 个字段</el-tag>
          </div>
          <el-table :data="selectedTable.columns || []" style="width: 100%" border size="default" class="column-table">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="name" label="字段名称" min-width="160">
              <template #default="{ row }">
                <span class="col-name">{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="字段类型" width="160">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="可空" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.nullable !== undefined" :type="row.nullable ? 'info' : 'danger'" size="small" effect="plain">
                  {{ row.nullable ? 'YES' : 'NO' }}
                </el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="主键" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.primaryKey" type="warning" size="small" effect="plain">PK</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="default" label="默认值" width="140">
              <template #default="{ row }">
                <span class="col-default">{{ row.default ?? '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="comment" label="备注" min-width="200">
              <template #default="{ row }">
                <span class="col-comment">{{ row.comment || '-' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh, Search } from '@element-plus/icons-vue'
import { getDatasource, getSchema, syncSchema } from '@/api/datasource'

const route = useRoute()
const router = useRouter()

const dsId = Number(route.params.id)
const loading = ref(false)
const syncing = ref(false)
const datasource = ref<any>(null)
const tables = ref<any[]>([])
const selectedTable = ref<any>(null)
const tableSearch = ref('')

const dbTypeColor: Record<string, string> = {
  mysql: 'primary',
  postgresql: 'success',
  sqlserver: 'warning',
}

const filteredTables = computed(() => {
  if (!tableSearch.value) return tables.value
  const kw = tableSearch.value.toLowerCase()
  return tables.value.filter((t) =>
    t.tableName.toLowerCase().includes(kw) ||
    (t.tableComment && t.tableComment.toLowerCase().includes(kw))
  )
})

function selectTable(table: any) {
  selectedTable.value = table
}

function goBack() {
  router.push('/data-config')
}

async function loadDatasource() {
  try {
    const res: any = await getDatasource(dsId)
    if (res.code === 0 && res.data) {
      datasource.value = res.data
    }
  } catch (e) {
    console.error('加载数据源详情失败', e)
  }
}

async function loadSchema() {
  loading.value = true
  try {
    const res: any = await getSchema(dsId)
    if (res.code === 0 && res.data) {
      tables.value = res.data
      if (tables.value.length > 0 && !selectedTable.value) {
        selectedTable.value = tables.value[0]
      }
    }
  } catch (e) {
    console.error('加载Schema失败', e)
  } finally {
    loading.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const res: any = await syncSchema(dsId)
    if (res.code === 0) {
      const { total = 0, added = 0, removed = 0, updated = 0 } = res.data || {}
      if (added === 0 && removed === 0 && updated === 0) {
        ElMessage.success(`Schema已是最新，共 ${total} 张表`)
      } else {
        ElMessage.success(`同步完成，共 ${total} 张表（新增 ${added}，移除 ${removed}，更新 ${updated}）`)
      }
      await loadSchema()
    }
  } catch (e: any) {
    console.error('Schema同步失败', e)
  } finally {
    syncing.value = false
  }
}

onMounted(async () => {
  await loadDatasource()
  await loadSchema()
})
</script>

<style lang="scss" scoped>
.datasource-detail-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  flex-shrink: 0;

  .back-btn {
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .header-info {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
  }

  .detail-title {
    font-size: 18px;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
  }

  .detail-sub {
    font-size: 13px;
    color: #64748b;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }
}

.detail-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.table-sidebar {
  width: 320px;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;

  .sidebar-header {
    padding: 16px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .sidebar-title {
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
    white-space: nowrap;
  }

  .table-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .table-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background-color: #f1f5f9;
    }

    &.active {
      background-color: #eff6ff;
      border-left: 3px solid #3b82f6;
    }

    .table-icon {
      width: 16px;
      height: 16px;
      color: #64748b;
      flex-shrink: 0;
    }

    .table-info {
      flex: 1;
      min-width: 0;
    }

    .table-name {
      font-size: 13px;
      font-weight: 500;
      color: #1e293b;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .table-comment {
      font-size: 11px;
      color: #94a3b8;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-top: 2px;
    }
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    color: #94a3b8;

    p {
      margin-bottom: 12px;
      font-size: 13px;
    }
  }
}

.table-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f8fafc;

  .detail-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #94a3b8;

    p {
      margin-top: 16px;
      font-size: 14px;
    }
  }

  .detail-content-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: #fff;
    border-bottom: 1px solid #e2e8f0;

    .content-title-area {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .content-title {
      font-size: 16px;
      font-weight: 600;
      color: #1e293b;
      margin: 0;
    }

    .content-comment {
      font-size: 13px;
      color: #64748b;
    }
  }

  .column-table {
    margin: 16px 24px;
    border-radius: 8px;
    overflow: hidden;

    .col-name {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-weight: 600;
      color: #1e293b;
    }

    .col-default {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 12px;
      color: #64748b;
    }

    .col-comment {
      font-size: 13px;
      color: #475569;
    }
  }
}
</style>
