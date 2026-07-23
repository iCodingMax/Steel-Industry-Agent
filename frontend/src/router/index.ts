import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/chat/embed/:appId',
    name: 'ChatEmbed',
    component: () => import('@/views/ChatEmbedView.vue'),
    meta: { title: '智能助手', requiresAuth: false },
  },
  {
    path: '/',
    name: 'MainLayout',
    component: () => import('@/components/layout/MainLayout.vue'),
    redirect: '/chat',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/ChatView.vue'),
        meta: { title: '智能对话', icon: 'ChatSquare' },
      },
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
        path: 'system-settings',
        name: 'SystemSettings',
        component: () => import('@/views/SystemSettingsView.vue'),
        meta: { title: '系统设置', icon: 'Setting' },
        children: [
          {
            path: 'user',
            name: 'UserSettings',
            component: () => import('@/views/SystemSettingsView.vue'),
            meta: { title: '用户管理', icon: 'User' },
          },
          {
            path: 'oauth',
            name: 'OAuthSettings',
            component: () => import('@/views/SystemSettingsView.vue'),
            meta: { title: '登录认证', icon: 'Lock' },
          },
        ],
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else {
    next()
  }
})

export default router
