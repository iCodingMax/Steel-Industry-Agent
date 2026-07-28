<template>
  <div class="app-list-view">
    <template v-if="!currentApp">
      <div class="page-header">
        <h2 class="page-title">应用管理</h2>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新建应用
        </el-button>
      </div>

      <div class="app-grid">
        <div v-for="app in applications" :key="app.id" class="app-card" @click="handleDetail(app)">
          <div class="app-icon">
            <el-icon :size="28"><Setting /></el-icon>
          </div>
          <div class="app-info">
            <h3 class="app-name">{{ app.name }}</h3>
            <p class="app-desc">{{ app.description || '暂无描述' }}</p>
            <div class="app-meta">
              <span class="app-model">
                <el-icon><Monitor /></el-icon>
                {{ app.modelName }}
              </span>
              <span class="app-status" :class="app.status">
                {{ statusText[app.status] || app.status }}
              </span>
            </div>
          </div>
          <div class="app-actions">
            <el-button text type="primary" @click.stop="handleDetail(app)">
              <el-icon><View /></el-icon>
              管理
            </el-button>
          </div>
        </div>

        <div class="app-card add-app" @click="handleCreate">
          <el-icon :size="48" class="add-icon"><Plus /></el-icon>
          <span>新建应用</span>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="app-detail-view">
        <div class="page-header">
          <div class="header-left">
            <el-button text @click="backToList">
              <el-icon><ArrowLeft /></el-icon>
              返回列表
            </el-button>
            <h2 class="page-title">{{ currentApp?.name }}</h2>
        </div>
        <div class="header-actions">
          <el-button @click="handleDeleteApp">删除应用</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
          <el-button type="success" @click="handlePublish">发布</el-button>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="app-tabs">
        <el-tab-pane label="应用设置" name="settings">
          <div class="settings-layout">
            <div class="settings-left">
              <el-form :model="appForm" label-width="120px" :rules="appRules" ref="appFormRef" class="app-form">
                <el-card shadow="never" class="form-card">
                  <template #header>
                    <span class="card-title">基本信息</span>
                  </template>
                  <el-form-item label="应用名称" prop="name">
                    <el-input v-model="appForm.name" placeholder="请输入应用名称" />
                  </el-form-item>
                  <el-form-item label="应用描述">
                    <el-input v-model="appForm.description" type="textarea" :rows="2" placeholder="请输入应用描述" />
                  </el-form-item>
                </el-card>

                <el-card shadow="never" class="form-card">
                  <template #header>
                    <span class="card-title">AI模型设置</span>
                  </template>
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="LLM模型">
                        <el-select v-model="appForm.modelName" placeholder="请选择模型">
                          <el-option v-for="model in llmModels" :key="model.id" :label="model.modelName" :value="model.modelName" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="最大输出Token">
                        <el-input-number v-model="appForm.maxTokens" :min="1024" :max="100000" style="width: 100%" />
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="20">
                    <el-col :span="12">
                      <el-form-item label="温度参数">
                        <el-slider v-model="appForm.temperature" :min="0" :max="2" :step="0.1" />
                        <span class="slider-value">{{ appForm.temperature }}</span>
                      </el-form-item>
                    </el-col>
                    <el-col :span="12">
                      <el-form-item label="Top-P参数">
                        <el-slider v-model="appForm.topP" :min="0" :max="1" :step="0.05" />
                        <span class="slider-value">{{ appForm.topP }}</span>
                      </el-form-item>
                    </el-col>
                  </el-row>
                </el-card>

                <el-card shadow="never" class="form-card">
                  <template #header>
                    <span class="card-title">提示词设置</span>
                  </template>
                  <el-form-item label="系统提示词">
                    <div class="textarea-wrapper">
                      <el-input 
                        ref="systemPromptRef"
                        v-model="appForm.systemPrompt" 
                        type="textarea" 
                        :rows="5" 
                        placeholder="请输入系统提示词，定义AI助手的角色和行为准则"
                        @focus="systemPromptFocused = true"
                        @blur="systemPromptFocused = false"
                        @input="checkPromptOverflow"
                      />
                      <div class="textarea-ellipsis" v-if="appForm.systemPrompt && !systemPromptFocused && isPromptOverflow">...</div>
                    </div>
                  </el-form-item>
                  <el-form-item label="用户提示词模板">
                    <el-input v-model="appForm.userPromptTemplate" type="textarea" :rows="3" placeholder="用户输入会被填充到这个模板中，例如：请基于以下知识回答问题：{{question}}" />
                  </el-form-item>
                </el-card>

                <el-card shadow="never" class="form-card">
                  <template #header>
                    <span class="card-title">关联设置</span>
                  </template>
                  <el-form-item label="关联知识库">
                    <el-select v-model="appForm.knowledgeBaseIds" multiple placeholder="请选择知识库" style="width: 100%">
                      <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
                    </el-select>
                    <p class="form-tip">选择后，AI将基于这些知识库的内容进行回答</p>
                  </el-form-item>
                  <el-form-item label="关联数据库">
                    <el-select v-model="appForm.datasourceIds" multiple placeholder="请选择数据源" style="width: 100%">
                      <el-option v-for="ds in datasources" :key="ds.id" :label="ds.name" :value="ds.id" />
                    </el-select>
                    <p class="form-tip">选择后，AI将基于数据库中的数据进行问答</p>
                  </el-form-item>
                </el-card>

                <el-card shadow="never" class="form-card">
                  <template #header>
                    <span class="card-title">开场白设置</span>
                  </template>
                  <el-form-item label="开场白消息">
                    <el-input v-model="appForm.greetingMessage" type="textarea" :rows="3" placeholder="用户首次进入对话时显示的欢迎消息" />
                  </el-form-item>
                </el-card>

                <el-card shadow="never" class="form-card">
                  <template #header>
                    <span class="card-title">集成设置</span>
                  </template>
                  <el-form-item label="公开访问">
                    <div class="integration-content">
                      <div class="public-link-section">
                        <div class="link-row">
                          <span class="link-label">公开访问链接</span>
                          <el-switch v-model="publicAccessEnabled" active-text="开启" inactive-text="关闭" />
                        </div>
                        <div class="link-display" v-if="publicAccessEnabled">
                          <input type="text" :value="publicAccessUrl" readonly class="link-input" />
                          <el-button type="text" @click="copyPublicLink" class="copy-btn">
                            <el-icon><CopyDocument /></el-icon>
                          </el-button>
                          <el-button type="text" @click="openPublicLink" class="open-btn">
                            <el-icon><View /></el-icon>
                          </el-button>
                        </div>
                      </div>
                      <div class="action-buttons">
                        <el-button class="action-btn" @click="openChat">
                          <el-icon><Message /></el-icon>
                          <span>去对话</span>
                        </el-button>
                        <el-button class="action-btn" @click="showEmbedModal = true">
                          <el-icon><Monitor /></el-icon>
                          <span>嵌入第三方</span>
                        </el-button>
                        <el-button class="action-btn" @click="showAccessModal = true">
                          <el-icon><Setting /></el-icon>
                          <span>访问限制</span>
                        </el-button>
                      </div>
                    </div>
                  </el-form-item>
                </el-card>
              </el-form>
            </div>

            <div class="settings-right">
              <el-card shadow="never" class="preview-card">
                <template #header>
                  <div class="preview-header">
                    <span class="card-title">调试预览</span>
                    <el-button class="refresh-btn" @click="clearMessages" title="清理历史记录">
                      <el-icon><RefreshLeft /></el-icon>
                      <span>清理</span>
                    </el-button>
                  </div>
                </template>
                <div class="chat-container">
                  <div ref="chatMessagesRef" class="chat-messages">
                    <div v-if="debugMessages.length === 0" class="chat-welcome">
                      <div class="welcome-icon">
                        <svg class="robot-icon" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                          <!-- 天线 -->
                          <line x1="32" y1="4" x2="32" y2="14" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
                          <circle cx="32" cy="4" r="3" fill="#fbbf24"/>
                          <!-- 头部 -->
                          <rect x="14" y="14" width="36" height="24" rx="6" fill="#e2e8f0"/>
                          <rect x="14" y="14" width="36" height="24" rx="6" stroke="#fff" stroke-width="1.5"/>
                          <!-- 眼睛 -->
                          <circle cx="24" cy="26" r="4" fill="#3b82f6"/>
                          <circle cx="40" cy="26" r="4" fill="#3b82f6"/>
                          <circle cx="24" cy="25" r="1.5" fill="#fff"/>
                          <circle cx="40" cy="25" r="1.5" fill="#fff"/>
                          <!-- 嘴巴 -->
                          <rect x="26" y="32" width="12" height="2.5" rx="1.25" fill="#3b82f6"/>
                          <!-- 身体 -->
                          <rect x="18" y="40" width="28" height="16" rx="4" fill="#cbd5e1"/>
                          <rect x="18" y="40" width="28" height="16" rx="4" stroke="#fff" stroke-width="1.5"/>
                          <!-- 身体按钮 -->
                          <circle cx="32" cy="48" r="3" fill="#3b82f6"/>
                          <circle cx="32" cy="48" r="1.2" fill="#fff"/>
                          <!-- 手臂 -->
                          <rect x="6" y="42" width="10" height="6" rx="3" fill="#94a3b8"/>
                          <rect x="48" y="42" width="10" height="6" rx="3" fill="#94a3b8"/>
                          <!-- 钢铁火花装饰 -->
                          <circle cx="10" cy="38" r="1" fill="#fbbf24"/>
                          <circle cx="54" cy="38" r="1" fill="#fbbf24"/>
                          <circle cx="8" cy="50" r="0.8" fill="#fb923c"/>
                          <circle cx="56" cy="50" r="0.8" fill="#fb923c"/>
                        </svg>
                      </div>
                      <p>{{ appForm.greetingMessage || '你好，有什么我可以帮你的吗？' }}</p>
                    </div>
                    <div
                      v-for="msg in debugMessages"
                      :key="msg.id"
                      class="message-item"
                      :class="[msg.role, msg.type || '']"
                    >
                      <div v-if="msg.role === 'user'" class="message-content user">
                        <div class="avatar-group">
                          <AvatarImage type="user" />
                        </div>
                        <div class="message-bubble-wrap">
                          <div class="message-bubble">
                            <div class="bubble-arrow"></div>
                            <div class="bubble-content">{{ msg.content }}</div>
                          </div>
                        </div>
                      </div>
                      <div v-else class="message-content assistant">
                        <div class="avatar-group">
                          <AvatarImage type="assistant" />
                        </div>
                        <div class="message-bubble-wrap">
                          <div class="thinking-process" v-if="(msg.thinkingSteps && msg.thinkingSteps.length > 0) || (msg.sqlTraces && msg.sqlTraces.length > 0)">
                            <div class="thinking-header" @click="toggleThinking(String(msg.id))">
                              <el-icon :class="{ 'rotated': thinkingExpanded[String(msg.id)] }"><ArrowRight /></el-icon>
                              <span class="thinking-title">思考过程</span>
                              <span class="thinking-count">{{ msg.thinkingSteps?.length || 0 }} 步</span>
                              <span class="thinking-action">{{ thinkingExpanded[String(msg.id)] ? '收起' : '展开' }}</span>
                            </div>
                            <div v-show="thinkingExpanded[String(msg.id)]" class="thinking-content">
                              <div v-if="msg.thinkingSteps && msg.thinkingSteps.length > 0" class="thinking-steps">
                                <div class="section-title">
                                  <el-icon><List /></el-icon>
                                  <span>执行步骤</span>
                                </div>
                                <div class="steps-timeline">
                                  <div v-for="(step, idx) in msg.thinkingSteps" :key="idx" class="step-item">
                                    <div class="step-connector">
                                      <div class="connector-line" :class="{ last: idx === msg.thinkingSteps!.length - 1 }"></div>
                                      <div class="step-dot" :class="{ active: idx === msg.thinkingSteps!.length - 1 && msg.isStreaming, completed: idx < msg.thinkingSteps!.length - 1 || !msg.isStreaming }">
                                        <el-icon v-if="idx === msg.thinkingSteps!.length - 1 && msg.isStreaming"><Loading class="step-loading" /></el-icon>
                                        <el-icon v-else-if="idx < msg.thinkingSteps!.length - 1 || !msg.isStreaming"><CircleCheck class="step-check" /></el-icon>
                                        <span v-else class="step-number-text">{{ step.step }}</span>
                                      </div>
                                    </div>
                                    <div class="step-content">
                                      <div class="step-title">{{ step.title }}</div>
                                      <div class="step-desc">{{ step.description }}</div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>

                          <!-- 消息气泡：始终显示，确保流式内容能实时展示 -->
                          <div class="message-bubble">
                            <div class="bubble-arrow"></div>
                            <!-- 打字指示器：仅在流式中且内容为空时显示 -->
                            <div v-if="msg.isStreaming && !msg.content" class="typing-indicator">
                              <span></span>
                              <span></span>
                              <span></span>
                            </div>
                            <!-- 消息内容：始终渲染，确保流式内容实时更新 -->
                            <template v-else>
                              <span class="message-text">{{ stripMarkdown(msg.content) }}</span>
                              <span v-if="msg.isStreaming" class="streaming-cursor">|</span>
                            </template>
                          </div>

                          <div v-if="msg.sqlTraces && msg.sqlTraces.length > 0" class="sql-section">
                            <div class="section-header">
                              <span>SQL查询</span>
                              <el-button text size="small" class="sql-copy-btn" @click="copySql(msg.sqlTraces[0].sql)">
                                <el-icon><CopyDocument /></el-icon>
                                复制
                              </el-button>
                            </div>
                            <div class="sql-content">
                              <pre class="sql-code">{{ msg.sqlTraces[0].sql }}</pre>
                              <div class="sql-meta">返回 {{ msg.sqlTraces[0].rows || 0 }} 行数据</div>
                            </div>
                          </div>

                          <div v-if="msg.dataResult && msg.dataResult.length > 0" class="chart-section">
                            <div class="section-header">
                              <el-icon><TrendCharts /></el-icon>
                              <span>数据可视化</span>
                              <div class="table-name-badge">表名：{{ getTableName(msg.sqlTraces || []) }}</div>
                              <div class="chart-view-toggle">
                                <el-radio-group v-model="dataViewMode[msg.id]" size="small">
                                  <el-radio-button value="table">表格</el-radio-button>
                                  <el-radio-button value="chart">图表</el-radio-button>
                                </el-radio-group>
                              </div>
                              <!-- 导出按钮 -->
                              <el-dropdown trigger="click" @command="(cmd: string) => handleDebugExport(cmd, msg)">
                                <el-button type="text" size="small" class="export-btn">
                                  <el-icon><Download /></el-icon>
                                  <span>导出</span>
                                </el-button>
                                <template #dropdown>
                                  <el-dropdown-menu>
                                    <el-dropdown-item command="excel">Excel</el-dropdown-item>
                                    <el-dropdown-item v-if="dataViewMode[msg.id] === 'chart'" command="image">图片</el-dropdown-item>
                                  </el-dropdown-menu>
                                </template>
                              </el-dropdown>
                            </div>
                            <div class="chart-body">
                              <div v-if="dataViewMode[msg.id] !== 'chart'" class="table-wrapper">
                                <el-table
                                  :data="msg.dataResult.slice(0, 100)"
                                  size="small"
                                  border
                                  max-height="400"
                                  stripe
                                  class="data-table"
                                >
                                  <el-table-column
                                    v-for="col in getDataColumns(msg.dataResult, msg.columnMeta)"
                                    :key="col.prop"
                                    :prop="col.prop"
                                    :label="col.label"
                                    :min-width="col.minWidth"
                                    show-overflow-tooltip
                                  />
                                </el-table>
                                <div v-if="msg.dataResult.length > 100" class="table-footer">
                                  仅展示前 100 行，共 {{ msg.dataResult.length }} 行
                                </div>
                              </div>
                              <div v-else class="chart-wrapper">
                                <div class="chart-controls">
                                  <el-select :model-value="getChartConfigValue(String(msg.id), 'chartType')" placeholder="图表类型" size="small" @change="(val: string) => { setChartConfigValue(String(msg.id), 'chartType', val); updateChartOption(String(msg.id), msg.columnMeta); }">
                                    <el-option label="柱状图" value="bar" />
                                    <el-option label="折线图" value="line" />
                                    <el-option label="饼图" value="pie" />
                                  </el-select>
                                  <el-select :model-value="getChartConfigValue(String(msg.id), 'xField')" placeholder="X轴" size="small" @change="(val: string) => { setChartConfigValue(String(msg.id), 'xField', val); updateChartOption(String(msg.id), msg.columnMeta); }">
                                    <el-option v-for="col in getDataColumns(msg.dataResult, msg.columnMeta)" :key="col.prop" :label="col.label" :value="col.prop" />
                                  </el-select>
                                  <el-select :model-value="getChartConfigValue(String(msg.id), 'yField')" placeholder="Y轴" size="small" @change="(val: string) => { setChartConfigValue(String(msg.id), 'yField', val); updateChartOption(String(msg.id), msg.columnMeta); }">
                                    <el-option v-for="col in getNumericColumns(msg.dataResult, msg.columnMeta)" :key="col.prop" :label="col.label" :value="col.prop" />
                                  </el-select>
                                </div>
                                <div v-if="chartConfig[String(msg.id)]?.option" class="chart-container">
                                  <ChartCard :option="chartConfig[String(msg.id)].option" />
                                </div>
                                <div v-else class="chart-placeholder">
                                  <el-icon :size="36" color="#cbd5e1">BarChart</el-icon>
                                  <p>请选择 X 轴和 Y 轴字段以生成图表</p>
                                </div>
                              </div>
                            </div>
                          </div>

                          <div v-if="msg.references && msg.references.length > 0" class="references-section">
                            <div class="references-header" @click="toggleReferences(String(msg.id))">
                              <el-icon :class="{ 'rotated': refsExpanded[String(msg.id)] }"><ArrowRight /></el-icon>
                              <span class="references-title">知识引用</span>
                              <span class="references-count">{{ msg.references.length }} 条</span>
                              <span class="references-action">{{ refsExpanded[String(msg.id)] ? '收起' : '展开' }}</span>
                            </div>
                            <div v-show="refsExpanded[String(msg.id)]" class="references-content">
                              <div class="ref-cards">
                                <div v-for="(ref, idx) in msg.references" :key="idx" class="ref-card">
                                  <div class="ref-header">
                                    <span class="ref-name">{{ ref.documentName }}</span>
                                    <span class="ref-score">{{ (ref.score * 100).toFixed(1) }}%</span>
                                  </div>
                                  <div class="ref-content">{{ ref.content.slice(0, 200) }}...</div>
                                </div>
                              </div>
                            </div>
                          </div>

                          <div v-if="msg.elapsedTime !== undefined" class="message-meta">
                            <span class="meta-time">耗时 {{ (msg.elapsedTime / 1000).toFixed(2) }}s</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="chat-input-area">
                    <div class="debug-input-wrapper">
                      <el-input
                        v-model="debugInput"
                        placeholder="请输入问题"
                        @keydown.enter.exact="handleDebugSend"
                        class="debug-input"
                      />
                      <el-button type="primary" :loading="debugSending" @click="handleDebugSend" class="send-btn">
                        <el-icon><Message /></el-icon>
                      </el-button>
                    </div>
                  </div>
                </div>
              </el-card>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
    </template>

    <el-dialog v-model="createDialogVisible" title="新建应用" width="500px" destroy-on-close>
      <el-form :model="createForm" label-width="100px" :rules="createRules" ref="createFormRef">
        <el-form-item label="应用名称" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入应用名称" />
        </el-form-item>
        <el-form-item label="应用描述">
          <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="请输入应用描述" />
        </el-form-item>
        <el-form-item label="LLM模型">
          <el-select v-model="createForm.modelName" placeholder="请选择模型">
            <el-option v-for="model in llmModels" :key="model.id" :label="model.modelName" :value="model.modelName" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEmbedModal" title="嵌入第三方" width="700px" destroy-on-close>
      <div class="embed-modal-content">
        <div class="embed-mode-tabs">
          <div class="embed-mode active">
            <div class="mode-icon full-icon">
              <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="4" y="8" width="40" height="32" rx="4" fill="#f1f5f9" stroke="#e2e8f0" stroke-width="2"/>
                <rect x="8" y="12" width="32" height="6" rx="2" fill="#cbd5e1"/>
                <rect x="8" y="22" width="28" height="14" rx="2" fill="#e2e8f0"/>
                <rect x="8" y="26" width="20" height="4" rx="1" fill="#cbd5e1"/>
              </svg>
            </div>
            <div class="mode-name">页面嵌入</div>
          </div>
        </div>

        <div class="embed-code-section">
          <div class="code-header">
            <span>复制以下代码进行嵌入</span>
            <el-button type="text" @click="copyEmbedCode" class="copy-code-btn">
              <el-icon><CopyDocument /></el-icon>
              复制代码
            </el-button>
          </div>
          <pre class="embed-code-block"><code>{{ currentEmbedCode }}</code></pre>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="showAccessModal" title="访问限制" width="500px" destroy-on-close>
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
      <template #footer>
        <el-button @click="showAccessModal = false">取消</el-button>
        <el-button type="primary" @click="handleSaveAccessSettings">保存设置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import * as XLSX from 'xlsx'
