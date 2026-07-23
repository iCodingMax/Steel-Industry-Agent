<template>
  <div class="chat-embed-view">
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <h2 class="sidebar-title">对话历史</h2>
        <el-button type="primary" size="small" @click="handleNewChat" class="new-chat-btn">
          <el-icon><Plus /></el-icon>
          新对话
        </el-button>
      </div>
      <div class="sidebar-search">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索历史对话..."
          size="small"
          prefix-icon="Search"
        />
      </div>
      <div class="sidebar-sessions">
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="selectSession(session.id)"
        >
          <div class="session-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <div class="session-info">
            <div v-if="editingSessionId === session.id" class="session-rename" @click.stop>
              <el-input
                v-model="renameValue"
                size="small"
                placeholder="输入新名称"
                @keyup.enter="confirmRename(session.id)"
                @keyup.escape="cancelRename"
                @blur="confirmRename(session.id)"
              />
            </div>
            <div v-else class="session-name">{{ session.title || '新对话' }}</div>
            <div class="session-time">{{ formatTime(session.updatedAt) }}</div>
          </div>
          <div v-if="editingSessionId !== session.id" class="session-actions" @click.stop>
            <el-button text size="small" class="action-btn" @click="startRename(session)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button text size="small" class="action-btn delete-btn" @click="handleDeleteSession(session)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <div v-if="currentSessionId === session.id && editingSessionId !== session.id" class="session-active-indicator"></div>
        </div>
      </div>
    </div>

    <div class="chat-main">
      <div class="chat-header">
        <div class="header-left">
          <div class="header-logo">
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="20" cy="20" r="18" stroke="#3b82f6" stroke-width="2" fill="none" opacity="0.6"/>
              <circle cx="20" cy="20" r="14" stroke="#3b82f6" stroke-width="1.5" fill="none" stroke-dasharray="22 66" stroke-dashoffset="0" opacity="0.8"/>
              <circle cx="20" cy="20" r="10" stroke="#60a5fa" stroke-width="1.5" fill="none" stroke-dasharray="16 47" stroke-dashoffset="-8" opacity="0.9"/>
              <circle cx="20" cy="20" r="4" fill="#3b82f6"/>
              <circle cx="20" cy="20" r="2" fill="#93c5fd"/>
            </svg>
          </div>
          <span class="session-title">{{ currentSession?.title || appName }}</span>
        </div>
      </div>

      <div ref="messagesRef" class="chat-messages">
        <div v-if="messages.length === 0" class="welcome-banner">
          <div class="welcome-icon">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              <line x1="32" y1="4" x2="32" y2="14" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
              <circle cx="32" cy="4" r="3" fill="#fbbf24"/>
              <rect x="14" y="14" width="36" height="24" rx="6" fill="#e2e8f0"/>
              <rect x="14" y="14" width="36" height="24" rx="6" stroke="#fff" stroke-width="1.5"/>
              <circle cx="24" cy="26" r="4" fill="#3b82f6"/>
              <circle cx="40" cy="26" r="4" fill="#3b82f6"/>
              <circle cx="24" cy="25" r="1.5" fill="#fff"/>
              <circle cx="40" cy="25" r="1.5" fill="#fff"/>
              <rect x="26" y="32" width="12" height="2.5" rx="1.25" fill="#3b82f6"/>
              <rect x="18" y="40" width="28" height="16" rx="4" fill="#cbd5e1"/>
              <rect x="18" y="40" width="28" height="16" rx="4" stroke="#fff" stroke-width="1.5"/>
              <circle cx="32" cy="48" r="3" fill="#3b82f6"/>
              <circle cx="32" cy="48" r="1.2" fill="#fff"/>
            </svg>
          </div>
          <p class="welcome-desc">{{ greetingMessage || '你好，有什么我可以帮你的吗？' }}</p>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-item"
          :class="[msg.role]"
        >
          <div v-if="msg.role === 'user'" class="message-content user">
            <div class="avatar-group">
              <div class="avatar-label">钢铁侠</div>
              <div class="user-avatar">
                <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:24px;height:24px">
                  <path d="M20 4C12 4 8 10 8 16c0 4 1 6 2 8l2 4c1 2 2 4 4 4h8c2 0 3-2 4-4l2-4c1-2 2-4 2-8 0-6-4-12-12-12z" fill="#dc2626"/>
                  <path d="M20 6C14 6 10 11 10 16c0 3 1 5 2 7l2 4c1 1 2 3 3 3h6c1 0 2-2 3-3l2-4c1-2 2-4 2-7 0-5-4-10-10-10z" fill="#d97706"/>
                </svg>
              </div>
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
              <div class="avatar-label">贾维斯</div>
              <div class="assistant-avatar">
                <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:24px;height:24px">
                  <circle cx="20" cy="20" r="16" stroke="#3b82f6" stroke-width="1.5" fill="none" opacity="0.5"/>
                  <circle cx="20" cy="20" r="12" stroke="#60a5fa" stroke-width="1.5" fill="none" stroke-dasharray="18 57" opacity="0.7"/>
                  <circle cx="20" cy="20" r="8" stroke="#93c5fd" stroke-width="1.5" fill="none" stroke-dasharray="12 38" stroke-dashoffset="-6" opacity="0.9"/>
                  <circle cx="20" cy="20" r="4" fill="#3b82f6"/>
                  <circle cx="20" cy="20" r="2" fill="#bfdbfe"/>
                </svg>
              </div>
            </div>
            <div class="message-bubble-wrap">
              <div class="message-bubble" v-if="msg.content || !msg.isStreaming">
                <div class="bubble-arrow"></div>
                <div v-if="msg.isStreaming && !msg.content" class="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <template v-else>
                  <span class="message-text">{{ stripMarkdown(msg.content) }}</span>
                  <span v-if="msg.isStreaming" class="streaming-cursor">|</span>
                </template>
              </div>

              <div v-if="msg.references && msg.references.length > 0" class="ref-section">
                <div class="section-title">知识引用</div>
                <div class="ref-cards">
                  <div v-for="(ref, idx) in msg.references.slice(0, 3)" :key="idx" class="ref-card">
                    <div class="ref-header">
                      <span class="ref-name">{{ ref.documentName || `文档${idx + 1}` }}</span>
                      <span class="ref-score">{{ (ref.score * 100).toFixed(1) }}%</span>
                    </div>
                    <div class="ref-content">{{ ref.content.slice(0, 150) }}...</div>
                  </div>
                </div>
              </div>

              <div v-if="msg.queryTime" class="message-meta">
                <span>耗时: {{ (msg.queryTime / 1000).toFixed(2) }}s</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="input-wrapper">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入您的问题..."
            resize="none"
            @keydown.enter.exact="handleEnterKey"
            class="chat-input"
          />
          <div class="input-actions">
            <el-button type="primary" :loading="isSending" @click="handleSend" class="send-btn">
              发送
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  ChatDotRound,
  Edit,
  Delete,
} from '@element-plus/icons-vue'
import { getApplication } from '@/api/application'
import type { Application } from '@/api/application'

