<template>
  <div class="monitoring-container">
    <!-- 系统健康状态 -->
    <el-card class="health-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>系统健康状态</span>
          <el-button @click="loadAll" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="8" v-for="item in healthStatus" :key="item.name">
          <div class="health-item">
            <el-icon :size="40" :color="item.status === 'healthy' ? '#67C23A' : '#F56C6C'">
              <component :is="item.icon" />
            </el-icon>
            <div class="health-info">
              <div class="health-name">{{ item.name }}</div>
              <el-tag :type="item.status === 'healthy' ? 'success' : 'danger'">
                {{ item.status === 'healthy' ? '正常' : '异常' }}
              </el-tag>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6" v-for="card in statCards" :key="card.title">
        <el-card shadow="hover" class="stat-card">
          <el-statistic :title="card.title" :value="card.value">
            <template #suffix>{{ card.suffix }}</template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <!-- 节点监控 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>节点状态</span>
      </template>
      
      <el-table :data="nodes" v-loading="loading">
        <el-table-column prop="name" label="节点名称" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'online' ? 'success' : 'danger'">
              {{ row.status === 'online' ? '在线' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="CPU" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.cpu_usage" :color="getProgressColor(row.cpu_usage)" />
          </template>
        </el-table-column>
        <el-table-column label="内存" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.memory_usage" :color="getProgressColor(row.memory_usage)" />
          </template>
        </el-table-column>
        <el-table-column label="磁盘" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.disk_usage" :color="getProgressColor(row.disk_usage)" />
          </template>
        </el-table-column>
        <el-table-column prop="container_count" label="容器数" width="100" />
      </el-table>
    </el-card>

    <!-- 活跃告警 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>活跃告警</span>
          <el-badge :value="activeAlerts.length" :max="99">
            <el-button size="small">查看详情</el-button>
          </el-badge>
        </div>
      </template>
      
      <el-alert
        v-for="alert in activeAlerts"
        :key="alert.rule_id"
        :title="alert.rule_name"
        :type="getAlertType(alert.severity)"
        :closable="false"
        show-icon
        style="margin-bottom: 10px"
      >
        <template #default>
          <div>当前值: {{ alert.value }} | 阈值: {{ alert.threshold }} | 触发次数: {{ alert.trigger_count }}</div>
          <div style="font-size: 12px; color: #999; margin-top: 5px">
            {{ alert.triggered_at }}
          </div>
        </template>
      </el-alert>
      
      <el-empty v-if="activeAlerts.length === 0" description="暂无活跃告警" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Monitor, Connection, Service } from '@element-plus/icons-vue'
import { 
  getDashboardData, 
  getHealthStatus, 
  getNodeMetrics,
  getActiveAlerts
} from '@/api/monitoring'

const loading = ref(false)
const dashboardData = ref({})
const healthStatus = ref([])
const nodes = ref([])
const activeAlerts = ref([])

const statCards = ref([
  { title: '调度配置', value: 0, suffix: '个' },
  { title: '任务总数', value: 0, suffix: '次' },
  { title: '成功率', value: 0, suffix: '%' },
  { title: '运行容器', value: 0, suffix: '个' }
])

const loadAll = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadDashboard(),
      loadHealth(),
      loadNodes(),
      loadAlerts()
    ])
  } catch (error) {
    ElMessage.error('加载监控数据失败')
  } finally {
    loading.value = false
  }
}

const loadDashboard = async () => {
  try {
    dashboardData.value = await getDashboardData()
    
    // 更新统计卡片
    statCards.value = [
      { title: '调度配置', value: dashboardData.value.schedules?.total || 0, suffix: '个' },
      { title: '任务总数', value: dashboardData.value.tasks?.total || 0, suffix: '次' },
      { title: '成功率', value: dashboardData.value.tasks?.success_rate || 0, suffix: '%' },
      { title: '运行容器', value: dashboardData.value.containers?.running || 0, suffix: '个' }
    ]
  } catch (error) {
    console.error('加载 Dashboard 失败', error)
  }
}

const loadHealth = async () => {
  try {
    const health = await getHealthStatus()
    
    healthStatus.value = [
      {
        name: '数据库',
        status: health.components?.database?.status || 'unhealthy',
        icon: 'Monitor'
      },
      {
        name: 'Redis',
        status: health.components?.redis?.status || 'unhealthy',
        icon: 'Connection'
      },
      {
        name: 'Docker',
        status: health.components?.docker?.status || 'unhealthy',
        icon: 'Service'
      }
    ]
  } catch (error) {
    console.error('加载健康状态失败', error)
  }
}

const loadNodes = async () => {
  try {
    const data = await getNodeMetrics()
    nodes.value = data.nodes || []
  } catch (error) {
    console.error('加载节点数据失败', error)
  }
}

const loadAlerts = async () => {
  try {
    activeAlerts.value = await getActiveAlerts()
  } catch (error) {
    console.error('加载告警数据失败', error)
  }
}

const getProgressColor = (percentage) => {
  if (percentage < 60) return '#67C23A'
  if (percentage < 80) return '#E6A23C'
  return '#F56C6C'
}

const getAlertType = (severity) => {
  const map = {
    'warning': 'warning',
    'critical': 'error',
    'emergency': 'error'
  }
  return map[severity] || 'info'
}

let refreshTimer = null

onMounted(() => {
  loadAll()
  
  // 每 30 秒自动刷新
  refreshTimer = setInterval(() => {
    loadAll()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.monitoring-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.health-card {
  margin-bottom: 20px;
}

.health-item {
  display: flex;
  align-items: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.health-info {
  margin-left: 20px;
}

.health-name {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 10px;
}

.stat-card {
  text-align: center;
}
</style>