import { saveAs } from 'file-saver'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import ChartCard from '@/components/chart/ChartCard.vue'
import AvatarImage from '@/components/AvatarImage.vue'
import {
  Plus,
  Setting,
  Monitor,
  CopyDocument,
  Link,
  RefreshLeft,
  TrendCharts,
  Download,
} from '@element-plus/icons-vue'
import {
  getApplications,
  createApplication,
  updateApplication,
  deleteApplication,
  regenerateApiKey,
  type Application,
  type ApplicationCreateForm,
  type ApplicationUpdateForm,
} from '@/api/application'
import { getKnowledgeBases } from '@/api/knowledge'
import { getLLMConfigs, type LLMConfigForm } from '@/api/llmConfig'
import { getDatasources } from '@/api/datasource'

const loading = ref(false)
const saving = ref(false)
const creating = ref(false)
const applications = ref<Application[]>([])
const knowledgeBases = ref<any[]>([])
const datasources = ref<any[]>([])
const llmModels = ref<LLMConfigForm[]>([])
const embeddingModels = ref<LLMConfigForm[]>([])
const rerankModels = ref<LLMConfigForm[]>([])

const currentApp = ref<Application | null>(null)
const activeTab = ref('settings')
const showApiKey = ref(false)

const appFormRef = ref<FormInstance>()
const appForm = reactive<ApplicationUpdateForm>({
  name: '',
  description: '',
  status: 'active',
  modelName: 'glm-5.1-fp8',
  embeddingModel: 'bge-m3',
  rerankModel: 'bge-reranker-large',
  systemPrompt: '',
  userPromptTemplate: '',
  greetingMessage: '',
  knowledgeBaseIds: [],
  datasourceIds: [],
  maxTokens: 8192,
  temperature: 0.7,
  topP: 0.9,
})

