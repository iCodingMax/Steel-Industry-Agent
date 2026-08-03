import request from './index'

export interface OAuthConfig {
  id: number
  configType: string
  authorizationUrl: string
  tokenUrl: string
  userInfoUrl: string
  scope: string
  clientId: string
  clientSecret: string
  fieldMapping: Record<string, string> | null
  redirectUrl: string
  enabled: boolean
  createdAt: string | null
  updatedAt: string | null
}

export interface OAuthLoginUrl {
  loginUrl: string
  state: string
}

export interface OAuthCallbackResult {
  token: string
  expiresIn: number
  user: Record<string, any>
}

/**
 * 获取系统OAuth2配置
 */
export function getOAuthConfig(configType: string = 'system') {
  return request.get<never, { code: number; message: string; data: OAuthConfig }>(
    `/oauth/config?config_type=${configType}`
  )
}

/**
 * 保存OAuth2配置
 */
export function saveOAuthConfig(data: Partial<OAuthConfig>) {
  return request.post<never, { code: number; message: string; data: OAuthConfig }>(
    '/oauth/config',
    data
  )
}

/**
 * 获取系统OAuth2授权URL（平台登录用）
 */
export function getOAuthLoginUrl() {
  return request.get<never, { code: number; message: string; data: OAuthLoginUrl }>(
    '/oauth/login-url'
  )
}

/**
 * 系统OAuth2回调处理（平台登录用）
 */
export function handleOAuthCallback(code: string, state?: string) {
  const data: Record<string, string> = { code }
  if (state) {
    data.state = state
  }
  return request.post<never, { code: number; message: string; data: OAuthCallbackResult }>(
    '/oauth/callback',
    data
  )
}

/**
 * 获取对话用户OAuth2授权URL（应用集成用）
 */
export function getChatOAuthLoginUrl() {
  return request.get<never, { code: number; message: string; data: OAuthLoginUrl }>(
    '/oauth/chat-login-url'
  )
}

/**
 * 对话用户OAuth2回调处理（应用集成用）
 */
export function handleChatOAuthCallback(code: string, state?: string) {
  const data: Record<string, string> = { code }
  if (state) {
    data.state = state
  }
  return request.post<never, { code: number; message: string; data: OAuthCallbackResult }>(
    '/oauth/chat-callback',
    data
  )
}
