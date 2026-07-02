import request from './index'

export interface ChatBIQuery {
  question: string
  datasourceId?: number
}

export interface ChatBIResponse {
  explanation: string
  data: any[]
  sqlTraces: any[]
  queryTime: number
}

export function queryChatBI(data: ChatBIQuery) {
  return request.post<ChatBIResponse>('/chatbi/query', data)
}