const appRules: FormRules = {
  name: [{ required: true, message: '请输入应用名称', trigger: 'blur' }],
}

const systemPromptFocused = ref(false)
const systemPromptRef = ref<any>()
const isPromptOverflow = ref(false)

function checkPromptOverflow() {
  nextTick(() => {
    // 优先通过 ref 获取
    let textarea = systemPromptRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement
    // 如果 ref 方式失败，使用 document.querySelector 兜底
    if (!textarea) {
      textarea = document.querySelector('.textarea-wrapper textarea') as HTMLTextAreaElement
    }
    if (textarea) {
      isPromptOverflow.value = textarea.scrollHeight > textarea.clientHeight + 10
    }
  })
}

const createDialogVisible = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive<ApplicationCreateForm>({
  name: '',
  description: '',
  modelName: 'glm-5.1-fp8',
  embeddingModel: 'bge-m3',
  rerankModel: 'bge-reranker-large',
  knowledgeBaseIds: [],
  maxTokens: 8192,
  temperature: 0.7,
  topP: 0.9,
})

const createRules: FormRules = {
  name: [{ required: true, message: '请输入应用名称', trigger: 'blur' }],
}

const integrationForm = reactive({
  iframeWidth: '400px',
  iframeHeight: '600px',
  iframeBorder: '0',
  customDomain: '',
})

const allowedOriginsText = ref('')

const publicAccessEnabled = ref(true)
const showEmbedModal = ref(false)
const showAccessModal = ref(false)

