<template>
  <div class="avatar-image" :class="[type, { 'has-image': hasImage }]">
    <!-- 优先显示图片 -->
    <img
      v-if="hasImage"
      :src="imageSrc"
      :alt="alt"
      class="avatar-img"
      @error="handleImageError"
    />
    <!-- 回退显示SVG -->
    <svg v-else viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" class="avatar-svg">
      <!-- 用户头像 SVG (钢铁侠) -->
      <template v-if="type === 'user'">
        <path d="M20 4C12 4 8 10 8 16c0 4 1 6 2 8l2 4c1 2 2 4 4 4h8c2 0 3-2 4-4l2-4c1-2 2-4 2-8 0-6-4-12-12-12z" fill="#dc2626"/>
        <path d="M20 6C14 6 10 11 10 16c0 3 1 5 2 7l2 4c1 1 2 3 3 3h6c1 0 2-2 3-3l2-4c1-2 2-4 2-7 0-5-4-10-10-10z" fill="#d97706"/>
        <line x1="20" y1="6" x2="20" y2="30" stroke="#991b1b" stroke-width="1.5"/>
        <path d="M12 15l4-2 4 2" fill="#60a5fa" stroke="#2563eb" stroke-width="0.5"/>
        <path d="M20 15l4-2 4 2" fill="#60a5fa" stroke="#2563eb" stroke-width="0.5"/>
        <rect x="15" y="24" width="10" height="2" rx="1" fill="#991b1b"/>
        <circle cx="20" cy="10" r="2" fill="#93c5fd" stroke="#3b82f6" stroke-width="0.5"/>
      </template>
      <!-- 助手头像 SVG (贾维斯) -->
      <template v-else>
        <rect x="0" y="0" width="40" height="40" rx="8" fill="white"/>
        <path d="M20 4 L28 20 L20 36 L12 20 Z" stroke="#fbbf24" stroke-width="3" fill="none"/>
        <path d="M28 10 L36 20 L28 30 L20 20 Z" stroke="#60a5fa" stroke-width="3" fill="none"/>
      </template>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

interface Props {
  type: 'user' | 'assistant'
  alt?: string
}

const props = withDefaults(defineProps<Props>(), {
  alt: '头像'
})

const hasImage = ref(false)
const imageSrc = ref('')

// 图片路径常量
const imageUrls: Record<string, string> = {
  user: '/src/assets/avatar-user.png',
  assistant: '/src/assets/avatar-assistant.png'
}

// 尝试加载图片
const tryLoadImage = () => {
  const url = imageUrls[props.type]
  
  // 创建一个临时图片对象来测试图片是否存在
  const img = new Image()
  img.onload = () => {
    imageSrc.value = url
    hasImage.value = true
  }
  img.onerror = () => {
    // 图片不存在，保持SVG显示
    hasImage.value = false
  }
  img.src = url
}

// 图片加载失败时回退到SVG
const handleImageError = () => {
  hasImage.value = false
}

onMounted(() => {
  tryLoadImage()
})

watch(() => props.type, () => {
  tryLoadImage()
})
</script>

<style scoped>
.avatar-image {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #fff;
}

.avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}

.avatar-svg {
  width: 100%;
  height: 100%;
}

.user .avatar-svg {
  width: 24px;
  height: 24px;
}

.assistant .avatar-svg {
  width: 28px;
  height: 28px;
}
</style>