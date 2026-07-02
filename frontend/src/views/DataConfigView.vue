<template>
  <div class="data-config-view">
    <div class="page-header">
      <h2 class="page-title">数据管理</h2>
    </div>

    <el-tabs v-model="activeTab" class="config-tabs">
      <el-tab-pane label="数据源管理" name="datasource">
        <div class="tab-content">
          <div class="tab-toolbar">
            <el-input
              v-model="datasourceSearch"
              placeholder="搜索数据源..."
              style="width: 240px"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button type="primary" @click="handleAddDatasource">
              <el-icon><Plus /></el-icon>
              新增数据源
            </el-button>
          </div>

          <el-table :data="filteredDatasources" style="width: 100%" v-loading="datasourceLoading">
            <el-table-column prop="name" label="数据源名称" min-width="160" />
            <el-table-column prop="type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="dbTypeColor[row.type]" effect="plain">
                  {{ row.type.toUpperCase() }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="host" label="主机" min-width="140" />
            <el-table-column prop="port" label="端口" width="80" />
            <el-table-column prop="database" label="数据库" width="140" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'danger'" effect="plain">
                  {{ row.status === 'active' ? '可用' : '不可用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="createdAt" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.createdAt) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="240" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="handleTestConn(row)">测试连接</el-button>
                <el-button link type="primary" @click="handleViewSchema(row)">查看Schema</el-button>
                <el-button link type="primary" @click="handleSyncSchema(row)">同步</el-button>
                <el-button link type="primary" @click="handleEditDatasource(row)">编辑</el-button>
                <el-button link type="danger" @click="handleDeleteDatasource(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="指标管理" name="metric">
        <div class="tab-content">
          <div class="tab-toolbar">
            <el-input
              v-model="metricSearch"
              placeholder="搜索指标..."
              style="width: 240px"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button type="primary" @click="handleAddMetric">
              <el-icon><Plus /></el-icon>
              新增指标
            </el-button>
          </div>

          <el-table :data="filteredMetrics" style="width: 100%" v-loading="metricLoading">
            <el-table-column prop="name" label="指标名称" min-width="160" />
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="description" label="描述" min-width="200" />
            <el-table-column prop="groupName" label="分组" width="120" />
            <el-table-column prop="unit" label="单位" width="100" />
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="handleEditMetric(row)">编辑</el-button>
                <el-button link type="danger" @click="handleDeleteMetric(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="维度管理" name="dimension">
        <div class="tab-content">
          <div class="tab-toolbar">
            <el-input
              v-model="dimensionSearch"
              placeholder="搜索维度..."
              style="width: 240px"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button type="primary" @click="handleAddDimension">
              <el-icon><Plus /></el-icon>
              新增维度
            </el-button>
          </div>

          <el-table :data="filteredDimensions" style="width: 100%" v-loading="dimensionLoading">
            <el-table-column prop="name" label="维度名称" min-width="160" />
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="tableName" label="表名" width="160" />
            <el-table-column prop="columnName" label="字段名" width="140" />
            <el-table-column prop="dataType" label="数据类型" width="120" />
            <el-table-column prop="description" label="描述" min-width="160" />
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="handleEditDimension(row)">编辑</el-button>
                <el-button link type="danger" @click="handleDeleteDimension(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="术语管理" name="term">
        <div class="tab-content">
          <div class="tab-toolbar">
            <el-input
              v-model="termSearch"
              placeholder="搜索术语..."
              style="width: 240px"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button type="primary" @click="handleAddTerm">
              <el-icon><Plus /></el-icon>
              新增术语
            </el-button>
          </div>

          <el-table :data="filteredTerms" style="width: 100%" v-loading="termLoading">
            <el-table-column prop="term" label="术语" min-width="140" />
            <el-table-column prop="code" label="编码" width="140" />
            <el-table-column prop="definition" label="定义" min-width="240" />
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column label="同义词" min-width="200">
              <template #default="{ row }">
                <el-tag
                  v-for="(syn, idx) in row.synonyms?.slice(0, 3)"
                  :key="idx"
                  size="small"
                  effect="plain"
                  style="margin-right: 4px"
                >
                  {{ syn }}
                </el-tag>
                <span v-if="row.synonyms?.length > 3" style="color: #909399; font-size: 12px">
                  +{{ row.synonyms.length - 3 }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="handleEditTerm(row)">编辑</el-button>
                <el-button link type="danger" @click="handleDeleteTerm(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="datasourceDialogVisible"
      :title="isEditDatasource ? '编辑数据源' : '新增数据源'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="datasourceForm" label-width="100px" :rules="datasourceRules" ref="datasourceFormRef">
        <el-form-item label="数据源名称" prop="name">
          <el-input v-model="datasourceForm.name" placeholder="请输入数据源名称" />
        </el-form-item>
        <el-form-item label="数据库类型" prop="type">
          <el-select v-model="datasourceForm.type" placeholder="请选择数据库类型" style="width: 100%">
            <el-option label="MySQL" value="mysql" />
            <el-option label="PostgreSQL" value="postgresql" />
            <el-option label="ClickHouse" value="clickhouse" />
            <el-option label="Oracle" value="oracle" />
          </el-select>
        </el-form-item>
        <el-form-item label="主机地址" prop="host">
          <el-input v-model="datasourceForm.host" placeholder="请输入主机地址" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="datasourceForm.port" :min="1" :max="65535" style="width: 100%" />
        </el-form-item>
        <el-form-item label="数据库名" prop="database">
          <el-input v-model="datasourceForm.database" placeholder="请输入数据库名" />
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="datasourceForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="datasourceForm.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="字符集">
          <el-input v-model="datasourceForm.charset" placeholder="utf8mb4" />
        </el-form-item>
        <el-form-item label="连接池大小">
          <el-input-number v-model="datasourceForm.poolSize" :min="1" :max="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="datasourceForm.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleTestConnFromDialog">测试连接</el-button>
        <el-button @click="datasourceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveDatasource" :loading="datasourceSaving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="metricDialogVisible"
      :title="isEditMetric ? '编辑指标' : '新增指标'"
      width="650px"
      destroy-on-close
    >
      <el-form :model="metricForm" label-width="100px" :rules="metricRules" ref="metricFormRef">
        <el-form-item label="指标名称" prop="name">
          <el-input v-model="metricForm.name" placeholder="请输入指标名称" />
        </el-form-item>
        <el-form-item label="指标编码" prop="code">
          <el-input v-model="metricForm.code" placeholder="请输入指标编码" />
        </el-form-item>
        <el-form-item label="数据源" prop="datasourceId">
          <el-select v-model="metricForm.datasourceId" placeholder="请选择数据源" style="width: 100%">
            <el-option
              v-for="ds in datasources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="指标分组">
          <el-input v-model="metricForm.groupName" placeholder="如：生产、质量、能源" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="metricForm.unit" placeholder="如：吨、%" />
        </el-form-item>
        <el-form-item label="SQL表达式" prop="sqlExpression">
          <el-input
            v-model="metricForm.sqlExpression"
            type="textarea"
            :rows="4"
            placeholder="如：SUM(production_qty) FROM steel_production"
          />
        </el-form-item>
        <el-form-item label="结果类型">
          <el-select v-model="metricForm.resultType" style="width: 100%">
            <el-option label="数值" value="number" />
            <el-option label="百分比" value="percent" />
            <el-option label="金额" value="currency" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="metricForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="metricDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveMetric" :loading="metricSaving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="dimensionDialogVisible"
      :title="isEditDimension ? '编辑维度' : '新增维度'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="dimensionForm" label-width="100px" :rules="dimensionRules" ref="dimensionFormRef">
        <el-form-item label="维度名称" prop="name">
          <el-input v-model="dimensionForm.name" placeholder="请输入维度名称" />
        </el-form-item>
        <el-form-item label="维度编码" prop="code">
          <el-input v-model="dimensionForm.code" placeholder="请输入维度编码" />
        </el-form-item>
        <el-form-item label="数据源" prop="datasourceId">
          <el-select v-model="dimensionForm.datasourceId" placeholder="请选择数据源" style="width: 100%">
            <el-option
              v-for="ds in datasources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="表名" prop="tableName">
          <el-input v-model="dimensionForm.tableName" placeholder="请输入表名" />
        </el-form-item>
        <el-form-item label="字段名" prop="columnName">
          <el-input v-model="dimensionForm.columnName" placeholder="请输入字段名" />
        </el-form-item>
        <el-form-item label="数据类型">
          <el-input v-model="dimensionForm.dataType" placeholder="如：varchar、int、date" />
        </el-form-item>
        <el-form-item label="层级">
          <el-input-number v-model="dimensionForm.level" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="父级维度">
          <el-select v-model="dimensionForm.parentId" placeholder="请选择父级维度" style="width: 100%" clearable>
            <el-option
              v-for="dim in dimensions"
              :key="dim.id"
              :label="dim.name"
              :value="dim.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="dimensionForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dimensionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveDimension" :loading="dimensionSaving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="termDialogVisible"
      :title="isEditTerm ? '编辑术语' : '新增术语'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="termForm" label-width="100px" :rules="termRules" ref="termFormRef">
        <el-form-item label="术语" prop="term">
          <el-input v-model="termForm.term" placeholder="请输入术语名称" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="termForm.code" placeholder="请输入术语编码" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="termForm.category" placeholder="如：生产、质量、设备" />
        </el-form-item>
        <el-form-item label="定义" prop="definition">
          <el-input v-model="termForm.definition" type="textarea" :rows="3" placeholder="请输入术语定义" />
        </el-form-item>
        <el-form-item label="同义词">
          <el-select
            v-model="termForm.synonyms"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入同义词后按回车添加"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="数据源">
          <el-select v-model="termForm.datasourceId" placeholder="选择关联数据源" style="width: 100%" clearable>
            <el-option
              v-for="ds in datasources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="termDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveTerm" :loading="termSaving">保存</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Search, Loading } from '@element-plus/icons-vue'
import {
  getDatasources,
  createDatasource,
  updateDatasource,
  deleteDatasource,
  testConnection,
  syncSchema,
  getSchema,
  type DatasourceForm,
} from '@/api/datasource'
import {
  getMetrics,
  createMetric,
  updateMetric,
  deleteMetric,
  type MetricForm,
} from '@/api/metric'
import {
  getDimensions,
  createDimension,
  updateDimension,
  deleteDimension,
  type DimensionForm,
} from '@/api/dimension'
import {
  getTerms,
  createTerm,
  updateTerm,
  deleteTerm,
  type TermForm,
} from '@/api/term'

const router = useRouter()

const activeTab = ref('datasource')
const datasourceSearch = ref('')
const metricSearch = ref('')
const dimensionSearch = ref('')
const termSearch = ref('')

const dbTypeColor: Record<string, string> = {
  mysql: 'primary',
  postgresql: 'success',
  clickhouse: 'warning',
  oracle: 'info',
}

const datasources = ref<any[]>([])
const metrics = ref<any[]>([])
const dimensions = ref<any[]>([])
const terms = ref<any[]>([])

const datasourceLoading = ref(false)
const metricLoading = ref(false)
const dimensionLoading = ref(false)
const termLoading = ref(false)

const datasourceDialogVisible = ref(false)
const metricDialogVisible = ref(false)
const dimensionDialogVisible = ref(false)
const termDialogVisible = ref(false)

const isEditDatasource = ref(false)
const isEditMetric = ref(false)
const isEditDimension = ref(false)
const isEditTerm = ref(false)

const datasourceSaving = ref(false)
const metricSaving = ref(false)
const dimensionSaving = ref(false)
const termSaving = ref(false)

const datasourceFormRef = ref<FormInstance>()
const metricFormRef = ref<FormInstance>()
const dimensionFormRef = ref<FormInstance>()
const termFormRef = ref<FormInstance>()

const editDatasourceId = ref<number | null>(null)
const editMetricId = ref<number | null>(null)
const editDimensionId = ref<number | null>(null)
const editTermId = ref<number | null>(null)

const datasourceForm = reactive<DatasourceForm>({
  name: '',
  type: 'mysql',
  host: '',
  port: 3306,
  database: '',
  username: '',
  password: '',
  charset: 'utf8mb4',
  poolSize: 5,
  maxOverflow: 10,
  description: '',
})

const metricForm = reactive<MetricForm>({
  name: '',
  code: '',
  description: '',
  datasourceId: 0,
  sqlExpression: '',
  resultType: 'number',
  unit: '',
  groupName: '',
  tags: [],
})

const dimensionForm = reactive<DimensionForm>({
  name: '',
  code: '',
  description: '',
  datasourceId: 0,
  tableName: '',
  columnName: '',
  dataType: '',
  level: 1,
  parentId: undefined,
})

const termForm = reactive<TermForm>({
  term: '',
  code: '',
  definition: '',
  category: '',
  synonyms: [],
  datasourceId: undefined,
  relatedTerms: [],
})

const datasourceRules: FormRules = {
  name: [{ required: true, message: '请输入数据源名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择数据库类型', trigger: 'change' }],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  database: [{ required: true, message: '请输入数据库名', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
}

const metricRules: FormRules = {
  name: [{ required: true, message: '请输入指标名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入指标编码', trigger: 'blur' }],
  datasourceId: [{ required: true, message: '请选择数据源', trigger: 'change' }],
  sqlExpression: [{ required: true, message: '请输入SQL表达式', trigger: 'blur' }],
}

const dimensionRules: FormRules = {
  name: [{ required: true, message: '请输入维度名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入维度编码', trigger: 'blur' }],
  datasourceId: [{ required: true, message: '请选择数据源', trigger: 'change' }],
  tableName: [{ required: true, message: '请输入表名', trigger: 'blur' }],
  columnName: [{ required: true, message: '请输入字段名', trigger: 'blur' }],
}

const termRules: FormRules = {
  term: [{ required: true, message: '请输入术语', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  definition: [{ required: true, message: '请输入定义', trigger: 'blur' }],
}

const filteredDatasources = computed(() => {
  if (!datasourceSearch.value) return datasources.value
  return datasources.value.filter((d) =>
    d.name.toLowerCase().includes(datasourceSearch.value.toLowerCase())
  )
})

const filteredMetrics = computed(() => {
  if (!metricSearch.value) return metrics.value
  return metrics.value.filter((m) =>
    m.name.toLowerCase().includes(metricSearch.value.toLowerCase())
  )
})

const filteredDimensions = computed(() => {
  if (!dimensionSearch.value) return dimensions.value
  return dimensions.value.filter((d) =>
    d.name.toLowerCase().includes(dimensionSearch.value.toLowerCase())
  )
})

const filteredTerms = computed(() => {
  if (!termSearch.value) return terms.value
  return terms.value.filter((t) =>
    t.term.toLowerCase().includes(termSearch.value.toLowerCase())
  )
})

async function loadDatasources() {
  datasourceLoading.value = true
  try {
    const res: any = await getDatasources()
    if (res.code === 0 && res.data) {
      datasources.value = res.data
    }
  } catch (e) {
    console.error('加载数据源列表失败', e)
  } finally {
    datasourceLoading.value = false
  }
}

async function loadMetrics() {
  metricLoading.value = true
  try {
    const res: any = await getMetrics()
    if (res.code === 0 && res.data) {
      metrics.value = res.data
    }
  } catch (e) {
    console.error('加载指标列表失败', e)
  } finally {
    metricLoading.value = false
  }
}

async function loadDimensions() {
  dimensionLoading.value = true
  try {
    const res: any = await getDimensions()
    if (res.code === 0 && res.data) {
      dimensions.value = res.data
    }
  } catch (e) {
    console.error('加载维度列表失败', e)
  } finally {
    dimensionLoading.value = false
  }
}

async function loadTerms() {
  termLoading.value = true
  try {
    const res: any = await getTerms()
    if (res.code === 0 && res.data) {
      terms.value = res.data
    }
  } catch (e) {
    console.error('加载术语列表失败', e)
  } finally {
    termLoading.value = false
  }
}

function handleAddDatasource() {
  isEditDatasource.value = false
  editDatasourceId.value = null
  Object.assign(datasourceForm, {
    name: '',
    type: 'mysql',
    host: '',
    port: 3306,
    database: '',
    username: '',
    password: '',
    charset: 'utf8mb4',
    poolSize: 5,
    maxOverflow: 10,
    description: '',
  })
  datasourceDialogVisible.value = true
}

function handleEditDatasource(row: any) {
  isEditDatasource.value = true
  editDatasourceId.value = row.id
  Object.assign(datasourceForm, {
    name: row.name,
    type: row.type,
    host: row.host,
    port: row.port,
    database: row.database,
    username: row.username,
    password: row.password || '',
    charset: row.charset || 'utf8mb4',
    poolSize: row.poolSize || 5,
    maxOverflow: row.maxOverflow || 10,
    description: row.description || '',
  })
  datasourceDialogVisible.value = true
}

async function handleSaveDatasource() {
  if (!datasourceFormRef.value) return
  await datasourceFormRef.value.validate(async (valid) => {
    if (!valid) return
    datasourceSaving.value = true
    try {
      if (isEditDatasource.value && editDatasourceId.value) {
        const res: any = await updateDatasource(editDatasourceId.value, datasourceForm)
        if (res.code === 0) {
          ElMessage.success('更新成功')
          datasourceDialogVisible.value = false
          await loadDatasources()
        }
      } else {
        const res: any = await createDatasource(datasourceForm)
        if (res.code === 0) {
          ElMessage.success('创建成功')
          datasourceDialogVisible.value = false
          await loadDatasources()
        }
      }
    } catch (e) {
      console.error('保存数据源失败', e)
    } finally {
      datasourceSaving.value = false
    }
  })
}

async function handleTestConn(row: any) {
  try {
    const res: any = await testConnection({
      type: row.type,
      host: row.host,
      port: row.port,
      database: row.database,
      username: row.username,
      password: row.password,
    })
    if (res.code === 0) {
      ElMessage.success('连接测试成功')
    }
  } catch (e) {
    console.error('连接测试失败', e)
  }
}

// ========== 表结构查看（已迁移到详情页） ==========

async function handleViewSchema(row: any) {
  router.push(`/datasource/${row.id}`)
}

async function handleTestConnFromDialog() {
  try {
    const res: any = await testConnection({
      type: datasourceForm.type,
      host: datasourceForm.host,
      port: datasourceForm.port,
      database: datasourceForm.database,
      username: datasourceForm.username,
      password: datasourceForm.password,
    })
    if (res.code === 0) {
      ElMessage.success('连接测试成功')
    }
  } catch (e) {
    console.error('连接测试失败', e)
  }
}

async function handleSyncSchema(row: any) {
  try {
    const res: any = await syncSchema(row.id)
    if (res.code === 0) {
      ElMessage.success(`Schema同步完成，共 ${res.data?.length || 0} 张表`)
    } else {
      ElMessage.error(res.message || '同步失败')
    }
  } catch (e: any) {
    console.error('Schema同步失败', e)
    ElMessage.error(e?.response?.data?.message || '同步失败，请检查数据库连接配置')
  }
}

async function handleDeleteDatasource(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除数据源「${row.name}」吗？`, '删除确认', {
      type: 'warning',
    })
    const res: any = await deleteDatasource(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadDatasources()
    }
  } catch {
    // user cancelled
  }
}

function handleAddMetric() {
  isEditMetric.value = false
  editMetricId.value = null
  Object.assign(metricForm, {
    name: '',
    code: '',
    description: '',
    datasourceId: datasources.value[0]?.id || 0,
    sqlExpression: '',
    resultType: 'number',
    unit: '',
    groupName: '',
    tags: [],
  })
  metricDialogVisible.value = true
}

function handleEditMetric(row: any) {
  isEditMetric.value = true
  editMetricId.value = row.id
  Object.assign(metricForm, {
    name: row.name,
    code: row.code,
    description: row.description || '',
    datasourceId: row.datasourceId,
    sqlExpression: row.sqlExpression || '',
    resultType: row.resultType || 'number',
    unit: row.unit || '',
    groupName: row.groupName || '',
    tags: row.tags || [],
  })
  metricDialogVisible.value = true
}

async function handleSaveMetric() {
  if (!metricFormRef.value) return
  await metricFormRef.value.validate(async (valid) => {
    if (!valid) return
    metricSaving.value = true
    try {
      if (isEditMetric.value && editMetricId.value) {
        const res: any = await updateMetric(editMetricId.value, metricForm)
        if (res.code === 0) {
          ElMessage.success('更新成功')
          metricDialogVisible.value = false
          await loadMetrics()
        }
      } else {
        const res: any = await createMetric(metricForm)
        if (res.code === 0) {
          ElMessage.success('创建成功')
          metricDialogVisible.value = false
          await loadMetrics()
        }
      }
    } catch (e) {
      console.error('保存指标失败', e)
    } finally {
      metricSaving.value = false
    }
  })
}

async function handleDeleteMetric(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除指标「${row.name}」吗？`, '删除确认', {
      type: 'warning',
    })
    const res: any = await deleteMetric(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadMetrics()
    }
  } catch {
    // user cancelled
  }
}

function handleAddDimension() {
  isEditDimension.value = false
  editDimensionId.value = null
  Object.assign(dimensionForm, {
    name: '',
    code: '',
    description: '',
    datasourceId: datasources.value[0]?.id || 0,
    tableName: '',
    columnName: '',
    dataType: '',
    level: 1,
    parentId: undefined,
  })
  dimensionDialogVisible.value = true
}

function handleEditDimension(row: any) {
  isEditDimension.value = true
  editDimensionId.value = row.id
  Object.assign(dimensionForm, {
    name: row.name,
    code: row.code,
    description: row.description || '',
    datasourceId: row.datasourceId,
    tableName: row.tableName || '',
    columnName: row.columnName || '',
    dataType: row.dataType || '',
    level: row.level || 1,
    parentId: row.parentId,
  })
  dimensionDialogVisible.value = true
}

async function handleSaveDimension() {
  if (!dimensionFormRef.value) return
  await dimensionFormRef.value.validate(async (valid) => {
    if (!valid) return
    dimensionSaving.value = true
    try {
      if (isEditDimension.value && editDimensionId.value) {
        const res: any = await updateDimension(editDimensionId.value, dimensionForm)
        if (res.code === 0) {
          ElMessage.success('更新成功')
          dimensionDialogVisible.value = false
          await loadDimensions()
        }
      } else {
        const res: any = await createDimension(dimensionForm)
        if (res.code === 0) {
          ElMessage.success('创建成功')
          dimensionDialogVisible.value = false
          await loadDimensions()
        }
      }
    } catch (e) {
      console.error('保存维度失败', e)
    } finally {
      dimensionSaving.value = false
    }
  })
}

async function handleDeleteDimension(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除维度「${row.name}」吗？`, '删除确认', {
      type: 'warning',
    })
    const res: any = await deleteDimension(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadDimensions()
    }
  } catch {
    // user cancelled
  }
}

function handleAddTerm() {
  isEditTerm.value = false
  editTermId.value = null
  Object.assign(termForm, {
    term: '',
    code: '',
    definition: '',
    category: '',
    synonyms: [],
    datasourceId: undefined,
    relatedTerms: [],
  })
  termDialogVisible.value = true
}

function handleEditTerm(row: any) {
  isEditTerm.value = true
  editTermId.value = row.id
  Object.assign(termForm, {
    term: row.term,
    code: row.code,
    definition: row.definition || '',
    category: row.category || '',
    synonyms: row.synonyms || [],
    datasourceId: row.datasourceId,
    relatedTerms: row.relatedTerms || [],
  })
  termDialogVisible.value = true
}

async function handleSaveTerm() {
  if (!termFormRef.value) return
  await termFormRef.value.validate(async (valid) => {
    if (!valid) return
    termSaving.value = true
    try {
      if (isEditTerm.value && editTermId.value) {
        const res: any = await updateTerm(editTermId.value, termForm)
        if (res.code === 0) {
          ElMessage.success('更新成功')
          termDialogVisible.value = false
          await loadTerms()
        }
      } else {
        const res: any = await createTerm(termForm)
        if (res.code === 0) {
          ElMessage.success('创建成功')
          termDialogVisible.value = false
          await loadTerms()
        }
      }
    } catch (e) {
      console.error('保存术语失败', e)
    } finally {
      termSaving.value = false
    }
  })
}

async function handleDeleteTerm(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除术语「${row.term}」吗？`, '删除确认', {
      type: 'warning',
    })
    const res: any = await deleteTerm(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadTerms()
    }
  } catch {
    // user cancelled
  }
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

watch(activeTab, (newTab) => {
  if (newTab === 'datasource' && datasources.value.length === 0) {
    loadDatasources()
  } else if (newTab === 'metric' && metrics.value.length === 0) {
    loadMetrics()
    if (datasources.value.length === 0) {
      loadDatasources()
    }
  } else if (newTab === 'dimension' && dimensions.value.length === 0) {
    loadDimensions()
    if (datasources.value.length === 0) {
      loadDatasources()
    }
  } else if (newTab === 'term' && terms.value.length === 0) {
    loadTerms()
  }
})

onMounted(() => {
  loadDatasources()
})
</script>

<style lang="scss" scoped>
.data-config-view {
  height: 100%;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
}

.config-tabs {
  :deep(.el-tabs__content) {
    background: #fff;
    border-radius: 0 $card-radius $card-radius $card-radius;
    padding: 20px;
    min-height: 400px;
  }
}

.tab-content {
  .tab-toolbar {
    display: flex;
    justify-content: space-between;
    margin-bottom: 16px;
  }
}

.schema-comment {
  padding: 8px 12px;
  margin-bottom: 8px;
  background-color: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}
</style>
