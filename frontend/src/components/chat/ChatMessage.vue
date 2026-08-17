<template>
  <div class="message-item" :class="[message.role, message.type || '', `size-${size}`]">
    <!-- 用户消息 -->
    <div v-if="message.role === 'user'" class="message-content user" :class="{ editing: isEditing }">
      <div class="avatar-group">
        <AvatarImage type="user" />
      </div>
      <div class="message-bubble-wrap user-bubble-wrap" :class="{ editing: isEditing }">
        <div class="message-bubble" v-if="!isEditing">
          <div class="bubble-arrow"></div>
          <div class="bubble-content">{{ message.content }}</div>
        </div>
        <!-- 编辑模式 -->
        <div v-else class="message-bubble edit-mode">
          <div class="edit-input-wrap">
            <el-input
              v-model="editContent"
              class="edit-input"
              placeholder="输入您的问题..."
              @keydown.enter.exact="handleSubmitEdit"
            />
            <div class="edit-actions">
              <el-button size="small" @click="handleCancelEdit">取消</el-button>
              <el-button size="small" type="primary" class="edit-send-btn" @click="handleSubmitEdit">发送</el-button>
            </div>
          </div>
        </div>
        <!-- 用户消息操作：复制、编辑 -->
        <div v-if="!isEditing" class="user-message-actions">
          <el-icon class="meta-action-icon" @click="handleCopy(message.content)" title="复制">
            <CopyDocument />
          </el-icon>
          <el-icon class="meta-action-icon" @click="handleStartEdit" title="编辑">
            <Edit />
          </el-icon>
        </div>
      </div>
    </div>

    <!-- AI消息 -->
    <div v-else class="message-content assistant">
      <div class="avatar-group">
        <AvatarImage type="assistant" />
      </div>
      <div class="message-bubble-wrap">
        <!-- 消息气泡（包含思考过程、回复、引用） -->
        <div class="message-bubble">
          <div class="bubble-arrow"></div>
          
          <!-- 执行过程（与回复在同一气泡内） -->
          <div v-if="showThinking" class="thinking-process">
            <div class="thinking-header" @click="toggleThinking">
              <el-icon :class="{ 'rotated': thinkingExpanded }"><ArrowRight /></el-icon>
              <span class="thinking-title">执行过程</span>
              <span class="thinking-count">{{ message.thinkingSteps?.length || 0 }} 步</span>
              <span class="thinking-action">{{ thinkingExpanded ? '收起' : '展开' }}</span>
            </div>
            <div v-show="thinkingExpanded" class="thinking-content">
              <div v-if="message.thinkingSteps && message.thinkingSteps.length > 0" class="thinking-steps">
                <div class="steps-timeline">
                  <div v-for="(step, idx) in message.thinkingSteps" :key="idx" class="step-item">
                    <div class="step-connector">
                      <div class="connector-line" :class="{ last: idx === message.thinkingSteps!.length - 1 }"></div>
                      <div class="step-dot" :class="{ active: idx === message.thinkingSteps!.length - 1 && message.isStreaming, completed: idx < message.thinkingSteps!.length - 1 || !message.isStreaming }">
                        <el-icon v-if="idx === message.thinkingSteps!.length - 1 && message.isStreaming"><Loading class="step-loading" /></el-icon>
                        <el-icon v-else-if="idx < message.thinkingSteps!.length - 1 || !message.isStreaming"><CircleCheck class="step-check" /></el-icon>
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

          <!-- 打字指示器 -->
          <div v-if="message.isStreaming && !message.content" class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <!-- 消息内容（支持Markdown渲染） -->
          <div v-else class="message-content-box">
            <div class="message-text markdown-content" v-html="renderedContent"></div>
            <span v-if="message.isStreaming" class="streaming-cursor">|</span>
          </div>

          <!-- 知识引用 -->
          <div v-if="message.references && message.references.length > 0" class="references-section">
            <div class="references-header" @click="toggleReferences">
              <el-icon :class="{ 'rotated': refsExpanded }"><ArrowRight /></el-icon>
              <el-icon><Document /></el-icon>
              <span class="references-title">引用</span>
              <span class="references-count">{{ message.references.length }} 条</span>
              <span class="references-action">{{ refsExpanded ? '收起' : '展开' }}</span>
            </div>
            <div v-show="refsExpanded" class="references-content">
              <div class="ref-cards">
                <div
                  v-for="(ref, idx) in message.references"
                  :key="idx"
                  class="ref-card"
                  @click="handleShowReference(ref)"
                >
                  <div class="ref-header">
                    <el-icon><Document /></el-icon>
                    <span class="ref-name">{{ ref.documentName }}</span>
                    <span class="ref-score">{{ (ref.score * 100).toFixed(1) }}%</span>
                  </div>
                  <div class="ref-content">{{ ref.content?.slice(0, 200) }}...</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 工具调用（MCP/Skill通用，根据intent显示不同标题） -->
        <div v-if="message.toolCalls && message.toolCalls.length > 0" class="tool-calls-section">
          <div class="section-header">
            <div class="header-left">
              <el-icon><Tools /></el-icon>
              <span>{{ message.intent === 'skill' ? 'Skill工具调用' : (message.intent === 'mcp' ? 'MCP工具调用' : '工具调用') }}</span>
              <span class="tool-calls-count">{{ message.toolCalls.length }} 个工具</span>
            </div>
          </div>
          <div class="tool-calls-content">
            <div v-for="(call, idx) in message.toolCalls" :key="idx" class="tool-call-item">
              <div class="tool-call-header">
                <el-icon class="tool-icon"><Tools /></el-icon>
                <span class="tool-name">{{ call.tool_name }}</span>
                <el-tag v-if="message.toolResults && message.toolResults[idx]" 
                  :type="message.toolResults[idx].success ? 'success' : 'danger'"
                  size="small"
                  class="tool-status-tag">
                  {{ message.toolResults[idx]?.success ? '成功' : '失败' }}
                </el-tag>
              </div>
              <div v-if="call.arguments && Object.keys(call.arguments).length > 0" class="tool-args">
                <span class="args-label">参数：</span>
                <span class="args-value">{{ formatToolArgs(call.arguments) }}</span>
              </div>
              <div v-if="message.toolResults && message.toolResults[idx]" class="tool-result">
                <div class="result-label">结果：</div>
                <div class="result-content">{{ message.toolResults[idx].result }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- SQL查询（仅当没有数据可视化时显示，因为数据可视化区域已有"查看SQL"按钮） -->
        <div v-if="message.sqlTraces && message.sqlTraces.length > 0 && (!message.dataResult || message.dataResult.length === 0)" class="sql-section">
          <div class="section-header">
            <span>SQL查询</span>
            <el-button text size="small" class="sql-copy-btn" @click="handleCopySql(message.sqlTraces[0].sql)">
              <el-icon><CopyDocument /></el-icon>
              复制
            </el-button>
          </div>
          <div class="sql-content">
            <pre class="sql-code">{{ message.sqlTraces[0].sql }}</pre>
            <div class="sql-meta">返回 {{ message.sqlTraces[0].rows || 0 }} 行数据</div>
          </div>
        </div>

        <!-- 数据可视化 -->
        <div v-if="message.dataResult && message.dataResult.length > 0" class="chart-section">
          <div class="section-header">
            <div class="header-left">
              <el-icon><TrendCharts /></el-icon>
              <span>数据可视化</span>
              <div class="table-name-badge">表名：{{ getTableName() }}</div>
              <div class="view-toggle-group">
                <el-dropdown trigger="click" @command="handleChartTypeChange">
                  <el-button type="text" size="small" class="chart-type-btn">
                    <!-- 根据当前图表类型显示不同图标 -->
                    <svg v-if="chartConfig.chartType === 'bar'" viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                      <path d="M1 8h2v7H1V8zm4-4h2v11H5V4zm4 3h2v8H9V7zm4-5h2v13h-2V2z"/>
                    </svg>
                    <svg v-else-if="chartConfig.chartType === 'line'" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14">
                      <polyline points="1,12 4,8 7,10 10,4 13,6 15,3"/>
                    </svg>
                    <svg v-else-if="chartConfig.chartType === 'pie'" viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                      <path d="M8 0C3.6 0 0 3.6 0 8s3.6 8 8 8 8-3.6 8-8S12.4 0 8 0zm0 2v6h6c0 3.3-2.7 6-6 6s-6-2.7-6-6 2.7-6 6-6z"/>
                    </svg>
                    <el-icon class="arrow-icon"><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="bar">
                        <!-- 柱状图图标 -->
                        <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                          <path d="M1 8h2v7H1V8zm4-4h2v11H5V4zm4 3h2v8H9V7zm4-5h2v13h-2V2z"/>
                        </svg>
                        <span>柱状图</span>
                      </el-dropdown-item>
                      <el-dropdown-item command="line">
                        <!-- 折线图图标 -->
                        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14">
                          <polyline points="1,12 4,8 7,10 10,4 13,6 15,3"/>
                        </svg>
                        <span>折线图</span>
                      </el-dropdown-item>
                      <el-dropdown-item command="pie">
                        <!-- 饼图图标 -->
                        <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                          <path d="M8 0C3.6 0 0 3.6 0 8s3.6 8 8 8 8-3.6 8-8S12.4 0 8 0zm0 2v6h6c0 3.3-2.7 6-6 6s-6-2.7-6-6 2.7-6 6-6z"/>
                        </svg>
                        <span>饼图</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button 
                  :class="['view-btn', { active: dataViewMode === 'table' }]"
                  size="small" 
                  @click="dataViewMode = 'table'"
                >
                  <!-- 表格图标：网格样式 -->
                  <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                    <path d="M0 0h16v16H0V0zm1 1v4h6V1H1zm7 0v4h6V1H8zm-7 5v4h6V6H1zm7 0v4h6V6H8zm-7 5v4h6v-4H1zm7 0v4h6v-4H8z"/>
                  </svg>
                </el-button>
              </div>
            </div>
            <div class="header-right">
              <el-button v-if="message.sqlTraces && message.sqlTraces.length > 0" type="text" size="small" class="sql-view-btn" @click="handleShowSql(message.sqlTraces[0].sql)">
                <el-icon><Document /></el-icon>
                <span>查看SQL</span>
              </el-button>
              <el-dropdown trigger="click" @command="(cmd: string) => handleExport(cmd)">
                <el-button type="text" size="small" class="export-btn">
                  <el-icon><Download /></el-icon>
                  <span>导出</span>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="excel">Excel</el-dropdown-item>
                    <el-dropdown-item v-if="dataViewMode === 'chart'" command="image">图片</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <div class="chart-body">
            <div v-if="dataViewMode !== 'chart'" class="table-wrapper">
              <el-table
                :data="message.dataResult.slice(0, 100)"
                size="small"
                border
                max-height="400"
                stripe
                class="data-table"
              >
                <el-table-column
                  v-for="col in getDataColumns()"
                  :key="col.prop"
                  :prop="col.prop"
                  :label="col.label"
                  :min-width="col.minWidth"
                  show-overflow-tooltip
                />
              </el-table>
              <div v-if="message.dataResult.length > 100" class="table-footer">
                仅展示前 100 行，共 {{ message.dataResult.length }} 行
              </div>
            </div>
            <div v-else class="chart-wrapper">
              <div v-if="chartOption" class="chart-container">
                <ChartCard ref="chartCardRef" :option="chartOption" />
              </div>
              <div v-else class="chart-placeholder">
                <el-icon :size="48" color="#cbd5e1">TrendCharts</el-icon>
                <p>暂无数据，请选择图表类型生成图表</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 消息元数据：复制、重新生成、耗时 -->
        <div v-if="message.role === 'assistant' && !message.isStreaming" class="message-meta">
          <span class="meta-actions">
            <el-icon class="meta-action-icon" @click="handleCopy(message.content)" title="复制">
              <CopyDocument />
            </el-icon>
            <el-icon class="meta-action-icon" @click="handleRegenerate" title="重新生成">
              <Refresh />
            </el-icon>
          </span>
          <el-icon class="meta-icon"><Clock /></el-icon>
          <span>耗时: {{ elapsedTime }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { CopyDocument, Edit, ArrowRight, ArrowDown, List, Loading, CircleCheck, Document, TrendCharts, PieChart, Download, Clock, Refresh, Tools } from '@element-plus/icons-vue';
import * as XLSX from 'xlsx';
import { marked } from 'marked';
import katex from 'katex';
import 'katex/dist/katex.min.css';
import ChartCard from '@/components/chart/ChartCard.vue';
import AvatarImage from '@/components/AvatarImage.vue';
import { copyToClipboard } from '@/utils/clipboard';

// 配置marked选项
marked.setOptions({
  breaks: true,
  gfm: true,
});

// KaTeX渲染函数：处理$...$行内公式和$$...$$块级公式
function renderLatex(content: string): string {
  // 预处理：修复LLM生成的常见无效LaTeX温度表达式
  // \text{^\circ C} 在文本模式中使用了上标，KaTeX无法渲染
  // 修复策略：把 ^\circ 从 \text{} 内部移到外部，转为数学模式的上标
  content = content.replace(/\\text\{\s*\^\s*\\circ\s*(C|c)\s*\}/g, '^\\circ\\text{$1}');
  // 兼容 \text{°C} 这种带特殊字符的写法（° 在某些字体下渲染异常）
  content = content.replace(/\\text\{\s*°\s*(C|c)\s*\}/g, '^\\circ\\text{$1}');

  // 先处理块级公式 $$...$$
  content = content.replace(/\$\$([\s\S]*?)\$\$/g, (_match, tex) => {
    try {
      return katex.renderToString(tex.trim(), {
        throwOnError: true,
        displayMode: true,
      });
    } catch {
      // 渲染失败：移除LaTeX命令，回退为纯文本（去掉$分隔符）
      return stripLatexCommands(tex.trim());
    }
  });

  // 再处理行内公式 $...$
  content = content.replace(/\$([^\$\n]+?)\$/g, (_match, tex) => {
    try {
      return katex.renderToString(tex.trim(), {
        throwOnError: true,
        displayMode: false,
      });
    } catch {
      // 渲染失败：移除LaTeX命令，回退为纯文本（去掉$分隔符）
      return stripLatexCommands(tex.trim());
    }
  });

  return content;
}

// LaTeX命令清理：把无法渲染的LaTeX公式转为可读的纯文本
// 例如：\text{^\circ C} → ^\circ C → °C；\frac{a}{b} → a/b
function stripLatexCommands(tex: string): string {
  let result = tex;
  // 常见LaTeX命令替换为可读字符
  const replacements: Array<[RegExp, string]> = [
    [/\\circ/g, '°'],           // \circ → °
    [/\\text\{([^}]*)}/g, '$1'], // \text{...} → ...
    [/\\degree/g, '°'],          // \degree → °
    [/\\cdot/g, '·'],            // \cdot → ·
    [/\\times/g, '×'],           // \times → ×
    [/\\pm/g, '±'],              // \pm → ±
    [/\\le/g, '≤'],              // \le → ≤
    [/\\ge/g, '≥'],              // \ge → ≥
    [/\\ne/g, '≠'],              // \ne → ≠
    [/\\approx/g, '≈'],          // \approx → ≈
    [/\\infty/g, '∞'],           // \infty → ∞
    [/\\sqrt\{([^}]*)}/g, '√($1)'], // \sqrt{x} → √(x)
    [/\\frac\{([^}]*)}\{([^}]*)}/g, '$1/$2'], // \frac{a}{b} → a/b
    [/\\alpha/g, 'α'],
    [/\\beta/g, 'β'],
    [/\\gamma/g, 'γ'],
    [/\\delta/g, 'δ'],
    [/\\epsilon/g, 'ε'],
    [/\\theta/g, 'θ'],
    [/\\lambda/g, 'λ'],
    [/\\mu/g, 'μ'],
    [/\\pi/g, 'π'],
    [/\\sigma/g, 'σ'],
    [/\\omega/g, 'ω'],
    [/\\Delta/g, 'Δ'],
    [/\\Sigma/g, 'Σ'],
    [/\\Omega/g, 'Ω'],
    // 移除剩余的简单LaTeX命令（\commandname）
    [/\\[a-zA-Z]+/g, ''],
    // 清理多余的花括号
    [/\{([^{}]*)}/g, '$1'],
    // 清理 ^ 和 _ 后的空格
    [/\^\s+/g, '^'],
    [/_\s+/g, '_'],
  ];
  for (const [pattern, replacement] of replacements) {
    result = result.replace(pattern, replacement);
  }
  // 压缩多余空格
  result = result.replace(/\s+/g, ' ').trim();
  return result;
}
const props = withDefaults(defineProps<{
 message: any;
 size?: 'sm' | 'md' | 'lg';
}>(), {
 size: 'md',
});
const emit = defineEmits<{
 (e: 'copy', content: string): void;
 (e: 'regenerate', message: any): void;
 (e: 'edit', message: any, content: string): void;
 (e: 'sql', sql: string): void;
 (e: 'reference', reference: any): void;
 (e: 'export', command: string, message: any, chartOption?: any, dataViewMode?: string): void;
}>();
// 思考过程展开状态
const thinkingExpanded = ref(true);
const refsExpanded = ref(false);
// ChartCard 组件引用（用于直接从页面已渲染实例导出图片，避免数据丢失）
const chartCardRef = ref<InstanceType<typeof ChartCard> | null>(null);
// 编辑模式
const isEditing = ref(false);
const editContent = ref('');
// 数据可视化 - 使用ref以便用户可以切换视图模式
const dataViewMode = ref('table');
const chartConfig = ref({
 chartType: 'bar',
 xField: '',
 yField: '',
});
const chartOption = ref<any>(null);
// 计算属性
const showThinking = computed(() => {
 return (props.message.thinkingSteps && props.message.thinkingSteps.length > 0) ||
 (props.message.sqlTraces && props.message.sqlTraces.length > 0);
});
// Markdown渲染内容（先处理LaTeX公式，再渲染Markdown）
const renderedContent = computed(() => {
 const content = props.message.content || '';
 // 先渲染LaTeX公式
 const processed = renderLatex(content);
 // 再渲染Markdown
 let html = marked.parse(processed) as string;
 // 兜底处理：marked 在某些情况下（流式中间态、特殊字符干扰）可能未正确解析 **text**
 // 手动将残留的 **text** 替换为 <strong>text</strong>，避免 ** 符号直接显示给用户
 html = html.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
 return html;
});
const elapsedTime = computed(() => {
 // 优先使用queryTime，其次使用elapsedTime
 // 存储单位统一为毫秒，显示时除以1000转为秒
 const queryTime = props.message.queryTime;
 const elapsedTimeVal = props.message.elapsedTime;
 const timeMs = queryTime != null ? queryTime : (elapsedTimeVal != null ? elapsedTimeVal : null);
 
 if (timeMs == null || timeMs <= 0) {
 return '--';
 }
 
 // 存储的是毫秒，统一除以1000转为秒显示
 const seconds = timeMs / 1000;
 return seconds.toFixed(2) + 's';
});
// 方法
function toggleThinking() {
 thinkingExpanded.value = !thinkingExpanded.value;
}
function toggleReferences() {
 refsExpanded.value = !refsExpanded.value;
}
function handleCopy(content: string) {
 emit('copy', content);
}
function formatToolArgs(args: Record<string, any>): string {
 if (!args || Object.keys(args).length === 0) {
 return '无参数';
 }
 try {
 return JSON.stringify(args, null, 2);
 } catch {
 return Object.entries(args)
 .map(([k, v]) => `${k}: ${String(v)}`)
 .join(', ');
 }
}
async function handleCopySql(sql: string) {
 const ok = await copyToClipboard(sql);
 ok ? ElMessage.success('SQL已复制') : ElMessage.error('复制失败');
}
function handleStartEdit() {
 isEditing.value = true;
 editContent.value = props.message.content;
}
function handleCancelEdit() {
 isEditing.value = false;
 editContent.value = '';
}
function handleSubmitEdit() {
 if (!editContent.value.trim()) {
 ElMessage.warning('请输入内容');
 return;
 }
 emit('edit', props.message, editContent.value.trim());
 isEditing.value = false;
 editContent.value = '';
}
function handleRegenerate() {
 emit('regenerate', props.message);
}
function handleShowSql(sql: string) {
 emit('sql', sql);
}
function handleShowReference(ref: any) {
 emit('reference', ref);
}
function handleExport(command: string) {
  // 导出图片：优先从页面上实际渲染的 ChartCard 实例直接导出（100%还原显示效果，无数据丢失）
  if (command === 'image' && dataViewMode.value === 'chart' && chartCardRef.value) {
    const base64Data = chartCardRef.value.exportImage({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff',
    });
    if (base64Data) {
      // 直接下载图片
      const tableName = getTableName();
      const link = document.createElement('a');
      link.download = `图表导出_${tableName || '数据'}_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.png`;
      link.href = base64Data;
      link.click();
      ElMessage.success('图表导出成功');
      return;
    }
  }
  // 兜底逻辑：Excel 导出 或 图片导出失败时，交给父组件处理（重新渲染canvas）
  emit('export', command, props.message, chartOption.value, dataViewMode.value);
}
function getTableName() {
 if (!props.message.sqlTraces || props.message.sqlTraces.length === 0)
 return '';
 const sql = props.message.sqlTraces[0].sql;
 const match = sql.match(/FROM\s+(\w+)/i);
 return match ? match[1] : '';
}
function getFieldAlias(fieldName: string) {
 if (!props.message.columnMeta || props.message.columnMeta.length === 0)
 return null;
 // 兼容不同的字段名格式：name（后端返回）或 columnName（其他来源）
 const meta = props.message.columnMeta.find((m: any) => (m.name || m.columnName) === fieldName);
 // 兼容不同的别名字段：comment（后端返回）或 columnAlias（其他来源）
 return meta?.comment || meta?.columnAlias || null;
}
function getDataColumns() {
 if (!props.message.dataResult || props.message.dataResult.length === 0)
 return [];
 const keys = Object.keys(props.message.dataResult[0]);
 return keys.map((key) => ({
 prop: key,
 label: getFieldAlias(key) || key,
 minWidth: 120,
 }));
}
function getNumericColumns() {
 if (!props.message.dataResult || props.message.dataResult.length === 0)
 return [];
 const keys = Object.keys(props.message.dataResult[0]);
 return keys
 .filter((key) => {
 const val = props.message.dataResult[0][key];
 return typeof val === 'number' || (!isNaN(Number(val)) && val !== null && val !== '');
 })
 .map((key) => ({
 prop: key,
 label: getFieldAlias(key) || key,
 minWidth: 120,
 }));
}
function handleChartChange() {
 updateChartOption();
}
function handleChartTypeChange(command: string) {
 chartConfig.value.chartType = command;
 // 当用户选择图表类型时，自动切换到图表视图
 if (dataViewMode.value !== 'chart') {
 dataViewMode.value = 'chart';
 }
 updateChartOption();
}
function getChartTypeName(chartType: string): string {
 const typeMap: Record<string, string> = {
 bar: '柱状图',
 line: '折线图',
 pie: '饼图',
 table: '表格',
 };
 return typeMap[chartType] || '柱状图';
}
function updateChartOption() {
 const data = props.message.dataResult;
 if (!data || data.length === 0)
 return;
 const allCols = getDataColumns();
 const numCols = getNumericColumns();
 // 图表配色方案 - 现代化配色
 const chartColors = [
 '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981',
 '#06b6d4', '#6366f1', '#f43f5e', '#84cc16', '#0ea5e9',
 ];
 // 柱状图专用渐变色
 const barColors = ['#3b82f6', '#2563eb', '#1d4ed8', '#1e40af', '#1e3a8a'];
 // 折线图专用色
 const lineColor = '#3b82f6';
 // 首次初始化时，使用后端推荐的图表类型（仅在chartOption为空时）
 if (!chartOption.value && props.message.chartType && ['bar', 'line', 'pie'].includes(props.message.chartType)) {
 chartConfig.value.chartType = props.message.chartType;
 }
 // 默认选择
 if (!chartConfig.value.xField && allCols.length > 0) {
 chartConfig.value.xField = allCols[0].prop;
 }
 if (!chartConfig.value.yField && numCols.length > 0) {
 chartConfig.value.yField = numCols[0].prop;
 }
 if (!chartConfig.value.xField || !chartConfig.value.yField)
 return;
 // 获取坐标轴名称（使用字段中文别名）
 const xFieldLabel = getFieldAlias(chartConfig.value.xField) || chartConfig.value.xField;
 const yFieldLabel = getFieldAlias(chartConfig.value.yField) || chartConfig.value.yField;
 
 // 数据项数量，用于调整图表配置
 const dataLength = data.length;
 const needRotateLabel = dataLength > 6; // 数据多于6项时旋转X轴标签
 
 // 根据尺寸调整配置
 const isSmallSize = props.size === 'sm';
 const fontSize = isSmallSize ? 10 : 11;
 const nameFontSize = isSmallSize ? 11 : 12;
 const barMaxWidth = isSmallSize ? 30 : 40;
 const pieRadius = isSmallSize ? ['35%', '65%'] : ['40%', '70%'];
 
 // 生成图表配置 - 使用百分比布局让图表自适应填充容器
 const option: any = {
 color: chartColors,
 tooltip: {
 trigger: 'axis',
 axisPointer: { type: 'shadow' },
 confine: true,
 backgroundColor: 'rgba(255, 255, 255, 0.95)',
 borderColor: '#e2e8f0',
 borderWidth: 1,
 textStyle: { color: '#1e293b', fontSize: fontSize },
 padding: [8, 12],
 },
 grid: {
 left: '8%',
 right: '5%',
 bottom: needRotateLabel ? '20%' : '15%',
 top: '10%',
 containLabel: true,
 }
 };
 if (chartConfig.value.chartType === 'bar') {
 option.xAxis = {
 type: 'category',
 name: xFieldLabel,
 nameLocation: 'middle',
 nameGap: needRotateLabel ? 25 : 15,
 nameTextStyle: { fontSize: nameFontSize, color: '#64748b' },
 axisLabel: {
 rotate: needRotateLabel ? 45 : 0,
 fontSize: fontSize,
 color: '#64748b',
 interval: dataLength > 10 ? Math.ceil(dataLength / 10) - 1 : 0,
 },
 axisLine: { lineStyle: { color: '#e2e8f0' } },
 axisTick: { show: false },
 data: data.map((d: any) => d[chartConfig.value.xField])
 };
 option.yAxis = {
 type: 'value',
 name: yFieldLabel,
 nameLocation: 'middle',
 nameGap: 35,
 nameTextStyle: { fontSize: nameFontSize, color: '#64748b' },
 axisLabel: { fontSize: fontSize, color: '#64748b' },
 axisLine: { show: false },
 axisTick: { show: false },
 splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
 };
 // 为每个柱子分配不同的颜色
 const barData = data.map((d: any, idx: number) => ({
 value: d[chartConfig.value.yField],
 itemStyle: {
 color: barColors[idx % barColors.length],
 borderRadius: [4, 4, 0, 0],
 }
 }));
 option.series = [{
 type: 'bar',
 data: barData,
 barMaxWidth: barMaxWidth,
 barMinHeight: 4,
 emphasis: {
 itemStyle: {
 shadowBlur: 10,
 shadowColor: 'rgba(59, 130, 246, 0.5)',
 }
 }
 }];
 }
 else if (chartConfig.value.chartType === 'line') {
 option.xAxis = {
 type: 'category',
 name: xFieldLabel,
 nameLocation: 'middle',
 nameGap: needRotateLabel ? 25 : 15,
 nameTextStyle: { fontSize: nameFontSize, color: '#64748b' },
 axisLabel: {
 rotate: needRotateLabel ? 45 : 0,
 fontSize: fontSize,
 color: '#64748b',
 interval: dataLength > 10 ? Math.ceil(dataLength / 10) - 1 : 0,
 },
 axisLine: { lineStyle: { color: '#e2e8f0' } },
 axisTick: { show: false },
 boundaryGap: false,
 data: data.map((d: any) => d[chartConfig.value.xField])
 };
 option.yAxis = {
 type: 'value',
 name: yFieldLabel,
 nameLocation: 'middle',
 nameGap: 35,
 nameTextStyle: { fontSize: nameFontSize, color: '#64748b' },
 axisLabel: { fontSize: fontSize, color: '#64748b' },
 axisLine: { show: false },
 axisTick: { show: false },
 splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
 };
 option.series = [{
 type: 'line',
 data: data.map((d: any) => d[chartConfig.value.yField]),
 smooth: true,
 showSymbol: dataLength <= 20,
 symbol: 'circle',
 symbolSize: isSmallSize ? 3 : 4,
 lineStyle: { width: isSmallSize ? 1.5 : 2, color: lineColor },
 itemStyle: { color: lineColor },
 areaStyle: {
 color: {
 type: 'linear',
 x: 0, y: 0, x2: 0, y2: 1,
 colorStops: [
 { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
 { offset: 1, color: 'rgba(59, 130, 246, 0.02)' },
 ]
 }
 },
 emphasis: {
 focus: 'series',
 itemStyle: {
 borderWidth: 2,
 borderColor: '#fff',
 shadowBlur: 10,
 shadowColor: 'rgba(59, 130, 246, 0.5)',
 }
 }
 }];
 }
 else if (chartConfig.value.chartType === 'pie') {
 option.grid = { top: '5%', bottom: '5%', left: '5%', right: '5%' };
 // 饼图tooltip配置，显示名称和数值
 option.tooltip = {
 trigger: 'item',
 backgroundColor: 'rgba(255, 255, 255, 0.95)',
 borderColor: '#e2e8f0',
 borderWidth: 1,
 textStyle: { color: '#1e293b', fontSize: fontSize },
 formatter: '{b}: {c} ({d}%)'
 };
 // 处理饼图数据：当数据点过多时，合并为"其他"
 let pieData = data.map((d: any) => ({
 name: d[chartConfig.value.xField],
 value: d[chartConfig.value.yField]
 }));
 // 如果数据点超过15个，只保留前10个，其余合并为"其他"
 if (pieData.length > 15) {
 pieData.sort((a, b) => b.value - a.value);
 const topData = pieData.slice(0, 10);
 const restValue = pieData.slice(10).reduce((sum, item) => sum + item.value, 0);
 if (restValue > 0) {
 topData.push({ name: '其他', value: restValue });
 }
 pieData = topData;
 }
 option.series = [{
 type: 'pie',
 radius: pieRadius,
 center: ['50%', '50%'],
 avoidLabelOverlap: true,
 itemStyle: {
 borderRadius: 4,
 borderColor: '#fff',
 borderWidth: 2
 },
 label: {
 show: pieData.length <= 10,
 fontSize: fontSize,
 color: '#64748b',
 formatter: '{b}: {c}'
 },
 labelLine: {
 show: pieData.length <= 10,
 length: isSmallSize ? 8 : 10,
 length2: isSmallSize ? 8 : 10,
 lineStyle: { color: '#e2e8f0' }
 },
 emphasis: {
 scale: true,
 scaleSize: 10,
 itemStyle: {
 shadowBlur: 10,
 shadowColor: 'rgba(0, 0, 0, 0.2)',
 }
 },
 data: pieData
 }];
 }
 chartOption.value = option;
}
// 监听数据变化和列元数据变化
watch(() => [props.message.dataResult, props.message.columnMeta], () => {
 if (props.message.dataResult && props.message.dataResult.length > 0) {
 // 首次初始化时，根据后端推荐的图表类型设置默认视图
 if (dataViewMode.value === 'table' && props.message.chartType && ['bar', 'line', 'pie'].includes(props.message.chartType)) {
 dataViewMode.value = 'chart';
 }
 // 重置图表配置，让updateChartOption自动选择合适的字段
 if (!chartConfig.value.xField || !chartConfig.value.yField) {
 updateChartOption();
 } else {
 // 如果已有配置，检查列名是否需要更新（因为columnMeta可能变化）
 updateChartOption();
 }
 }
}, { immediate: true, deep: true });
</script>

<style lang="scss" scoped>
.message-item {
  width: 100%;

  // 小尺寸样式 - 用于调试预览等紧凑场景
  &.size-sm {
    .message-content {
      gap: 8px;
    }
    .avatar-group {
      width: 28px;
      height: 28px;
      overflow: hidden;
      :deep(.avatar-image) {
        width: 28px;
        height: 28px;
      }
    }
    .message-bubble {
      padding: 8px 12px;
      font-size: 12px;
      line-height: 1.5;
    }
    .thinking-process {
      margin-bottom: 8px;
      .thinking-header {
        padding: 6px 10px;
        .thinking-title { font-size: 12px; }
        .thinking-count { font-size: 11px; padding: 1px 6px; }
        .thinking-action { font-size: 11px; }
      }
      .thinking-content { padding: 8px 10px; }
      .step-item { padding: 4px 0 4px 24px; }
      .step-title { font-size: 12px; }
      .step-desc { font-size: 11px; }
    }
    .references-section {
      margin-top: 8px;
      padding-top: 8px;
      .references-header { font-size: 12px; }
      .ref-card { padding: 6px 10px; }
    }
    .sql-section {
      .section-header { padding: 6px 10px; font-size: 11px; }
      .sql-content { padding: 8px; }
      .sql-code { font-size: 11px; }
    }
    .chart-section {
      .section-header { padding: 6px 8px; }
      .header-left { font-size: 12px; gap: 4px; }
      .table-name-badge {
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .view-toggle-group { margin-left: 6px; padding-left: 6px; gap: 2px; }
      .chart-type-btn { padding: 2px 4px; }
      .view-btn { width: 24px; height: 24px; }
      .chart-body { padding: 6px; }
      .chart-container { height: 220px; min-height: 180px; }
      .chart-placeholder { padding: 20px; }
      .header-right { gap: 4px; }
      .export-btn { 
        padding: 2px 6px; 
        span { font-size: 12px; }
      }
    }
    .message-meta {
      margin-top: 6px;
      .meta-action-icon { font-size: 12px; }
      span { font-size: 11px; }
    }
    .user-message-actions {
      .meta-action-icon { font-size: 12px; }
    }
  }

  // 大尺寸样式 - 用于全屏智能对话
  &.size-lg {
    .message-content {
      gap: 16px;
    }
    .avatar-group {
      width: 44px;
      height: 44px;
      overflow: hidden;
      :deep(.avatar-image) {
        width: 44px;
        height: 44px;
      }
    }
    .message-bubble {
      padding: 16px 20px;
      font-size: 15px;
      line-height: 1.7;
    }
    .thinking-process {
      margin-bottom: 16px;
      .thinking-header {
        padding: 12px 16px;
        .thinking-title { font-size: 14px; }
      }
      .thinking-content { padding: 14px 16px; }
    }
    .chart-section {
      .chart-container { height: 320px; min-height: 260px; }
    }
  }

  .message-content {
    display: flex;
    gap: 12px;
    max-width: 100%;
    animation: fadeIn 0.3s ease;

    &.user {
      flex-direction: row-reverse;
    }

    &.assistant {
      flex-direction: row;
    }
  }

  .avatar-group {
    flex-shrink: 0;
    width: 36px;
    height: 36px;
  }

  .message-bubble-wrap {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 80%;

    // 助手消息固定宽度，确保不同类型回答（文本/图表）宽度一致
    &:not(.user-bubble-wrap) {
      width: 80%;
    }

    // 用户消息靠右，右边与AI消息右边对齐
    &.user-bubble-wrap {
      margin-left: auto;
    }

    // 编辑模式：全宽显示，左边与AI消息左边对齐
    &.editing {
      width: 100%;
      max-width: 100%;
      margin-left: 0;
    }
  }

  .message-bubble {
    position: relative;
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 14px;
    line-height: 1.6;
    word-break: break-word;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    box-shadow: none;
    box-sizing: border-box;

    .bubble-arrow {
      display: none;
    }

    .bubble-content {
      white-space: pre-wrap;
    }

    .message-text {
      white-space: pre-wrap;
    }
    
    // 消息内容容器 - 透明背景，与message-bubble融合
    .message-content-box {
      border: none;
      border-radius: 0;
      padding: 0;
      margin-bottom: 0;
      background: transparent;
    }

    // Markdown渲染样式
    .markdown-content {
      white-space: normal;
      
      :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
        margin: 8px 0 4px;
        font-weight: 600;
        line-height: 1.4;
      }
      
      :deep(h1) { font-size: 16px; }
      :deep(h2) { font-size: 15px; }
      :deep(h3) { font-size: 14px; }
      
      :deep(p) {
        margin: 4px 0;
        line-height: 1.6;
      }
      
      :deep(strong), :deep(b) {
        font-weight: 600;
      }
      
      :deep(em), :deep(i) {
        font-style: italic;
      }
      
      :deep(ul), :deep(ol) {
        margin: 4px 0;
        padding-left: 20px;
      }
      
      :deep(li) {
        margin: 2px 0;
        line-height: 1.5;
      }
      
      :deep(code) {
        background: #f1f5f9;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 13px;
      }
      
      :deep(pre) {
        background: #1e293b;
        color: #e2e8f0;
        padding: 12px;
        border-radius: 8px;
        overflow-x: auto;
        margin: 8px 0;
      }
      
      :deep(pre code) {
        background: transparent;
        padding: 0;
        color: inherit;
      }
      
      :deep(a) {
        color: #3b82f6;
        text-decoration: none;
        
        &:hover {
          text-decoration: underline;
        }
      }
      
      :deep(blockquote) {
        margin: 8px 0;
        padding: 8px 12px;
        border-left: 3px solid #3b82f6;
        background: #f8fafc;
        border-radius: 0 8px 8px 0;
        color: #475569;
      }
      
      :deep(hr) {
        margin: 12px 0;
        border: none;
        border-top: 1px solid #e2e8f0;
      }
      
      :deep(table) {
        border-collapse: collapse;
        margin: 8px 0;
        width: 100%;
      }
      
      :deep(th), :deep(td) {
        border: 1px solid #e2e8f0;
        padding: 6px 10px;
        text-align: left;
      }
      
      :deep(th) {
        background: #f8fafc;
        font-weight: 600;
      }
    }

    .streaming-cursor {
      display: inline-block;
      margin-left: 2px;
      animation: blink 0.7s infinite;
    }

    .typing-indicator {
      display: flex;
      gap: 4px;
      padding: 4px 0;

      span {
        width: 6px;
        height: 6px;
        background: #94a3b8;
        border-radius: 50%;
        animation: typing 1.4s infinite;

        &:nth-child(2) { animation-delay: 0.2s; }
        &:nth-child(3) { animation-delay: 0.4s; }
      }
    }

    // 用户消息样式 - 继承.message-bubble的边框
    .user & {
      background: #ffffff;
      color: #1e293b;
      border: 1px solid #e2e8f0;
      box-shadow: none;
    }

    // AI消息样式 - 继承.message-bubble的边框
    .assistant & {
      background: #ffffff;
      color: #1e293b;
      border: 1px solid #e2e8f0;
      box-shadow: none;
    }
  }

  // 编辑模式
  .message-bubble.edit-mode {
    background: #ffffff;
    border: 1px solid #3b82f6;
    padding: 8px;
  }

  .edit-input-wrap {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .edit-input {
    :deep(.el-textarea__inner) {
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 8px 12px;
    }
  }

  .edit-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  // 思考过程（内嵌在消息气泡内）
  .thinking-process {
    background-color: #f8fafc;
    border-radius: 8px;
    border: none;
    overflow: hidden;
    margin-bottom: 12px;

    .thinking-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      cursor: pointer;
      background: #f8fafc;
      transition: background-color 0.2s;

      &:hover {
        background: #f1f5f9;
      }
    }

    .thinking-title {
      font-size: 13px;
      font-weight: 600;
      color: #475569;
    }

    .thinking-count {
      font-size: 12px;
      color: #94a3b8;
      padding: 2px 8px;
      background: #e2e8f0;
      border-radius: 10px;
    }

    .thinking-action {
      font-size: 12px;
      color: #64748b;
      margin-left: auto;
    }

    .thinking-content {
      padding: 10px 12px;
      border-top: 1px solid #e2e8f0;
    }

    .steps-timeline {
      position: relative;
      padding-left: 0;
    }

    .step-item {
      position: relative;
      display: flex;
      gap: 10px;
      padding: 8px 0 8px 24px;
      min-height: 36px;
    }

    .step-connector {
      position: absolute;
      left: 0;
      top: 8px;
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 24px;
      height: calc(100% - 16px);
    }

    .connector-line {
      position: absolute;
      left: 50%;
      top: 20px;
      transform: translateX(-50%);
      width: 2px;
      height: calc(100% - 20px);
      background: #e2e8f0;

      &.last {
        background: transparent;
      }
    }

    .step-dot {
      position: relative;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #e2e8f0;
      z-index: 1;
      flex-shrink: 0;

      &.active {
        background: #3b82f6;
        animation: pulse 1.5s ease-in-out infinite;
      }

      &.completed {
        background: #10b981;
      }
    }

    .step-content {
      flex: 1;
      padding-left: 4px;
      padding-bottom: 4px;
    }

    .step-title {
      font-size: 13px;
      font-weight: 500;
      color: #1e293b;
      line-height: 20px;
    }

    .step-desc {
      font-size: 12px;
      color: #64748b;
      margin-top: 2px;
      line-height: 18px;
      word-break: break-word;
      white-space: normal;
    }
  }

  // 知识引用（与message-bubble视觉一体）
  .references-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #e2e8f0;

    .references-header {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 13px;
      color: #475569;
      font-weight: 500;

      .references-count {
        font-size: 12px;
        color: #94a3b8;
      }

      .references-action {
        font-size: 12px;
        color: #64748b;
        margin-left: auto;
      }
    }

    .ref-cards {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .ref-card {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 10px 12px;
      background: #f8fafc;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        background: #f1f5f9;
        border-color: #3b82f6;
      }
    }

    .ref-header {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;

      .ref-name {
        flex: 1;
        font-weight: 500;
        color: #1e293b;
      }

      .ref-score {
        color: #10b981;
        font-weight: 500;
      }
    }

    .ref-content {
      font-size: 12px;
      color: #64748b;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }

  // 工具调用
  .tool-calls-section {
    margin-top: 8px;
    background: #f0f9ff;
    border-radius: 8px;
    border: 1px solid #bae6fd;
    overflow: hidden;

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      background: #e0f2fe;
      color: #0369a1;
      font-size: 12px;
      font-weight: 500;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .tool-calls-count {
      background: #0284c7;
      color: white;
      padding: 2px 6px;
      border-radius: 10px;
      font-size: 11px;
    }

    .tool-calls-content {
      padding: 10px 12px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .tool-call-item {
      background: white;
      border-radius: 6px;
      padding: 10px;
      border: 1px solid #e2e8f0;
    }

    .tool-call-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .tool-icon {
      color: #0284c7;
      font-size: 14px;
    }

    .tool-name {
      font-size: 13px;
      font-weight: 500;
      color: #1e293b;
    }

    .tool-status-tag {
      margin-left: auto;
    }

    .tool-args {
      display: flex;
      gap: 4px;
      font-size: 12px;
      margin-bottom: 6px;

      .args-label {
        color: #64748b;
        flex-shrink: 0;
      }

      .args-value {
        color: #334155;
        font-family: 'Courier New', monospace;
        word-break: break-all;
      }
    }

    .tool-result {
      background: #f8fafc;
      border-radius: 4px;
      padding: 8px;
      font-size: 12px;

      .result-label {
        color: #64748b;
        margin-bottom: 4px;
      }

      .result-content {
        color: #334155;
        white-space: pre-wrap;
        word-break: break-word;
      }
    }
  }

  // SQL查询
  .sql-section {
    margin-top: 8px;
    background: #1e293b;
    border-radius: 8px;
    overflow: hidden;

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      background: #334155;
      color: #e2e8f0;
      font-size: 12px;
      font-weight: 500;
    }

    .sql-content {
      padding: 12px;
    }

    .sql-code {
      color: #94a3b8;
      font-size: 12px;
      font-family: 'Courier New', monospace;
      white-space: pre-wrap;
      word-break: break-all;
      margin: 0;
    }

    .sql-meta {
      margin-top: 8px;
      font-size: 11px;
      color: #64748b;
    }
  }

  // 数据可视化
  .chart-section {
    margin-top: 8px;
    background: #ffffff;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    overflow: hidden;

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 13px;
      font-weight: 500;
      color: #1e293b;
      flex: 1;
      min-width: 0;
    }

    .table-name-badge {
      background: #eef2ff;
      color: #4f46e5;
      border-radius: 4px;
      font-size: 11px;
      font-family: 'Courier New', monospace;
      max-width: 200px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex-shrink: 1;
    }

    .view-toggle-group {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-left: 12px;
      padding-left: 8px;
      border-left: 1px solid #e2e8f0;
      flex-shrink: 0;
    }

    .chart-type-btn {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: #1e293b;
      padding: 4px 8px;
      flex-shrink: 0;
      
      &:hover {
        background: #f1f5f9;
      }
    }

    .arrow-icon {
      font-size: 12px;
      color: #94a3b8;
    }

    .view-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border-radius: 6px;
      color: #64748b;
      background: transparent;
      border: 1px solid transparent;
      padding: 0;

      &:hover {
        color: #1e293b;
        background: #f1f5f9;
      }

      &.active {
        color: #3b82f6;
        background: #eff6ff;
        border-color: #bfdbfe;
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }

    .export-btn {
      white-space: nowrap;
      flex-shrink: 0;
    }

    .chart-body {
      padding: 8px;
    }

    .table-wrapper {
      max-height: 300px;
      overflow: auto;
    }

    .table-footer {
      padding: 8px 0;
      text-align: center;
      font-size: 12px;
      color: #94a3b8;
    }

    .chart-wrapper {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .chart-container {
      height: 280px;
      min-height: 220px;
    }

    .chart-placeholder {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px;
      color: #94a3b8;

      p {
        margin-top: 12px;
        font-size: 13px;
      }
    }
  }

  // 消息元数据
  .message-meta {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 8px;

    .meta-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .meta-action-icon {
      font-size: 14px;
      color: #94a3b8;
      cursor: pointer;
      transition: color 0.2s;

      &:hover {
        color: #3b82f6;
      }
    }

    .meta-icon {
      font-size: 12px;
      color: #94a3b8;
    }

    span {
      font-size: 12px;
      color: #94a3b8;
    }
  }

  // 用户消息操作按钮
  .user-message-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;

    .meta-action-icon {
      font-size: 14px;
      color: #94a3b8;
      cursor: pointer;
      transition: color 0.2s;

      &:hover {
        color: #3b82f6;
      }
    }
  }
}

// 动画
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(59, 130, 246, 0);
  }
}
</style>
