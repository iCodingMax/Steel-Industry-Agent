/**
 * 对话用户 API 接口
 */
import request from './index'

export interface ChatUser {
  id: number
  username: string
  name: string | null
  email: string | null
  phone: string | null
  status: string
  userSource: string
  forceChangePassword: boolean
  lastLoginAt: string | null
  createdAt: string | null
  updatedAt: string | null
}

export interface ChatUserListResponse {
  total: number
  items: ChatUser[]
}

export interface ChatUserCreateForm {
  username: string
  name?: string
  email?: string
  phone?: string
  status?: string
}

export interface ChatUserUpdateForm {
  name?: string
  email?: string
  phone?: string
  status?: string
}

export interface ResetPasswordForm {
  newPassword: string
}

/**
 * 获取对话用户列表
 */
export function getChatUserList(params: {
  keyword?: string
  status?: string
  page?: number
  pageSize?: number
}) {
  return request.get<never, { code: number; message: string; data: ChatUserListResponse }>(
    '/chat-users',
    { params }
  )
}

/**
 * 获取对话用户详情
 */
export function getChatUser(userId: number) {
  return request.get<never, { code: number; message: string; data: ChatUser }>(
    `/chat-users/${userId}`
  )
}

/**
 * 创建对话用户
 */
export function createChatUser(data: ChatUserCreateForm) {
  return request.post<never, { code: number; message: string; data: ChatUser }>(
    '/chat-users',
    data
  )
}

/**
 * 更新对话用户
 */
export function updateChatUser(userId: number, data: ChatUserUpdateForm) {
  return request.put<never, { code: number; message: string; data: ChatUser }>(
    `/chat-users/${userId}`,
    data
  )
}

/**
 * 删除对话用户
 */
export function deleteChatUser(userId: number) {
  return request.delete<never, { code: number; message: string; data: null }>(
    `/chat-users/${userId}`
  )
}

/**
 * 切换用户状态
 */
export function toggleChatUserStatus(userId: number) {
  return request.patch<never, { code: number; message: string; data: ChatUser }>(
    `/chat-users/${userId}/toggle-status`
  )
}

/**
 * 重置对话用户密码
 */
export function resetChatUserPassword(userId: number, data: ResetPasswordForm) {
  return request.post<never, { code: number; message: string; data: null }>(
    `/chat-users/${userId}/reset-password`,
    data
  )
}
