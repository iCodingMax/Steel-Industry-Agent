import request from './index'

export interface Application {
  id: number
  name: string
  description?: string
  icon?: string
  status: string
  modelName: string
  embeddingModel: string
  rerankModel: string
  systemPrompt?: string
  userPromptTemplate?: string
  greetingMessage?: string
  knowledgeBaseIds: number[]
  iframeAllowedOrigins: string[]
  iframeHeight: number
  iframeWidth: string
  customDomain?: string
  apiKey?: string
  maxTokens: number
  temperature: number
  topP: number
  createdAt?: string
  updatedAt?: string
  createdBy?: number
  prompts?: AppPrompt[]
}

export interface AppPrompt {
  id: number
  applicationId: number
  name: string
  type: string
  content: string
  isActive: boolean
  sortOrder: number
  createdAt?: string
  updatedAt?: string
}

export interface ApplicationCreateForm {
  name: string
  description?: string
  modelName?: string
  embeddingModel?: string
  rerankModel?: string
  systemPrompt?: string
  userPromptTemplate?: string
  greetingMessage?: string
  knowledgeBaseIds?: number[]
  maxTokens?: number
  temperature?: number
  topP?: number
}

export interface ApplicationUpdateForm {
  name?: string
  description?: string
  icon?: string
  status?: string
  modelName?: string
  embeddingModel?: string
  rerankModel?: string
  systemPrompt?: string
  userPromptTemplate?: string
  greetingMessage?: string
  knowledgeBaseIds?: number[]
  iframeAllowedOrigins?: string[]
  iframeHeight?: number
  iframeWidth?: string
  customDomain?: string
  maxTokens?: number
  temperature?: number
  topP?: number
}

export interface AppPromptCreateForm {
  name: string
  type?: string
  content: string
  isActive?: boolean
  sortOrder?: number
}

export interface AppPromptUpdateForm {
  name?: string
  type?: string
  content?: string
  isActive?: boolean
  sortOrder?: number
}

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export function getApplications(params?: { page?: number; pageSize?: number; keyword?: string }) {
  return request.get<ApiResponse<{ data: Application[]; total: number; page: number; pageSize: number }>>('/applications', { params })
}

export function getApplication(id: number) {
  return request.get<ApiResponse<Application>>(`/applications/${id}`)
}

export function createApplication(data: ApplicationCreateForm) {
  return request.post<ApiResponse<Application>>('/applications', data)
}

export function updateApplication(id: number, data: ApplicationUpdateForm) {
  return request.put<ApiResponse<Application>>(`/applications/${id}`, data)
}

export function deleteApplication(id: number) {
  return request.delete<ApiResponse<{ message: string }>>(`/applications/${id}`)
}

export function regenerateApiKey(id: number) {
  return request.post<ApiResponse<{ apiKey: string }>>(`/applications/${id}/regenerate-api-key`)
}

export function getAppPrompts(appId: number) {
  return request.get<ApiResponse<{ data: AppPrompt[] }>>(`/applications/${appId}/prompts`)
}

export function createAppPrompt(appId: number, data: AppPromptCreateForm) {
  return request.post<ApiResponse<AppPrompt>>(`/applications/${appId}/prompts`, data)
}

export function updateAppPrompt(appId: number, promptId: number, data: AppPromptUpdateForm) {
  return request.put<ApiResponse<AppPrompt>>(`/applications/${appId}/prompts/${promptId}`, data)
}

export function deleteAppPrompt(appId: number, promptId: number) {
  return request.delete<ApiResponse<{ message: string }>>(`/applications/${appId}/prompts/${promptId}`)
}

export function getIframeUrl(appId: number) {
  return request.get<ApiResponse<{ url: string; embedCode: string }>>(`/applications/${appId}/iframe-url`)
}
