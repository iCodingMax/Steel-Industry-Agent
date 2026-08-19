/**
 * Vue Router 路由配置（前端导航核心）
 *
 * 职责：
 *   1. 定义所有页面路由（管理后台 + 嵌入对话 + 认证回调）
 *   2. 路由守卫：鉴权（未登录跳转登录页）+ 懒加载用户信息
 *
 * 架构定位（面试重点）：
 *   本模块是前端「导航层」的核心，决定了用户访问不同 URL 时渲染哪个组件。
 *   路由分为两大类：
 *     A. 管理后台路由 —— requiresAuth: true，需要系统管理员 JWT token
 *     B. 公开对话路由 —— requiresAuth: false，网页嵌入/链接分享，无需登录
 *
 * 路由懒加载策略（面试考点 —— 性能优化）：
 *   所有 component 都用 () => import() 动态导入，实现按需加载。
 *   好处：首屏只加载当前路由的组件代码，其他路由的代码在访问时才加载，
 *         减小初始包体积，提升首屏渲染速度。
 *   Vite 会自动将动态 import 的组件拆分为独立的 chunk 文件。
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  // ===================== 认证相关路由（无需登录） =====================
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/app-login',
    name: 'AppLogin',
    component: () => import('@/views/AppLoginView.vue'),
    meta: { title: '应用登录', requiresAuth: false },
  },
  // OAuth2 认证回调路由（第三方登录回调入口）
  {
    path: '/admin/api/oauth2',
    name: 'OAuthCallback',
    component: () => import('@/views/OAuthCallbackView.vue'),
    meta: { title: '系统认证回调', requiresAuth: false },
  },
  {
    path: '/chat/api/auth/oauth2',
    name: 'AppOAuthCallback',
    component: () => import('@/views/AppOAuthCallbackView.vue'),
    meta: { title: '对话用户认证回调', requiresAuth: false },
  },

  // ===================== 公开对话路由（无需登录） =====================
  // 嵌入式对话：通过 appId 参数指定对话应用
  {
    path: '/chat/embed/:appId',
    name: 'ChatEmbed',
    component: () => import('@/views/ChatEmbedView.vue'),
    meta: { title: '智能助手', requiresAuth: false },
  },
  // 链接分享对话：通过 accessHash 参数（加密的访问链接）
  {
    path: '/chat/:accessHash',
    name: 'ChatEmbedByHash',
    component: () => import('@/views/ChatEmbedView.vue'),
    meta: { title: '智能助手', requiresAuth: false },
  },
  // AI助手独立路由（与 /chat/embed/:appId 共用同一组件）
  {
    path: '/ai-assistant',
    name: 'AiAssistant',
    component: () => import('@/views/ChatEmbedView.vue'),
    meta: { title: 'AI智能助手', requiresAuth: false },
  },
  {
    path: '/ai-assistant/:accessHash',
    name: 'AiAssistantByHash',
    component: () => import('@/views/ChatEmbedView.vue'),
    meta: { title: 'AI智能助手', requiresAuth: false },
  },

  // ===================== 管理后台路由（需要登录） =====================
  // 嵌套路由：MainLayout 是布局容器，children 是各管理页面
  // 菜单顺序约束（项目硬约束）：智能对话, 应用管理, 知识管理, 数据管理, 工具管理, 模型配置, 审计日志, 系统设置
  {
    path: '/',
    name: 'MainLayout',
    component: () => import('@/components/layout/MainLayout.vue'),
    // redirect: '/chat',   // 原默认跳转到智能对话页面（已注释）
    redirect: '/app-management',  // 现默认跳转到应用管理页面
    meta: { requiresAuth: true },
    children: [
      // {
      //   path: 'chat',
      //   name: 'Chat',
      //   component: () => import('@/views/ChatView.vue'),
      //   meta: { title: '智能对话', icon: 'ChatSquare' },
      // },
      {
        path: 'app-management',
        name: 'AppManagement',
        component: () => import('@/views/AppListView.vue'),
        meta: { title: '应用管理', icon: 'AppSettings' },
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/KnowledgeView.vue'),
        meta: { title: '知识管理', icon: 'FolderOpened' },
      },
      {
        path: 'data-config',
        name: 'DataConfig',
        component: () => import('@/views/DataConfigView.vue'),
        meta: { title: '数据管理', icon: 'DataLine' },
      },
      {
        path: 'tool-management',
        name: 'ToolManagement',
        component: () => import('@/views/ToolManagementView.vue'),
        meta: { title: '工具管理', icon: 'Tool' },
      },
      {
        path: 'datasource/:id',
        name: 'DatasourceDetail',
        component: () => import('@/views/DatasourceDetailView.vue'),
        meta: { title: '数据源详情', icon: 'DataLine' },
      },
      {
        path: 'audit-log',
        name: 'AuditLog',
        component: () => import('@/views/AuditLogView.vue'),
        meta: { title: '审计日志', icon: 'Notebook' },
      },
      {
        path: 'model-config',
        name: 'ModelConfig',
        component: () => import('@/views/ModelConfigView.vue'),
        meta: { title: '模型配置', icon: 'Monitor' },
      },
      {
        path: 'chat-users',
        name: 'ChatUsers',
        component: () => import('@/views/ChatUserView.vue'),
        meta: { title: '对话用户', icon: 'UserFilled' },
      },
      {
        path: 'system-settings',
        name: 'SystemSettings',
        component: () => import('@/views/SystemSettingsView.vue'),
        meta: { title: '系统设置', icon: 'Setting' },
      },
    ],
  },
]

// 创建路由实例（使用 HTML5 History 模式，非 hash 模式）
const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ===================== 全局前置守卫（路由拦截） =====================
// 职责：在每次路由切换前执行鉴权和用户信息加载
router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')

  // 鉴权：需要登录但未携带 token 的请求，重定向到登录页
  if (to.meta.requiresAuth && !token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })  // 登录后可跳回原页面
    return
  }

  try {
    // 懒加载用户信息（面试考点 —— 避免每次路由切换都请求后端）
    // 只在首次加载时获取用户信息（authStore.userInfo 为空时），
    // 后续路由切换直接复用 Pinia store 中的缓存数据。
    if (token) {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      if (!authStore.userInfo) {
        await authStore.fetchUserInfo()
      }
    }
    next()
  } catch (error) {
    console.error('路由守卫执行失败:', error)
    // 即使获取用户信息失败，也继续路由，避免阻塞页面显示
    // （用户信息获取失败不应该阻止用户访问页面，最多是 UI 显示不完整）
    next()
  }
})

export default router
