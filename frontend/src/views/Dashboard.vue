<template>
  <div>
    <h2>仪表盘</h2>
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6">
        <el-card shadow="hover" v-loading="loading">
          <el-statistic title="项目总数" :value="stats.projects">
            <template #suffix>
              <el-icon><Files /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" v-loading="loading">
          <el-statistic title="运行中任务" :value="stats.runningTasks">
            <template #suffix>
              <el-icon><VideoPlay /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" v-loading="loading">
          <el-statistic title="今日任务" :value="stats.todayTasks">
            <template #suffix>
              <el-icon><Document /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" v-loading="loading">
          <el-statistic title="成功率" :value="stats.successRate" suffix="%">
            <template #prefix>
              <el-icon><SuccessFilled /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>最近任务</span>
          </template>
          <el-table :data="recentTasks" v-loading="loading" size="small" max-height="300">
            <el-table-column prop="spider_name" label="爬虫" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="taskStatusType(row.status)" size="small">
                  {{ taskStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="160">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>系统状态</span>
          </template>
          <el-descriptions :column="1" border size="small" v-loading="loading">
            <el-descriptions-item label="后端服务">
              <el-tag :type="health.services?.database === 'connected' ? 'success' : 'danger'" size="small">
                {{ health.services?.database === 'connected' ? '正常' : '异常' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据库">
              <el-tag :type="health.services?.database === 'connected' ? 'success' : 'danger'" size="small">
                {{ health.services?.database || '未知' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Redis">
              <el-tag :type="health.services?.redis === 'connected' ? 'success' : 'danger'" size="small">
                {{ health.services?.redis || '未知' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="调度器">
              <el-tag :type="health.services?.scheduler === 'running' ? 'success' : 'warning'" size="small">
                {{ health.services?.scheduler || '未知' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card style="margin-top: 20px" shadow="hover">
      <template #header>
        <h3>欢迎使用 CrawloPilot</h3>
      </template>
      <p>CrawloPilot 是 Crawlo 爬虫框架的配套管理部署平台。</p>
      <p>当前版本：v1.0.0</p>
      <el-divider />
      <h4>快速开始</h4>
      <ul>
        <li>创建您的第一个爬虫项目</li>
        <li>配置任务调度</li>
        <li>监控运行状态</li>
        <li>查看数据统计</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getProjects } from '@/api/project'
import { listTasks } from '@/api/execution'
import { getDashboardData, getHealthStatus } from '@/api/monitoring'

const loading = ref(false)
const stats = reactive({
  projects: 0,
  runningTasks: 0,
  todayTasks: 0,
  successRate: 0
})
const recentTasks = ref([])
const health = reactive({
  status: 'unknown',
  services: {}
})

const taskStatusType = (status) => {
  const map = { pending: 'info', running: 'warning', success: 'success', failed: 'danger', cancelled: 'info' }
  return map[status] || 'info'
}

const taskStatusText = (status) => {
  const map = { pending: '待执行', running: '运行中', success: '成功', failed: '失败', cancelled: '已取消' }
  return map[status] || status
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const loadDashboard = async () => {
  loading.value = true
  try {
    // 并行加载所有数据
    const [projectsRes, runningRes, todayRes, tasksRes, healthRes] = await Promise.allSettled([
      getProjects({ limit: 1 }),
      listTasks({ status: 'running', limit: 1 }),
      listTasks({ status: 'success', limit: 500 }),
      listTasks({ limit: 10 }),
      getHealthStatus()
    ])

    // 项目总数
    if (projectsRes.status === 'fulfilled') {
      const data = projectsRes.value
      stats.projects = data.total || (Array.isArray(data) ? data.length : 0)
    }

    // 运行中任务数
    if (runningRes.status === 'fulfilled') {
      const data = runningRes.value
      stats.runningTasks = data.total || (Array.isArray(data) ? data.length : 0)
    }

    // 今日任务 / 成功率（复用成功查询结果）
    if (todayRes.status === 'fulfilled') {
      const data = todayRes.value
      const successItems = data.items || data
      const successCount = Array.isArray(successItems) ? successItems.length : 0
      const totalTasks = stats.runningTasks + successCount
      stats.todayTasks = totalTasks
      stats.successRate = totalTasks > 0 ? Math.round((successCount / totalTasks) * 100) : 100
    }

    // 最近任务
    if (tasksRes.status === 'fulfilled') {
      const data = tasksRes.value
      recentTasks.value = data.items || data || []
    }

    // 健康状态
    if (healthRes.status === 'fulfilled') {
      Object.assign(health, healthRes.value)
    }
  } catch (error) {
    console.error('加载仪表盘数据失败', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDashboard()
})
</script>
