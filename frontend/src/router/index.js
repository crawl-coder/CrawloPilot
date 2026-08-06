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
        component: () => import('@/views/Dashboard.vue')
      },
      {
        path: 'projects',
        name: 'Projects',
        component: () => import('@/views/Projects.vue')
      },
      {
        path: 'projects/:id',
        name: 'ProjectDetail',
        component: () => import('@/views/ProjectDetail.vue')
      },
      {
        path: 'spiders',
        name: 'Spiders',
        component: () => import('@/views/Spiders.vue')
      },
      {
        path: 'spiders/:id',
        name: 'SpiderDetail',
        component: () => import('@/views/SpiderDetail.vue')
      },
      {
        path: 'nodes',
        name: 'Nodes',
        component: () => import('@/views/Nodes.vue')
      },
      {
        path: 'servers/:id',
        name: 'ServerDetail',
        component: () => import('@/views/ServerDetail.vue')
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/Tasks.vue')
      },
      {
        path: 'tasks/:id',
        name: 'TaskDetail',
        component: () => import('@/views/TaskDetail.vue')
      },
      {
        path: 'users',
        name: 'Users',
        meta: { requiresAdmin: true },
        component: () => import('@/views/Users.vue')
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
