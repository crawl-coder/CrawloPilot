<template>
  <div class="api-management-container">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #409EFF">
              <el-icon :size="30"><Connection /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_calls || 0 }}</div>
              <div class="stat-label">总调用次数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #67C23A">
              <el-icon :size="30"><SuccessFilled /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.success_rate || 0 }}%</div>
              <div class="stat-label">成功率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #E6A23C">
              <el-icon :size="30"><Timer /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.average_response_time || 0 }}</div>
              <div class="stat-label">平均响应(ms)</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #F56C6C">
              <el-icon :size="30"><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.circuit_breaker_trips || 0 }}</div>
              <div class="stat-label">熔断次数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作栏 -->
    <el-card class="action-card">
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><Plus /></el-icon>
        添加 API 配置
      </el-button>
    </el-card>

    <!-- API 配置列表 -->
    <el-card>
      <el-table :data="apiList" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="API 名称" width="150" />
        <el-table-column prop="base_url" label="基础 URL" min-width="250" show-overflow-tooltip />
        <el-table-column prop="auth_type" label="认证方式" width="120" />
        <el-table-column prop="rate_limit" label="限流(次/分)" width="120" />
        <el-table-column prop="circuit_breaker_threshold" label="熔断阈值" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'danger'">
              {{ row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 调用趋势图 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>调用趋势</span>
        </div>
      </template>
      <div ref="trendChartRef" style="height: 350px"></div>
    </el-card>

    <!-- 添加 API 配置对话框 -->
    <el-dialog v-model="showAddDialog" title="添加 API 配置" width="600px">
      <el-form :model="apiForm" label-width="150px">
        <el-form-item label="API 名称" required>
          <el-input v-model="apiForm.name" placeholder="例如：Twitter API" />
        </el-form-item>
        <el-form-item label="基础 URL" required>
          <el-input v-model="apiForm.base_url" placeholder="例如：https://api.twitter.com/2" />
        </el-form-item>
        <el-form-item label="项目 ID" required>
          <el-input-number v-model="apiForm.project_id" :min="1" />
        </el-form-item>
        <el-form-item label="认证方式">
          <el-select v-model="apiForm.auth_type">
            <el-option label="无" value="none" />
            <el-option label="API Key" value="api_key" />
            <el-option label="OAuth2" value="oauth2" />
          </el-select>
        </el-form-item>
        <el-form-item label="API Key" v-if="apiForm.auth_type === 'api_key'">
          <el-input v-model="apiForm.api_key" type="password" show-password />
        </el-form-item>
        <el-form-item label="限流(次/分钟)">
          <el-input-number v-model="apiForm.rate_limit" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="熔断阈值">
          <el-input-number v-model="apiForm.circuit_breaker_threshold" :min="1" :max="100" />
          <div class="form-tip">连续失败次数达到此值时触发熔断</div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="apiForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddApi">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getApiConfigs, createApiConfig, getApiStats, getApiTrend } from '@/api/proxyApi'
import { ElMessage } from 'element-plus'
import { Connection, SuccessFilled, Timer, CircleClose, Plus } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const loading = ref(false)
const apiList = ref([])
const stats = ref({})
const showAddDialog = ref(false)
const trendChartRef = ref(null)
let trendChart = null

const apiForm = ref({
  name: '',
  base_url: '',
  project_id: 1,
  auth_type: 'none',
  api_key: '',
  rate_limit: 60,
  circuit_breaker_threshold: 10,
  enabled: true
})

const loadData = async () => {
  loading.value = true
  try {
    const [listData, statsData, trendData] = await Promise.all([
      getApiConfigs({}),
      getApiStats({ days: 30 }),
      getApiTrend({ days: 30 })
    ])
    
    apiList.value = listData
    stats.value = statsData
    
    // 更新趋势图
    updateTrendChart(trendData)
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleAddApi = async () => {
  try {
    await createApiConfig(apiForm.value)
    ElMessage.success('添加成功')
    showAddDialog.value = false
    loadData()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const updateTrendChart = (data) => {
  if (!data || data.length === 0) return
  if (!trendChart) return

  const dates = data.map(item => item.date)
  const calls = data.map(item => item.total_calls)
  const successRates = data.map(item => {
    return item.total_calls > 0 ? (item.success_calls / item.total_calls * 100).toFixed(2) : 0
  })

  trendChart.setOption({
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['调用次数', '成功率']
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: [
      {
        type: 'value',
        name: '调用次数'
      },
      {
        type: 'value',
        name: '成功率(%)',
        min: 0,
        max: 100
      }
    ],
    series: [
      {
        name: '调用次数',
        type: 'line',
        data: calls,
        smooth: true,
        areaStyle: {
          opacity: 0.3
        },
        itemStyle: {
          color: '#409EFF'
        }
      },
      {
        name: '成功率',
        type: 'line',
        yAxisIndex: 1,
        data: successRates,
        smooth: true,
        itemStyle: {
          color: '#67C23A'
        }
      }
    ]
  })
}

const initChart = () => {
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
  }
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  initChart()
  loadData()
})
</script>

<style scoped>
.api-management-container {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.action-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}
</style>
