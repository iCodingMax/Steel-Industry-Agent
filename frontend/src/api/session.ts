import request from './index'

export interface Session {
  id: number
  userId: number
  title: string
  intentType?: string
  status: string
  createdAt: string
  updatedAt: string
}

export interface Message {
  id: number
  sessionId: number
  role: 'user' | 'assistant'
  content: string
  intent?: string
  references?: any[]
  sqlTraces?: any[]
  dataResult?: any[]
  queryTime?: number
  createdAt: string
}

export interface ChatRequest {
  sessionId: number
  question: string
  knowledgeBaseId?: number
  datasourceId?: number
}

export function getSessions(params?: { skip?: number; limit?: number }) {
  return request.get<{ list: Session[]; total: number }>('/sessions', { params })
}

export function createSession(data: { title?: string }) {
  return request.post<Session>('/sessions', data)
}

export function getSession(id: number) {
  return request.get<any>(`/sessions/${id}`)
}

export function updateSession(id: number, data: { title: string }) {
  return request.put<Session>(`/sessions/${id}`, data)
}

export function deleteSession(id: number) {
  return request.delete(`/sessions/${id}`)
}

export function getMessages(sessionId: number, params?: { skip?: number; limit?: number }) {
  return request.get<{ list: Message[]; total: number }>(`/sessions/${sessionId}/messages`, { params })
}

export function sendMessage(data: ChatRequest) {
  return request.post<any>('/sessions/send', data)
}

/**
 * SSE流式对话
 * 使用fetch API发送请求，通过ReadableStream解析SSE事件
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
    const response = await fetch(`${baseURL}/sessions/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('No readable stream available')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // 解析SSE事件
      const lines = buffer.split('\n')
      buffer = ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const eventData = JSON.parse(line.slice(6))
            onEvent(eventData)

            // 收到done事件，结束流
            if (eventData.type === 'done') {
              onComplete?.()
              return
            }
          } catch {
            // 忽略解析失败的行
          }
        } else if (line.trim() !== '') {
          // 不完整的行，放回buffer
          buffer = line + '\n'
        }
      }
    }

    onComplete?.()
  } catch (error) {
    onError?.(error as Error)
  }
}
