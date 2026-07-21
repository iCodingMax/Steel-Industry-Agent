<template>
  <div class="app-integration-view">
    <div class="page-header">
      <h2 class="page-title">集成设置</h2>
    </div>

    <el-card shadow="never" class="main-card">
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="app-select-section">
            <h3 class="section-title">选择应用</h3>
            <el-select v-model="selectedAppId" placeholder="请选择应用" style="width: 100%" @change="handleAppChange">
              <el-option v-for="app in applications" :key="app.id" :label="app.name" :value="app.id" />
            </el-select>
          </div>
        </el-col>
        <el-col :span="18">
          <template v-if="currentApp">
            <div class="integration-content">
              <el-card shadow="never" class="embed-card">
                <template #header>
                  <span class="card-title">iFrame嵌入代码</span>
                </template>
                <el-form :model="integrationForm" label-width="120px">
                  <el-row :gutter="20">
                    <el-col :span="8">
                      <el-form-item label="嵌入宽度">
                        <el-input v-model="integrationForm.iframeWidth" placeholder="例如：400px 或 100%" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="嵌入高度">
                        <el-input v-model="integrationForm.iframeHeight" placeholder="例如：600px" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="边框样式">
                        <el-select v-model="integrationForm.iframeBorder" placeholder="选择边框">
                          <el-option label="无边框" value="0" />
                          <el-option label="细边框" value="1px solid #ccc" />
                          <el-option label="圆角边框" value="1px solid #ccc; border-radius: 8px" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                  </el-row>
                </el-form>

                <div class="code-section">
                  <div class="code-header">
                    <span>嵌入代码</span>
                    <el-button type="text" @click="copyEmbedCode">
                      <el-icon><CopyDocument /></el-icon>
                      复制代码
                    </el-button>
                  </div>
                  <pre class="code-block"><code>{{ embedCode }}</code></pre>
                </div>

                <div class="preview-section">
                  <div class="preview-header">
                    <span>预览效果</span>
                  </div>
                  <div class="preview-container">
                    <iframe :src="previewUrl" :width="integrationForm.iframeWidth" :height="integrationForm.iframeHeight" :style="{ border: integrationForm.iframeBorder === '0' ? 'none' : integrationForm.iframeBorder }" title="智能助手嵌入预览"></iframe>
                  </div>
                </div>
              </el-card>

              <el-card shadow="never" class="api-card">
                <template #header>
                  <span class="card-title">API密钥管理</span>
                </template>
                <div class="api-key-section">
                  <div class="api-key-row">
                    <label>API密钥</label>
                    <div class="api-key-value">
                      <span class="key-masked">{{ maskedApiKey }}</span>
                      <el-button type="text" @click="toggleApiKeyVisibility" size="small">
                        {{ showApiKey ? '隐藏' : '显示' }}
                      </el-button>
                    </div>
                  </div>
                  <div class="api-key-actions">
                    <el-button type="warning" @click="handleRegenerateApiKey">重新生成密钥</el-button>
                    <el-button type="primary" @click="copyApiKey">复制密钥</el-button>
                  </div>
                  <p class="api-tip">
                    <el-icon><InfoFilled /></el-icon>
                    密钥用于验证嵌入请求的合法性。重新生成后，旧密钥将立即失效。
                  </p>
                </div>
              </el-card>

              <el-card shadow="never" class="security-card">
                <template #header>
                  <span class="card-title">安全设置</span>
                </template>
                <el-form :model="integrationForm" label-width="120px">
                  <el-form-item label="允许的来源">
                    <el-input v-model="allowedOriginsText" type="textarea" :rows="3" placeholder="输入允许嵌入的域名，每行一个，如：https://example.com" />
                    <p class="form-tip">留空则允许所有来源，建议限制为具体域名以提高安全性</p>
                  </el-form-item>
                  <el-form-item label="自定义域名">
                    <el-input v-model="integrationForm.customDomain" placeholder="如：https://chat.example.com" />
                    <p class="form-tip">设置后可使用自定义域名访问嵌入页面</p>
                  </el-form-item>
                </el-form>
                <el-button type="primary" @click="handleSaveIntegration">保存设置</el-button>
              </el-card>

              <el-card shadow="never" class="usage-card">
                <template #header>
                  <span class="card-title">使用说明</span>
                </template>
                <div class="usage-steps">
                  <h4>嵌入到业务系统</h4>
                  <ol>
                    <li>复制上方的iFrame代码</li>
                    <li>将代码粘贴到业务系统页面的HTML中</li>
                    <li>根据需要调整宽度和高度</li>
                    <li>确保业务系统域名已添加到"允许的来源"列表中</li>
                  </ol>
                  <h4>API调用方式</h4>
                  <pre class="code-block small"><code>POST /api/v1/sessions/embed/chat
Content-Type: application/json
X-API-Key: {{ currentApp.apiKey }}

{
  "applicationId": {{ currentApp.id }},
  "question": "用户问题",
  "sessionId": "可选，用于保持对话上下文"
}</code></pre>
                </div>
              </el-card>
            </div>
          </template>

          <div v-else class="empty-state">
            <el-empty description="请先选择一个应用" />
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, InfoFilled } from '@element-plus/icons-vue'
import { getApplications, getApplication, regenerateApiKey, updateApplication, type Application } from '@/api/application'

const loading = ref(false)
const selectedAppId = ref<number | null>(null)
const currentApp = ref<Application | null>(null)
const applications = ref<Application[]>([])
const showApiKey = ref(false)
const saving = ref(false)

