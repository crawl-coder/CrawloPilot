<template>
  <div class="dashboard-container">
    <div class="page-header">
      <h2>仪表盘</h2>
      <span class="page-subtitle">系统运行总览</span>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <StatCard label="项目总数" :value="stats.projects" :icon="Files" color="var(--cp-chart-1)" />
      </el-col>
      <el-col :span="6">
        <StatCard label="爬虫总数" :value="stats.spiders" :icon="Aim" color="#7c5cff" />
      </el-col>
      <el-col :span="6">
        <StatCard label="运行中任务" :value="stats.runningTasks" :icon="VideoPlay" color="var(--cp-warning)" />
      </el-col>
      <el-col :span="6">
        <StatCard label="今日任务" :value="stats.todayTasks" :icon="Document" color="var(--cp-chart-5)" />
      </el-col>
    </el-row>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <StatCard label="成功率" :value="stats.successRate" suffix="%" :icon="SuccessFilled" color="var(--cp-success)" />
      </el-col>
      <el-col :span="6">
        <StatCard label="在线节点" :value="stats.onlineNodes" :icon="Monitor" color="var(--cp-chart-2)" />
      </el-col>
      <el-col :span="6">
        <StatCard label="节点总数" :value="stats.totalNodes" :icon="Connection" color="var(--cp-info)" />
      </el-col>
    </el-row>

    <el-card class="welcome-card cp-animate-in" shadow="never">
      <template #header>
        <h3>欢迎使用 CrawloPilot</h3>
      </template>
      <p>CrawloPilot 是 Crawlo 爬虫框架的配套管理部署平台。</p>
      <p class="version-text">当前版本：v1.0.0</p>
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
import { Files, Aim, VideoPlay, Document, SuccessFilled, Monitor, Connection } from '@element-plus/icons-vue'
import { getDashboardData } from '@/api/monitoring'
import { getSpiders } from '@/api/spider'
import { getNodes } from '@/api/node'
import StatCard from '@/components/StatCard.vue'

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
  padding: 0;
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: var(--cp-space-sm);
  margin-bottom: var(--cp-space-lg);
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--cp-text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--cp-text-secondary);
}

.stats-row {
  margin-bottom: var(--cp-space-md);
}

.welcome-card {
  margin-top: var(--cp-space-md);
}

.welcome-card h3 {
  font-weight: 600;
}

.version-text {
  color: var(--cp-text-secondary);
  font-size: 13px;
}
</style>