interface Session {
  id: string
  title: string
  messages: any[]
  updatedAt: string
}

const route = useRoute()
const messagesRef = ref<HTMLElement>()
const inputText = ref('')
const isSending = ref(false)

const appId = computed(() => parseInt(route.params.appId as string))
const appName = ref('钢铁行业智能助手')
const greetingMessage = ref('')
const app = ref<Application | null>(null)

const sessions = ref<Session[]>([])
const currentSessionId = ref<string>('')
const searchKeyword = ref('')
const editingSessionId = ref<string | null>(null)
const renameValue = ref('')

const currentSession = computed(() => sessions.value.find(s => s.id === currentSessionId.value))
const messages = computed(() => currentSession.value?.messages || [])

const filteredSessions = computed(() => {
  if (!searchKeyword.value) return sessions.value
  const keyword = searchKeyword.value.toLowerCase()
  return sessions.value.filter((s) =>
    (s.title || '新对话').toLowerCase().includes(keyword)
  )
})

function formatTime(date: Date | string) {
  const d = new Date(date)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function stripMarkdown(content: string) {
  return content.replace(/\*\*/g, '')
}

function scrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

function handleEnterKey(e: KeyboardEvent) {
  if (!e.ctrlKey && !e.shiftKey && !e.altKey) {
    e.preventDefault()
    handleSend()
  }
}

function loadFromQueryParams() {
  const query = route.query
  if (query.appName) {
    appName.value = decodeURIComponent(query.appName as string) || '钢铁行业智能助手'
  }
  if (query.greetingMessage) {
    greetingMessage.value = decodeURIComponent(query.greetingMessage as string) || ''
  }
}

async function loadAppConfig() {
  loadFromQueryParams()
  
  if (route.query.appName) {
    return
  }
  
  try {
    const res = await getApplication(appId.value)
    const appData = (res.data as unknown as { data: Application }).data
    app.value = appData
    appName.value = appData.name || '钢铁行业智能助手'
    greetingMessage.value = appData.greetingMessage || ''
  } catch (error) {
    console.error('加载应用配置失败', error)
  }
}

function createNewSession() {
  const newSession: Session = {
    id: `embed-${Date.now()}`,
    title: '新对话',
    messages: [],
    updatedAt: new Date().toISOString(),
  }
  sessions.value.unshift(newSession)
  currentSessionId.value = newSession.id
  saveSessions()
}

function selectSession(sessionId: string) {
  currentSessionId.value = sessionId
}

function saveSessions() {
  try {
    localStorage.setItem(`embed_sessions_${appId.value}`, JSON.stringify(sessions.value))
  } catch (e) {
    console.error('保存会话失败', e)
  }
}

function loadSessions() {
  try {
    const saved = localStorage.getItem(`embed_sessions_${appId.value}`)
    if (saved) {
      sessions.value = JSON.parse(saved)
    }
  } catch (e) {
    console.error('加载会话失败', e)
  }
}

function handleNewChat() {
  editingSessionId.value = null
  renameValue.value = ''
  createNewSession()
}

function startRename(session: Session) {
  editingSessionId.value = session.id
  renameValue.value = session.title || '新对话'
}

function cancelRename() {
  editingSessionId.value = null
  renameValue.value = ''
}

function confirmRename(sessionId: string) {
  if (!editingSessionId.value) return
  const title = renameValue.value.trim()
  if (!title) {
    cancelRename()
    return
  }
  const session = sessions.value.find(s => s.id === sessionId)
  if (session) {
    session.title = title
    session.updatedAt = new Date().toISOString()
    saveSessions()
  }
  editingSessionId.value = null
  renameValue.value = ''
}

async function handleDeleteSession(session: Session) {
  try {
    await ElMessageBox.confirm(
      `确定删除会话「${session.title || '新对话'}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    const index = sessions.value.findIndex(s => s.id === session.id)
    if (index !== -1) {
      sessions.value.splice(index, 1)
      saveSessions()
      if (currentSessionId.value === session.id) {
        if (sessions.value.length > 0) {
          currentSessionId.value = sessions.value[0].id
        } else {
          createNewSession()
        }
      }
    }
    ElMessage.success('会话已删除')
  } catch {
    // 用户取消
  }
}

async function handleSend() {
  if (!inputText.value.trim()) {
    return
  }

  const userMsg = {
    id: Date.now(),
    role: 'user',
    content: inputText.value.trim(),
  }
  
  const session = currentSession.value
  if (session) {
    session.messages.push(userMsg)
    session.updatedAt = new Date().toISOString()
    if (!session.title || session.title === '新对话') {
      session.title = inputText.value.trim().substring(0, 20) + (inputText.value.length > 20 ? '...' : '')
    }
    saveSessions()
  }
  
  inputText.value = ''
  nextTick(() => scrollToBottom())

  isSending.value = true

  const aiMsgId = Date.now() + 1
  if (session) {
    session.messages.push({
      id: aiMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    })
    saveSessions()
  }
  nextTick(() => scrollToBottom())

  try {
      const knowledgeBaseId = app.value?.knowledgeBaseIds?.[0] || null
      
      const response = await fetch(`/api/v1/sessions/embed/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sessionId: currentSessionId.value,
          question: userMsg.content,
          knowledgeBaseId,
          applicationId: appId.value,
        }),
      })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('无法读取响应')
    }

    const decoder = new TextDecoder()
    let buffer = ''
    const currentMsgs = currentSession.value?.messages || []
    const aiMsg = currentMsgs.find(m => m.id === aiMsgId)

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
          
          if (data.type === 'content') {
            if (aiMsg) {
              aiMsg.content += data.content
              aiMsg.isStreaming = true
            }
            saveSessions()
            nextTick(() => scrollToBottom())
          } else if (data.type === 'references') {
            if (aiMsg) {
              aiMsg.references = data.data
            }
            saveSessions()
          } else if (data.type === 'done') {
            if (aiMsg) {
              aiMsg.isStreaming = false
            }
            saveSessions()
          } else if (data.type === 'error') {
            if (aiMsg) {
              aiMsg.content = `错误: ${data.message}`
              aiMsg.isStreaming = false
            }
            saveSessions()
          }
        } catch (e) {
          console.error('解析SSE消息失败', e)
        }
      }
    }
  } catch (error: any) {
    const currentMsgs = currentSession.value?.messages || []
    const aiMsg = currentMsgs.find(m => m.id === aiMsgId)
    if (aiMsg) {
      aiMsg.content = `发送失败: ${error.message || '未知错误'}`
      aiMsg.isStreaming = false
    }
    saveSessions()
  } finally {
    isSending.value = false
    nextTick(() => scrollToBottom())
  }
}

