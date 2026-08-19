/**
 * Axios HTTP 客户端实例配置（全局请求/响应拦截器）
 *
 * 职责：
 *   1. 创建统一的 axios 实例（baseURL、超时、默认请求头）
 *   2. 请求拦截器：自动注入 JWT token（非公开页面）
 *   3. 响应拦截器：统一处理业务错误码（{code, message, data} 信封格式）
 *
 * 架构定位（面试重点）：
 *   本模块是前端「API 层」的基础设施，所有普通 HTTP 请求都通过此实例发出。
 *   例外：SSE 流式请求用 fetch API（见 session.ts 的 streamChat），不走 axios。
 *
 * 统一响应格式（与后端 exception_handler.py 对应）：
 *   成功：{ code: 0, message: "success", data: {...} }
 *   失败：{ code: 404, message: "会话不存在", data: null }
 *   响应拦截器检查 res.code !== 0 即为业务错误，统一弹 ElMessage 提示。
 *
 * 双模式认证策略（面试考点 —— 嵌入式 vs 管理后台）：
 *   本系统有两种使用场景：
 *     1. 管理后台模式 —— 用户登录后使用，携带系统管理员 JWT token
 *     2. 嵌入对话模式 —— 网页嵌入/链接分享，不需要系统管理员登录
 *   通过 isPublicPage() 区分：路由以 /chat/ 开头（非 /chat/api/）的页面为公开页面，
 *   公开页面不注入系统管理员 token，避免与对话用户的认证体系冲突。
 */
import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

// 创建 axios 实例（工厂模式）
const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',        // API 前缀，由 Vite 代理转发到后端
  timeout: 120000,           // 超时 120 秒（LLM 调用可能较慢）
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * 判断当前是否在公开访问页面（嵌入/链接访问模式）
 *
 * 公开页面的路由特征：以 /chat/ 开头，但不包含 /chat/api/
 *   - /chat/embed/:appId       → 嵌入式对话（公开）
 *   - /chat/:accessHash        → 链接分享对话（公开）
 *   - /chat/api/auth/oauth2    → 对话用户认证回调（非公开，不走此逻辑）
 *
 * 公开页面与后台管理页面的认证体系不同：
 *   - 后台管理页面用系统管理员 JWT token（localStorage 'token'）
 *   - 公开页面用对话用户认证（sessionStorage 或 accessHash）
 *   所以公开页面不注入管理员 token，避免认证冲突。
 */
function isPublicPage(): boolean {
  const path = window.location.pathname
  return path.startsWith('/chat/') && !path.startsWith('/chat/api/')
}

// ===================== 请求拦截器 =====================
// 职责：在请求发出前，自动注入认证 token
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 公开页面不添加系统管理员 token，避免认证冲突
    if (!isPublicPage()) {
      const token = localStorage.getItem('token')
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// ===================== 响应拦截器 =====================
// 职责：统一处理后端返回的 {code, message, data} 信封格式
// 注意：HTTP status_code 始终为 200（后端设计），错误信息在 body.code 字段中
request.interceptors.response.use(
  (response) => {
    const res = response.data

    // 检查业务错误码：code !== 0 表示业务错误（如会话不存在、参数校验失败等）
    if (res.code !== 0) {
      // 公开页面静默处理错误，不弹提示也不跳转登录页
      // （公开页面的错误处理由各组件自行处理，如显示"对话不可用"等）
      if (!isPublicPage()) {
        ElMessage.error(res.message || '请求失败')
        // 401 = 未认证或 token 过期，清除 token 并跳转登录页
        if (res.code === 401) {
          localStorage.removeItem('token')
          router.push('/login')
        }
      }
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    // 成功响应，返回 data 部分（剥离 code/message 信封）
    return res
  },
  (error) => {
    // 网络层错误（非 2xx HTTP 状态码，如 500 服务器内部错误）
    if (error.response?.status === 401) {
      // 公开页面 401 静默处理，非公开页面跳转登录
      if (!isPublicPage()) {
        localStorage.removeItem('token')
        router.push('/login')
      }
    } else if (!isPublicPage()) {
      // 非公开页面才显示网络错误提示，公开页面由各组件自行处理
      ElMessage.error(error.message || '网络错误')
    }
    return Promise.reject(error)
  }
)

export default request
