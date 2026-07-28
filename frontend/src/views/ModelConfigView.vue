<template>
  <div class="model-config-view">
    <div class="page-header">
      <h2 class="page-title">模型配置</h2>
    </div>

    <div class="toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">全部模型</span>
      </div>
      <div class="toolbar-right">
        <el-select v-model="searchType" placeholder="分类" class="sort-select">
          <el-option label="模型名称" value="name" />
          <el-option label="模型类型" value="modelType" />
        </el-select>
        <!-- 按名称搜索时显示输入框 -->
        <el-input 
          v-if="searchType === 'name'"
          v-model="searchQuery" 
          placeholder="按名称搜索" 
          class="search-input" 
          @keyup.enter="loadModels" 
        />
        <!-- 按类型搜索时显示下拉框 -->
        <el-select 
          v-else
          v-model="searchQuery" 
          placeholder="请选择模型类型" 
          class="search-input"
          clearable
          @change="loadModels"
        >
          <el-option label="大语言模型" value="llm" />
          <el-option label="向量模型" value="embedding" />
          <el-option label="重排模型" value="rerank" />
        </el-select>
        <el-button type="primary" @click="handleAddModel">
          <el-icon><Plus /></el-icon>
          添加模型
        </el-button>
      </div>
    </div>

    <div class="model-grid">
      <div
        v-for="model in modelList"
        :key="model.id"
        class="model-card"
      >
        <div class="card-header">
          <div class="provider-info">
            <div class="provider-icon" :class="getProviderClass(model.type)">
              {{ getProviderIcon(model.type) }}
            </div>
            <div class="model-title">
              <div class="model-name">
                {{ model.name }}
                <el-tag v-if="model.isDefault" type="primary" size="small" class="default-tag">默认</el-tag>
              </div>
              <div class="model-meta">{{ model.createdBy || '系统管理员' }} 创建于 {{ formatDate(model.createdAt) }}</div>
            </div>
          </div>
          <el-dropdown @command="(cmd: string) => handleCardAction(cmd, model)" trigger="click">
            <span class="card-menu">
              <el-icon><MoreFilled /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑配置</el-dropdown-item>
                <el-dropdown-item command="test">连接测试</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="card-body">
          <div class="model-info">
            <span class="info-label">模型类型</span>
            <el-tag :type="getModelTypeTagType(model.modelType)" effect="plain">{{ getModelTypeName(model.modelType) }}</el-tag>
          </div>
          <div class="model-info">
            <span class="info-label">基础模型</span>
            <span class="info-value">{{ model.modelName }}</span>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-if="modelList.length === 0" description="暂无模型配置，请点击右上角添加" />

    <el-dialog
      v-model="configDialogVisible"
      :title="configDialogTitle"
      width="600px"
      destroy-on-close
    >
      <el-form :model="configForm" label-width="120px" :rules="configRules" ref="configFormRef">
        <el-form-item label="模型类型*" prop="modelType">
          <el-select v-model="configForm.modelType" placeholder="请选择模型类型">
            <el-option label="大语言模型" value="llm" />
            <el-option label="向量模型" value="embedding" />
            <el-option label="重排模型" value="rerank" />
          </el-select>
        </el-form-item>
        <el-form-item label="供应商类型*" prop="type">
          <el-select v-model="configForm.type" placeholder="请选择供应商类型">
            <el-option label="Ollama" value="ollama" />
            <el-option label="Xorbits Inference" value="xinference" />
            <el-option label="vLLM" value="vllm" />
            <el-option label="NewAPI" value="newapi" />
            <el-option label="OpenAI" value="openai" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称*" prop="name">
          <el-input v-model="configForm.name" placeholder="请输入模型名称" />
        </el-form-item>
        <el-form-item label="基础模型*" prop="modelName">
          <el-input v-model="configForm.modelName" placeholder="请输入基础模型名称" />
        </el-form-item>
        <el-form-item label="服务地址*" prop="baseUrl">
          <el-input v-model="configForm.baseUrl" placeholder="请输入服务地址" />
        </el-form-item>
        <el-form-item label="API密钥" v-if="configForm.type !== 'ollama'">
          <el-input v-model="configForm.apiKey" type="password" show-password placeholder="请输入API密钥" />
        </el-form-item>
        <el-form-item label="最大输出Token">
          <el-input-number v-model="configForm.maxTokens" :min="1024" :max="100000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="温度参数">
          <el-input-number v-model="configForm.temperature" :min="0" :max="2" :step="0.1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="configForm.status" active-value="active" inactive-value="inactive" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="configForm.isDefault" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="configForm.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleTestConnection" :loading="testingConnection">测试连接</el-button>
        <el-button type="primary" @click="handleSaveConfig" :loading="configSaving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, MoreFilled } from '@element-plus/icons-vue'
