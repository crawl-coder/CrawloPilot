import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        meta: { title: '仪表盘' },
        component: () => import('@/views/Dashboard.vue')
      },
      {
        path: 'projects',
        name: 'Projects',
        meta: { title: '项目管理' },
        component: () => import('@/views/Projects.vue')
      },
      {
        path: 'projects/:id',
        name: 'ProjectDetail',
        meta: { title: '项目详情' },
        component: () => import('@/views/ProjectDetail.vue')
      },
      {
        path: 'spiders',
        name: 'Spiders',
        meta: { title: '爬虫管理' },
        component: () => import('@/views/Spiders.vue')
      },
      {
        path: 'spiders/:id',
        name: 'SpiderDetail',
        meta: { title: '爬虫详情' },
        component: () => import('@/views/SpiderDetail.vue')
      },
      {
        path: 'nodes',
        name: 'Nodes',
        meta: { title: '节点管理', requiresAdmin: true },
        component: () => import('@/views/Nodes.vue')
      },
      {
        path: 'servers/:id',
        name: 'ServerDetail',
        meta: { title: '服务器详情', requiresAdmin: true },
        component: () => import('@/views/ServerDetail.vue')
      },
      {
        path: 'tasks',
        name: 'Tasks',
        meta: { title: '任务管理' },
        component: () => import('@/views/Tasks.vue')
      },
      {
        path: 'tasks/:id',
        name: 'TaskDetail',
        meta: { title: '任务详情' },
        component: () => import('@/views/TaskDetail.vue')
      },
      {
        path: 'schedules',
        name: 'Schedules',
        meta: { title: '定时任务' },
        component: () => import('@/views/Schedules.vue')
      },
      {
        path: 'users',
        name: 'Users',
        meta: { title: '用户管理', requiresAdmin: true },
        component: () => import('@/views/Users.vue')
      },
      {
        path: 'login-logs',
        name: 'LoginLogs',
        meta: { title: '登录日志', requiresAdmin: true },
        component: () => import('@/views/LoginLogs.vue')
      },
      {
        path: 'alerts/rules',
        name: 'AlertRules',
        meta: { title: '告警规则', requiresAdmin: true },
        component: () => import('@/views/AlertRules.vue')
      },
      {
        path: 'alerts/records',
        name: 'AlertRecords',
        meta: { title: '告警记录' },
        component: () => import('@/views/AlertRecords.vue')
      },
      {
        path: 'profile',
        name: 'Profile',
        meta: { title: '个人中心' },
        component: () => import('@/views/Profile.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.path === '/login') {
    if (token) next('/')
    else next()
    return
  }

  if (!token) {
    next('/login')
    return
  }

  // 需要 admin 权限的路由：确保用户信息已加载后再校验
  if (to.meta?.requiresAdmin) {
    try {
      const userStore = useUserStore()
      if (!userStore.user) {
        await userStore.fetchUser()
      }
      if (!userStore.isAdmin) {
        next('/dashboard')
        return
      }
    } catch (e) {
      next('/login')
      return
    }
  }

  next()
})

export default router
