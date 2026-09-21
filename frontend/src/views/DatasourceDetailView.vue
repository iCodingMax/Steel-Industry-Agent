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

    <el-tabs v-model="activeTab" class="detail-tabs">
      <!-- Tab 1 表结构（字段备注双列） -->
      <el-tab-pane label="表结构" name="schema">
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
                <div class="header-right-area">
                  <el-button
                    v-if="dirtyCount > 0"
                    type="primary"
                    size="small"
                    @click="saveRemarks"
                    :loading="savingRemarks"
                  >
                    保存字段备注({{ dirtyCount }})
                  </el-button>
                  <el-tag type="info" effect="plain">{{ (selectedTable.columns || []).length }} 个字段</el-tag>
                </div>
              </div>
              <el-alert
                v-if="remarkEditedTip"
                :title="remarkEditedTip"
                type="info"
                show-icon
                :closable="true"
                class="remark-tip"
              />
              <el-table :data="selectedTable.columns || []" style="width: 100%" border size="default" class="column-table" max-height="100%">
                <el-table-column type="index" label="#" width="50" />
                <el-table-column prop="name" label="字段名称" min-width="150">
                  <template #default="{ row }">
                    <span class="col-name">{{ row.name }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="type" label="字段类型" width="140">
                  <template #default="{ row }">
                    <el-tag size="small" effect="plain">{{ row.type }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="可空" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.nullable !== undefined" :type="row.nullable ? 'info' : 'danger'" size="small" effect="plain">
                      {{ row.nullable ? 'YES' : 'NO' }}
                    </el-tag>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column label="主键" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.primaryKey" type="warning" size="small" effect="plain">PK</el-tag>
                    <span v-else>-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="comment" label="原字段备注" min-width="150" show-overflow-tooltip>
                  <template #default="{ row }">
                    <span class="col-origin-comment">{{ row.comment || '-' }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="字段备注" min-width="240">
                  <template #header>
                    <span class="remark-header">
                      字段备注
                      <el-tooltip content="LLM 实际消费的业务语义；初始同步取原字段备注，可编辑。保存后自动重建向量索引" placement="top">
                        <el-icon class="remark-help"><QuestionFilled /></el-icon>
                      </el-tooltip>
                    </span>
                  </template>
                  <template #default="{ row }">
                    <div class="remark-cell">
                      <el-input
                        v-model="remarkDrafts[row.name]"
                        size="small"
                        :placeholder="row.comment || '填写业务语义备注'"
                        @keydown.enter.prevent
                      />
                      <el-button
                        v-if="remarkDrafts[row.name] !== undefined && remarkDrafts[row.name] !== (row.comment || '')"
                        link
                        type="info"
                        size="small"
                        title="重置为原字段备注"
                        @click="resetRemark(row)"
                      >
                        重置
                      </el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </template>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 2 表关系 -->
      <el-tab-pane name="relations" lazy>
        <template #label>
          <el-badge :value="inactiveCount" :hidden="inactiveCount === 0" :max="99" class="tab-badge">
            表关系
          </el-badge>
        </template>
        <RelationPanel :ds-id="dsId" @stats-change="onRelationStats" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh, Search, QuestionFilled } from '@element-plus/icons-vue'
import {
  getDatasource,
  getSchema,
  syncSchema,
  updateColumnRemarks,
} from '@/api/datasource'
import RelationPanel from '@/components/datasource/RelationPanel.vue'

const route = useRoute()
const router = useRouter()

const dsId = Number(route.params.id)
const loading = ref(false)
const syncing = ref(false)
const datasource = ref<any>(null)
const tables = ref<any[]>([])
const selectedTable = ref<any>(null)
const tableSearch = ref('')

const activeTab = ref('schema')
const inactiveCount = ref(0)

// 字段备注双列编辑（V2.1：remark 可编辑，comment 只读镜像）
const remarkDrafts = ref<Record<string, string>>({})
const remarkOrigins = ref<Record<string, string>>({})
const savingRemarks = ref(false)

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

/** 脏字段列表（草稿与已保存 remark 不一致的） */
const dirtyNames = computed(() => {
  const dirty: string[] = []
  for (const col of selectedTable.value?.columns || []) {
    const draft = remarkDrafts.value[col.name]
    if (draft !== undefined && draft !== (remarkOrigins.value[col.name] ?? '')) {
      dirty.push(col.name)
    }
  }
  return dirty
})

const dirtyCount = computed(() => dirtyNames.value.length)

/** 同步冲突提示（原注释变化但人工备注被保留） */
const remarkEditedTip = ref('')

function selectTable(table: any) {
  selectedTable.value = table
  initRemarkDrafts(table)
}

function initRemarkDrafts(table: any) {
  const drafts: Record<string, string> = {}
  const origins: Record<string, string> = {}
  for (const col of table?.columns || []) {
    origins[col.name] = typeof col.remark === 'string' ? col.remark : ''
    drafts[col.name] = origins[col.name]
  }
  remarkDrafts.value = drafts
  remarkOrigins.value = origins
}

/** 重置为原字段备注（服务端语义：remark=comment 且 remark_edited=False） */
function resetRemark(row: any) {
  remarkDrafts.value[row.name] = row.comment || ''
}

async function saveRemarks() {
  if (!selectedTable.value || dirtyCount.value === 0) return
  savingRemarks.value = true
  try {
    const remarks = dirtyNames.value.map((name) => {
      const col = (selectedTable.value.columns || []).find((c: any) => c.name === name)
      const draft = remarkDrafts.value[name] || ''
      // 草稿与原字段备注一致时走重置语义（remark_edited=False，后续同步跟随 comment 刷新）
      const reset = !!col && draft === (col.comment || '')
      return { name, remark: draft, reset }
    })
    const res: any = await updateColumnRemarks(dsId, selectedTable.value.tableName, remarks)
    if (res.code === 0) {
      const { updated = 0, embedded = false } = res.data || {}
      // 同步本地数据，避免重新拉取
      for (const item of remarks) {
        const col = (selectedTable.value.columns || []).find((c: any) => c.name === item.name)
        if (col) {
          col.remark = item.remark
          col.remark_edited = !item.reset
        }
      }
      initRemarkDrafts(selectedTable.value)
      ElMessage.success(`字段备注已保存（${updated} 个字段）${embedded ? '，向量索引已更新' : '（向量索引重建中）'}`)
    }
  } catch (e) {
    console.error('保存字段备注失败', e)
  } finally {
    savingRemarks.value = false
  }
}

function onRelationStats(stats: { inactive: number }) {
  inactiveCount.value = stats.inactive
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
        selectTable(tables.value[0])
      } else if (selectedTable.value) {
        // 同步后表对象已替换，重新绑定并保持选中表
        const fresh = tables.value.find((t) => t.tableName === selectedTable.value?.tableName) || tables.value[0]
        selectTable(fresh)
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
      const { total = 0, added = 0, removed = 0, updated = 0, remarkConflicts = 0 } = res.data || {}
      if (added === 0 && removed === 0 && updated === 0) {
        ElMessage.success(`Schema已是最新，共 ${total} 张表`)
      } else {
        ElMessage.success(`同步完成，共 ${total} 张表（新增 ${added}，移除 ${removed}，更新 ${updated}）`)
      }
      if (remarkConflicts > 0) {
        remarkEditedTip.value = `本次同步有 ${remarkConflicts} 个字段的原始注释已变化，但您编辑过的字段备注已保留；如需跟随新注释，请在"字段备注"列点击"重置"`
      } else {
        remarkEditedTip.value = ''
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
  overflow: hidden;
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

.detail-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
  padding: 0 24px;

  :deep(.el-tabs__header) {
    flex-shrink: 0;
    margin-bottom: 0;
  }

  :deep(.el-tabs__content) {
    flex: 1;
    overflow: hidden;
  }

  :deep(.el-tab-pane) {
    height: 100%;
  }

  .tab-badge {
    :deep(.el-badge__content) {
      top: 8px;
      right: -14px;
    }
  }
}

.detail-body {
  height: 100%;
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

    .header-right-area {
      display: flex;
      align-items: center;
      gap: 10px;
    }
  }

  .remark-tip {
    margin: 12px 24px 0;
  }

  .column-table {
    margin: 16px 24px;
    border-radius: 8px;
    overflow: hidden;
    flex: 1;

    .col-name {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-weight: 600;
      color: #1e293b;
    }

    .col-origin-comment {
      font-size: 13px;
      color: #94a3b8;
    }

    .remark-header {
      display: inline-flex;
      align-items: center;
      gap: 4px;

      .remark-help {
        color: #94a3b8;
        cursor: help;
      }
    }

    .remark-cell {
      display: flex;
      align-items: center;
      gap: 4px;

      :deep(.el-input) {
        // 输入框固定合理宽度，避免撑满整列把"重置"按钮挤到最右
        flex: 0 0 200px;
        width: 200px;
      }
    }
  }
}
</style>
