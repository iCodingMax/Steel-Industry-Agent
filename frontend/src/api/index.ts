import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * 判断当前是否在公开访问页面（嵌入/链接访问）
 * 公开页面的路由以 /chat/ 开头（但不包含 /chat/api/）
 */
function isPublicPage(): boolean {
  const path = window.location.pathname
  return path.startsWith('/chat/') && !path.startsWith('/chat/api/')
}

request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 公开页面不添加系统管理员token，避免认证冲突
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

request.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res.code !== 0) {
      // 公开页面静默处理错误，不弹提示也不跳转登录页
      if (!isPublicPage()) {
        ElMessage.error(res.message || '请求失败')
        if (res.code === 401) {
          localStorage.removeItem('token')
          router.push('/login')
        }
      }
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res
  },
  (error) => {
    if (error.response?.status === 401) {
      // 公开页面401静默处理，非公开页面跳转登录
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
