<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <svg class="jarvis-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="20" cy="20" r="18" stroke="#3b82f6" stroke-width="2" fill="none" opacity="0.6"/>
          <circle cx="20" cy="20" r="14" stroke="#3b82f6" stroke-width="1.5" fill="none" stroke-dasharray="22 66" stroke-dashoffset="0" opacity="0.8"/>
          <circle cx="20" cy="20" r="10" stroke="#60a5fa" stroke-width="1.5" fill="none" stroke-dasharray="16 47" stroke-dashoffset="-8" opacity="0.9"/>
          <circle cx="20" cy="20" r="4" fill="#3b82f6"/>
          <circle cx="20" cy="20" r="2" fill="#93c5fd"/>
        </svg>
        <span class="logo-text">钢铁行业智能助手</span>
      </div>
    </div>
    <div class="sidebar-menu">
      <div
        v-for="item in menuItems"
        :key="item.path"
        class="menu-item"
        :class="{ active: isActive(item.path) }"
        @click="navigateTo(item.path)"
      >
        <svg class="menu-svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" v-html="item.svgPath" />
        <span class="menu-text">{{ item.title }}</span>
      </div>
    </div>
    <div class="sidebar-footer">
      <div class="system-status">
        <span class="status-dot"></span>
        <span>System Online</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// 使用 Feather Icons 风格的 SVG path，不依赖 @element-plus/icons-vue
const menuItems = [
  {
    path: '/chat',
    title: '智能对话',
    svgPath: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  },
  {
    path: '/knowledge',
    title: '知识管理',
    svgPath: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
  },
  {
    path: '/data-config',
    title: '数据管理',
    svgPath: '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
  },
  {
    path: '/audit-log',
    title: '审计日志',
    svgPath: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  },
  {
    path: '/model-config',
    title: '模型配置',
    svgPath: '<rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
  },
  {
    path: '/system-settings',
    title: '系统设置',
    svgPath: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  },
]

const isActive = (path: string) => {
  return route.path.startsWith(path)
}

const navigateTo = (path: string) => {
  router.push(path)
}
</script>

<style lang="scss" scoped>
.sidebar {
  width: $sidebar-width;
  background: linear-gradient(180deg, #0a0e27 0%, #0d1b3e 40%, #0f2044 100%);
  display: flex;
  flex-direction: column;
  color: $sidebar-text;
  flex-shrink: 0;
  border-right: 1px solid rgba(59, 130, 246, 0.15);
}

.sidebar-header {
  height: $header-height;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.15);
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;

  .jarvis-icon {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
  }
}

.logo-text {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  line-height: 1.2;
  white-space: nowrap;
  background: linear-gradient(90deg, #60a5fa 0%, #93c5fd 50%, #60a5fa 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.sidebar-menu {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin-bottom: 4px;
  border-radius: $border-radius;
  cursor: pointer;
  transition: all 0.2s ease;
  color: rgba(226, 232, 240, 0.8);

  .menu-svg-icon {
    width: 18px;
    height: 18px;
    flex-shrink: 0;
  }

  .menu-text {
    font-size: 14px;
  }

  &:hover {
    background-color: rgba(59, 130, 246, 0.1);
    color: #fff;
  }

  &.active {
    background: linear-gradient(90deg, rgba(59, 130, 246, 0.2) 0%, rgba(59, 130, 246, 0.08) 100%);
    color: #fff;
    font-weight: 500;
    border-left: 3px solid #3b82f6;

    .menu-svg-icon {
      color: #60a5fa;
    }
  }
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(59, 130, 246, 0.15);
}

.system-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(226, 232, 240, 0.5);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: $success-color;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
