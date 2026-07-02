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
