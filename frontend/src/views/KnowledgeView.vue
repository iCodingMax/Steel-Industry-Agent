<template>
  <div class="knowledge-view">
    <div v-if="!currentKB" class="kb-list-view">
      <div class="page-header">
        <h2 class="page-title">知识管理</h2>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新建知识库
        </el-button>
      </div>

      <div class="kb-grid">
        <div v-for="kb in knowledgeBases" :key="kb.id" class="kb-card" @click="handleDetail(kb)">
          <div class="kb-icon">
            <el-icon :size="28"><FolderOpened /></el-icon>
          </div>
          <div class="kb-info">
            <h3 class="kb-name">{{ kb.name }}</h3>
            <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>
            <div class="kb-meta">
              <span class="kb-count">
                <el-icon><Document /></el-icon>
                {{ kb.documentCount ?? 0 }} 个文档
              </span>
              <span class="kb-status" :class="kb.status">
                {{ statusText[kb.status] || kb.status }}
              </span>
            </div>
          </div>
          <div class="kb-actions">
            <el-button text type="primary" @click.stop="handleDetail(kb)">
              <el-icon><View /></el-icon>
              管理
            </el-button>
          </div>
        </div>

        <div class="kb-card add-kb" @click="handleCreate">
          <el-icon :size="48" class="add-icon"><Plus /></el-icon>
          <span>新建知识库</span>
        </div>
      </div>
    </div>

    <div v-else class="kb-detail-view">
      <div class="page-header">
        <div class="header-left">
          <el-button text @click="backToList">
            <el-icon><ArrowLeft /></el-icon>
            返回列表
          </el-button>
          <h2 class="page-title">{{ currentKB.name }}</h2>
        </div>
        <div class="header-actions">
          <el-button @click="handleBuildIndex" :loading="buildingIndex">
            <el-icon><RefreshRight /></el-icon>
            构建索引
          </el-button>
          <el-button type="primary" @click="handleUpload">
            <el-icon><Upload /></el-icon>
            上传文档
          </el-button>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="kb-tabs">
        <el-tab-pane label="文档列表" name="documents">
          <div class="tab-toolbar">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索文档..."
              style="width: 240px"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>

          <el-table :data="filteredDocuments" style="width: 100%" v-loading="loadingDocs">
            <el-table-column prop="fileName" label="文件名" min-width="200" />
            <el-table-column prop="fileType" label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.fileType?.toUpperCase() }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="fileSize" label="大小" width="100">
              <template #default="{ row }">
                {{ formatFileSize(row.fileSize) }}
              </template>
            </el-table-column>
            <el-table-column prop="segmentCount" label="切片数" width="100" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="docStatusType[row.status]" effect="plain" size="small">
                  {{ docStatusText[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="createdAt" label="上传时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.createdAt) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="danger" @click="handleDeleteDoc(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="知识库设置" name="settings">
          <el-form :model="kbSettings" label-width="120px" style="max-width: 600px">
            <el-form-item label="知识库名称">
              <el-input v-model="kbSettings.name" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="kbSettings.description" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="嵌入模型">
              <el-input v-model="kbSettings.embeddingModel" />
            </el-form-item>
            <el-form-item label="切片大小">
              <el-input-number v-model="kbSettings.chunkSize" :min="100" :max="2000" :step="50" />
            </el-form-item>
            <el-form-item label="重叠长度">
              <el-input-number v-model="kbSettings.chunkOverlap" :min="0" :max="500" :step="20" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveSettings">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>

    <el-dialog v-model="dialogVisible" title="新建知识库" width="500px">
      <el-form :model="formData" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="formData.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入知识库描述"
          />
        </el-form-item>
        <el-form-item label="嵌入模型">
          <el-input v-model="formData.embeddingModel" />
        </el-form-item>
        <el-form-item label="切片大小">
          <el-input-number v-model="formData.chunkSize" :min="100" :max="2000" :step="50" />
        </el-form-item>
        <el-form-item label="重叠长度">
          <el-input-number v-model="formData.chunkOverlap" :min="0" :max="500" :step="20" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">创建</el-button>
      </template>
    </el-dialog>

    <input ref="fileInputRef" type="file" style="display: none" @change="onFileSelected" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  FolderOpened,
  Document,
  View,
  ArrowLeft,
  Upload,
  Search,
  RefreshRight,
} from '@element-plus/icons-vue'
import { getKnowledgeBases, createKnowledgeBase, getDocuments, uploadDocument, deleteDocument, buildIndex, updateKnowledgeBase, type KnowledgeBase } from '@/api/knowledge'

const dialogVisible = ref(false)
const loadingDocs = ref(false)
const buildingIndex = ref(false)
const currentKB = ref<KnowledgeBase | null>(null)
const activeTab = ref('documents')
const searchKeyword = ref('')
const fileInputRef = ref<HTMLInputElement>()
const documents = ref<any[]>([])

const formData = reactive({
  name: '',
  description: '',
  embeddingModel: 'bge-m3',
  chunkSize: 500,
  chunkOverlap: 100,
})

const kbSettings = reactive({
  name: '',
  description: '',
  embeddingModel: 'bge-m3',
  chunkSize: 500,
  chunkOverlap: 100,
})

const knowledgeBases = ref<KnowledgeBase[]>([])

const statusText: Record<string, string> = {
  ready: '已就绪',
  building: '构建中',
  error: '异常',
  active: '已启用',
  inactive: '已停用',
}

const docStatusText: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
}

const docStatusType: Record<string, string> = {
  pending: 'info',
  processing: 'warning',
  completed: 'success',
  failed: 'danger',
}

const filteredDocuments = computed(() => {
  if (!searchKeyword.value) return documents.value
  return documents.value.filter((d) =>
    d.fileName?.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

async function loadKnowledgeBases() {
  try {
    const res = await getKnowledgeBases() as any
    if (res.code === 0 && res.data) {
      // 兼容 res.data 为数组或 { list, total } 结构
      knowledgeBases.value = Array.isArray(res.data) ? res.data : (res.data.list || [])
    }
  } catch (e) {
    console.error('加载知识库列表失败', e)
  }
}

async function loadDocuments(kbId: number) {
  loadingDocs.value = true
  try {
    const res = await getDocuments(kbId) as any
    if (res.code === 0 && res.data) {
      documents.value = Array.isArray(res.data) ? res.data : (res.data.list || [])
    }
  } catch (e) {
    console.error('加载文档列表失败', e)
  } finally {
    loadingDocs.value = false
  }
}

function handleCreate() {
  formData.name = ''
  formData.description = ''
  formData.embeddingModel = 'bge-m3'
  formData.chunkSize = 500
  formData.chunkOverlap = 100
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formData.name.trim()) {
    ElMessage.warning('请输入知识库名称')
    return
  }
  try {
    const res = await createKnowledgeBase({
      name: formData.name,
      description: formData.description,
      embeddingModel: formData.embeddingModel,
      chunkSize: formData.chunkSize,
      chunkOverlap: formData.chunkOverlap,
    }) as any
    if (res.code === 0) {
      ElMessage.success('知识库创建成功')
      dialogVisible.value = false
      await loadKnowledgeBases()
    }
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

async function handleDetail(kb: KnowledgeBase) {
  currentKB.value = kb
  kbSettings.name = kb.name
  kbSettings.description = kb.description || ''
  kbSettings.embeddingModel = kb.embeddingModel
  kbSettings.chunkSize = kb.chunkSize
  kbSettings.chunkOverlap = kb.chunkOverlap
  await loadDocuments(kb.id)
}

function backToList() {
  currentKB.value = null
  loadKnowledgeBases()
}

function handleUpload() {
  fileInputRef.value?.click()
}

async function onFileSelected(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file || !currentKB.value) return

  try {
    const res = await uploadDocument(currentKB.value.id, file) as any
    if (res.code === 0) {
      ElMessage.success('文档上传成功，正在后台处理')
      await loadDocuments(currentKB.value.id)
    }
  } catch (e) {
    ElMessage.error('上传失败')
  } finally {
    target.value = ''
  }
}

async function handleDeleteDoc(doc: any) {
  try {
    await ElMessageBox.confirm(`确定删除文档「${doc.fileName}」吗？`, '删除确认', {
      type: 'warning',
    })
    if (currentKB.value) {
      await deleteDocument(currentKB.value.id, doc.id)
      ElMessage.success('删除成功')
      await loadDocuments(currentKB.value.id)
    }
  } catch {
    // 取消
  }
}

async function handleBuildIndex() {
  if (!currentKB.value) return
  buildingIndex.value = true
  try {
    const res = await buildIndex(currentKB.value.id) as any
    if (res.code === 0) {
      ElMessage.success(`索引构建完成，共 ${res.data.indexedDocuments} 个文档`)
    }
  } catch (e) {
    ElMessage.error('索引构建失败')
  } finally {
    buildingIndex.value = false
  }
}

async function saveSettings() {
  if (!currentKB.value) return
  try {
    const res = await updateKnowledgeBase(currentKB.value.id, kbSettings) as any
    if (res.code === 0) {
      ElMessage.success('设置保存成功')
      currentKB.value = { ...currentKB.value, ...res.data }
    }
  } catch (e) {
    ElMessage.error('保存失败')
  }
}

function formatFileSize(bytes?: number) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadKnowledgeBases()
})
</script>

<style lang="scss" scoped>
.knowledge-view {
  height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
  margin: 0;
}

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.kb-card {
  background: #fff;
  border: 1px solid $card-border;
  border-radius: $card-radius;
  padding: 24px;
  transition: all 0.3s ease;
  cursor: pointer;

  &:hover {
    box-shadow: $card-shadow;
    transform: translateY(-2px);
  }
}

.kb-icon {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(59, 130, 246, 0.2));
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $primary-color;
  margin-bottom: 16px;
}

.kb-info {
  margin-bottom: 16px;
}

.kb-name {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
  margin-bottom: 6px;
}

.kb-desc {
  font-size: 13px;
  color: $text-secondary;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kb-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.kb-count {
  display: flex;
  align-items: center;
  gap: 4px;
  color: $text-secondary;
}

.kb-status {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;

  &.active {
    background: rgba(16, 185, 129, 0.1);
    color: $success-color;
  }

  &.inactive {
    background: rgba(239, 68, 68, 0.1);
    color: $danger-color;
  }
}

.kb-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid $card-border;
}

.add-kb {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 2px dashed $card-border;
  color: $text-placeholder;
  min-height: 200px;
  gap: 12px;
  font-size: 14px;

  &:hover {
    border-color: $primary-color;
    color: $primary-color;
    background: rgba(59, 130, 246, 0.02);
  }
}

.add-icon {
  color: inherit;
}

.kb-detail-view {
  height: 100%;
  display: flex;
  flex-direction: column;

  .kb-tabs {
    flex: 1;
    overflow: hidden;
    background: #fff;
    border-radius: 0 $card-radius $card-radius $card-radius;

    :deep(.el-tabs__content) {
      height: calc(100% - 55px);
      overflow: auto;
      padding: 20px;
    }
  }
}

.tab-toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 8px;
}
</style>