const publicAccessUrl = computed(() => {
  if (!currentApp.value) return ''
  return `${window.location.origin}/chat/${currentApp.value.accessHash}`
})

const currentEmbedCode = computed(() => {
  if (!currentApp.value) return ''
  const origin = window.location.origin
  const baseUrl = `${origin}/chat/${currentApp.value.accessHash}`
  return '<iframe src="' + baseUrl + '" style="width: 100%; height: 100%;" frameborder="0" allow="microphone"></iframe>'
})

function stripMarkdown(text: string): string {
  return text.replace(/\*\*/g, '')
}

interface DebugMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  type?: 'text' | 'data'
  isStreaming?: boolean
  thinkingSteps?: Array<{
    step: number
    title: string
    description: string
  }>
  sqlTraces?: Array<{
    sql: string
    rows: number
  }>
  dataResult?: any[]
  columnMeta?: any[]
  chartType?: string
  references?: Array<{
    documentName: string
    content: string
    score: number
  }>
  elapsedTime?: number
}

interface ChartConfig {
  chartType: string
  xField: string
  yField: string
  option?: any
}

const debugInput = ref('')
const debugSending = ref(false)
const debugMessages = ref<DebugMessage[]>([])
const chatMessagesRef = ref<HTMLElement>()
const thinkingExpanded = reactive<Record<string, boolean>>({})
const refsExpanded = reactive<Record<string, boolean>>({})
const dataViewMode = reactive<Record<string, string>>({})
const chartConfig = reactive<Record<string, ChartConfig>>({})

function toggleThinking(msgId: string) {
  thinkingExpanded[msgId] = !thinkingExpanded[msgId]
}

function toggleReferences(msgId: string) {
  refsExpanded[msgId] = !refsExpanded[msgId]
}

function getFieldAlias(fieldName: string, columnMeta?: any[]): string | null {
  if (!columnMeta || columnMeta.length === 0) return null
  const meta = columnMeta.find((m) => m.columnName === fieldName)
  return meta?.columnAlias || null
}

function getTableName(sqlTraces: any[]) {
  if (!sqlTraces || sqlTraces.length === 0) return ''
  const sql = sqlTraces[0].sql
  const match = sql.match(/FROM\s+(\w+)/i)
  return match ? match[1] : ''
}

function getDataColumns(data: any[], columnMeta?: any[]) {
  if (!data || data.length === 0) return []
  const keys = Object.keys(data[0])
  return keys.map((key) => ({
    prop: key,
    label: getFieldAlias(key, columnMeta) || key,
    minWidth: 120,
  }))
}

function getNumericColumns(data: any[], columnMeta?: any[]) {
  if (!data || data.length === 0) return []
  const keys = Object.keys(data[0])
  return keys
    .filter((key) => {
      const val = data[0][key]
      return typeof val === 'number' || (!isNaN(Number(val)) && val !== null && val !== '')
    })
    .map((key) => ({
      prop: key,
      label: getFieldAlias(key, columnMeta) || key,
      minWidth: 120,
    }))
}

function copySql(sql: string) {
  navigator.clipboard.writeText(sql).then(() => {
    ElMessage.success('SQL已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

function getChartConfigValue(msgId: string, key: 'chartType' | 'xField' | 'yField') {
  return chartConfig[msgId]?.[key] || ''
}

function setChartConfigValue(msgId: string, key: 'chartType' | 'xField' | 'yField', value: string) {
  if (!chartConfig[msgId]) {
    chartConfig[msgId] = { chartType: 'bar', xField: '', yField: '', option: null }
  }
  chartConfig[msgId][key] = value
}

function initChartConfig(msgId: string, data: any[], columnMeta?: any[]) {
  const allCols = getDataColumns(data, columnMeta)
  const numCols = getNumericColumns(data, columnMeta)

  if (allCols.length === 0 || numCols.length === 0) return

  const xCol = allCols.find((c) => !numCols.some((n) => n.prop === c.prop))?.prop || allCols[0].prop
  const yCol = numCols[0].prop

  chartConfig[msgId] = {
    chartType: 'bar',
    xField: xCol,
    yField: yCol,
    option: null,
  }
  // 默认展示图表视图
  dataViewMode[msgId] = 'chart'
  updateChartOption(msgId, columnMeta)
}

function updateChartOption(msgId: string, columnMeta?: any[]) {
  const config = chartConfig[msgId]
  if (!config || !config.xField || !config.yField) return

  const msg = debugMessages.value.find((m) => m.id === Number(msgId))
  if (!msg?.dataResult) return

  const meta = columnMeta || msg.columnMeta
  const data = msg.dataResult
  const xData = data.map((row: any) => String(row[config.xField] ?? ''))
  const yData = data.map((row: any) => Number(row[config.yField]) || 0)

  const xAxisName = getFieldAlias(config.xField, meta) || config.xField
  const yAxisName = getFieldAlias(config.yField, meta) || config.yField

  if (config.chartType === 'pie') {
    config.option = {
      tooltip: { trigger: 'item' },
      legend: {
        type: 'scroll',
        orient: 'horizontal',
        bottom: 10,
        itemGap: 12,
        textStyle: { fontSize: 10 },
      },
      grid: { top: 20, bottom: 50, left: '3%', right: '3%', containLabel: true },
      series: [{
        type: 'pie',
        radius: ['25%', '55%'],
        center: ['50%', '40%'],
        data: xData.map((name: string, i: number) => ({ name, value: yData[i] })),
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } },
        label: { fontSize: 10, formatter: '{b}: {d}%' },
        labelLine: { length: 10, length2: 15, smooth: true },
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
      }],
    }
  } else {
    config.option = {
      tooltip: { trigger: 'axis' },
      grid: { top: 30, right: 15, bottom: 50, left: 15, containLabel: true },
      xAxis: {
        type: 'category',
        name: xAxisName,
        data: xData,
        axisLabel: { rotate: xData.length > 10 ? 45 : 0, fontSize: 10, interval: 0 },
        nameTextStyle: { fontSize: 11, padding: [8, 0, 0, 0] },
        nameLocation: 'middle',
        nameGap: 25,
      },
      yAxis: {
        type: 'value',
        name: yAxisName,
        nameTextStyle: { fontSize: 11, padding: [0, 0, 0, 30] },
        axisLabel: { fontSize: 10 },
      },
      series: [{
        type: config.chartType,
        data: yData,
        barMaxWidth: 30,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#409eff' },
            { offset: 1, color: '#79bbff' },
          ]),
          borderRadius: [3, 3, 0, 0],
        },
        smooth: config.chartType === 'line',
        areaStyle: config.chartType === 'line' ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.02)' },
          ]),
        } : undefined,
        lineStyle: config.chartType === 'line' ? { width: 2, color: '#409eff' } : undefined,
        symbol: config.chartType === 'line' ? 'circle' : undefined,
        symbolSize: config.chartType === 'line' ? 5 : undefined,
      }],
    }
  }
}

// 导出Excel
function exportToExcel(data: any[], columnMeta?: any[], fileName?: string) {
  if (!data || data.length === 0) {
    ElMessage.warning('没有数据可导出')
    return
  }

  const cols = getDataColumns(data, columnMeta)
  const headers = cols.map((c) => c.label)
  const rows = data.map((row) => cols.map((col) => String(row[col.prop] ?? '')))

  const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows])
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, '数据')

  const name = fileName || `数据导出_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}`
  XLSX.writeFile(workbook, `${name}.xlsx`)
}

// 导出图表为图片
function exportChartToImage(msgId: string) {
  const config = chartConfig[msgId]
  if (!config?.option) {
    ElMessage.warning('没有图表可导出')
    return
  }

  try {
    // 创建隐藏的canvas元素
    const canvas = document.createElement('canvas')
    canvas.width = 800
    canvas.height = 400
    canvas.style.display = 'none'
    document.body.appendChild(canvas)

    // 创建图表实例
    const chart = echarts.init(canvas, undefined, {
      renderer: 'canvas',
    })
    chart.setOption(config.option)

    // 等待图表渲染完成
    setTimeout(() => {
      const url = chart.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff',
      })

      chart.dispose()
      document.body.removeChild(canvas)

      // 将base64转换为Blob并下载
      const link = document.createElement('a')
      link.download = `图表导出_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.png`
      link.href = url
      link.click()
    }, 500)
  } catch (error) {
    console.error('图表导出失败:', error)
    ElMessage.error('图表导出失败，请重试')
  }
}

