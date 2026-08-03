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
      <!-- 用户头像 SVG (紫色圆形+白色小人，与右上角账号头像一致) -->
      <template v-if="type === 'user'">
        <circle cx="20" cy="20" r="18" fill="#6366f1"/>
        <path d="M20 14c-2.2 0-4 1.8-4 4s1.8 4 4 4 4-1.8 4-4-1.8-4-4-4zM12 30c0-4.4 3.6-8 8-8s8 3.6 8 8" stroke="#ffffff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
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
  width: 32px;
  height: 32px;
}

.assistant .avatar-svg {
  width: 28px;
  height: 28px;
}
</style>