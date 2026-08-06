/**
 * 用户状态管理 Store
 * 集中管理登录态、用户信息、权限，替代 localStorage 手动同步
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCurrentUser } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  // state
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)

  // getters
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => {
    if (!user.value?.roles) return false
    return user.value.roles.some(r => r.name === 'admin')
  })
  const username = computed(() => user.value?.username || '')

  // actions
  function setToken(newToken) {
    token.value = newToken
    if (newToken) {
      localStorage.setItem('token', newToken)
    } else {
      localStorage.removeItem('token')
    }
  }

  async function fetchUser() {
    if (!token.value) return null
    try {
      user.value = await getCurrentUser()
      return user.value
    } catch (e) {
      // 仅在 401（token 失效）时登出；
      // 网络错误/5xx 属于临时故障，不应清空登录态
      if (e?.response?.status === 401) {
        logout()
      }
      throw e
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    username,
    setToken,
    fetchUser,
    logout
  }
})
