<template>
  <div class="chat-panel" :class="[`size-${size}`]">
    <!-- 消息列表 -->
    <div class="chat-messages" ref="messagesRef" @scroll="handleScroll">
      <!-- 欢迎提示 -->
      <div v-if="messages.length === 0" class="chat-welcome">
        <div class="welcome-icon">
          <el-icon :size="48" color="#3b82f6"><ChatDotRound /></el-icon>
        </div>
        <h3 class="welcome-title">{{ welcomeTitle }}</h3>
        <p class="welcome-desc">{{ welcomeDesc }}</p>
        <div v-if="suggestions && suggestions.length > 0" class="suggestions">
          <div
            v-for="(suggestion, idx) in suggestions"
            :key="idx"
            class="suggestion-item"
            @click="handleSuggestion(suggestion)"
          >
            {{ suggestion }}
          </div>
        </div>
      </div>
      
      <!-- 消息列表 -->
      <ChatMessage
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
        :size="size"
        @copy="(content) => emit('copy', content)"
        @regenerate="(message) => emit('regenerate', message)"
        @edit="(message, content) => emit('edit', message, content)"
        @sql="(sql) => emit('sql', sql)"
        @reference="(reference) => emit('reference', reference)"
        @export="(command, message, chartOption, dataViewMode) => emit('export', command, message, chartOption, dataViewMode)"
      />
    </div>

    <!-- 输入框区域（支持上边框拖拽调整高度） -->
    <div class="chat-input-area" :style="{ height: inputAreaHeight + 'px' }" ref="inputAreaRef">
      <!-- 拖拽把手：位于输入框上边缘，鼠标按住向上拖拽增加输入框高度 -->
      <div
        class="input-resize-handle"
        @mousedown="startResize"
        title="拖拽调整输入框高度"
      >
        <span class="resize-indicator"></span>
      </div>
      <div class="input-wrapper">
        <el-input
          v-model="localInputText"
          type="textarea"
          :rows="inputRows"
          :placeholder="inputPlaceholder"
          resize="none"
          @keydown.enter.exact="handleEnterKey"
          class="chat-input"
          :disabled="disabled"
        />
        <div class="input-actions">
          <el-button
            type="primary"
            :loading="isSending"
            @click="handleSend"
            class="send-btn"
            :disabled="!localInputText.trim() || disabled"
          >
            <el-icon><Right /></el-icon>
            {{ sendButtonText }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onUnmounted } from 'vue'
import { ChatDotRound, Right } from '@element-plus/icons-vue'
import ChatMessage from './ChatMessage.vue'

const props = withDefaults(defineProps<{
  messages: any[]
  modelValue: string
  isSending: boolean
  welcomeTitle?: string
  welcomeDesc?: string
  suggestions?: string[]
  inputPlaceholder?: string
  sendButtonText?: string
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
}>(), {
  welcomeTitle: '您好，有什么可以帮您？',
  welcomeDesc: '请输入您的问题，我将为您解答',
  inputPlaceholder: '输入您的问题...',
  sendButtonText: '发送',
  size: 'md',
  disabled: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'send', content: string): void
  (e: 'suggestion', suggestion: string): void
  (e: 'copy', content: string): void
  (e: 'regenerate', message: any): void
  (e: 'edit', message: any, content: string): void
  (e: 'sql', sql: string): void
  (e: 'reference', reference: any): void
  (e: 'export', command: string, message: any, chartOption?: any, dataViewMode?: string): void
}>()

// 本地输入框文本，与 modelValue 同步
const localInputText = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const messagesRef = ref<HTMLElement>()
const inputAreaRef = ref<HTMLElement>()
const inputRows = computed(() => props.size === 'sm' ? 1 : 2)

// ===================== 输入框拖拽调整高度 =====================
// 输入框区域高度（px），用户可通过拖拽上边缘把手调整
// 默认值根据 size 不同有所差异：sm=60, md/md=80
const defaultInputHeight = computed(() => props.size === 'sm' ? 60 : 80)
const inputAreaHeight = ref(defaultInputHeight.value)

// 拖拽限制（px）
const MIN_INPUT_HEIGHT = 44    // 最小高度（单行输入）
const MAX_INPUT_HEIGHT = 320   // 最大高度（约15行）

