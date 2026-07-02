import request from './index'

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  token: string
  expiresIn: number
}

export interface UserInfo {
  id: number
  username: string
  role: string
  createdAt: string
  lastLoginAt: string
  forceChangePassword: boolean
}

export interface ChangePasswordRequest {
  oldPassword: string
  newPassword: string
}

export function loginApi(data: LoginRequest) {
  return request.post<never, { code: number; message: string; data: LoginResponse }>(
    '/auth/login',
    data
  )
}

export function getUserInfoApi() {
  return request.get<never, { code: number; message: string; data: UserInfo }>('/auth/me')
}

export function changePasswordApi(data: ChangePasswordRequest) {
  return request.post<never, { code: number; message: string; data: null }>(
    '/auth/change-password',
    data
  )
}

export function logoutApi() {
  return request.post<never, { code: number; message: string; data: null }>('/auth/logout')
}