onMounted(() => {
  loadAppConfig()
  loadSessions()
  if (sessions.value.length === 0) {
    createNewSession()
  } else {
    currentSessionId.value = sessions.value[0].id
  }
})
</script>

<style lang="scss" scoped>
.chat-embed-view {
  display: flex;
  height: 100vh;
  background-color: #f1f5f9;
}

.chat-sidebar {
  width: 280px;
  background-color: #f8fafc;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e2e8f0;

  .sidebar-header {
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid #e2e8f0;
  }

  .sidebar-title {
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
    margin: 0;
    white-space: nowrap;
  }

  .new-chat-btn {
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 500;
  }

  .sidebar-search {
    padding: 12px 16px;
  }

  .sidebar-sessions {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .session-item {
    display: flex;
    align-items: center;
    padding: 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;

    &:hover {
      background-color: #f1f5f9;
    }

    &.active {
      background-color: #eff6ff;
      border-left: 3px solid #3b82f6;
    }

    .session-icon {
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: #ecfdf5;
      border-radius: 8px;
      margin-right: 10px;
      flex-shrink: 0;

      .el-icon {
        font-size: 16px;
        color: #10b981;
      }
    }

    .session-info {
      flex: 1;
      min-width: 0;

      .session-name {
        font-size: 13px;
        font-weight: 500;
        color: #1e293b;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .session-time {
        font-size: 11px;
        color: #94a3b8;
        margin-top: 2px;
      }

      .session-rename {
        :deep(.el-input__inner) {
          font-size: 13px;
          padding: 4px 8px;
        }
      }
    }

    .session-actions {
      display: flex;
      gap: 4px;
      opacity: 0;
      transition: opacity 0.2s;

      .action-btn {
        color: #94a3b8;

        &:hover {
          color: #3b82f6;
        }

        &.delete-btn:hover {
          color: #ef4444;
        }
      }
    }

    &:hover .session-actions {
      opacity: 1;
    }

    .session-active-indicator {
      position: absolute;
      right: 12px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: #3b82f6;
    }
  }
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header {
  padding: 12px 16px;
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;

    .header-logo {
      svg {
        width: 20px;
        height: 20px;
      }
    }

    .session-title {
      font-size: 14px;
      font-weight: 600;
      color: #fff;
      white-space: nowrap;
    }
  }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);

  .welcome-banner {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    text-align: center;
  }

  .welcome-icon {
    width: 64px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
    border-radius: 16px;
    margin-bottom: 16px;
    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);

    svg {
      width: 40px;
      height: 40px;
    }
  }

  .welcome-desc {
    font-size: 14px;
    color: #64748b;
    margin: 0;
    max-width: 300px;
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
    max-width: 85%;
    min-width: 0;
    overflow: hidden;
    gap: 10px;

    &.user {
      flex-direction: row-reverse;

      .avatar-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        flex-shrink: 0;
      }

      .message-bubble-wrap {
        display: flex;
        flex-direction: column;
        gap: 8px;
        flex: 0 1 auto;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        align-items: flex-end;
      }

      .message-bubble {
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
        color: #ffffff;
        border-radius: 12px 12px 4px 12px;
        position: relative;
        padding: 12px 16px;
        font-size: 14px;
        line-height: 1.6;
        word-break: break-word;
        overflow-wrap: break-word;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        width: auto;
        max-width: 100%;

        .bubble-arrow {
          position: absolute;
          width: 0;
          height: 0;
          top: 12px;
          border: 6px solid transparent;
          right: -12px;
          border-left-color: #6366f1;
        }
      }
    }

    &.assistant {
      flex-direction: row;

      .avatar-group {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        flex-shrink: 0;
      }

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
        border-radius: 12px 12px 12px 4px;
        position: relative;
        padding: 12px 16px;
        font-size: 14px;
        line-height: 1.6;
        word-break: break-word;
        overflow-wrap: break-word;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        width: 100%;

        .bubble-arrow {
          position: absolute;
          width: 0;
          height: 0;
          top: 12px;
          border: 6px solid transparent;
          left: -12px;
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

    .user-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, #fde8e8 0%, #fef3c7 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 6px rgba(220, 38, 38, 0.15);
    }

    .assistant-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);
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
      gap: 6px;
      padding: 8px 0;

      span {
        width: 8px;
        height: 8px;
        background-color: #cbd5e1;
        border-radius: 50%;
        animation: typing 1.4s infinite ease-in-out both;

        &:nth-child(1) { animation-delay: -0.32s; }
        &:nth-child(2) { animation-delay: -0.16s; }
      }
    }

    .ref-section {
      background-color: #ffffff;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      padding: 12px;
      width: 100%;

      .section-title {
        font-size: 12px;
        font-weight: 600;
        color: #475569;
        margin-bottom: 10px;
        padding-left: 6px;
        border-left: 3px solid #3b82f6;
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
            padding: 1px 5px;
            background-color: #dcfce7;
            color: #16a34a;
            border-radius: 4px;
            font-weight: 500;
          }
        }

        .ref-content {
          font-size: 11px;
          color: #64748b;
          line-height: 1.5;
        }
      }
    }

    .message-meta {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 6px;
      margin-top: 4px;

      span {
        font-size: 11px;
        color: #94a3b8;
      }
    }
  }
}

.chat-input-area {
  background-color: #ffffff;
  border-top: 1px solid #e2e8f0;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.04);

  .input-wrapper {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    padding: 10px 16px;

    .chat-input {
      flex: 1;

      :deep(.el-textarea__inner) {
        border-radius: 10px;
        padding: 10px 14px;
        font-size: 13px;
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
      background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
      border: none;
      border-radius: 8px;
      padding: 8px 20px;
      font-weight: 500;
      font-size: 13px;
      box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);

      &:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(59, 130, 246, 0.4);
      }

      &:disabled {
        opacity: 0.7;
      }
    }
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>