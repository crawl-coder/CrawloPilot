<template>
  <el-container class="layout-container">
    <el-aside :width="'var(--cp-sidebar-width)'">
      <div class="logo">
        <img src="@/assets/crawlopilot-logo.png" class="logo-img" alt="CrawloPilot" />
        <span class="logo-text">CrawloPilot</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="var(--cp-sidebar-bg)"
        text-color="var(--cp-sidebar-text)"
        active-text-color="var(--cp-sidebar-active)"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        
        <el-menu-item index="/projects">
          <el-icon><Files /></el-icon>
          <span>项目管理</span>
        </el-menu-item>
        
        <el-menu-item index="/spiders">
          <el-icon><Aim /></el-icon>
          <span>爬虫管理</span>
        </el-menu-item>
        
        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <span>任务管理</span>
        </el-menu-item>

        <el-menu-item index="/schedules">
          <el-icon><Clock /></el-icon>
          <span>定时任务</span>
        </el-menu-item>

        <el-menu-item index="/nodes">
          <el-icon><Monitor /></el-icon>
          <span>节点管理</span>
        </el-menu-item>
        
        <el-sub-menu v-if="userStore.isAdmin" index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/login-logs">
            <el-icon><Document /></el-icon>
            <span>登录日志</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header>
        <div class="header-content">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>{{ $route.meta.title || $route.name }}</el-breadcrumb-item>
          </el-breadcrumb>
          <div class="user-info">
            <el-tooltip :content="themeStore.isDark ? '切换到浅色模式' : '切换到暗色模式'" placement="bottom">
              <el-icon class="theme-toggle" @click="themeStore.toggle()">
                <Sunny v-if="themeStore.isDark" />
                <Moon v-else />
              </el-icon>
            </el-tooltip>
            <el-dropdown @command="handleCommand">
              <span class="user-name">
                {{ username }}
                <el-icon><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                  <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </el-header>
      
      <el-main>
        <router-view v-slot="{ Component }">
          <transition name="cp-page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Odometer, Files, User, ArrowDown, Monitor, List, Aim, Setting, Moon, Sunny, Clock, Document } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'

const router = useRouter()
const userStore = useUserStore()
const themeStore = useThemeStore()

const currentUser = computed(() => userStore.user)
const username = computed(() => userStore.username || '用户')

onMounted(async () => {
  // 路由守卫可能已获取过用户（如访问需权限页面），避免重复请求
  if (userStore.user) return
  try {
    await userStore.fetchUser()
  } catch (error) {
    // token 失效（401）时 store 已自动 logout 并由拦截器跳转，不重复处理
  }
})

const handleCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  }
}
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
}

.el-aside {
  background-color: var(--cp-sidebar-bg);
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  background-color: var(--cp-sidebar-logo-bg);
}

.logo-img {
  width: 32px;
  height: 32px;
  padding: 2px;
  object-fit: contain;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.el-header {
  background-color: var(--cp-header-bg);
  box-shadow: var(--cp-header-shadow);
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--cp-space-md);
}

.theme-toggle {
  font-size: 18px;
  cursor: pointer;
  color: var(--cp-text-regular);
  transition: color var(--cp-motion-fast) var(--cp-ease-out),
              transform var(--cp-motion-base) var(--cp-ease-out);
}

.theme-toggle:hover {
  color: var(--cp-primary);
  transform: rotate(15deg);
}

.user-name {
  cursor: pointer;
  color: var(--cp-text-regular);
}

.el-header {
  transition: background-color var(--cp-motion-base) var(--cp-ease-out);
}

.el-main {
  background-color: var(--cp-page-bg);
  padding: var(--cp-space-lg);
  transition: background-color var(--cp-motion-base) var(--cp-ease-out);
}
</style>
