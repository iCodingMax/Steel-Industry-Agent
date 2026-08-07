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

    <!-- 输入框 -->
    <div class="chat-input-area">
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
const inputRows = computed(() => props.size === 'sm' ? 1 : 2)

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

  .input-wrapper {
    display: flex;
    align-items: flex-end;
    gap: 8px;
  }

  .chat-input {
    flex: 1;

    :deep(.el-textarea__inner) {
      border-radius: 8px;
      padding: 6px 12px;
      font-size: 14px;
      border: 1px solid #e2e8f0;
      transition: all 0.2s;

      &:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
      }
    }
  }

  .input-actions {
    flex-shrink: 0;
  }

  .send-btn {
    border-radius: 8px;
    padding: 6px 16px;
    height: 32px;
  }
}
</style>
