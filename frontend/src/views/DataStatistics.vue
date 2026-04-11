<template>
  <div class="data-statistics-container">
    <!-- 汇总统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="summary-card">
            <div class="summary-label">总数据量</div>
            <div class="summary-value">{{ summary.total_records || 0 }}</div>
            <div class="summary-unit">条</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="summary-card">
            <div class="summary-label">平均成功率</div>
            <div class="summary-value">{{ summary.average_success_rate || 0 }}%</div>
            <el-progress 
              :percentage="summary.average_success_rate || 0" 
              :color="getSuccessColor(summary.average_success_rate)"
              :stroke-width="10"
              style="margin-top: 10px"
            />
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div class="summary-card">
            <div class="summary-label">统计周期</div>
            <div class="summary-value">{{ summary.period_days || 30 }}</div>
            <div class="summary-unit">天</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="queryForm">
        <el-form-item label="项目">
          <el-select v-model="queryForm.project_id" placeholder="选择项目">
            <el-option label="全部项目" :value="null" />
          </el-select>
        </el-form-item>
        <el-form-item label="统计维度">
          <el-select v-model="queryForm.stat_type">
            <el-option label="按天" value="daily" />
            <el-option label="按周" value="weekly" />
            <el-option label="按月" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-select v-model="queryForm.days">
            <el-option label="近7天" :value="7" />
            <el-option label="近30天" :value="30" />
            <el-option label="近90天" :value="90" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadStatistics">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数据趋势图表 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>数据量趋势</span>
            </div>
          </template>
          <div ref="recordsChartRef" style="height: 350px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>成功率趋势</span>
            </div>
          </template>
          <div ref="successChartRef" style="height: 350px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 详细数据表格 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>详细统计数据</span>
        </div>
      </template>
      <el-table :data="statisticsList" v-loading="loading" stripe>
        <el-table-column prop="stat_date" label="统计日期" width="180">
          <template #default="{ row }">
            {{ formatDate(row.stat_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="spider_name" label="爬虫名称" width="150" />
        <el-table-column prop="total_records" label="总数据量" width="120" />
        <el-table-column prop="increment_records" label="增量数据" width="120" />
        <el-table-column label="数据大小" width="120">
          <template #default="{ row }">
            {{ formatSize(row.data_size_bytes) }}
          </template>
        </el-table-column>
        <el-table-column prop="avg_response_time" label="平均响应时间" width="140">
          <template #default="{ row }">
            {{ row.avg_response_time ? row.avg_response_time + 'ms' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="success_rate" label="成功率" width="100">
          <template #default="{ row }">
            {{ row.success_rate ? row.success_rate + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="data_source" label="数据源" width="150" />
        <el-table-column prop="category" label="数据分类" width="120" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getSummaryStatistics, getProjectStatistics } from '@/api/dataQuality'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const loading = ref(false)
const summary = ref({})
const statisticsList = ref([])
const recordsChartRef = ref(null)
const successChartRef = ref(null)

let recordsChart = null
let successChart = null

const queryForm = ref({
  project_id: null,
  stat_type: 'daily',
  days: 30
})

const loadStatistics = async () => {
  loading.value = true
  try {
    // 加载汇总统计
    const summaryData = await getSummaryStatistics({
      project_id: queryForm.value.project_id,
      days: queryForm.value.days
    })
    summary.value = summaryData

    // 加载详细统计
    if (queryForm.value.project_id) {
      const statsData = await getProjectStatistics({
        project_id: queryForm.value.project_id,
        stat_type: queryForm.value.stat_type,
        days: queryForm.value.days
      })
      statisticsList.value = statsData
      
      // 更新图表
      updateCharts(statsData)
    }
  } catch (error) {
    ElMessage.error('加载统计数据失败')
  } finally {
    loading.value = false
  }
}

const updateCharts = (data) => {
  if (!data || data.length === 0) return

  const dates = data.map(item => formatDate(item.stat_date))
  const records = data.map(item => item.total_records)
  const successRates = data.map(item => item.success_rate || 0)

  // 数据量趋势图
  if (recordsChart) {
    recordsChart.setOption({
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: dates
      },
      yAxis: {
        type: 'value',
        name: '数据量'
      },
      series: [{
        data: records,
        type: 'line',
        smooth: true,
        areaStyle: {
          opacity: 0.3
        },
        itemStyle: {
          color: '#409EFF'
        }
      }]
    })
  }

  // 成功率趋势图
  if (successChart) {
    successChart.setOption({
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: dates
      },
      yAxis: {
        type: 'value',
        name: '成功率(%)',
        min: 0,
        max: 100
      },
      series: [{
        data: successRates,
        type: 'line',
        smooth: true,
        areaStyle: {
          opacity: 0.3
        },
        itemStyle: {
          color: '#67C23A'
        }
      }]
    })
  }
}

const initCharts = () => {
  if (recordsChartRef.value) {
    recordsChart = echarts.init(recordsChartRef.value)
  }
  if (successChartRef.value) {
    successChart = echarts.init(successChartRef.value)
  }
}

const getSuccessColor = (rate) => {
  if (rate >= 95) return '#67C23A'
  if (rate >= 80) return '#E6A23C'
  return '#F56C6C'
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('zh-CN')
}

const formatSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(2) + ' MB'
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + ' GB'
}

onMounted(() => {
  initCharts()
  loadStatistics()
})
</script>

<style scoped>
.data-statistics-container {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.summary-card {
  text-align: center;
  padding: 20px 0;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 36px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
  margin-bottom: 5px;
}

.summary-unit {
  font-size: 14px;
  color: #606266;
}

.filter-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}
</style>
