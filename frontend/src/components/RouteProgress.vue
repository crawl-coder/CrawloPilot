<template>
  <transition name="cp-fade">
    <div v-show="visible" class="route-progress">
      <div class="route-progress-bar" :style="{ width: percent + '%' }"></div>
    </div>
  </transition>
</template>

<script setup>
/**
 * 路由切换顶部进度条
 * 监听路由事件，提供全局加载反馈
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const visible = ref(false)
const percent = ref(0)
let timer = null
let removeAfter = null
let removeBefore = null

const start = () => {
  visible.value = true
  percent.value = 0
  clearInterval(timer)
  timer = setInterval(() => {
    // 模拟渐进，最多到 90%
    if (percent.value < 90) {
      percent.value += Math.random() * 15
    }
  }, 200)
}

const finish = () => {
  clearInterval(timer)
  percent.value = 100
  setTimeout(() => {
    visible.value = false
    percent.value = 0
  }, 200)
}

onMounted(() => {
  removeBefore = router.beforeEach((to, from, next) => {
    if (to.path !== from.path) start()
    next()
  })
  removeAfter = router.afterEach(() => finish())
})

onUnmounted(() => {
  clearInterval(timer)
  removeBefore?.()
  removeAfter?.()
})
</script>

<style scoped>
.route-progress {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  z-index: 9999;
  pointer-events: none;
}

.route-progress-bar {
  height: 100%;
  background: var(--cp-primary, #409eff);
  transition: width 0.2s ease;
  box-shadow: 0 0 8px var(--cp-primary, #409eff);
}

.cp-fade-enter-active,
.cp-fade-leave-active {
  transition: opacity 0.2s;
}

.cp-fade-enter-from,
.cp-fade-leave-to {
  opacity: 0;
}
</style>
