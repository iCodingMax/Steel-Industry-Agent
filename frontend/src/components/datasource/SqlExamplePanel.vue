<template>
  <div class="sql-example-panel">
    <!-- 工具栏 -->
    <div class="toolbar">
      <el-button type="primary" size="small" @click="openCreate">
        <el-icon><Plus /></el-icon>
        新增示例
      </el-button>
      <el-select v-model="filterStatus" placeholder="状态" clearable size="small" style="width: 110px" @change="handleFilterChange">
        <el-option label="启用" value="active" />
        <el-option label="停用" value="retired" />
      </el-select>
      <el-input
        v-model="keyword"
        placeholder="搜索标准问题/SQL/备注..."
        size="small"
        clearable
        style="width: 240px"
        @keyup.enter="handleFilterChange"
        @clear="handleFilterChange"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <span class="toolbar-tip">启用的示例将作为 Few-shot 参考注入 NL2SQL Prompt（相似度 ≥ 0.75 才注入）</span>
    </div>

    <!-- 示例列表 -->
    <el-table :data="list" v-loading="loading" size="default" border class="example-table">
      <el-table-column prop="question" label="标准问题" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="question-text">{{ row.question }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="sql" label="SQL摘要" min-width="260">
        <template #default="{ row }">
          <el-tooltip :content="row.sql" placement="top" :show-after="300">
            <span class="sql-brief" @click="viewSql(row)">{{ briefSql(row.sql) }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="备注" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.description || '-' }}</template>
      </el-table-column>
      <el-table-column prop="datasourceName" label="数据源" min-width="120">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" type="info">
            {{ row.datasourceName || `数据源${row.datasourceId}` }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="76" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.status === 'active'"
            :disabled="row.source === 'auto'"
            @change="(val: any) => handleToggleStatus(row, !!val)"
          />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="170" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="handleDryRun(row)" :loading="dryRunningId === row.id">测试</el-button>
          <el-button v-if="row.source === 'manual'" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-state">
          <p>暂无示例SQL</p>
          <el-button type="primary" size="small" @click="openCreate">新增示例</el-button>
        </div>
      </template>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        small
        @current-change="loadList"
        @size-change="handleFilterChange"
      />
    </div>

    <!-- 新增/编辑示例弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingRow ? '编辑示例SQL' : '新增示例SQL'"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="80px" size="default">
        <el-form-item label="数据源" required>
          <el-select
            v-model="form.datasourceId"
            placeholder="请选择数据源"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="ds in datasources"
              :key="ds.id"
              :label="`${ds.name}（${ds.database || ds.type}）`"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标准问题" required>
          <el-input
            v-model="form.question"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            placeholder="录入用户可能提问的标准表述，作为向量召回键。如：近7天高炉炉况评分趋势"
          />
        </el-form-item>
        <el-form-item label="SQL" required>
          <el-input
            v-model="form.sql"
            type="textarea"
            :rows="7"
            class="sql-input"
            placeholder="标准答案SQL（只读SELECT，保存时自动校验语法与只读白名单）"
          />
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            maxlength="500"
            placeholder="适用场景、口径约定等（选填）"
          />
        </el-form-item>
        <el-form-item v-if="!editingRow" label="启用状态">
          <el-switch v-model="form.active" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-alert
          title="示例仅供参考模式注入，LLM 生成时字段以本次 Schema 为准；建议保存后点击「测试」确认结果符合预期"
          type="info"
          show-icon
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- SQL查看弹窗 -->
    <el-dialog v-model="sqlViewVisible" title="标准答案SQL" width="640px">
      <pre class="sql-view">{{ viewingSql }}</pre>
    </el-dialog>

    <!-- 试跑结果弹窗 -->
    <el-dialog v-model="dryRunVisible" title="试跑结果" width="640px">
      <template v-if="dryRunResult">
        <el-alert
          :title="`执行成功，共 ${dryRunResult.rows} 行${dryRunResult.rows >= 1000 ? '（已达行数上限，仅返回前1000行）' : ''}`"
          type="success"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />
        <el-table v-if="dryRunResult.preview" :data="[dryRunResult.preview]" border size="small" max-height="360">
          <el-table-column
            v-for="col in previewColumns"
            :key="col.key"
            :prop="col.key"
            :label="col.label"
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
        <div v-else class="empty-preview">查询结果为空（0 行）</div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import {
  getAllSqlExamples,
  createSqlExample,
  updateSqlExample,
  updateSqlExampleStatus,
  deleteSqlExample,
  dryRunSqlExample,
  getDatasources,
} from '@/api/datasource'

// ===================== 状态定义 =====================
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterStatus = ref('')
const keyword = ref('')

// 数据源下拉（新建示例时选择目标数据源）
const datasources = ref<any[]>([])

const dialogVisible = ref(false)
const editingRow = ref<any>(null)
const saving = ref(false)

const sqlViewVisible = ref(false)
const viewingSql = ref('')

const dryRunVisible = ref(false)
const dryRunningId = ref<number | null>(null)
const dryRunResult = ref<{ rows: number; preview: any; columns: any[] } | null>(null)

const form = ref({
  datasourceId: undefined as number | undefined,
  question: '',
  sql: '',
  description: '',
  active: true,
})

// ===================== 计算属性 =====================
/** 试跑预览列：结果行键 + 字段元信息中文名（comment > name） */
const previewColumns = computed(() => {
  if (!dryRunResult.value?.preview) return []
  const metaMap: Record<string, string> = {}
  for (const c of dryRunResult.value.columns || []) {
    if (c?.name) metaMap[String(c.name).toLowerCase()] = c.comment || c.name
  }
  return Object.keys(dryRunResult.value.preview).map((key) => ({
    key,
    label: metaMap[key.toLowerCase()] || key,
  }))
})

// ===================== 工具函数 =====================
function briefSql(sql: string): string {
  const one = sql.replace(/\s+/g, ' ').trim()
  return one.length > 80 ? one.slice(0, 80) + '...' : one
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 19)
}