import { getLLMConfigs, createLLMConfig, updateLLMConfig, deleteLLMConfig, testLLMConnection, type LLMConfigForm } from '@/api/llmConfig'

const loading = ref(false)
const configSaving = ref(false)
const testingConnection = ref(false)
const configDialogVisible = ref(false)
const configFormRef = ref<FormInstance>()

const modelList = ref<any[]>([])
const searchQuery = ref('')
const searchType = ref('name')

const searchPlaceholder = computed(() => {
  if (searchType.value === 'name') {
    return '按名称搜索'
  } else {
    return '按类型搜索（大语言模型/向量模型/重排模型）'
  }
})

const editingConfigId = ref<number | null>(null)

const configDialogTitle = computed(() => {
  if (!editingConfigId.value) {
    return '新增模型'
  }
  return '编辑模型'
})

const configForm = reactive<LLMConfigForm>({
  name: '',
  type: 'xinference',
  baseUrl: '',
  apiKey: '',
  modelName: '',
  modelType: 'llm',
  maxTokens: 2048,
  temperature: 0.7,
  topP: undefined,
  extraParams: {},
  isDefault: false,
  description: '',
  status: 'active',
})

const configRules: FormRules = {
  modelType: [{ required: true, message: '请选择模型类型', trigger: 'change' }],
  type: [{ required: true, message: '请选择供应商类型', trigger: 'change' }],
  name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  modelName: [{ required: true, message: '请输入基础模型名称', trigger: 'blur' }],
  baseUrl: [{ required: true, message: '请输入服务地址', trigger: 'blur' }],
}

function getProviderClass(type: string) {
  const classMap: Record<string, string> = {
    vllm: 'provider-vllm',
    xinference: 'provider-xinference',
    ollama: 'provider-ollama',
    openai: 'provider-openai',
    newapi: 'provider-newapi',
  }
  return classMap[type] || 'provider-default'
}

function getProviderIcon(type: string) {
  const iconMap: Record<string, string> = {
    vllm: 'vLLM',
    xinference: 'XI',
    ollama: 'O',
    openai: 'OA',
    newapi: 'NA',
  }
  return iconMap[type] || 'AI'
}

function getModelTypeTagType(modelType: string) {
  const typeMap: Record<string, string> = {
    llm: 'warning',
    embedding: 'primary',
    rerank: 'success',
  }
  return typeMap[modelType] || 'info'
}

function getModelTypeName(modelType: string) {
  const nameMap: Record<string, string> = {
    llm: '大语言模型',
    embedding: '向量模型',
    rerank: '重排模型',
  }
  return nameMap[modelType] || modelType
}

function formatDate(dateStr?: string) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

async function loadModels() {
  loading.value = true
  try {
    const res: any = await getLLMConfigs()
    if (res.code === 0 && res.data) {
      let configs = Array.isArray(res.data) ? res.data : (res.data.list || [])
      
      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase()
        if (searchType.value === 'name') {
          // 按名称搜索
          configs = configs.filter((c: any) => 
            c.name.toLowerCase().includes(query) ||
            c.modelName.toLowerCase().includes(query)
          )
        } else {
          // 按模型类型搜索（下拉框已返回英文值）
          configs = configs.filter((c: any) => 
            c.modelType === searchQuery.value
          )
        }
      }
      
      // 默认按名称排序
      configs.sort((a: any, b: any) => a.name.localeCompare(b.name))
      
      modelList.value = configs
    }
  } catch (e) {
    console.error('加载模型配置失败', e)
  } finally {
    loading.value = false
  }
}

function handleAddModel() {
  editingConfigId.value = null
  Object.assign(configForm, {
    name: '',
    type: 'xinference',
    baseUrl: '',
    apiKey: '',
    modelName: '',
    modelType: 'llm',
    maxTokens: 2048,
    temperature: 0.7,
    topP: undefined,
    extraParams: {},
    isDefault: false,
    description: '',
    status: 'active',
  })
  configDialogVisible.value = true
}

function handleCardAction(command: string, model: any) {
  if (command === 'edit') {
    editingConfigId.value = model.id
    Object.assign(configForm, {
      name: model.name,
      type: model.type,
      baseUrl: model.baseUrl,
      apiKey: model.apiKey || '',
      modelName: model.modelName,
      modelType: model.modelType,
      maxTokens: model.maxTokens || 2048,
      temperature: model.temperature || 0.7,
      topP: model.topP,
      extraParams: model.extraParams || {},
      isDefault: model.isDefault,
      description: model.description || '',
      status: model.status || 'active',
    })
    configDialogVisible.value = true
  } else if (command === 'test') {
    handleTestConnection(model)
  } else if (command === 'delete') {
    handleDeleteModel(model)
  }
}

