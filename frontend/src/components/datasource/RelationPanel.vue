<template>
  <div class="relation-panel">
    <!-- 顶部统计条：状态常显（方案 4.4.1，三视图共享） -->
    <div class="stats-bar">
      <span class="stat-item">
        已生效 <b class="num active">{{ stats.active }}</b> 条
        <span class="sub">（外键 {{ stats.activeFk }} / 人工 {{ stats.activeManual }}）</span>
      </span>
      <el-divider direction="vertical" />
      <span class="stat-item">
        待确认 <b class="num inactive">{{ stats.inactive }}</b> 条
      </span>
      <el-divider direction="vertical" />
      <span class="stat-item">
        已忽略 <b class="num ignored">{{ stats.ignored }}</b> 条
      </span>
      <span class="stat-tip">已生效关系将作为 NL2SQL 联表查询的 JOIN 白名单</span>
    </div>

    <!-- 视图切换 + 工具栏（方案 4.4.2 三视图：列表/画布/总览） -->
    <div class="toolbar">
      <el-radio-group v-model="viewMode" size="small">
        <el-radio-button value="list">
          <el-icon><List /></el-icon>
          列表
        </el-radio-button>
        <el-radio-button value="canvas">
          <el-icon><Share /></el-icon>
          画布
        </el-radio-button>
        <el-radio-button value="overview">
          <el-icon><DataBoard /></el-icon>
          总览
        </el-radio-button>
      </el-radio-group>

      <!-- 列表模式专属工具栏 -->
      <template v-if="viewMode === 'list'">
        <el-select v-model="filterStatus" placeholder="状态" clearable size="small" style="width: 110px" @change="handleFilterChange">
          <el-option label="已生效" value="active" />
          <el-option label="待确认" value="inactive" />
          <el-option label="已忽略" value="ignored" />
        </el-select>
        <el-select v-model="filterSource" placeholder="来源" clearable size="small" style="width: 110px" @change="handleFilterChange">
          <el-option label="外键" value="foreign_key" />
          <el-option label="同名推荐" value="auto_guess" />
          <el-option label="人工" value="manual" />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索表名/字段名/描述..."
          size="small"
          clearable
          style="width: 220px"
          @keyup.enter="handleFilterChange"
          @clear="handleFilterChange"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </template>

      <div class="toolbar-spacer" />
      <el-button size="small" @click="handleCollect" :loading="collecting">
        <el-icon><MagicStick /></el-icon>
        采集关系
      </el-button>
      <el-button v-if="viewMode === 'list'" type="primary" size="small" @click="openCreate">
        <el-icon><Plus /></el-icon>
        新建关系
      </el-button>
    </div>

    <!-- ==================== 视图 1：列表模式（批量确认主力） ==================== -->
    <template v-if="viewMode === 'list'">
    <!-- 批量操作栏 -->
    <div class="batch-bar" v-if="selectedRows.length > 0">
      <span>已选 <b>{{ selectedRows.length }}</b> 条</span>
      <el-button size="small" type="success" plain @click="handleBatchConfirm" :loading="batchLoading">批量确认</el-button>
      <el-button size="small" warning plain @click="handleBatchIgnore" :loading="batchLoading">批量忽略</el-button>
      <el-button size="small" plain @click="handleBatchProbe" :loading="batchProbing">批量探测</el-button>
    </div>

    <!-- 关系列表 -->
    <el-table
      ref="tableRef"
      :data="list"
      v-loading="loading"
      size="default"
      border
      class="relation-table"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="42" :selectable="isSelectable" />
      <el-table-column label="关联字段" min-width="280">
        <template #default="{ row }">
          <div class="pair-line">
            <span class="pair-table">{{ row.leftTable }}</span>
            <span class="pair-col">.{{ row.leftColumn }}</span>
            <el-icon class="pair-arrow"><Right /></el-icon>
            <span class="pair-table">{{ row.rightTable }}</span>
            <span class="pair-col">.{{ row.rightColumn }}</span>
            <el-tag v-if="row.relationGroup" size="small" type="info" effect="plain">复合键</el-tag>
          </div>
          <div v-if="isBlacklisted(row)" class="risk-line">⚠ 命中黑名单字段（{{ blacklistHit(row) }}），不建议用于关联</div>
        </template>
      </el-table-column>
      <el-table-column label="类型匹配" width="150">
        <template #default="{ row }">
          <span v-if="typeText(row)" class="type-text" :class="{ mismatch: isTypeMismatch(row) }">{{ typeText(row) }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="cardinality" label="基数" width="70" align="center" />
      <el-table-column label="JOIN" width="76" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" :type="row.joinType === 'left' ? 'warning' : 'info'">
            {{ (row.joinType || 'inner').toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="plain" :type="sourceTagType(row.source)">{{ sourceText(row.source) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="84" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="light" :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="探测结论" width="130" align="center">
        <template #default="{ row }">
          <span v-if="probeFactor(row) !== null" :class="probeClass(probeFactor(row)!)">
            {{ probeFactor(row) }}x {{ probeFactor(row)! <= 1.05 ? '✓ 无放大' : '⚠ 数据放大' }}
          </span>
          <span v-else class="probe-none">未探测</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" align="center" fixed="right" class-name="op-col">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="handleProbe(row)" :loading="probingId === row.id">探测</el-button>
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status === 'inactive'" link type="success" size="small" @click="handleConfirm(row)">确认</el-button>
          <el-button v-if="row.status !== 'ignored'" link type="warning" size="small" @click="handleIgnore(row)">忽略</el-button>
          <el-button v-if="row.source !== 'foreign_key'" link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-state">
          <p>暂无表关系数据</p>
          <el-button type="primary" size="small" @click="handleCollect" :loading="collecting">采集关系</el-button>
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
    </template>

    <!-- ==================== 视图 2：画布模式（拓扑探索 + 手工连线） ==================== -->
    <div v-else-if="viewMode === 'canvas'" class="view-container">
      <TableRelationCanvas :ds-id="dsId" :relation-graph="graphAgg" @refresh="onChildRefresh" />
    </div>

    <!-- ==================== 视图 3：总览模式（全库宏观体检，只读） ==================== -->
    <div v-else class="view-container">
      <RelationOverviewGraph :ds-id="dsId" :relation-graph="graphAgg" />
    </div>

    <!-- 新建/编辑关系弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingRow ? '编辑表关系' : '新建表关系'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="80px" size="default">
        <template v-if="!editingRow">
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="左表" required>
                <el-select v-model="form.leftTable" placeholder="选择左表" filterable style="width: 100%" @change="form.leftColumn = ''">
                  <el-option v-for="n in nodes" :key="n.id" :label="n.label" :value="n.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="左字段" required>
                <el-select v-model="form.leftColumn" placeholder="选择字段" filterable style="width: 100%" :disabled="!form.leftTable">
                  <el-option v-for="c in columnsOf(form.leftTable)" :key="c.name" :label="`${c.name} (${c.type})`" :value="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="12">
            <el-col :span="12">
              <el-form-item label="右表" required>
                <el-select v-model="form.rightTable" placeholder="选择右表" filterable style="width: 100%" @change="form.rightColumn = ''">
                  <el-option v-for="n in nodes" :key="n.id" :label="n.label" :value="n.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="右字段" required>
                <el-select v-model="form.rightColumn" placeholder="选择字段" filterable style="width: 100%" :disabled="!form.rightTable">
                  <el-option v-for="c in columnsOf(form.rightTable)" :key="c.name" :label="`${c.name} (${c.type})`" :value="c.name" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </template>
        <div v-else class="endpoints-view">
          <span class="pair-table">{{ editingRow.leftTable }}.{{ editingRow.leftColumn }}</span>
          <el-icon><Right /></el-icon>
          <span class="pair-table">{{ editingRow.rightTable }}.{{ editingRow.rightColumn }}</span>
        </div>
        <el-form-item label="基数">
          <el-radio-group v-model="form.cardinality">
            <el-radio value="1:1">1:1</el-radio>
            <el-radio value="1:N">1:N</el-radio>
            <el-radio value="N:1">N:1</el-radio>
            <el-radio value="M:N">M:N</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="JOIN类型">
          <el-radio-group v-model="form.joinType">
            <el-radio value="inner">INNER</el-radio>
            <el-radio value="left">LEFT</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.relationDesc" placeholder="如：一炉次一次打分" maxlength="255" />
        </el-form-item>
        <el-alert
          v-if="probeSuggestion"
          :title="probeSuggestion"
          :type="probeSuggestionLevel"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          v-if="!editingRow && form.leftTable && form.leftColumn && form.rightTable && form.rightColumn"
          @click="handleDialogProbe"
          :loading="dialogProbing"
        >
          SQL 探测
        </el-button>
        <el-button type="primary" @click="handleSave" :loading="saving" :disabled="probeWarningBlock">
          {{ editingRow ? '保存' : '确认并生效' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Right, MagicStick, List, Share, DataBoard } from '@element-plus/icons-vue'
import TableRelationCanvas from '@/components/datasource/TableRelationCanvas.vue'
import RelationOverviewGraph from '@/components/datasource/RelationOverviewGraph.vue'
import {
  getRelations,
  createRelation,
  updateRelation,
  deleteRelation,
  batchConfirmRelations,
  batchIgnoreRelations,
  probeRelation,
  collectRelations,
  getRelationGraph,
} from '@/api/datasource'

const props = defineProps<{ dsId: number }>()
const emit = defineEmits<{ (e: 'stats-change', stats: { inactive: number }): void }>()

// ===================== 状态定义 =====================
// 三视图切换（方案 4.4.2：列表默认 / 画布 / 总览）
const viewMode = ref<'list' | 'canvas' | 'overview'>('list')
// 聚合数据（三视图共享一份，切换零请求）
const graphAgg = ref<{ nodes: any[]; edges: any[]; stats?: any } | null>(null)
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterStatus = ref('')
const filterSource = ref('')
const keyword = ref('')

const selectedRows = ref<any[]>([])
const batchLoading = ref(false)
const batchProbing = ref(false)

const collecting = ref(false)
const probingId = ref<number | null>(null)

const dialogVisible = ref(false)
const editingRow = ref<any>(null)
const saving = ref(false)
const dialogProbing = ref(false)
const probeSuggestion = ref('')
const probeSuggestionLevel = ref<'success' | 'warning' | 'error'>('success')

const form = ref({
  leftTable: '',
  leftColumn: '',
  rightTable: '',
  rightColumn: '',
  cardinality: '1:1',
  joinType: 'inner',
  relationDesc: '',
})

// 图聚合数据（nodes 用于表/字段下拉与类型匹配，edges 用于统计）
const nodes = ref<any[]>([])
const stats = ref({ active: 0, inactive: 0, ignored: 0, activeFk: 0, activeManual: 0 })

// 黑名单字段（命中候选不可勾选确认，方案 4.4.3）
const BLACKLIST_FIELDS = ['IS_DELETED', 'DELETED', 'CREATED_AT', 'UPDATED_AT', 'CREATE_TIME', 'UPDATE_TIME']

// ===================== 计算属性 =====================
/** 字段类型映射：`${table}.${column}` -> type */
const colTypeMap = computed(() => {
  const map: Record<string, string> = {}
  for (const n of nodes.value) {
    for (const c of n.columns || []) {
      map[`${n.id}.${c.name}`] = String(c.type || '')
    }
  }
  return map
})

/** 探测放大系数 > 1.5 时阻断保存（需先调整基数或取消） */
const probeWarningBlock = computed(() => {
  if (!editingRow.value && probeSuggestionLevel.value === 'error') return true
  return false
})

// ===================== 工具函数 =====================
function typeText(row: any): string {
  const lt = colTypeMap.value[`${row.leftTable}.${row.leftColumn}`]
  const rt = colTypeMap.value[`${row.rightTable}.${row.rightColumn}`]
  if (!lt && !rt) return ''
  return `${lt || '?'} ↔ ${rt || '?'}`
}

function isTypeMismatch(row: any): boolean {
  const lt = colTypeMap.value[`${row.leftTable}.${row.leftColumn}`]
  const rt = colTypeMap.value[`${row.rightTable}.${row.rightColumn}`]
  return !!lt && !!rt && lt.toLowerCase() !== rt.toLowerCase()
}

function isBlacklisted(row: any): boolean {
  return BLACKLIST_FIELDS.some(
    (f) => row.leftColumn?.toUpperCase() === f || row.rightColumn?.toUpperCase() === f
  )
}

function blacklistHit(row: any): string {
  return (
    BLACKLIST_FIELDS.find(
      (f) => row.leftColumn?.toUpperCase() === f || row.rightColumn?.toUpperCase() === f
    ) || ''
  )
}

function isSelectable(row: any): boolean {
  // 黑名单候选默认不可勾选确认
  return !(isBlacklisted(row) && row.status === 'inactive')
}

function probeFactor(row: any): number | null {
  const p = row.probe
  if (p && typeof p === 'object' && typeof p.factor === 'number') {
    return Math.round(p.factor * 10) / 10
  }
  return null
}

function probeClass(factor: number): string {
  if (factor <= 1.05) return 'probe-ok'
  if (factor > 1.5) return 'probe-bad'
  return 'probe-warn'
}

function sourceText(s: string): string {
  return { foreign_key: '外键', auto_guess: '同名推荐', manual: '人工' }[s] || s
}

function sourceTagType(s: string): 'primary' | 'info' | 'success' {
  return ({ foreign_key: 'primary', auto_guess: 'info', manual: 'success' } as any)[s] || 'info'
}

function statusText(s: string): string {
  return { active: '已生效', inactive: '待确认', ignored: '已忽略' }[s] || s
}

function statusTagType(s: string): 'success' | 'warning' | 'info' {
  return ({ active: 'success', inactive: 'warning', ignored: 'info' } as any)[s] || 'info'
}

function columnsOf(tableName: string) {
  return nodes.value.find((n) => n.id === tableName)?.columns || []
}

// ===================== 数据加载 =====================
async function loadList() {
  loading.value = true
  try {
    const res: any = await getRelations(props.dsId, {
      status: filterStatus.value || undefined,
      source: filterSource.value || undefined,
      keyword: keyword.value || undefined,
      page: page.value,
      pageSize: pageSize.value,
    })
    if (res.code === 0 && res.data) {
      list.value = res.data.list || []
      total.value = res.data.total || 0
    }
  } catch (e) {
    console.error('加载表关系失败', e)
  } finally {
    loading.value = false
  }
}

async function loadGraph() {
  try {
    const res: any = await getRelationGraph(props.dsId)
    if (res.code === 0 && res.data) {
      // 聚合数据统一持有，三视图共享下发（切换零请求）
      graphAgg.value = {
        nodes: res.data.nodes || [],
        edges: res.data.edges || [],
        stats: res.data.stats,
      }
      nodes.value = res.data.nodes || []
      const edges: any[] = res.data.edges || []
      const s = { active: 0, inactive: 0, ignored: 0, ...(res.data.stats || {}) }
      s.activeFk = edges.filter((e) => e.status === 'active' && e.source_type === 'foreign_key').length
      s.activeManual = edges.filter((e) => e.status === 'active' && e.source_type !== 'foreign_key').length
      stats.value = s
      emit('stats-change', { inactive: s.inactive })
    }
  } catch (e) {
    console.error('加载关系图失败', e)
  }
}

/** 子视图（画布）增删改后回调：父级统一刷新聚合数据 + 列表 */
async function onChildRefresh() {
  await Promise.all([loadList(), loadGraph()])
}

async function refreshAll() {
  await Promise.all([loadList(), loadGraph()])
}

function handleFilterChange() {
  page.value = 1
  loadList()
}

function onSelectionChange(rows: any[]) {
  selectedRows.value = rows
}

// ===================== 采集与批量操作 =====================
async function handleCollect() {
  collecting.value = true
  try {
    const res: any = await collectRelations(props.dsId)
    if (res.code === 0 && res.data) {
      const { fk_created = 0, guess_created = 0, skipped = 0 } = res.data
      if (fk_created + guess_created > 0) {
        ElMessage.success(`采集完成：新增外键 ${fk_created} 条、同名推荐 ${guess_created} 条${skipped ? `，跳过重复 ${skipped} 条` : ''}`)
      } else {
        ElMessage.info('采集完成：暂无新关系')
      }
      await refreshAll()
    }
  } catch (e) {
    console.error('关系采集失败', e)
  } finally {
    collecting.value = false
  }
}

async function handleBatchConfirm() {
  batchLoading.value = true
  try {
    const ids = selectedRows.value.map((r) => r.id)
    const res: any = await batchConfirmRelations(props.dsId, ids)
    if (res.code === 0) {
      ElMessage.success(res.message || '批量确认成功')
      await refreshAll()
    }
  } catch (e) {
    console.error('批量确认失败', e)
  } finally {
    batchLoading.value = false
  }
}

async function handleBatchIgnore() {
  batchLoading.value = true
  try {
    const ids = selectedRows.value.map((r) => r.id)
    const res: any = await batchIgnoreRelations(props.dsId, ids)
    if (res.code === 0) {
      ElMessage.success(res.message || '批量忽略成功')
      await refreshAll()
    }
  } catch (e) {
    console.error('批量忽略失败', e)
  } finally {
    batchLoading.value = false
  }
}

/** 批量探测（并发限流 5，方案 4.4.3） */
async function handleBatchProbe() {
  batchProbing.value = true
  const rows = [...selectedRows.value]
  const CHUNK = 5
  let ok = 0
  let fail = 0
  try {
    for (let i = 0; i < rows.length; i += CHUNK) {
      const chunk = rows.slice(i, i + CHUNK)
      const results = await Promise.allSettled(chunk.map((r) => doProbe(r)))
      results.forEach((r, idx) => {
        if (r.status === 'fulfilled' && r.value) ok++
        else {
          fail++
          if (r.status === 'rejected') {
            chunk[idx].probe = null
          }
        }
      })
      if (rows.length > CHUNK) loadList()
    }
    ElMessage.success(`批量探测完成：成功 ${ok} 条${fail ? `，失败 ${fail} 条` : ''}`)
    await Promise.all([loadList(), loadGraph()])
  } catch (e) {
    console.error('批量探测失败', e)
  } finally {
    batchProbing.value = false
  }
}

// ===================== 单条操作 =====================
/** 执行探测并回填 probe 缓存；返回是否成功 */
async function doProbe(row: any): Promise<boolean> {
  const res: any = await probeRelation(props.dsId, {
    leftTable: row.leftTable,
    leftColumn: row.leftColumn,
    rightTable: row.rightTable,
    rightColumn: row.rightColumn,
  })
  if (res.code === 0 && res.data) {
    row.probe = { ...res.data, probedAt: new Date().toISOString() }
    return true
  }
  return false
}

async function handleProbe(row: any) {
  probingId.value = row.id
  try {
    const ok = await doProbe(row)
    if (ok) {
      const factor = probeFactor(row)
      if (factor !== null && factor > 1.5) {
        ElMessage.warning(`探测完成：放大系数 ${factor}x，JOIN 可能产生数据放大，请确认基数`)
      } else {
        ElMessage.success('探测完成，结论已缓存')
      }
    }
  } catch (e: any) {
    row.probe = null
    const msg = e?.response?.data?.message || e?.message || '探测失败'
    ElMessage.error(String(msg))
  } finally {
    probingId.value = null
  }
}

async function handleConfirm(row: any) {
  try {
    const res: any = await batchConfirmRelations(props.dsId, [row.id])
    if (res.code === 0) {
      ElMessage.success('关系已确认生效')
      await refreshAll()
    }
  } catch (e) {
    console.error('确认失败', e)
  }
}

async function handleIgnore(row: any) {
  try {
    const res: any = await batchIgnoreRelations(props.dsId, [row.id])
    if (res.code === 0) {
      ElMessage.success('关系已忽略')
      await refreshAll()
    }
  } catch (e) {
    console.error('忽略失败', e)
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除关系 ${row.leftTable}.${row.leftColumn} ↔ ${row.rightTable}.${row.rightColumn} 吗？`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    const res: any = await deleteRelation(props.dsId, row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await refreshAll()
    }
  } catch (e) {
    console.error('删除失败', e)
  }
}

// ===================== 新建/编辑弹窗 =====================
function openCreate() {
  editingRow.value = null
  probeSuggestion.value = ''
  form.value = {
    leftTable: '',
    leftColumn: '',
    rightTable: '',
    rightColumn: '',
    cardinality: '1:1',
    joinType: 'inner',
    relationDesc: '',
  }
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingRow.value = row
  probeSuggestion.value = ''
  form.value = {
    leftTable: row.leftTable,
    leftColumn: row.leftColumn,
    rightTable: row.rightTable,
    rightColumn: row.rightColumn,
    cardinality: row.cardinality || '1:1',
    joinType: row.joinType || 'inner',
    relationDesc: row.relationDesc || '',
  }
  dialogVisible.value = true
}

async function handleDialogProbe() {
  dialogProbing.value = true
  try {
    const res: any = await probeRelation(props.dsId, {
      leftTable: form.value.leftTable,
      leftColumn: form.value.leftColumn,
      rightTable: form.value.rightTable,
      rightColumn: form.value.rightColumn,
    })
    if (res.code === 0 && res.data) {
      const { joinedRows, leftDistinct, rightDistinct, factor, verdict } = res.data
      const f = Math.round((factor ?? 1) * 10) / 10
      if (f > 1.5) {
        probeSuggestion.value = `左表 ${leftDistinct} 行 · 右表 ${rightDistinct} 行 · JOIN 后 ${joinedRows} 行，放大系数 ${f}x ⚠ 数据放大，可能产生笛卡尔积，请调整基数或重新选择关联字段`
        probeSuggestionLevel.value = 'error'
      } else if (f > 1.05) {
        probeSuggestion.value = `左表 ${leftDistinct} 行 · 右表 ${rightDistinct} 行 · JOIN 后 ${joinedRows} 行，判定 ${verdict} · 放大系数 ${f}x`
        probeSuggestionLevel.value = 'warning'
      } else {
        probeSuggestion.value = `左表 ${leftDistinct} 行 · 右表 ${rightDistinct} 行 · JOIN 后 ${joinedRows} 行，判定 ${verdict} · 放大系数 ${f}x ✓`
        probeSuggestionLevel.value = 'success'
      }
    }
  } catch (e: any) {
    probeSuggestion.value = e?.response?.data?.message || e?.message || '探测失败，请检查关联字段'
    probeSuggestionLevel.value = 'warning'
  } finally {
    dialogProbing.value = false
  }
}

async function handleSave() {
  // 表/字段完整性校验
  if (!editingRow.value && (!form.value.leftTable || !form.value.leftColumn || !form.value.rightTable || !form.value.rightColumn)) {
    ElMessage.warning('请完整选择左右表与关联字段')
    return
  }
  if (form.value.leftTable === form.value.rightTable && !editingRow.value) {
    ElMessage.warning('左右表不能相同（防自环）')
    return
  }
  saving.value = true
  try {
    let res: any
    if (editingRow.value) {
      res = await updateRelation(props.dsId, editingRow.value.id, {
        cardinality: form.value.cardinality as any,
        joinType: form.value.joinType as any,
        relationDesc: form.value.relationDesc,
      })
    } else {
      res = await createRelation(props.dsId, {
        leftTable: form.value.leftTable,
        leftColumn: form.value.leftColumn,
        rightTable: form.value.rightTable,
        rightColumn: form.value.rightColumn,
        cardinality: form.value.cardinality as any,
        joinType: form.value.joinType as any,
        relationDesc: form.value.relationDesc,
      })
    }
    if (res.code === 0) {
      ElMessage.success(editingRow.value ? '关系更新成功' : '关系创建成功，已生效')
      dialogVisible.value = false
      await refreshAll()
    }
  } catch (e) {
    console.error('保存关系失败', e)
  } finally {
    saving.value = false
  }
}

onMounted(refreshAll)
</script>

<style lang="scss" scoped>
.relation-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 12px 24px 16px;
  overflow: hidden;
}

/* 操作列：压缩相邻按钮间距 + 增大字号，保证 5 个按钮单行展示不换行 */
:deep(.op-col) {
  .el-button + .el-button {
    margin-left: 6px;
  }
  .el-button {
    font-size: 14px;
  }
}

/* 画布/总览视图容器（撑满剩余高度） */
.view-container {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.stats-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;

  .stat-item {
    font-size: 13px;
    color: #475569;

    .num {
      font-size: 16px;
      margin: 0 2px;

      &.active { color: #16a34a; }
      &.inactive { color: #d97706; }
      &.ignored { color: #94a3b8; }
    }

    .sub {
      font-size: 12px;
      color: #94a3b8;
    }
  }

  .stat-tip {
    margin-left: auto;
    font-size: 12px;
    color: #94a3b8;
  }
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;

  .toolbar-spacer {
    flex: 1;
  }
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;
  font-size: 13px;
  color: #1e40af;

  b { color: #1d4ed8; }
}

.relation-table {
  flex: 1;
  overflow: auto;

  .pair-line {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-wrap: wrap;

    .pair-table {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-weight: 600;
      color: #1e293b;
      font-size: 13px;
    }

    .pair-col {
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      color: #3b82f6;
      font-size: 13px;
    }

    .pair-arrow {
      color: #94a3b8;
      margin: 0 4px;
    }
  }

  .risk-line {
    font-size: 12px;
    color: #d97706;
    margin-top: 4px;
  }

  .type-text {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 12px;
    color: #16a34a;

    &.mismatch { color: #dc2626; }
  }

  .probe-ok { color: #16a34a; font-size: 12px; }
  .probe-warn { color: #d97706; font-size: 12px; }
  .probe-bad { color: #dc2626; font-size: 12px; font-weight: 600; }
  .probe-none { color: #cbd5e1; font-size: 12px; }
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

.endpoints-view {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 6px;
  margin-bottom: 16px;

  .pair-table {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-weight: 600;
    color: #1e293b;
    font-size: 13px;
  }
}
</style>