function viewSql(row: any) {
  viewingSql.value = row.sql
  sqlViewVisible.value = true
}

// ===================== 数据加载 =====================
async function loadList() {
  loading.value = true
  try {
    const res: any = await getAllSqlExamples({
      status: filterStatus.value || undefined,
      keyword: keyword.value || undefined,
      page: page.value,
      pageSize: pageSize.value,
    })
    if (res.code === 0 && res.data) {
      list.value = res.data.list || []
      total.value = res.data.total || 0
    }
  } catch (e) {
    console.error('加载示例SQL失败', e)
  } finally {
    loading.value = false
  }
}

/** 加载数据源下拉列表（新建示例时选择） */
async function loadDatasources() {
  try {
    const res: any = await getDatasources({ page: 1, pageSize: 100 })
    if (res.code === 0 && res.data) {
      datasources.value = res.data.list || []
    }
  } catch (e) {
    console.error('加载数据源列表失败', e)
  }
}

function handleFilterChange() {
  page.value = 1
  loadList()
}

// ===================== 新增/编辑 =====================
function openCreate() {
  editingRow.value = null
  form.value = { datasourceId: undefined, question: '', sql: '', description: '', active: true }
  if (datasources.value.length === 0) {
    loadDatasources()
  }
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingRow.value = row
  form.value = {
    datasourceId: row.datasourceId,
    question: row.question,
    sql: row.sql,
    description: row.description || '',
    active: row.status === 'active',
  }
  if (datasources.value.length === 0) {
    loadDatasources()
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.datasourceId) {
    ElMessage.warning('请选择数据源')
    return
  }
  if (!form.value.question.trim()) {
    ElMessage.warning('请填写标准问题')
    return
  }
  if (!form.value.sql.trim()) {
    ElMessage.warning('请填写标准答案SQL')
    return
  }
  saving.value = true
  try {
    let res: any
    if (editingRow.value) {
      res = await updateSqlExample(editingRow.value.datasourceId, editingRow.value.id, {
        datasourceId: form.value.datasourceId,
        question: form.value.question,
        sql: form.value.sql,
        description: form.value.description || undefined,
      })
    } else {
      res = await createSqlExample(form.value.datasourceId!, {
        question: form.value.question,
        sql: form.value.sql,
        description: form.value.description || undefined,
        status: form.value.active ? 'active' : 'retired',
      })
    }
    if (res.code === 0) {
      ElMessage.success(editingRow.value ? '示例更新成功' : '示例创建成功')
      dialogVisible.value = false
      await loadList()
    }
  } catch (e) {
    console.error('保存示例失败', e)
  } finally {
    saving.value = false
  }
}

// ===================== 状态/删除 =====================
async function handleToggleStatus(row: any, active: boolean) {
  try {
    const res: any = await updateSqlExampleStatus(row.datasourceId, row.id, active ? 'active' : 'retired')
    if (res.code === 0) {
      row.status = active ? 'active' : 'retired'
      ElMessage.success(active ? '已启用' : '已停用')
    }
  } catch (e) {
    console.error('状态更新失败', e)
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除示例「${row.question.slice(0, 30)}」吗？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    const res: any = await deleteSqlExample(row.datasourceId, row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadList()
    }
  } catch (e) {
    console.error('删除失败', e)
  }
}

// ===================== 试跑 =====================
async function handleDryRun(row: any) {
  dryRunningId.value = row.id
  try {
    const res: any = await dryRunSqlExample(row.datasourceId, row.id)
    if (res.code === 0 && res.data) {
      dryRunResult.value = res.data
      dryRunVisible.value = true
    }
  } catch (e) {
    console.error('试跑失败', e)
  } finally {
    dryRunningId.value = null
  }
}

onMounted(loadList)
</script>

<style lang="scss" scoped>
.sql-example-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px 24px 16px;
  overflow: hidden;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;

  .toolbar-tip {
    margin-left: auto;
    font-size: 12px;
    color: #94a3b8;
  }
}

.example-table {
  flex: 1;
  overflow: auto;

  .question-text {
    color: #1e293b;
    font-weight: 500;
  }

  .sql-brief {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12px;
    color: #475569;
    cursor: pointer;

    &:hover { color: #3b82f6; }
  }
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  flex-shrink: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;

  p {
    margin-bottom: 12px;
    font-size: 13px;
    color: #94a3b8;
  }
}

.sql-input {
  :deep(textarea) {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 13px;
  }
}

.sql-view {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  color: #1e293b;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.empty-preview {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 24px 0;
}
</style>
