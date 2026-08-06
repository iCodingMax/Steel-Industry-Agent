<template>
  <div class="avatar-image" :class="[type]">
    <img
      :src="imageSrc"
      :alt="alt"
      class="avatar-img"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import userAvatar from '@/assets/avatar-user.png'
import assistantAvatar from '@/assets/avatar-assistant.png'

interface Props {
  type: 'user' | 'assistant'
  alt?: string
}

const props = withDefaults(defineProps<Props>(), {
  alt: '头像'
})

const imageMap: Record<string, string> = {
  user: userAvatar,
  assistant: assistantAvatar
}

const imageSrc = computed(() => imageMap[props.type] || assistantAvatar)
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
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}
</style>
