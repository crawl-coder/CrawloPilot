/**
 * 主题（暗色模式）状态管理
 * 通过 html.dark class 切换 element-plus 与自定义 token 的暗色变体
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'cp-theme'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(localStorage.getItem(STORAGE_KEY) === 'dark')

  function apply() {
    document.documentElement.classList.toggle('dark', isDark.value)
  }

  function toggle() {
    isDark.value = !isDark.value
    localStorage.setItem(STORAGE_KEY, isDark.value ? 'dark' : 'light')
    apply()
  }

  // 初始化时应用一次
  apply()

  return { isDark, toggle, apply }
})
