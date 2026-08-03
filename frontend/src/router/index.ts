import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
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
  {
    path: '/chat/embed/:appId',
    name: 'ChatEmbed',
    component: () => import('@/views/ChatEmbedView.vue'),
    meta: { title: '智能助手', requiresAuth: false },
  },
  {
    path: '/chat/:accessHash',
    name: 'ChatEmbedByHash',
    component: () => import('@/views/ChatEmbedView.vue'),
    meta: { title: '智能助手', requiresAuth: false },
  },
  {
    path: '/',
    name: 'MainLayout',
    component: () => import('@/components/layout/MainLayout.vue'),
    // redirect: '/chat',
    redirect: '/app-management',
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

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }
  
  try {
    // 只在首次加载时获取用户信息，避免每次路由切换都请求
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
    next()
  }
})

export default router
