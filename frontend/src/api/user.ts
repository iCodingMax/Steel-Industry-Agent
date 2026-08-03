import request from './index'

export interface UserInfo {
  id: number
  username: string
  name: string | null
  email: string | null
  phone: string | null
  role: string
  status: string
  userSource: string
  oauthProvider: string | null
  createdAt: string | null
  updatedAt: string | null
  lastLoginAt: string | null
  forceChangePassword: boolean
}

export interface UserListResponse {
  total: number
  list: UserInfo[]
}

export interface UserCreateForm {
  username: string
  password: string
  name?: string
  email?: string
  phone?: string
  role?: string
}

export interface UserUpdateForm {
  name?: string
  email?: string
  phone?: string
  role?: string
  status?: string
}

export interface PasswordResetForm {
  password: string
}

/**
 * 获取用户列表
 */
export function getUsers(params: {
  page?: number
  pageSize?: number
  keyword?: string
  status?: string
}) {
  return request.get<never, { code: number; message: string; data: UserListResponse }>(
    '/users',
    { params }
  )
}

/**
 * 获取用户详情
 */
export function getUser(userId: number) {
  return request.get<never, { code: number; message: string; data: UserInfo }>(
    `/users/${userId}`
  )
}

/**
 * 创建用户
 */
export function createUser(data: UserCreateForm) {
  return request.post<never, { code: number; message: string; data: UserInfo }>(
    '/users',
    data
  )
}

/**
 * 更新用户信息
 */
export function updateUser(userId: number, data: UserUpdateForm) {
  return request.put<never, { code: number; message: string; data: UserInfo }>(
    `/users/${userId}`,
    data
  )
}

/**
 * 删除用户
 */
export function deleteUser(userId: number) {
  return request.delete<never, { code: number; message: string; data: null }>(
    `/users/${userId}`
  )
}

/**
 * 重置用户密码
 */
export function resetUserPassword(userId: number, data: PasswordResetForm) {
  return request.put<never, { code: number; message: string; data: null }>(
    `/users/${userId}/reset-password`,
    data
  )
}

/**
 * 启用/禁用用户
 */
export function toggleUserStatus(userId: number) {
  return request.put<never, { code: number; message: string; data: UserInfo }>(
    `/users/${userId}/toggle-status`
  )
}