// 处理导出命令
function handleDebugExport(cmd: string, msg: DebugMessage) {
  if (cmd === 'excel') {
    exportToExcel(msg.dataResult || [], msg.columnMeta)
  } else if (cmd === 'image') {
    exportChartToImage(String(msg.id))
  }
}

const statusText: Record<string, string> = {
  active: '启用',
  inactive: '停用',
}

const maskedApiKey = computed(() => {
  if (!currentApp.value?.apiKey) return ''
  if (showApiKey.value) return currentApp.value.apiKey
  return currentApp.value.apiKey.substring(0, 8) + '****************'
})

const previewUrl = computed(() => {
  if (!currentApp.value) return ''
  const params = new URLSearchParams()
  params.set('appName', encodeURIComponent(currentApp.value.name || ''))
  params.set('greetingMessage', encodeURIComponent(currentApp.value.greetingMessage || ''))
  return `/chat/${currentApp.value.accessHash}?${params.toString()}`
})

const embedCode = computed(() => {
  if (!currentApp.value) return ''
  const origin = window.location.origin
  const url = `${origin}/chat/${currentApp.value.accessHash}`
  const borderStyle = integrationForm.iframeBorder === '0' ? 'none' : integrationForm.iframeBorder
  return `<iframe src="${url}" width="${integrationForm.iframeWidth}" height="${integrationForm.iframeHeight}" style="border: ${borderStyle}" frameborder="0" title="智能助手"></iframe>`
})

async function loadApplications() {
  loading.value = true
  try {
    const res = await getApplications({
      page: 1,
      page_size: 100,
    })
    applications.value = (res.data as any).data || []
  } catch (error) {
    ElMessage.error('加载应用列表失败')
  } finally {
    loading.value = false
  }
}

async function loadKnowledgeBases() {
  try {
    const res = await getKnowledgeBases()
    knowledgeBases.value = (res.data as any) || []
  } catch (error) {
    knowledgeBases.value = []
  }
}

async function loadDatasources() {
  try {
    const res = await getDatasources() as any
    if (res.code === 0) {
      // 兼容分页格式：新接口返回 {total, list}，旧接口直接返回数组
      if (res.data && Array.isArray(res.data.list)) {
        datasources.value = res.data.list
      } else if (Array.isArray(res.data)) {
        datasources.value = res.data
      } else {
        datasources.value = []
      }
    }
  } catch (error) {
    console.error('加载数据源失败', error)
    datasources.value = []
  }
}

async function loadModels() {
  try {
    const res = await getLLMConfigs()
    const configs = (res.data as any) || []
    llmModels.value = configs.filter((c: LLMConfigForm) => c.modelType === 'llm')
    embeddingModels.value = configs.filter((c: LLMConfigForm) => c.modelType === 'embedding')
    rerankModels.value = configs.filter((c: LLMConfigForm) => c.modelType === 'rerank')
  } catch (error) {
    llmModels.value = []
    embeddingModels.value = []
    rerankModels.value = []
  }
}

function handleCreate() {
  Object.assign(createForm, {
    name: '',
    description: '',
    modelName: 'glm-5.1-fp8',
    embeddingModel: 'bge-m3',
    rerankModel: 'bge-reranker-large',
    knowledgeBaseIds: [],
    maxTokens: 8192,
    temperature: 0.7,
    topP: 0.9,
  })
  createDialogVisible.value = true
}