// 当 size 切换时（如从对话页切到调试预览），重置为该 size 的默认高度
watch(defaultInputHeight, (newH) => {
  inputAreaHeight.value = newH
})

// 拖拽状态
let isResizing = false
let resizeStartY = 0
let resizeStartHeight = 0

// 开始拖拽
function startResize(e: MouseEvent) {
  // 避免右键或中键触发
  if (e.button !== 0) return
  e.preventDefault()
  e.stopPropagation()

  isResizing = true
  resizeStartY = e.clientY
  resizeStartHeight = inputAreaRef.value?.offsetHeight || inputAreaHeight.value

  // 拖拽期间禁用文本选择，避免选中输入框内容
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'ns-resize'

  // 绑定全局事件（拖拽过程中鼠标可能移出把手元素）
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', stopResize)
}

// 拖拽移动：鼠标向上移动 → 输入框高度增加
function onResizeMove(e: MouseEvent) {
  if (!isResizing) return
  // 鼠标向上移动时 deltaY 为负值，高度 = 起始高度 - deltaY
  const deltaY = e.clientY - resizeStartY
  let newHeight = resizeStartHeight - deltaY

  // 边界约束
  if (newHeight < MIN_INPUT_HEIGHT) newHeight = MIN_INPUT_HEIGHT
  if (newHeight > MAX_INPUT_HEIGHT) newHeight = MAX_INPUT_HEIGHT

  inputAreaHeight.value = newHeight
}

// 结束拖拽
function stopResize() {
  if (!isResizing) return
  isResizing = false

  // 恢复样式
  document.body.style.userSelect = ''
  document.body.style.cursor = ''

  // 解绑全局事件
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', stopResize)
}

// 组件卸载时清理拖拽事件监听
onUnmounted(() => {
  if (isResizing) {
    document.removeEventListener('mousemove', onResizeMove)
    document.removeEventListener('mouseup', stopResize)
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
  }
})
// =================================================================

// 滚动控制状态
const isNearBottom = ref(true)  // 用户是否接近底部（50px 以内）
let scrollRafId: number | null = null
let isUserScrolling = false

// 监听滚动事件，判断用户是否在查看历史
function handleScroll() {
  if (!messagesRef.value) return
  const el = messagesRef.value
  const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  isNearBottom.value = distanceFromBottom <= 50
  isUserScrolling = true
  
  // 清除之前的定时器
  if ((window as any)._scrollTimer) {
    clearTimeout((window as any)._scrollTimer)
  }
  
  // 300ms 后恢复用户滚动状态
  ;(window as any)._scrollTimer = setTimeout(() => {
    isUserScrolling = false
  }, 300)
}

// 平滑滚动到底部
function scrollToBottom() {
  nextTick(() => {
    if (!messagesRef.value) return
    const el = messagesRef.value
    cancelAnimationFrame(scrollRafId!)
    scrollRafId = requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight
    })
  })
}

// 监听消息数量变化（新消息添加时）
watch(() => props.messages.length, () => {
  scrollToBottom()
})

// 监听消息内容变化（流式输出时内容更新）
watch(
  () => props.messages.map(m => m.content),
  () => {
    if (props.isSending && isNearBottom.value) {
      scrollToBottom()
    }
  }
)

// 监听思考过程步骤变化（执行过程时滚动条自动滚动）
watch(
  () => props.messages.map(m => m.thinkingSteps?.length || 0),
  () => {
    if (props.isSending) {
      // 执行过程更新时，强制滚动到底部
      scrollToBottom()
    }
  }
)

// 监听 isSending 状态变化
watch(() => props.isSending, (val) => {
  if (val) {
    // 开始发送时，重置自动滚动状态
    isNearBottom.value = true
  } else {
    // 发送完成后，滚动到底部
    scrollToBottom()
  }
})

// 组件卸载时清理
onUnmounted(() => {
  if (scrollRafId) {
    cancelAnimationFrame(scrollRafId)
  }
})

function handleEnterKey(e: KeyboardEvent) {
  if (e.shiftKey) {
    return
  }
  e.preventDefault()
  handleSend()
}

