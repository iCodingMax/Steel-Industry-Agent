import request from './index'

export interface LLMConfigForm {
  id?: number
  name: string
  type: string
  baseUrl: string
  apiKey?: string
  modelName: string
  modelType?: string
  maxTokens?: number
  temperature?: number
  topP?: number
  extraParams?: Record<string, any>
  isDefault?: boolean
  description?: string
  status?: string
}

export function getLLMConfigs(params?: { page?: number; pageSize?: number; type?: string }) {
  return request.get<{ list: any[]; total: number }>('/llm-configs', { params })
}

export function getLLMConfig(id: number) {
  return request.get<any>(`/llm-configs/${id}`)
}

export function createLLMConfig(data: LLMConfigForm) {
  return request.post<any>('/llm-configs', data)
}

export function updateLLMConfig(id: number, data: Partial<LLMConfigForm>) {
  return request.put<any>(`/llm-configs/${id}`, data)
}

export function deleteLLMConfig(id: number) {
  return request.delete<any>(`/llm-configs/${id}`)
}

export function testLLMConnection(data: Partial<LLMConfigForm>) {
  return request.post<any>('/llm-configs/test-connection', data)
}