async function handleSubmitCreate() {
  if (!createFormRef.value) return
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }

  creating.value = true
  try {
    await createApplication({ ...createForm })
    ElMessage.success('应用创建成功')
    createDialogVisible.value = false
    await loadApplications()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

function handleDetail(app: Application) {
  currentApp.value = app
  activeTab.value = 'settings'
  Object.assign(appForm, {
    name: app.name,
    description: app.description || '',
    status: app.status,
    modelName: app.modelName,
    embeddingModel: app.embeddingModel,
    rerankModel: app.rerankModel,
    systemPrompt: app.systemPrompt || '',
    userPromptTemplate: app.userPromptTemplate || '',
    greetingMessage: app.greetingMessage || '',
    knowledgeBaseIds: [...app.knowledgeBaseIds],
    datasourceIds: [...app.datasourceIds],
    maxTokens: app.maxTokens,
    temperature: app.temperature,
    topP: app.topP,
  })
  integrationForm.iframeWidth = app.iframeWidth || '400px'
  integrationForm.iframeHeight = String(app.iframeHeight) || '600px'
  integrationForm.customDomain = app.customDomain || ''
  allowedOriginsText.value = (app.iframeAllowedOrigins || []).join('\n')
  // 检测系统提示词是否溢出
  checkPromptOverflow()
}

function backToList() {
  currentApp.value = null
  activeTab.value = 'settings'
  loadApplications()
}

async function handleSave() {
  if (!appFormRef.value || !currentApp.value) return
  try {
    await appFormRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    await updateApplication(currentApp.value.id, { ...appForm })
    ElMessage.success('应用保存成功')
    await loadApplications()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handlePublish() {
  if (!appFormRef.value || !currentApp.value) return
  try {
    await appFormRef.value.validate()
  } catch {
    return
  }

  appForm.status = 'active'
  saving.value = true
  try {
    await updateApplication(currentApp.value.id, { ...appForm })
    ElMessage.success('应用已发布')
    await loadApplications()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '发布失败')
  } finally {
    saving.value = false
  }
}

async function handleDeleteApp() {
  if (!currentApp.value) return
  try {
    await ElMessageBox.confirm(`确定要删除应用「${currentApp.value.name}」吗？`, '提示', {
      type: 'warning',
    })
    await deleteApplication(currentApp.value.id)
    ElMessage.success('删除成功')
    currentApp.value = null
    await loadApplications()
  } catch {
  }
}

function toggleApiKeyVisibility() {
  showApiKey.value = !showApiKey.value
}

async function copyEmbedCode() {
  try {
    await navigator.clipboard.writeText(currentEmbedCode.value)
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

function openChat() {
  if (!currentApp.value) return
  window.open(`/chat/${currentApp.value.accessHash}`, '_blank')
}

async function copyPublicLink() {
  try {
    await navigator.clipboard.writeText(publicAccessUrl.value)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

function openPublicLink() {
  if (!currentApp.value) return
  window.open(publicAccessUrl.value, '_blank')
}

async function handleSaveAccessSettings() {
  if (!currentApp.value) return
  saving.value = true
  try {
    const allowedOrigins = allowedOriginsText.value
      .split('\n')
      .map(line => line.trim())
      .filter(line => line)

    await updateApplication(currentApp.value.id, {
      iframeAllowedOrigins: allowedOrigins,
      customDomain: integrationForm.customDomain,
    })
    showAccessModal.value = false
    ElMessage.success('访问限制已保存')
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

function scrollToBottom() {
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
  }
}

function clearMessages() {
  debugMessages.value = []
}

async function handleDebugSend() {
  if (!debugInput.value.trim() || !currentApp.value) return

  const userMsg: DebugMessage = {
    id: Date.now(),
    role: 'user',
    content: debugInput.value.trim(),
  }
  debugMessages.value.push(userMsg)
  debugInput.value = ''
  scrollToBottom()

  debugSending.value = true
  const aiMsg = reactive<DebugMessage>({
    id: Date.now() + 1,
    role: 'assistant',
    content: '',
    isStreaming: true,
  })
  debugMessages.value.push(aiMsg)
  scrollToBottom()

  try {
    const knowledgeBaseId = appForm.knowledgeBaseIds?.[0] || null
    const datasourceId = appForm.datasourceIds?.[0] || null
    // 根据modelName查找llmConfigId
    const llmConfig = llmModels.value.find((m) => m.modelName === appForm.modelName)
    const llmConfigId = llmConfig?.id || null
    
    const requestBody: any = {
      sessionId: `debug-${currentApp.value.id}-${Date.now()}`,
      question: userMsg.content,
      applicationId: currentApp.value.id,
    }
    
    if (knowledgeBaseId !== null) {
      requestBody.knowledgeBaseId = knowledgeBaseId
    }
    if (datasourceId !== null) {
      requestBody.datasourceId = datasourceId
    }
    if (llmConfigId !== null) {
      requestBody.llmConfigId = llmConfigId
    }
    
    const response = await fetch(`/api/v1/sessions/embed/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(requestBody),
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`请求失败: ${response.status} - ${errorText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法读取响应')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmedLine = line.trim()
        if (!trimmedLine.startsWith('data: ')) continue

        try {
          const jsonStr = trimmedLine.substring(6)
          const data = JSON.parse(jsonStr)

          if (data.type === 'start') {
            // 会话开始事件
          } else if (data.type === 'intent') {
            // 意图识别结果
          } else if (data.type === 'content') {
            aiMsg.content += data.content
            aiMsg.isStreaming = true
            scrollToBottom()
          } else if (data.type === 'thinking') {
            if (!aiMsg.thinkingSteps) {
              aiMsg.thinkingSteps = []
            }
            aiMsg.thinkingSteps.push({
              step: data.step,
              title: data.title,
              description: data.description,
            })
            scrollToBottom()
          } else if (data.type === 'references') {
            aiMsg.references = data.data
            scrollToBottom()
          } else if (data.type === 'sql_traces') {
            aiMsg.sqlTraces = data.data
            scrollToBottom()
          } else if (data.type === 'data_result') {
            aiMsg.dataResult = data.data
            if (data.columnMeta) {
              aiMsg.columnMeta = data.columnMeta
            }
            if (data.chartType) {
              aiMsg.chartType = data.chartType
            }
            aiMsg.type = 'data'
            initChartConfig(String(aiMsg.id), data.data, data.columnMeta)
            scrollToBottom()
          } else if (data.type === 'column_meta') {
            aiMsg.columnMeta = data.data
            if (aiMsg.dataResult && aiMsg.dataResult.length > 0) {
              initChartConfig(String(aiMsg.id), aiMsg.dataResult, aiMsg.columnMeta)
            }
            scrollToBottom()
          } else if (data.type === 'done') {
            aiMsg.isStreaming = false
            const elapsedTime = data.elapsed_time || data.elapsedTime
            if (elapsedTime !== undefined) {
              aiMsg.elapsedTime = Math.round(elapsedTime * 1000)
            }
          } else if (data.type === 'error') {
            aiMsg.content += `\n\n[错误] ${data.message}`
            aiMsg.isStreaming = false
          }
        } catch (e) {
          console.warn('解析SSE消息失败:', e)
        }
      }
    }
  } catch (error: any) {
    console.error('调试对话失败:', error)
    aiMsg.content = aiMsg.content || '抱歉，消息发送失败，请稍后重试。'
    aiMsg.isStreaming = false
  } finally {
    debugSending.value = false
    scrollToBottom()
  }
}

onMounted(() => {
  loadApplications()
  loadKnowledgeBases()
  loadDatasources()
  loadModels()
})
</script>

<style lang="scss" scoped>
.app-list-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 100px); /* Header 60px + content-area padding 40px */
  min-height: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .page-title {
    font-size: 20px;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }
}

.app-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.app-card {
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

.app-icon {
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

.app-info {
  margin-bottom: 16px;
}

.app-name {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
  margin-bottom: 6px;
}

.app-desc {
  font-size: 13px;
  color: $text-secondary;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.app-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.app-model {
  display: flex;
  align-items: center;
  gap: 4px;
  color: $text-secondary;
}

.app-status {
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

.app-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid $card-border;
}

.add-app {
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

.app-detail-view {
  display: flex;
  flex-direction: column;
  height: 100%;

  .app-tabs {
    background: #fff;
    border-radius: 0 $card-radius $card-radius $card-radius;
    min-height: 0;
    flex: 1;
    display: flex;
    flex-direction: column;

    :deep(.el-tabs__header) {
      flex-shrink: 0;
    }

    :deep(.el-tabs__content) {
      padding: 20px;
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    :deep(.el-tab-pane) {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
  }
}

.integration-content {
  width: 100%;

  .public-link-section {
    margin-bottom: 24px;
    padding: 16px;
    background: #f8fafc;
    border-radius: 12px;

    .link-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      .link-label {
        font-size: 14px;
        font-weight: 500;
        color: $text-primary;
      }
    }

    .link-display {
      display: flex;
      align-items: center;
      gap: 8px;

      .link-input {
        flex: 1;
        padding: 8px 12px;
        border: 1px solid $card-border;
        border-radius: 8px;
        font-size: 13px;
        font-family: monospace;
        color: $text-secondary;
        background: #fff;

        &:focus {
          outline: none;
          border-color: $primary-color;
        }
      }

      .copy-btn,
      .open-btn {
        padding: 8px;
        color: $text-secondary;

        &:hover {
          color: $primary-color;
        }
      }
    }
  }

  .action-buttons {
    display: flex;
    gap: 12px;

    .action-btn {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      padding: 16px 12px;
      border: 1px solid $card-border;
      border-radius: 12px;
      background: #fff;
      color: $text-primary;
      transition: all 0.2s;

      :deep(.el-icon) {
        font-size: 20px;
        color: $primary-color;
      }

      span {
        font-size: 13px;
        font-weight: 500;
      }

      &:hover {
        border-color: $primary-color;
        background: rgba(59, 130, 246, 0.05);
      }
    }
  }
}

.integration-card {
  max-width: 600px;
  margin: 0 auto;

  :deep(.el-card__body) {
    padding: 24px;
  }

  .integration-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid $card-border;

    .app-info {
      display: flex;
      align-items: center;
      gap: 12px;

      .app-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 0;

        svg {
          width: 24px;
          height: 24px;
        }
      }

      .app-name {
        font-size: 18px;
        font-weight: 600;
        color: $text-primary;
        margin-bottom: 0;
      }
    }

    .public-access-badge {
      font-size: 12px;
      padding: 4px 12px;
      background: rgba(59, 130, 246, 0.1);
      color: $primary-color;
      border-radius: 12px;
      font-weight: 500;
    }
  }
}

.app-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-card {
  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: #1e293b;
  }
}

.form-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.slider-value {
  font-size: 13px;
  color: #64748b;
  margin-left: 8px;
}

.embed-card,
.api-card,
.security-card,
.usage-card {
  margin-bottom: 16px;

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

.settings-layout {
    display: flex;
    gap: 20px;
    align-items: stretch;
    flex: 1;
    min-height: 0;

    .settings-left {
        width: 40%;
        flex-shrink: 0;
        overflow-y: auto;
        max-height: 100%;

      :deep(.el-card) {
        margin-bottom: 0;
        border-radius: 10px;
      }

      :deep(.el-card__body) {
        padding: 24px;
      }

      :deep(.el-card__body .el-row) {
        margin-bottom: 24px;

        &:last-child {
          margin-bottom: 0;
        }
      }

      :deep(.el-card__header) {
        padding: 10px 16px;
        border-bottom: 1px solid #e2e8f0;
      }

      .card-title {
        font-size: 14px;
        font-weight: 600;
        color: #1e293b;
      }

      :deep(.el-form) {
        label-width: 90px;
      }

      :deep(.el-form-item) {
        margin-bottom: 24px;

        &:last-child {
          margin-bottom: 0;
        }

        // 应用描述等textarea与上一行保持足够间距
        &:has(.el-textarea__inner) {
          margin-top: 8px;
        }
      }

      :deep(.el-form-item__label) {
        font-size: 13px;
        font-weight: 500;
        color: #475569;
      }

      :deep(.el-input__wrapper) {
        border-radius: 8px;
        padding: 4px 8px;
        width: 100%;
        height: 36px;
        box-sizing: border-box;
      }

      :deep(.el-input__inner) {
        font-size: 12px;
        padding: 8px 10px;
        width: 100%;
        min-width: 0;
        height: 28px;
        line-height: 28px;
      }

      :deep(.el-select__wrapper) {
        border-radius: 8px;
        padding: 4px 8px;
        width: 100%;
        height: 36px;
        box-sizing: border-box;
      }

      :deep(.el-select__inner) {
        font-size: 12px;
        padding: 8px 10px;
        width: 100%;
        height: 28px;
        line-height: 28px;
      }

      :deep(.el-input-number) {
        width: 100%;
        min-width: 0;
      }

      :deep(.el-input-number .el-input__wrapper) {
        border-radius: 8px;
        width: 100%;
        padding: 4px 8px;
        box-sizing: border-box;
        height: 36px;
      }

      :deep(.el-input-number .el-input__inner) {
        font-size: 12px;
        width: 100%;
        padding-right: 30px;
        height: 28px;
        line-height: 28px;
      }

      :deep(.el-input-number__decrease),
      :deep(.el-input-number__increase) {
        width: 24px;
        height: 36px;
        line-height: 36px;

        .el-icon {
          font-size: 12px;
        }
      }

      :deep(.el-textarea__inner) {
        font-size: 12px;
        padding: 10px;
        border-radius: 8px;
        width: 100%;
        min-width: 0;
        resize: none;
      }

      .textarea-wrapper {
        position: relative;
        width: 100%;

        .textarea-ellipsis {
          position: absolute;
          bottom: 12px;
          right: 14px;
          background: #fff;
          padding: 0 8px;
          color: #94a3b8;
          font-size: 12px;
          pointer-events: none;
        }
      }

      :deep(.el-slider) {
        margin-bottom: 6px;
      }

      :deep(.el-switch) {
        font-size: 12px;
        padding: 0 8px;
      }

      :deep(.el-switch__core) {
        width: 32px;
        height: 18px;
      }

      :deep(.el-switch__button) {
        width: 16px;
        height: 16px;
      }

      :deep(.el-switch__label) {
        font-size: 12px;
        padding: 0 4px;
        line-height: normal;
        overflow: visible;
        height: auto;
      }

      .slider-value {
        font-size: 11px;
        color: #64748b;
        margin-left: 6px;
      }

      .form-tip {
        margin-top: 6px;
        font-size: 11px;
        color: #94a3b8;
      }
    }

    .settings-right {
      width: 60%;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
      box-sizing: border-box;
    }

    .preview-card {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border-radius: 10px;
      min-height: 0;
      border: 1px solid #e2e8f0 !important;

      :deep(.el-card__body) {
        padding: 0;
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        margin: 0;
        min-height: 0;
      }

    .preview-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 16px;
      background-color: #ffffff;
      border-bottom: 1px solid #e2e8f0;

      .card-title {
        font-size: 14px;
        font-weight: 600;
        color: #1e293b;
      }

      .refresh-btn {
        border-radius: 8px;
        padding: 6px 14px;
        display: flex;
        align-items: center;
        gap: 4px;
        border: 1px solid #e2e8f0;
        color: #475569;
        transition: all 0.2s;

        &:hover {
          color: #3b82f6;
          border-color: #3b82f6;
          background-color: #eff6ff;
        }
      }
    }
  }

  .chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    background-color: #f1f5f9;
  }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 16px 16px 16px 16px;
    padding-right: 32px; /* 给滚动条留出更多空间 */
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    scrollbar-gutter: stable; /* 保持滚动条占位稳定 */
    box-sizing: border-box;

    .chat-welcome {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px 24px;
      text-align: center;

      .welcome-icon {
        width: 70px;
        height: 70px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        border-radius: 18px;
        margin-bottom: 16px;
        box-shadow: 0 6px 24px rgba(59, 130, 246, 0.3);

        svg {
          width: 44px;
          height: 44px;
        }
      }

      p {
        font-size: 12px;
        color: #64748b;
        margin: 0;
        max-width: 200px;
        line-height: 1.6;
      }
    }

    .message-item {
      display: flex;
      margin-bottom: 16px;

      &.user {
        justify-content: flex-end;
      }

      &.assistant {
        justify-content: flex-start;
      }
    }

    .message-content {
      display: flex;
      max-width: 90%;
      min-width: 0;
      overflow: hidden;
      gap: 8px;

      &.user {
        flex-direction: row-reverse;

        .message-bubble-wrap {
          display: flex;
          flex-direction: column;
          gap: 4px;
          flex: 0 1 auto;
          min-width: 0;
          max-width: 100%;
          overflow: hidden;
          align-items: flex-end;
        }

        .message-bubble {
          background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
          color: #ffffff;
          border-radius: 14px 14px 4px 14px;
          position: relative;
          padding: 12px 14px;
          font-size: 12px;
          line-height: 1.6;
          word-break: break-word;
          overflow-wrap: break-word;
          box-shadow: 0 3px 12px rgba(0, 0, 0, 0.06);
          width: auto;
          max-width: 100%;

          .bubble-arrow {
            right: -14px;
            border: 7px solid transparent;
            border-left-color: #6366f1;
          }
        }
      }

      &.assistant {
        flex-direction: row;

        .message-bubble-wrap {
          display: flex;
          flex-direction: column;
          gap: 8px;
          flex: 1;
          min-width: 0;
          align-items: stretch;
          overflow: hidden;
        }

        .message-bubble {
          background-color: #ffffff;
          color: #1e293b;
          border-radius: 14px 14px 14px 4px;
          position: relative;
          padding: 12px 14px;
          font-size: 12px;
          line-height: 1.6;
          word-break: break-word;
          overflow-wrap: break-word;
          overflow: hidden;
          box-shadow: 0 3px 12px rgba(0, 0, 0, 0.06);
          width: 100%;

          .bubble-arrow {
            left: -14px;
            border: 7px solid transparent;
            border-right-color: #ffffff;
          }
        }
      }

      .avatar-label {
        font-size: 10px;
        font-weight: 600;
        color: #1e293b;
        white-space: nowrap;
      }

      .avatar-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 3px;
        flex-shrink: 0;
      }

      .avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;

        &.user-avatar {
          background: linear-gradient(135deg, #fde8e8 0%, #fef3c7 100%);
          box-shadow: 0 2px 6px rgba(220, 38, 38, 0.15);
        }

        &.assistant-avatar {
          background: white;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
        }
      }

      .message-text {
        white-space: pre-wrap;
      }

      .streaming-cursor {
        animation: blink 1s infinite;
        font-weight: bold;
      }

      .typing-indicator {
        display: flex;
        gap: 5px;
        padding: 6px 0;

        span {
          width: 6px;
          height: 6px;
          background-color: #94a3b8;
          border-radius: 50%;
          animation: typing 1.4s infinite ease-in-out;

          &:nth-child(1) { animation-delay: -0.32s; }
          &:nth-child(2) { animation-delay: -0.16s; }
          &:nth-child(3) { animation-delay: 0s; }
        }
      }

      .bubble-arrow {
        position: absolute;
        width: 0;
        height: 0;
        top: 12px;
      }

      .bubble-content {
        white-space: pre-wrap;
      }

      .thinking-process {
        background-color: #ffffff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
        width: 100%;

        .thinking-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          cursor: pointer;
          background: linear-gradient(90deg, #f1f5f9 0%, #ffffff 100%);
          transition: background-color 0.2s;

          &:hover {
            background: linear-gradient(90deg, #e2e8f0 0%, #f1f5f9 100%);
          }

          .el-icon {
            font-size: 12px;
            color: #64748b;
            transition: transform 0.25s;

            &.rotated {
              transform: rotate(90deg);
            }
          }

          .thinking-title {
            font-size: 11px;
            font-weight: 600;
            color: #475569;
          }

          .thinking-count {
            font-size: 10px;
            padding: 2px 6px;
            background-color: #e0e7ff;
            color: #6366f1;
            border-radius: 8px;
            font-weight: 500;
          }

          .thinking-action {
            margin-left: auto;
            font-size: 10px;
            color: #94a3b8;
          }
        }

        .thinking-content {
          padding: 12px;
        }

        .section-title {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 11px;
          font-weight: 600;
          color: #475569;
          margin-bottom: 10px;
          padding-left: 6px;
          border-left: 3px solid #3b82f6;

          .el-icon {
            font-size: 12px;
            color: #3b82f6;
          }
        }

        .thinking-steps {
          margin-bottom: 14px;
        }

        .steps-timeline {
          display: flex;
          flex-direction: column;
          gap: 0;
        }

        .step-item {
          display: flex;
          gap: 10px;
          padding-bottom: 14px;

          &:last-child {
            padding-bottom: 0;

            .step-connector {
              .connector-line {
                display: none;
              }
            }
          }
        }

        .step-connector {
          display: flex;
          flex-direction: column;
          align-items: center;
          width: 16px;
          flex-shrink: 0;

          .connector-line {
            width: 2px;
            flex: 1;
            background-color: #e2e8f0;
            margin-top: 3px;

            &.last {
              display: none;
            }
          }

          .step-dot {
            width: 16px;
            height: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            background-color: #e2e8f0;
            border-radius: 50%;
            border: 2px solid #ffffff;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
            flex-shrink: 0;
            font-size: 9px;

            &.active {
              background-color: #3b82f6;
              animation: pulse 2s infinite;
            }

            &.completed {
              background-color: #10b981;
            }

            .step-loading {
              font-size: 8px;
              color: #fff;
            }

            .step-check {
              font-size: 8px;
              color: #fff;
            }

            .step-number-text {
              color: #64748b;
              font-weight: 600;
            }
          }
        }

        .step-content {
          flex: 1;
          padding-top: 2px;

          .step-title {
            font-size: 11px;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 3px;
          }

          .step-desc {
            font-size: 10px;
            color: #64748b;
            line-height: 1.5;
          }
        }
      }

      .sql-section {
        background-color: #0f172a;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 3px 12px rgba(0, 0, 0, 0.12);
        width: 100%;

        .section-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          background-color: #1e293b;
          border-bottom: 1px solid #334155;

          span {
            font-size: 11px;
            font-weight: 600;
            color: #f1f5f9;
          }

          .sql-copy-btn {
            margin-left: auto;
            color: #94a3b8;
            font-size: 10px;
            gap: 3px;

            &:hover {
              color: #e2e8f0;
            }
          }
        }

        .sql-content {
          padding: 12px;

          .sql-code {
            font-family: 'JetBrains Mono', 'Fira Code', monospace;
            font-size: 10px;
            color: #e2e8f0;
            line-height: 1.6;
            margin: 0;
            overflow-x: auto;
          }

          .sql-meta {
            margin-top: 8px;
            font-size: 10px;
            color: #64748b;
            text-align: right;
          }
        }
      }

      .chart-section {
        background-color: #ffffff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
        width: 100%;

        .section-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          background: linear-gradient(90deg, #ecfdf5 0%, #ffffff 100%);
          border-bottom: 1px solid #d1fae5;

          .el-icon {
            font-size: 14px;
            color: #10b981;
          }

          span {
            font-size: 12px;
            font-weight: 600;
            color: #065f46;
          }

          .table-name-badge {
            font-size: 10px;
            padding: 3px 8px;
            background-color: #e0e7ff;
            color: #6366f1;
            border-radius: 5px;
            margin-left: auto;
          }

          .chart-view-toggle {
            margin-left: 8px;
          }

          .export-btn {
            margin-left: 8px;
            color: #64748b;
            font-size: 11px;
            padding: 3px 8px;

            &:hover {
              color: #3b82f6;
              background-color: #eff6ff;
            }
          }
        }

        .chart-body {
          padding: 10px 12px 12px;
        }

        .table-wrapper {
          :deep(.data-table) {
            font-size: 10px;
            border-radius: 6px;
            overflow: hidden;
          }
        }

        .table-footer {
          margin-top: 8px;
          text-align: center;
          font-size: 10px;
          color: #94a3b8;
        }

        .chart-wrapper {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .chart-controls {
          display: flex;
          gap: 6px;
          justify-content: flex-end;
          padding: 0 4px;

          :deep(.el-select) {
            width: 80px;
          }

          :deep(.el-select__wrapper) {
            border-radius: 6px;
          }

          :deep(.el-select__inner) {
            font-size: 11px;
            padding: 6px 10px;
          }
        }

        .chart-container {
          width: 100%;
          min-height: 200px;
        }

        .chart-placeholder {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 24px;
          background-color: #f8fafc;
          border-radius: 6px;

          p {
            font-size: 11px;
            color: #94a3b8;
            margin-top: 8px;
          }
        }
      }

      .message-meta {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 4px;
        margin-top: 6px;

        span {
          font-size: 10px;
          color: #94a3b8;
        }
      }

      .references-section {
        background-color: #ffffff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        overflow: hidden;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
        width: 100%;
        margin-top: 8px;

        .references-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 12px;
          cursor: pointer;
          background: linear-gradient(90deg, #f1f5f9 0%, #ffffff 100%);
          transition: background-color 0.2s;

          &:hover {
            background: linear-gradient(90deg, #e2e8f0 0%, #f1f5f9 100%);
          }

          .el-icon {
            font-size: 12px;
            color: #64748b;
            transition: transform 0.25s;

            &.rotated {
              transform: rotate(90deg);
            }
          }

          .references-title {
            font-size: 11px;
            font-weight: 600;
            color: #475569;
          }

          .references-count {
            font-size: 10px;
            padding: 2px 6px;
            background-color: #dcfce7;
            color: #16a34a;
            border-radius: 8px;
            font-weight: 500;
          }

          .references-action {
            margin-left: auto;
            font-size: 10px;
            color: #94a3b8;
          }
        }

        .references-content {
          padding: 12px;
        }

        .ref-cards {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .ref-card {
          padding: 10px;
          background-color: #f8fafc;
          border-radius: 6px;
          border: 1px solid #e2e8f0;

          .ref-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;

            .ref-name {
              font-size: 11px;
              font-weight: 600;
              color: #1e293b;
            }

            .ref-score {
              font-size: 10px;
              padding: 2px 5px;
              background-color: #dcfce7;
              color: #16a34a;
              border-radius: 5px;
              font-weight: 500;
            }
          }

          .ref-content {
            font-size: 10px;
            color: #64748b;
            line-height: 1.5;
          }
        }
      }
    }
  }

  .chat-input-area {
    flex-shrink: 0; /* 确保输入框不被压缩 */
    background-color: #ffffff;
    border-top: 1px solid #e2e8f0;
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);
    padding: 10px 16px;
    box-sizing: border-box;

    .debug-input-wrapper {
      display: flex;
      gap: 10px;
      align-items: center;
      width: 100%;

      .debug-input {
        flex: 1;
        min-width: 0;

        :deep(.el-input__wrapper) {
          border-radius: 10px;
          border: 1px solid #e2e8f0;
          box-shadow: 0 0 0 1px #e2e8f0 inset;
          transition: all 0.2s;

          &:hover {
            box-shadow: 0 0 0 1px #3b82f6 inset;
          }

          &.is-focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 1px #3b82f6 inset, 0 0 0 3px rgba(59, 130, 246, 0.1);
          }
        }

        :deep(.el-input__inner) {
          padding: 10px 14px;
          font-size: 12px;
        }
      }

      .send-btn {
        flex-shrink: 0;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        border: none;
        border-radius: 10px;
        width: 36px;
        height: 36px;
        padding: 0;
        box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);

        &:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 3px 10px rgba(59, 130, 246, 0.4);
        }

        &:disabled {
          opacity: 0.7;
        }

        .el-icon {
          font-size: 16px;
        }
      }
    }
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes typing {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}

.embed-modal-content {
  .embed-mode-tabs {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;

    .embed-mode {
      flex: 1;
      padding: 16px;
      border: 2px solid $card-border;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.2s;
      text-align: center;

      &.active {
        border-color: $primary-color;
        background: rgba(59, 130, 246, 0.05);
      }

      .mode-icon {
        width: 64px;
        height: 64px;
        margin: 0 auto 12px;
        display: flex;
        align-items: center;
        justify-content: center;

        svg {
          width: 48px;
          height: 48px;
        }
      }

      .mode-name {
        font-size: 14px;
        font-weight: 600;
        color: $text-primary;
      }
    }
  }

  .embed-code-section {
    background: #f8fafc;
    border-radius: 12px;
    padding: 16px;

    .code-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      span {
        font-size: 14px;
        font-weight: 500;
        color: $text-primary;
      }

      .copy-code-btn {
        color: $primary-color;
      }
    }

    .embed-code-block {
      background: #0f172a;
      color: #e2e8f0;
      padding: 16px;
      border-radius: 8px;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 12px;
      line-height: 1.6;
      overflow-x: auto;
      margin: 0;

      code {
        background: none;
        padding: 0;
        font-family: inherit;
      }
    }
  }
}

.display-settings {
  padding: 20px;
  text-align: center;

  p {
    color: $text-secondary;
    font-size: 14px;
  }
}
</style>