const integrationForm = reactive({
  iframeWidth: '400px',
  iframeHeight: '600px',
  iframeBorder: '0',
  customDomain: '',
})

const allowedOriginsText = ref('')

const maskedApiKey = computed(() => {
  if (!currentApp.value?.apiKey) return ''
  if (showApiKey.value) return currentApp.value.apiKey
  return currentApp.value.apiKey.substring(0, 8) + '****************'
})

const previewUrl = computed(() => {
  if (!currentApp.value) return ''
  return `/chat/embed/${currentApp.value.id}`
})

const embedCode = computed(() => {
  if (!currentApp.value) return ''
  const origin = window.location.origin
  const url = `${origin}/chat/embed/${currentApp.value.id}`
  const borderStyle = integrationForm.iframeBorder === '0' ? 'none' : integrationForm.iframeBorder
  return `<iframe src="${url}" width="${integrationForm.iframeWidth}" height="${integrationForm.iframeHeight}" style="border: ${borderStyle}" frameborder="0" title="智能助手"></iframe>`
})

async function loadApplications() {
  try {
    const res = await getApplications({
      page: 1,
      pageSize: 100,
    })
    applications.value = (res.data as any).data || []
  } catch (error) {
    ElMessage.error('加载应用列表失败')
  }
}

async function handleAppChange(appId: number) {
  if (!appId) {
    currentApp.value = null
    return
  }
  try {
    const res = await getApplication(appId)
    const appData = res.data as any
    currentApp.value = appData
    integrationForm.iframeWidth = appData?.iframeWidth || '400px'
    integrationForm.iframeHeight = String(appData?.iframeHeight) || '600px'
    integrationForm.customDomain = currentApp.value?.customDomain || ''
    allowedOriginsText.value = (currentApp.value?.iframeAllowedOrigins || []).join('\n')
  } catch (error) {
    ElMessage.error('加载应用详情失败')
  }
}

function toggleApiKeyVisibility() {
  showApiKey.value = !showApiKey.value
}

async function copyEmbedCode() {
  try {
    await navigator.clipboard.writeText(embedCode.value)
    ElMessage.success('嵌入代码已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function copyApiKey() {
  if (!currentApp.value?.apiKey) return
  try {
    await navigator.clipboard.writeText(currentApp.value.apiKey)
    ElMessage.success('API密钥已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function handleRegenerateApiKey() {
  if (!currentApp.value) return
  try {
    await ElMessageBox.confirm('重新生成API密钥后，旧密钥将立即失效，是否继续？', '确认', {
      type: 'warning',
    })
    const res = await regenerateApiKey(currentApp.value.id)
    currentApp.value.apiKey = (res.data.data as { apiKey: string }).apiKey
    showApiKey.value = true
    ElMessage.success('API密钥已重新生成')
  } catch {
  }
}

async function handleSaveIntegration() {
  if (!currentApp.value) return
  saving.value = true
  try {
    const allowedOrigins = allowedOriginsText.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line)

    await updateApplication(currentApp.value.id, {
      iframeWidth: integrationForm.iframeWidth,
      iframeHeight: parseInt(integrationForm.iframeHeight) || 600,
      iframeAllowedOrigins: allowedOrigins,
      customDomain: integrationForm.customDomain,
    })
    ElMessage.success('集成设置已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadApplications()
})
</script>

<style lang="scss" scoped>
.app-integration-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }

  .page-title {
    font-size: 20px;
    font-weight: 600;
    color: #1a1a2e;
    margin: 0;
  }

  .main-card {
    padding: 20px;
  }

  .app-select-section {
    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: #374151;
      margin-bottom: 12px;
    }
  }

  .integration-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .embed-card,
  .api-card,
  .security-card,
  .usage-card {
    .card-title {
      font-size: 15px;
      font-weight: 600;
      color: #1e293b;
    }
  }

  .code-section {
    margin-top: 16px;

    .code-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      font-size: 13px;
      color: #64748b;
    }

    .code-block {
      background: #1e293b;
      color: #e2e8f0;
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      font-size: 13px;
      margin: 0;

      &.small {
        font-size: 12px;
        padding: 10px;
      }
    }
  }

  .preview-section {
    margin-top: 16px;

    .preview-header {
      font-size: 13px;
      color: #64748b;
      margin-bottom: 8px;
    }

    .preview-container {
      border: 1px dashed #cbd5e1;
      border-radius: 8px;
      padding: 16px;
      background: #f8fafc;

      iframe {
        display: block;
        margin: 0 auto;
        background: #fff;
        border-radius: 4px;
      }
    }
  }

  .api-key-section {
    .api-key-row {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-bottom: 12px;

      label {
        font-size: 14px;
        color: #374151;
        font-weight: 500;
      }

      .api-key-value {
        flex: 1;
        display: flex;
        align-items: center;
        gap: 8px;
        background: #f3f4f6;
        padding: 8px 12px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 14px;
        color: #1f2937;
      }
    }

    .api-key-actions {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
    }

    .api-tip {
      font-size: 12px;
      color: #6b7280;
      margin: 0;
      padding-left: 20px;
    }
  }

  .form-tip {
    margin-top: 8px;
    font-size: 12px;
    color: #94a3b8;
  }

  .usage-steps {
    h4 {
      font-size: 14px;
      font-weight: 600;
      color: #374151;
      margin: 16px 0 8px;
    }

    ol {
      margin: 0;
      padding-left: 20px;
      font-size: 13px;
      color: #4b5563;
      line-height: 1.8;
    }
  }

  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 400px;
  }
}
</style>
