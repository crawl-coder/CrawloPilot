<template>
  <RouteProgress />
  <router-view />
</template>

<script setup>
import RouteProgress from '@/components/RouteProgress.vue'
import { useThemeStore } from '@/stores/theme'

// 应用启动时初始化主题（html.dark class），确保登录页等非布局页面也生效
useThemeStore()
</script>

<style>
/* 全局样式已迁移至 styles/global.css 与 styles/tokens.css */
</style>
