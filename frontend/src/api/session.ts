/**
 * 会话管理 API 模块
 *
 * 职责：封装与后端会话相关的所有 HTTP 请求，包括：
 *   1. 会话 CRUD（创建/查询/更新/删除）
 *   2. 消息列表查询
 *   3. SSE 流式对话（核心）
 *
 * 架构定位（面试重点）：
 *   本模块是前端「API 层」的一部分，位于「状态管理层 (Pinia store)」和「后端 API」之间。
 *   - 普通请求用 axios（通过 ./index 导入的 request 实例）
 *   - 流式请求用 fetch API（因为 axios 不支持 ReadableStream 逐块读取）
 *
 * 面试考点 —— 为什么 streamChat 用 fetch 而不是 axios？
 *   axios 的响应拦截器会一次性读取完整响应体，无法逐块处理 SSE 流。
 *   fetch API 支持 response.body.getReader()，可以逐块读取流式数据，
 *   适合 SSE（Server-Sent Events）协议的逐事件解析。
 */
import request from './index'

/**
 * 会话数据接口
 * 对应后端 Session 模型，表示一个对话会话
 */
export interface Session {
  id: number
  userId: number
  title: string
  intentType?: string  // 意图类型（可选，用于会话分类）
  status: string        // 会话状态
  createdAt: string
  updatedAt: string
}

/**
 * 消息数据接口
 * 对应后端 Message 模型，表示一条对话消息（用户消息或AI回复）
 */
export interface Message {
  id: number
  sessionId: number
  role: 'user' | 'assistant'  // 消息角色：用户 或 助手
  content: string               // 消息文本内容
  intent?: string               // 意图分类（knowledge/data/mcp/skill/hybrid/chat）
  references?: any[]            // 知识引用列表（RAG检索结果）
  sqlTraces?: any[]             // SQL查询追踪（NL2SQL生成的SQL）
  dataResult?: any[]            // 数据查询结果（JSON格式）
  queryTime?: number            // 查询耗时（毫秒）
  createdAt: string
}

/**
 * 对话请求参数接口
 * 发送问题时携带的参数，包括会话ID、问题、知识库/数据源/LLM配置
 */
export interface ChatRequest {
  sessionId: number
  question: string
  knowledgeBaseId?: number  // 知识库ID（RAG检索用）
  datasourceId?: number    // 数据源ID（NL2SQL用）
  llmConfigId?: number     // LLM配置ID（应用级模型覆盖）
}

// ===================== 会话 CRUD API =====================

/** 获取会话列表（分页） */
export function getSessions(params?: { skip?: number; limit?: number }) {
  return request.get<{ list: Session[]; total: number }>('/sessions', { params })
}

/** 创建新会话 */
export function createSession(data: { title?: string }) {
  return request.post<Session>('/sessions', data)
}

/** 获取单个会话详情 */
export function getSession(id: number) {
  return request.get<any>(`/sessions/${id}`)
}

/** 更新会话标题 */
export function updateSession(id: number, data: { title: string }) {
  return request.put<Session>(`/sessions/${id}`, data)
}

/** 删除会话（级联删除消息和溯源） */
export function deleteSession(id: number) {
  return request.delete(`/sessions/${id}`)
}

// ===================== 消息 API =====================

/** 获取会话的消息列表（分页，按创建时间升序） */
export function getMessages(sessionId: number, params?: { skip?: number; limit?: number }) {
  return request.get<{ list: Message[]; total: number }>(`/sessions/${sessionId}/messages`, { params })
}

/** 发送消息（非流式，一次性获取完整回复） */
export function sendMessage(data: ChatRequest) {
  return request.post<any>('/sessions/send', data)
}

// ===================== SSE 流式对话（核心） =====================