async function handleSaveConfig() {
  if (!configFormRef.value) return
  await configFormRef.value.validate(async (valid) => {
    if (!valid) return
    configSaving.value = true
    try {
      const saveData: any = {
        ...configForm,
        status: configForm.status || 'active',
      }

      if (editingConfigId.value) {
        const res: any = await updateLLMConfig(editingConfigId.value, saveData)
        if (res.code === 0) {
          ElMessage.success('更新成功')
          configDialogVisible.value = false
          await loadModels()
        } else {
          ElMessage.error(res.message || '更新失败')
        }
      } else {
        const res: any = await createLLMConfig(saveData)
        if (res.code === 0) {
          ElMessage.success('创建成功')
          configDialogVisible.value = false
          await loadModels()
        } else {
          ElMessage.error(res.message || '创建失败')
        }
      }
    } catch (e) {
      console.error('保存配置失败', e)
      ElMessage.error('保存配置失败，请重试')
    } finally {
      configSaving.value = false
    }
  })
}

async function handleDeleteModel(model: any) {
  try {
    await ElMessageBox.confirm(`确定要删除模型「${model.name}」吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const res: any = await deleteLLMConfig(model.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      await loadModels()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除模型失败', e)
      ElMessage.error('删除失败，请重试')
    }
  }
}

async function handleTestConnection(model?: any) {
  // 确定使用哪个数据源
  const useForm = !model || configDialogVisible.value
  const dataSource = useForm ? configForm : model
  
  // 如果使用表单数据，先验证必填字段
  if (useForm) {
    if (!configFormRef.value) return
    
    // 使用 validate 方法验证所有必填字段
    const valid = await configFormRef.value.validate()
    
    if (!valid) {
      ElMessage.warning('请填写完整的必填信息')
      return
    }
  }
  
  testingConnection.value = true
  try {
    const sendData = {
      baseUrl: (dataSource.baseUrl || '').trim(),
      apiKey: dataSource.apiKey || '',
      modelName: (dataSource.modelName || '').trim(),
      modelType: dataSource.modelType || 'llm',
      type: dataSource.type || 'xinference',
    }
    console.log('发送到后端的数据:', sendData)
    
    // 验证发送的数据
    if (!sendData.baseUrl) {
      ElMessage.warning('服务地址不能为空')
      testingConnection.value = false
      return
    }
    if (!sendData.modelName) {
      ElMessage.warning('模型名称不能为空')
      testingConnection.value = false
      return
    }
    
    const res: any = await testLLMConnection(sendData)
    if (res.code === 0) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error(res.message || '连接测试失败')
    }
  } catch (e: any) {
    console.error('连接测试失败', e)
    ElMessage.error(e.response?.data?.message || e.message || '连接测试失败')
  } finally {
    testingConnection.value = false
  }
}

onMounted(() => {
  loadModels()
})
</script>

<style lang="scss" scoped>
.model-config-view {
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

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.toolbar-left {
  .toolbar-title {
    font-size: 16px;
    font-weight: 600;
    color: $text-primary;
  }
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sort-select {
  width: 120px;
}

.search-input {
  width: 200px;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.model-card {
  background: #fff;
  border: 1px solid $card-border;
  border-radius: $card-radius;
  padding: 20px;
  transition: all 0.2s ease;

  &:hover {
    border-color: $primary-color;
    box-shadow: 0 2px 12px rgba(64, 128, 255, 0.1);
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.provider-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #fff;

  &.provider-vllm {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  }

  &.provider-xinference {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  }

  &.provider-ollama {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  }

  &.provider-openai {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  }

  &.provider-newapi {
    background: linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%);
  }

  &.provider-default {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  }
}

.model-title {
  flex: 1;
}

.model-name {
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
  display: flex;
  align-items: center;
  gap: 8px;

  .default-tag {
    font-size: 11px;
    padding: 1px 6px;
    line-height: 1;
  }
}

.model-meta {
  font-size: 12px;
  color: $text-secondary;
  margin-top: 4px;
}

.card-menu {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;

  &:hover {
    background-color: #f5f7fa;
  }

  .el-icon {
    font-size: 16px;
    color: $text-secondary;
  }
}

.card-body {
  padding-top: 12px;
  border-top: 1px solid $card-border;
}

.model-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  &:last-child {
    margin-bottom: 0;
  }
}

.info-label {
  font-size: 12px;
  color: $text-secondary;
  width: 60px;
  flex-shrink: 0;
}

.info-value {
  font-size: 13px;
  color: $text-primary;
  font-family: 'Courier New', monospace;
}
</style>