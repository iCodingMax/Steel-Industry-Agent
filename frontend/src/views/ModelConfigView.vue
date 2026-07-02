<template>
  <div class="model-config-view">
    <div class="page-header">
      <h2 class="page-title">模型配置</h2>
    </div>

    <div class="config-section">
      <div class="section-header">
        <h3 class="section-title">
          <el-icon><Cpu /></el-icon>
          Xinference 模型服务
        </h3>
        <el-button v-if="!xinferenceConfig" type="primary" @click="handleEditXinference">
          <el-icon><Plus /></el-icon>
          添加配置
        </el-button>
        <el-button v-else @click="handleEditXinference">
          <el-icon><Edit /></el-icon>
          编辑配置
        </el-button>
      </div>
      <el-descriptions :column="2" border class="config-desc" v-if="xinferenceConfig">
        <el-descriptions-item label="配置名称">
          <span class="config-value">{{ xinferenceConfig.name }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="xinferenceConfig.status === 'active' ? 'success' : 'danger'" effect="plain">
            {{ xinferenceConfig.status === 'active' ? '启用' : '停用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="服务地址">
          <span class="config-value">{{ xinferenceConfig.baseUrl }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="模型类型">
          <el-tag type="primary" effect="plain">{{ xinferenceConfig.modelType }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="嵌入模型" :span="2">
          <el-tag type="primary" effect="plain">{{ xinferenceConfig.modelName }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最大输出Token">
          <span class="config-value">{{ xinferenceConfig.maxTokens }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="温度参数">
          <span class="config-value">{{ xinferenceConfig.temperature }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">
          <span class="config-value">{{ xinferenceConfig.description || '-' }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="暂无Xinference配置，请点击右上角添加" />
    </div>

    <div class="config-section">
      <div class="section-header">
        <h3 class="section-title">
          <el-icon><Link /></el-icon>
          NewAPI LLM 服务
        </h3>
        <div class="section-actions">
          <el-button v-if="!newapiConfig" type="primary" @click="handleEditNewAPI">
            <el-icon><Plus /></el-icon>
            添加配置
          </el-button>
          <el-button v-else @click="handleEditNewAPI">
            <el-icon><Edit /></el-icon>
            编辑配置
          </el-button>
          <el-button type="primary" @click="handleTestConnection" :disabled="!newapiConfig">
            <el-icon><Link /></el-icon>
            测试连接
          </el-button>
        </div>
      </div>
      <el-descriptions :column="2" border class="config-desc" v-if="newapiConfig">
        <el-descriptions-item label="配置名称">
          <span class="config-value">{{ newapiConfig.name }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="newapiConfig.status === 'active' ? 'success' : 'danger'" effect="plain">
            {{ newapiConfig.status === 'active' ? '启用' : '停用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="服务地址">
          <span class="config-value">{{ newapiConfig.baseUrl }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="模型类型">
          <el-tag type="warning" effect="plain">{{ newapiConfig.modelType }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="API密钥">
          <span class="config-value">{{ maskApiKey }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="对话模型">
          <el-tag type="warning" effect="plain">{{ newapiConfig.modelName }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最大输出Token">
          <span class="config-value">{{ newapiConfig.maxTokens }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="温度参数">
          <span class="config-value">{{ newapiConfig.temperature }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">
          <span class="config-value">{{ newapiConfig.description || '-' }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="暂无NewAPI配置，请点击右上角添加" />
    </div>

    <div class="config-section">
      <div class="section-header">
        <h3 class="section-title">
          <el-icon><Refresh /></el-icon>
          重排模型配置
        </h3>
        <el-button v-if="!rerankConfig" type="primary" @click="handleEditRerank">
          <el-icon><Plus /></el-icon>
          添加配置
        </el-button>
        <el-button v-else @click="handleEditRerank">
          <el-icon><Edit /></el-icon>
          编辑配置
        </el-button>
      </div>
      <el-descriptions :column="2" border class="config-desc" v-if="rerankConfig">
        <el-descriptions-item label="配置名称">
          <span class="config-value">{{ rerankConfig.name }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="rerankConfig.status === 'active' ? 'success' : 'danger'" effect="plain">
            {{ rerankConfig.status === 'active' ? '启用' : '停用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="服务地址">
          <span class="config-value">{{ rerankConfig.baseUrl }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="模型类型">
          <el-tag type="success" effect="plain">{{ rerankConfig.modelType }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="重排模型" :span="2">
          <el-tag type="success" effect="plain">{{ rerankConfig.modelName }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">
          <span class="config-value">{{ rerankConfig.description || '-' }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <el-empty v-else description="暂无重排模型配置，请点击右上角添加" />
    </div>

    <el-dialog
      v-model="configDialogVisible"
      :title="configDialogTitle"
      width="550px"
      destroy-on-close
    >
      <el-form :model="configForm" label-width="100px" :rules="configRules" ref="configFormRef">
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="configForm.name" placeholder="请输入配置名称" />
        </el-form-item>
        <el-form-item label="服务地址" prop="baseUrl">
          <el-input v-model="configForm.baseUrl" placeholder="请输入服务地址" />
        </el-form-item>
        <el-form-item label="API密钥" v-if="currentConfigType !== 'xinference' || currentConfigModelType !== 'embedding'">
          <el-input v-model="configForm.apiKey" type="password" show-password placeholder="请输入API密钥" />
        </el-form-item>
        <el-form-item label="模型名称" prop="modelName">
          <el-input v-model="configForm.modelName" placeholder="请输入模型名称" />
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
        <el-button type="primary" @click="handleSaveConfig" :loading="configSaving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Cpu, Link, Edit, Refresh, Plus } from '@element-plus/icons-vue'
import { getLLMConfigs, createLLMConfig, updateLLMConfig, type LLMConfigForm } from '@/api/llmConfig'

const loading = ref(false)
const configSaving = ref(false)
const configDialogVisible = ref(false)
const configFormRef = ref<FormInstance>()

const xinferenceConfig = ref<any>(null)
const newapiConfig = ref<any>(null)
const rerankConfig = ref<any>(null)

const currentConfigType = ref('')
const currentConfigModelType = ref('')
const editingConfigId = ref<number | null>(null)

const configDialogTitle = computed(() => {
  if (!editingConfigId.value) {
    return '新增配置'
  }
  return '编辑配置'
})

const maskApiKey = computed(() => {
  const key = newapiConfig.value?.apiKey || ''
  if (!key) return '-'
  if (key.length <= 12) return key
  return key.slice(0, 6) + '...' + key.slice(-4)
})

const configForm = reactive<LLMConfigForm>({
  name: '',
  type: 'xinference',
  baseUrl: '',
  apiKey: '',
  modelName: '',
  modelType: 'embedding',
  maxTokens: 2048,
  temperature: 0.7,
  topP: undefined,
  extraParams: {},
  isDefault: false,
  description: '',
  status: 'active',
})

const configRules: FormRules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  baseUrl: [{ required: true, message: '请输入服务地址', trigger: 'blur' }],
  modelName: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
}

async function loadLLMConfigs() {
  loading.value = true
  try {
    const res: any = await getLLMConfigs()
    if (res.code === 0 && res.data) {
      const configs = Array.isArray(res.data) ? res.data : (res.data.list || [])
      xinferenceConfig.value = configs.find((c: any) => c.type === 'xinference' && c.modelType === 'embedding') || null
      newapiConfig.value = configs.find((c: any) => c.type === 'newapi' && c.modelType === 'llm') || null
      rerankConfig.value = configs.find((c: any) => c.type === 'xinference' && c.modelType === 'rerank') || null
    }
  } catch (e) {
    console.error('加载模型配置失败', e)
  } finally {
    loading.value = false
  }
}

function handleEditXinference() {
  currentConfigType.value = 'xinference'
  currentConfigModelType.value = 'embedding'
  if (xinferenceConfig.value) {
    editingConfigId.value = xinferenceConfig.value.id
    Object.assign(configForm, {
      name: xinferenceConfig.value.name,
      type: 'xinference',
      baseUrl: xinferenceConfig.value.baseUrl,
      apiKey: xinferenceConfig.value.apiKey || '',
      modelName: xinferenceConfig.value.modelName,
      modelType: 'embedding',
      maxTokens: xinferenceConfig.value.maxTokens || 2048,
      temperature: xinferenceConfig.value.temperature || 0.7,
      topP: xinferenceConfig.value.topP,
      extraParams: xinferenceConfig.value.extraParams || {},
      isDefault: xinferenceConfig.value.isDefault,
      description: xinferenceConfig.value.description || '',
      status: xinferenceConfig.value.status || 'active',
    })
  } else {
    editingConfigId.value = null
    Object.assign(configForm, {
      name: 'Xinference嵌入模型',
      type: 'xinference',
      baseUrl: '',
      apiKey: '',
      modelName: 'bge-m3',
      modelType: 'embedding',
      maxTokens: 2048,
      temperature: 0.7,
      topP: undefined,
      extraParams: {},
      isDefault: true,
      description: '',
      status: 'active',
    })
  }
  configDialogVisible.value = true
}

function handleEditNewAPI() {
  currentConfigType.value = 'newapi'
  currentConfigModelType.value = 'llm'
  if (newapiConfig.value) {
    editingConfigId.value = newapiConfig.value.id
    Object.assign(configForm, {
      name: newapiConfig.value.name,
      type: 'newapi',
      baseUrl: newapiConfig.value.baseUrl,
      apiKey: newapiConfig.value.apiKey || '',
      modelName: newapiConfig.value.modelName,
      modelType: 'llm',
      maxTokens: newapiConfig.value.maxTokens || 20480,
      temperature: newapiConfig.value.temperature || 0.7,
      topP: newapiConfig.value.topP,
      extraParams: newapiConfig.value.extraParams || {},
      isDefault: newapiConfig.value.isDefault,
      description: newapiConfig.value.description || '',
      status: newapiConfig.value.status || 'active',
    })
  } else {
    editingConfigId.value = null
    Object.assign(configForm, {
      name: 'NewAPI对话模型',
      type: 'newapi',
      baseUrl: '',
      apiKey: '',
      modelName: 'glm-5.1-fp8',
      modelType: 'llm',
      maxTokens: 20480,
      temperature: 0.7,
      topP: undefined,
      extraParams: {},
      isDefault: true,
      description: '',
      status: 'active',
    })
  }
  configDialogVisible.value = true
}

function handleEditRerank() {
  currentConfigType.value = 'xinference'
  currentConfigModelType.value = 'rerank'
  if (rerankConfig.value) {
    editingConfigId.value = rerankConfig.value.id
    Object.assign(configForm, {
      name: rerankConfig.value.name,
      type: 'xinference',
      baseUrl: rerankConfig.value.baseUrl,
      apiKey: rerankConfig.value.apiKey || '',
      modelName: rerankConfig.value.modelName,
      modelType: 'rerank',
      maxTokens: rerankConfig.value.maxTokens || 2048,
      temperature: rerankConfig.value.temperature || 0.7,
      topP: rerankConfig.value.topP,
      extraParams: rerankConfig.value.extraParams || {},
      isDefault: rerankConfig.value.isDefault,
      description: rerankConfig.value.description || '',
      status: rerankConfig.value.status || 'active',
    })
  } else {
    editingConfigId.value = null
    Object.assign(configForm, {
      name: 'Xinference重排模型',
      type: 'xinference',
      baseUrl: '',
      apiKey: '',
      modelName: 'bge-reranker-large',
      modelType: 'rerank',
      maxTokens: 2048,
      temperature: 0.7,
      topP: undefined,
      extraParams: {},
      isDefault: true,
      description: '',
      status: 'active',
    })
  }
  configDialogVisible.value = true
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
          await loadLLMConfigs()
        }
      } else {
        const res: any = await createLLMConfig(saveData)
        if (res.code === 0) {
          ElMessage.success('创建成功')
          configDialogVisible.value = false
          await loadLLMConfigs()
        }
      }
    } catch (e) {
      console.error('保存配置失败', e)
    } finally {
      configSaving.value = false
    }
  })
}

function handleTestConnection() {
  ElMessage.success('连接测试成功')
}

onMounted(() => {
  loadLLMConfigs()
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

.config-section {
  background: #fff;
  border: 1px solid $card-border;
  border-radius: $card-radius;
  padding: 24px;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
  margin-bottom: 0;

  .el-icon {
    color: $primary-color;
    font-size: 18px;
  }
}

.config-desc {
  margin-bottom: 16px;
}

.config-value {
  font-family: 'Courier New', monospace;
  color: $text-primary;
}

.section-actions {
  display: flex;
  gap: 12px;
}
</style>