/**
 * SSE 流式对话（前端核心方法）
 *
 * 使用 fetch API 发送 POST 请求，通过 ReadableStream 逐块解析 SSE 事件。
 * 这是前端「流式渲染」的数据入口，接收后端推送的多种事件类型：
 *
 * SSE 事件类型（event.type）：
 *   - intent:    意图分类结果（knowledge/data/mcp/skill/hybrid/chat）
 *   - thinking:  思考过程步骤（推理链，逐步展示AI的思考过程）
 *   - content:   文本内容块（逐字推送，前端拼接成完整回答）
 *   - sql:       SQL查询语句（NL2SQL生成的SQL，展示在"查看SQL"弹窗中）
 *   - data:      数据查询结果（表格数据，展示在数据可视化组件中）
 *   - references:知识引用列表（RAG检索命中的文档片段+相似度分数）
 *   - chart:     图表配置（ECharts option JSON，前端直接渲染图表）
 *   - tool_call: 工具调用信息（MCP/Skill调用的名称和参数）
 *   - tool_result: 工具调用结果
 *   - done:      流结束标记（触发 onComplete 回调）
 *   - error:     错误信息（流中推送的错误，如SQL执行失败等）
 *
 * 缓冲区策略（面试考点 —— SSE流解析的难点）：
 *   SSE 协议以 \n 分隔每行，但网络传输的 chunk 可能不按行对齐。
 *   一个 chunk 可能包含半行数据，需要用 buffer 缓存不完整的行，
 *   等待下一个 chunk 到来后拼接完整再解析。
 *
 * @param data        对话请求参数（会话ID、问题、配置等）
 * @param onEvent     事件回调，每收到一个SSE事件触发
 * @param onError     错误回调，请求失败时触发
 * @param onComplete  完成回调，收到 done 事件或流结束时触发
 */
export async function streamChat(
  data: ChatRequest,
  onEvent: (event: { type: string; [key: string]: any }) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void,
): Promise<void> {
  const token = localStorage.getItem('token')
  const baseURL = '/api/v1'

  try {
    // 发起 POST 请求（注意：不能用 axios，因为要逐块读取流）
    const response = await fetch(`${baseURL}/sessions/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })

    // HTTP错误处理（非2xx状态码）
    if (!response.ok) {
      try {
        const errorData = await response.json()
        const detail = errorData.detail || errorData.message || 'Unknown error'
        console.error('聊天请求失败:', errorData)
        throw new Error(`HTTP error! status: ${response.status}, detail: ${JSON.stringify(detail)}`)
      } catch {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
    }

    // 获取 ReadableStream 的 reader，逐块读取响应体
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No readable stream available')
    }

    const decoder = new TextDecoder()  // 字节流 → 字符串解码器
    let buffer = ''                    // 缓冲区：保存不完整的行，等待下一个chunk拼接

    // 循环读取流数据块
    while (true) {
      const { done, value } = await reader.read()
      if (done) break  // 流结束

      // 将当前 chunk 解码后追加到缓冲区
      buffer += decoder.decode(value, { stream: true })  // stream:true 表示可能还有后续数据

      // 按 \n 分隔行（SSE协议每行一个事件）
      const lines = buffer.split('\n')
      buffer = ''  // 清空缓冲区（最后一行可能不完整，下面会放回去）

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          // SSE 格式行："data: {json}"，解析 JSON 事件
          try {
            const eventData = JSON.parse(line.slice(6))  // 去掉 "data: " 前缀
            onEvent(eventData)  // 触发事件回调，交给上层 store 处理

            // 收到 done 事件，表示流结束
            if (eventData.type === 'done') {
              onComplete?.()
              return  // 直接返回，不再读取后续数据
            }
          } catch {
            // JSON 解析失败的行直接跳过（可能是心跳包或空行）
          }
        } else if (line.trim() !== '') {
          // 不完整的行（不是以 "data: " 开头但非空），放回缓冲区等待下一chunk拼接
          buffer = line + '\n'
        }
      }
    }

    // 流正常结束（未收到 done 事件但流已关闭）
    onComplete?.()
  } catch (error) {
    onError?.(error as Error)
  }
}
