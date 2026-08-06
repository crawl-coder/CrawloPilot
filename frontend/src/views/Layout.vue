<template>
  <el-container class="layout-container">
    <el-aside width="200px">
      <div class="logo">
        <img src="@/assets/crawlopilot-logo.png" class="logo-img" alt="CrawloPilot" />
        <span class="logo-text">CrawloPilot</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
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

        <el-menu-item index="/nodes">
          <el-icon><Monitor /></el-icon>
          <span>节点管理</span>
        </el-menu-item>
        
        <el-sub-menu index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header>
        <div class="header-content">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ $route.name }}</el-breadcrumb-item>
          </el-breadcrumb>
          <div class="user-info">
            <el-dropdown @command="handleCommand">
              <span class="user-name">
                {{ currentUser?.username || '用户' }}
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
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Odometer, Files, User, ArrowDown, Monitor, List, Aim, Setting } from '@element-plus/icons-vue'
import { getCurrentUser } from '@/api/auth'

const router = useRouter()
const currentUser = ref(null)

onMounted(async () => {
  try {
    currentUser.value = await getCurrentUser()
  } catch (error) {
    console.error('获取用户信息失败', error)
  }
})

const handleCommand = (command) => {
  if (command === 'logout') {
    localStorage.removeItem('token')
    ElMessage.success('已退出登录')
    router.push('/login')
  } else if (command === 'profile') {
    ElMessage.info('个人信息页面开发中')
  }
}
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
}

.el-aside {
  background-color: #304156;
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  background-color: #2b3a4a;
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
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
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
}

.user-name {
  cursor: pointer;
  color: #606266;
}

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