function handleSend() {
  if (!localInputText.value.trim() || props.isSending || props.disabled) {
    return
  }
  emit('send', localInputText.value.trim())
  localInputText.value = ''
}

function handleSuggestion(suggestion: string) {
  emit('suggestion', suggestion)
}

// 暴露方法给父组件
defineExpose({
  scrollToBottom,
  localInputText,
})
</script>

<style lang="scss" scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #ffffff;
  border-radius: 12px;
  overflow: hidden;
  min-height: 0;

  &.size-sm {
    .chat-messages {
      padding: 12px;
    }
    .chat-input-area {
      padding: 8px;
      flex-shrink: 0;
    }
    .welcome-title {
      font-size: 16px;
    }
    .welcome-desc {
      font-size: 12px;
    }
  }

  &.size-md {
    .chat-messages {
      padding: 16px;
    }
    .chat-input-area {
      padding: 10px 16px;
      flex-shrink: 0;

      .chat-input {
        :deep(.el-textarea__inner) {
          padding: 6px 12px;
        }
      }

      .send-btn {
        padding: 6px 16px;
        height: 32px;
      }
    }
  }

  &.size-lg {
    .chat-messages {
      padding: 20px;
    }
    .chat-input-area {
      padding: 10px 20px;
      flex-shrink: 0;
    }
  }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: #f8fafc;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 3px;

    &:hover {
      background: #94a3b8;
    }
  }
}

.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.welcome-icon {
  margin-bottom: 16px;
}

.welcome-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 8px;
}

.welcome-desc {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 24px;
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  max-width: 480px;
}

.suggestion-item {
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  color: #475569;
  text-align: left;

  &:hover {
    border-color: #3b82f6;
    background: #f0f7ff;
    color: #1e40af;
  }
}

.chat-input-area {
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
  flex-shrink: 0;
  padding-right: 4px;
  /* 高度由 JS 控制（inputAreaHeight），这里设置 display:flex 让内部 wrapper 填充 */
  display: flex;
  flex-direction: column;
  /* height 设置包含 padding，避免尺寸计算混乱 */
  box-sizing: border-box;
  /* 过渡动画让非拖拽状态下的高度变化更平滑（拖拽时由于频繁更新，过渡会被自然跳过） */
  transition: height 0.1s ease-out;
  position: relative;

  /* 拖拽把手：位于输入框区域顶部，呈现为一条可悬停的细条 */
  .input-resize-handle {
    height: 6px;
    flex-shrink: 0;
    cursor: ns-resize;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    transition: background 0.15s;
    user-select: none;

    /* 中间的视觉指示条（默认浅色，悬停时高亮） */
    .resize-indicator {
      width: 36px;
      height: 3px;
      background: #cbd5e1;
      border-radius: 2px;
      transition: background 0.15s, width 0.15s;
    }

    &:hover {
      background: #f1f5f9;

      .resize-indicator {
        background: #3b82f6;
        width: 48px;
      }
    }

    /* 拖拽激活状态（由 JS 在 body 上设置 cursor，这里仅做视觉提示） */
    &:active {
      .resize-indicator {
        background: #2563eb;
      }
    }
  }

  .input-wrapper {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    /* 让 wrapper 填充除把手外的剩余空间 */
    flex: 1;
    min-height: 0;
    padding: 0 0 0 4px;
  }

  .chat-input {
    flex: 1;
    min-width: 0;
    /* 让 el-input 撑满 wrapper 高度 */
    height: 100%;

    :deep(.el-textarea) {
      height: 100%;
    }

    :deep(.el-textarea__inner) {
      border-radius: 8px;
      padding: 6px 12px;
      font-size: 14px;
      border: 1px solid #e2e8f0;
      transition: border-color 0.2s, box-shadow 0.2s;
      /* 让 textarea 内部撑满高度 */
      height: 100% !important;
      min-height: 36px;
      resize: none;
      box-sizing: border-box;

      &:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
      }
    }
  }

  .input-actions {
    flex-shrink: 0;
    margin-right: 4px;
  }

  .send-btn {
    border-radius: 8px;
    padding: 6px 16px;
    height: 32px;
    white-space: nowrap;
  }
}
</style>
