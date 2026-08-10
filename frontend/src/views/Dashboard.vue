<template>
  <div class="dashboard-container">
    <div class="page-header">
      <h2>仪表盘</h2>
      <span class="page-subtitle">系统运行总览</span>
      <el-button class="refresh-btn" :icon="Refresh" circle size="small" :loading="loading" @click="loadData" />
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

    <el-row :gutter="16">
      <!-- 最近任务 -->
      <el-col :span="16">
        <el-card shadow="never" class="cp-animate-in panel-card">
          <template #header>
            <div class="panel-header">
              <h3>最近任务</h3>
              <el-link type="primary" :underline="'never'" @click="router.push('/tasks')">
                查看全部<el-icon><ArrowRight /></el-icon>
              </el-link>
            </div>
          </template>
          <el-table :data="recentTasks" v-loading="tasksLoading" size="default"
                    @row-click="(row) => router.push(`/tasks/${row.id}`)" class="recent-table">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="spider_name" label="爬虫" min-width="140" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="开始时间" width="170">
              <template #default="{ row }">{{ formatTime(row.started_at || row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="耗时" width="90" align="right">
              <template #default="{ row }">{{ formatDuration(row) }}</template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无任务记录" :image-size="80" />
            </template>
          </el-table>
        </el-card>
      </el-col>

      <!-- 系统状态 -->
      <el-col :span="8">
        <el-card shadow="never" class="cp-animate-in panel-card">
          <template #header>
            <h3>系统状态</h3>
          </template>

          <div class="rate-block">
            <el-progress type="circle" :percentage="stats.successRate" :width="110"
                         :color="rateColor" :stroke-width="8">
              <template #default="{ percentage }">
                <div class="rate-value">{{ percentage }}%</div>
                <div class="rate-label">任务成功率</div>
              </template>
            </el-progress>
          </div>

          <el-divider />

          <div class="status-list">
            <div class="status-item">
              <span class="status-label">节点状态</span>
              <span class="status-value">
                <span class="dot dot-online"></span>在线 {{ stats.onlineNodes }}
                <span class="status-divider">/</span>共 {{ stats.totalNodes }}
              </span>
            </div>
            <div class="status-item">
              <span class="status-label">容器</span>
              <span class="status-value">
                运行 {{ stats.runningContainers }}<span class="status-divider">/</span>共 {{ stats.totalContainers }}
              </span>
            </div>
            <div class="status-item">
              <span class="status-label">任务分布</span>
              <span class="status-value">
                成功 {{ taskDist.success }} · 失败 {{ taskDist.failed }} · 运行中 {{ taskDist.running }}
              </span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Files, Aim, VideoPlay, Document, Refresh, ArrowRight } from '@element-plus/icons-vue'
import { getDashboardData } from '@/api/monitoring'
import { getSpiders } from '@/api/spider'
import { getNodes } from '@/api/node'
import { getTaskStats, getRecentTasks } from '@/api/execution'
import StatCard from '@/components/StatCard.vue'
import { getTaskStatusType as getStatusType, getTaskStatusText as getStatusText, formatDateTime as formatTime } from '@/utils/common'

const router = useRouter()
const loading = ref(false)
const tasksLoading = ref(false)

const stats = ref({
  projects: 0,
  spiders: 0,
  runningTasks: 0,
  todayTasks: 0,
  successRate: 0,
  onlineNodes: 0,
  totalNodes: 0,
  totalContainers: 0,
  runningContainers: 0
})
const taskDist = ref({ success: 0, failed: 0, running: 0 })
const recentTasks = ref([])

const rateColor = computed(() => {
  const r = stats.value.successRate
  if (r >= 80) return 'var(--cp-success)'
  if (r >= 50) return 'var(--cp-warning)'
  return 'var(--cp-danger)'
})

const formatDuration = (row) => {
  if (!row.started_at || !row.finished_at) return '-'
  const secs = (new Date(row.finished_at) - new Date(row.started_at)) / 1000
  if (secs < 1) return '<1s'
  if (secs < 60) return `${Math.round(secs)}s`
  return `${Math.floor(secs / 60)}m${Math.round(secs % 60)}s`
}

const loadData = async () => {
  loading.value = true
  tasksLoading.value = true
  try {
    const [dashboard, spidersData, nodesData, statsData, recentData] = await Promise.allSettled([
      getDashboardData().catch(() => ({})),
      getSpiders({ limit: 1 }).catch(() => ({ total: 0 })),
      getNodes().catch(() => []),
      getTaskStats().catch(() => ({})),
      getRecentTasks(8).catch(() => [])
    ])

    if (dashboard.status === 'fulfilled' && dashboard.value) {
      const d = dashboard.value
      stats.value.projects = d.projects?.total || 0
      stats.value.runningTasks = d.tasks?.running || 0
      stats.value.todayTasks = d.tasks?.today || 0
      stats.value.successRate = d.tasks?.success_rate || 0
      stats.value.totalNodes = d.nodes?.total || 0
      stats.value.onlineNodes = d.nodes?.online || 0
      stats.value.totalContainers = d.containers?.total || 0
      stats.value.runningContainers = d.containers?.running || 0
    }

    if (spidersData.status === 'fulfilled') {
      stats.value.spiders = spidersData.value.total || 0
    }

    // /monitoring/dashboard 异常时用 /nodes 兜底
    if (nodesData.status === 'fulfilled' && !stats.value.totalNodes) {
      const nodes = Array.isArray(nodesData.value) ? nodesData.value : (nodesData.value?.items || [])
      stats.value.totalNodes = nodes.length
      stats.value.onlineNodes = nodes.filter(n => n.status === 'online').length
    }

    if (statsData.status === 'fulfilled' && statsData.value) {
      const s = statsData.value
      taskDist.value = {
        success: s.success || 0,
        failed: s.failed || 0,
        running: s.running || 0
      }
    }

    if (recentData.status === 'fulfilled') {
      const r = recentData.value
      recentTasks.value = Array.isArray(r) ? r : (r?.items || [])
    }
  } finally {
    loading.value = false
    tasksLoading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.dashboard-container {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
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

.refresh-btn {
  margin-left: auto;
}

.stats-row {
  margin-bottom: var(--cp-space-md);
}

.panel-card {
  min-height: 100%;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header h3,
.panel-card h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--cp-text-primary);
}

.recent-table :deep(.el-table__row) {
  cursor: pointer;
}

.rate-block {
  display: flex;
  justify-content: center;
  padding: var(--cp-space-sm) 0;
}

.rate-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--cp-text-primary);
  font-variant-numeric: tabular-nums;
}

.rate-label {
  font-size: 12px;
  color: var(--cp-text-secondary);
  margin-top: 2px;
}

.status-list {
  display: flex;
  flex-direction: column;
  gap: var(--cp-space-sm);
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.status-label {
  color: var(--cp-text-secondary);
}

.status-value {
  color: var(--cp-text-regular);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-divider {
  color: var(--cp-text-secondary);
  margin: 0 2px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot-online {
  background: var(--cp-success);
  box-shadow: 0 0 6px var(--cp-success);
}
</style>
