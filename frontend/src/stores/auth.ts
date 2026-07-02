import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { loginApi, getUserInfoApi, changePasswordApi } from '@/api/auth'
import type { LoginRequest, UserInfo } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const userInfo = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const username = computed(() => userInfo.value?.username || '')

  async function login(data: LoginRequest) {
    const res = await loginApi(data)
    token.value = res.data.token
    localStorage.setItem('token', res.data.token)
    await fetchUserInfo()
    return res
  }

  async function fetchUserInfo() {
    if (!token.value) return
    const res = await getUserInfoApi()
    userInfo.value = res.data
    return res
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    const res = await changePasswordApi({ oldPassword, newPassword })
    return res
  }

  function logout() {
    token.value = null
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    username,
    login,
    fetchUserInfo,
    changePassword,
    logout,
  }
})
