import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getSessions, createSession, getSession, getMessages, streamChat, updateSession, deleteSession, type Session, type Message, type ChatRequest } from '@/api/session'
import { getDefaultLLMConfig, getLLMConfigs } from '@/api/llmConfig'

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
  type?: 'text' | 'knowledge' | 'data' | 'chart' | 'sql' | 'tool' | 'mcp' | 'skill'
  isStreaming?: boolean
  references?: any[]
  sqlTraces?: any[]
  queryTime?: number
  intent?: string
  dataResult?: any[]  // ChatBI 数据查询结果
  columnMeta?: any[]  // 字段元信息（注释、类型等）
  chartType?: string  // 推荐图表类型
  thinkingSteps?: ThinkingStep[]  // 思考过程步骤
  toolCalls?: any[]  // 工具调用信息（MCP/Skill通用）
  toolResults?: any[]  // 工具调用结果（MCP/Skill通用）
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

  const isLoadingMessages = ref(false)

  // LLM模型配置
  const selectedLLMConfigId = ref<number | null>(null)
  const defaultLLMConfig = ref<any>(null)
  const llmConfigs = ref<any[]>([])

  const currentSession = computed(() =>
    sessions.value.find((s) => s.id === currentSessionId.value)
  )

  // 获取默认LLM配置
  async function fetchDefaultLLMConfig() {
    try {
      const res: any = await getDefaultLLMConfig('llm')
      if (res.code === 0 && res.data) {
        defaultLLMConfig.value = res.data
        selectedLLMConfigId.value = res.data.id
      }
    } catch (e: any) {
      console.error('获取默认LLM配置失败', e)
      // 获取完整的错误信息
      if (e.response) {
        console.error('错误响应:', e.response.status, e.response.data)
      }
    }
  }

  // 获取所有LLM配置
  async function fetchLLMConfigs() {
    try {
      const res: any = await getLLMConfigs()
      if (res.code === 0 && res.data) {
        const configs = Array.isArray(res.data) ? res.data : (res.data.list || [])
        llmConfigs.value = configs.filter((c: any) => c.modelType === 'llm')
      }
    } catch (e) {
      console.error('获取LLM配置列表失败', e)
    }
  }

  // 设置LLM配置
  function setLLMConfigId(id: number | null) {
    selectedLLMConfigId.value = id
  }

  async function fetchSessions() {
    try {
      const res = await getSessions() as any
      if (res.code === 0 && res.data) {
        // 前端按ID降序排序（ID最大=最新创建的会话排第一），不依赖后端排序
        sessions.value = res.data
          .map((s: Session) => ({
            id: String(s.id),
            title: s.title,
            lastMessage: '',
            updatedAt: new Date(s.updatedAt),
            messageCount: 0,
            intentType: s.intentType,
          }))
          .sort((a: ChatSession, b: ChatSession) => Number(b.id) - Number(a.id))
      }
    } catch (e) {
      console.error('获取会话列表失败', e)
    }
  }

  async function createNewSession() {
    try {
      const res = await createSession({ title: '新对话' }) as any
      if (res.code === 0 && res.data && res.data.id) {
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
    // 如果选择的是当前会话，不做任何操作
    if (currentSessionId.value === id) {
      return
    }
    // 立即显示加载状态，避免旧消息闪烁
    isLoadingMessages.value = true
    currentSessionId.value = id
    // 清空消息，但保持加载状态直到新消息加载完成
    messages.value = []
    try {
      await fetchMessages(id)
    } finally {
      isLoadingMessages.value = false
    }
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
          type: (m.intent === 'data' || m.intent === 'hybrid') && m.dataResult ? 'data'
              : (m.intent === 'mcp' ? 'mcp'
              : (m.intent === 'skill' ? 'skill'
              : (m.intent === 'tool' ? 'tool' : 'text'))),
          isStreaming: false,
          references: m.references,
          sqlTraces: m.sqlTraces,
          dataResult: m.dataResult,
          columnMeta: (m as any).columnMeta,
          chartType: (m as any).chartType,
          queryTime: m.queryTime,
          intent: m.intent,
          thinkingSteps: (m as any).thinkingSteps || [],
          toolCalls: (m as any).toolCalls || [],
          toolResults: (m as any).toolResults || [],
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
      const session = await createNewSession()
      if (!session) {
        throw new Error('创建会话失败，请重试')
      }
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
      const sessionId = Number(currentSessionId.value)
      if (isNaN(sessionId) || sessionId <= 0) {
        throw new Error('无效的会话ID')
      }
      const chatRequest: ChatRequest = {
        sessionId: sessionId,
        question: content,
      }
      console.log('发送聊天请求:', chatRequest)
      if (selectedKnowledgeBaseId.value !== null && selectedKnowledgeBaseId.value !== undefined) {
        chatRequest.knowledgeBaseId = selectedKnowledgeBaseId.value
      }
      if (selectedDatasourceId.value !== null && selectedDatasourceId.value !== undefined) {
        chatRequest.datasourceId = selectedDatasourceId.value
      }
      if (selectedLLMConfigId.value !== null && selectedLLMConfigId.value !== undefined) {
        chatRequest.llmConfigId = selectedLLMConfigId.value
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
            case 'column_meta':
              // 列元数据（用于图表字段映射）
              msg.columnMeta = event.data
              break
            case 'data_result':
              // 数据查询结果
              msg.dataResult = event.data
              // 如果data_result事件中包含columnMeta，优先使用
              if (event.columnMeta) {
                msg.columnMeta = event.columnMeta
              }
              // 如果没有指定chartType，使用后端建议的类型
              if (event.chartType) {
                msg.chartType = event.chartType
              }
              msg.type = 'data'
              break
            case 'tool_calls':
              // 工具调用信息（MCP/Skill通用，根据intent区分类型）
              msg.toolCalls = event.data
              msg.type = msg.intent === 'skill' ? 'skill' : (msg.intent === 'mcp' ? 'mcp' : 'tool')
              break
            case 'tool_results':
              // 工具调用结果
              msg.toolResults = event.data
              break
            case 'content':
              // 流式内容，逐字追加
              msg.content += event.content
              break
            case 'done':
              // 流式完成，包含耗时
              msg.queryTime = Math.round(event.elapsed_time * 1000)
              msg.elapsedTime = Math.round(event.elapsed_time * 1000)
              msg.isStreaming = false
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
    isLoadingMessages,
    selectedKnowledgeBaseId,
    selectedDatasourceId,
    selectedLLMConfigId,
    defaultLLMConfig,
    llmConfigs,
    fetchDefaultLLMConfig,
    fetchLLMConfigs,
    setLLMConfigId,
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
