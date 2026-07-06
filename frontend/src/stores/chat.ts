import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getSessions, createSession, getSession, getMessages, streamChat, updateSession, deleteSession, type Session, type Message, type ChatRequest } from '@/api/session'

export interface ThinkingStep {
  step: number
  total_steps: number
  title: string
  description: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  type?: 'text' | 'knowledge' | 'data' | 'chart' | 'sql'
  isStreaming?: boolean
  references?: any[]
  sqlTraces?: any[]
  queryTime?: number
  intent?: string
  dataResult?: any[]  // ChatBI 数据查询结果
  columnMeta?: any[]  // 字段元信息（注释、类型等）
  chartType?: string  // 推荐图表类型
  thinkingSteps?: ThinkingStep[]  // 思考过程步骤
}

export interface ChatSession {
  id: string
  title: string
  lastMessage: string
  updatedAt: Date
  messageCount: number
  intentType?: string
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)

  // 从 localStorage 恢复选择状态
  const selectedKnowledgeBaseId = ref<number | null>(
    localStorage.getItem('chat_selectedKB') ? Number(localStorage.getItem('chat_selectedKB')) : null
  )
  const selectedDatasourceId = ref<number | null>(
    localStorage.getItem('chat_selectedDS') ? Number(localStorage.getItem('chat_selectedDS')) : null
  )

  const currentSession = computed(() =>
    sessions.value.find((s) => s.id === currentSessionId.value)
  )

  async function fetchSessions() {
    try {
      const res = await getSessions() as any
      if (res.code === 0 && res.data) {
        sessions.value = res.data.map((s: Session) => ({
          id: String(s.id),
          title: s.title,
          lastMessage: '',
          updatedAt: new Date(s.updatedAt),
          messageCount: 0,
          intentType: s.intentType,
        }))
      }
    } catch (e) {
      console.error('获取会话列表失败', e)
    }
  }

  async function createNewSession() {
    try {
      const res = await createSession({ title: '新对话' }) as any
      if (res.code === 0 && res.data) {
        const session: ChatSession = {
          id: String(res.data.id),
          title: res.data.title,
          lastMessage: '',
          updatedAt: new Date(res.data.updatedAt),
          messageCount: 0,
          intentType: res.data.intentType,
        }
        sessions.value.unshift(session)
        currentSessionId.value = session.id
        messages.value = []
        return session
      }
    } catch (e) {
      console.error('创建会话失败', e)
    }
    return null
  }

  async function selectSession(id: string) {
    currentSessionId.value = id
    await fetchMessages(id)
  }

  async function fetchMessages(sessionId: string) {
    try {
      const res = await getMessages(Number(sessionId)) as any
      if (res.code === 0 && res.data) {
        messages.value = res.data.map((m: Message) => ({
          id: String(m.id),
          role: m.role,
          content: m.content,
          timestamp: new Date(m.createdAt),
          type: (m.intent === 'data' || m.intent === 'hybrid') && m.dataResult ? 'data' : 'text',
          isStreaming: false,
          references: m.references,
          sqlTraces: m.sqlTraces,
          dataResult: m.dataResult,
          columnMeta: (m as any).columnMeta,
          chartType: (m as any).chartType,
          queryTime: m.queryTime,
          intent: m.intent,
          thinkingSteps: (m as any).thinkingSteps || [],
        }))
      }
    } catch (e) {
      console.error('获取消息列表失败', e)
    }
  }

  function addMessage(message: ChatMessage) {
    messages.value.push(message)
  }

  function updateStreamingMessage(id: string, content: string) {
    const msg = messages.value.find((m) => m.id === id)
    if (msg) {
      msg.content = content
    }
  }

  function finishStreaming(id: string, extras?: Partial<ChatMessage>) {
    const msg = messages.value.find((m) => m.id === id)
    if (msg) {
      msg.isStreaming = false
      if (extras) {
        Object.assign(msg, extras)
      }
    }
  }

  async function sendUserMessage(content: string) {
    if (!currentSessionId.value) {
      await createNewSession()
    }

    const userMsgId = Date.now().toString()
    addMessage({
      id: userMsgId,
      role: 'user',
      content,
      timestamp: new Date(),
      type: 'text',
    })

    const aiMsgId = (Date.now() + 1).toString()
    addMessage({
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      type: 'text',
      isStreaming: true,
    })

    isLoading.value = true

    try {
      const chatRequest: ChatRequest = {
        sessionId: Number(currentSessionId.value),
        question: content,
      }
      if (selectedKnowledgeBaseId.value) {
        chatRequest.knowledgeBaseId = selectedKnowledgeBaseId.value
      }
      if (selectedDatasourceId.value) {
        chatRequest.datasourceId = selectedDatasourceId.value
      }

      // 使用SSE流式接口
      await streamChat(
        chatRequest,
        // onEvent: 处理每个SSE事件
        (event) => {
          const msg = messages.value.find((m) => m.id === aiMsgId)
          if (!msg) return

          switch (event.type) {
            case 'start':
              // 流式开始
              break
            case 'intent':
              // 意图识别结果
              msg.intent = event.intent
              break
            case 'thinking':
              // 思考过程步骤
              if (!msg.thinkingSteps) {
                msg.thinkingSteps = []
              }
              msg.thinkingSteps.push({
                step: event.step,
                total_steps: event.total_steps,
                title: event.title,
                description: event.description,
              })
              break
            case 'references':
              // 知识引用
              msg.references = event.data
              break
            case 'sql_traces':
              // SQL溯源
              msg.sqlTraces = event.data
              break
            case 'data_result':
              // 数据查询结果
              msg.dataResult = event.data
              msg.columnMeta = event.columnMeta
              msg.chartType = event.chartType
              msg.type = 'data'
              break
            case 'content':
              // 流式内容，逐字追加
              msg.content += event.content
              break
            case 'error':
              // 错误事件
              msg.content += `\n\n[错误] ${event.message}`
              msg.isStreaming = false
              break
          }
        },
        // onError: 处理网络错误
        (error) => {
          console.error('流式请求失败', error)
          const msg = messages.value.find((m) => m.id === aiMsgId)
          if (msg) {
            msg.content = msg.content || '抱歉，消息发送失败，请稍后重试。'
            msg.isStreaming = false
          }
        },
        // onComplete: 流式完成
        () => {
          const msg = messages.value.find((m) => m.id === aiMsgId)
          if (msg) {
            msg.isStreaming = false
          }
        },
      )
    } catch (e) {
      console.error('发送消息失败', e)
      finishStreaming(aiMsgId, {
        content: '抱歉，消息发送失败，请稍后重试。',
      })
    } finally {
      isLoading.value = false
    }
  }

  function setKnowledgeBaseId(id: number | null) {
    selectedKnowledgeBaseId.value = id
    if (id !== null) {
      localStorage.setItem('chat_selectedKB', String(id))
    } else {
      localStorage.removeItem('chat_selectedKB')
    }
  }

  function setDatasourceId(id: number | null) {
    selectedDatasourceId.value = id
    if (id !== null) {
      localStorage.setItem('chat_selectedDS', String(id))
    } else {
      localStorage.removeItem('chat_selectedDS')
    }
  }

  async function renameSession(id: string, title: string) {
    try {
      const res = await updateSession(Number(id), { title }) as any
      if (res.code === 0) {
        const session = sessions.value.find((s) => s.id === id)
        if (session) {
          session.title = title
        }
      }
    } catch (e) {
      console.error('重命名会话失败', e)
    }
  }

  async function removeSession(id: string) {
    try {
      const res = await deleteSession(Number(id)) as any
      if (res.code === 0) {
        sessions.value = sessions.value.filter((s) => s.id !== id)
        // 如果删除的是当前会话，切换到第一个或新建
        if (currentSessionId.value === id) {
          if (sessions.value.length > 0) {
            await selectSession(sessions.value[0].id)
          } else {
            await createNewSession()
          }
        }
      }
    } catch (e) {
      console.error('删除会话失败', e)
    }
  }

  return {
    sessions,
    currentSessionId,
    currentSession,
    messages,
    isLoading,
    selectedKnowledgeBaseId,
    selectedDatasourceId,
    fetchSessions,
    createNewSession,
    selectSession,
    fetchMessages,
    addMessage,
    updateStreamingMessage,
    finishStreaming,
    sendUserMessage,
    setKnowledgeBaseId,
    setDatasourceId,
    renameSession,
    removeSession,
  }
})
