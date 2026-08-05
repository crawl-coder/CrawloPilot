<template>
  <div class="dashboard-container">
    <h2>仪表盘</h2>
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="项目总数" :value="stats.projects">
            <template #suffix>
              <el-icon><Files /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="爬虫总数" :value="stats.spiders">
            <template #suffix>
              <el-icon><Aim /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="运行中任务" :value="stats.runningTasks">
            <template #suffix>
              <el-icon><VideoPlay /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="今日任务" :value="stats.todayTasks">
            <template #suffix>
              <el-icon><Document /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="成功率" :value="stats.successRate" suffix="%">
            <template #prefix>
              <el-icon><SuccessFilled /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="在线节点" :value="stats.onlineNodes">
            <template #suffix>
              <el-icon><Monitor /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="节点总数" :value="stats.totalNodes" />
        </el-card>
      </el-col>
    </el-row>
    
    <el-card style="margin-top: 20px">
      <template #header>
        <h3>欢迎使用 CrawloPilot</h3>
      </template>
      <p>CrawloPilot 是 Crawlo 爬虫框架的配套管理部署平台。</p>
      <p>当前版本：v1.0.0</p>
      <el-divider />
      <h4>快速开始</h4>
      <el-steps :space="200" direction="vertical">
        <el-step title="创建项目" description="在项目管理中创建您的第一个爬虫项目" />
        <el-step title="创建爬虫" description="在项目中添加爬虫，支持上传/空模板" />
        <el-step title="上传代码" description="通过项目文件管理上传爬虫代码" />
        <el-step title="执行与监控" description="在任务管理中查看运行状态和实时日志" />
      </el-steps>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Files, Aim, VideoPlay, Document, SuccessFilled, Monitor } from '@element-plus/icons-vue'
import { getDashboardData } from '@/api/monitoring'
import { getSpiders } from '@/api/spider'
import { getNodes } from '@/api/node'

const stats = ref({
  projects: 0,
  spiders: 0,
  runningTasks: 0,
  todayTasks: 0,
  successRate: 0,
  onlineNodes: 0,
  totalNodes: 0
})

onMounted(async () => {
  try {
    // 并行加载各类统计数据
    const [dashboard, spidersData, nodesData] = await Promise.allSettled([
      getDashboardData().catch(() => ({})),
      getSpiders({ limit: 1 }).catch(() => ({ total: 0 })),
      getNodes().catch(() => [])
    ])

    if (dashboard.status === 'fulfilled' && dashboard.value) {
      const d = dashboard.value
      stats.value.projects = d.projects?.total || 0
      stats.value.runningTasks = d.tasks?.running || 0
      stats.value.todayTasks = d.tasks?.today || 0
      stats.value.successRate = d.tasks?.success_rate || 0
    }

    if (spidersData.status === 'fulfilled') {
      stats.value.spiders = spidersData.value.total || 0
    }

    if (nodesData.status === 'fulfilled') {
      const nodes = Array.isArray(nodesData.value) ? nodesData.value : (nodesData.value?.items || [])
      stats.value.totalNodes = nodes.length
      stats.value.onlineNodes = nodes.filter(n => n.status === 'online').length
    }
  } catch (error) {
    console.error('加载 Dashboard 数据失败:', error)
  }
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}

.stat-card {
  text-align: center;
}
</style>
