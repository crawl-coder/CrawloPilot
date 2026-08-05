<template>
  <div class="data-management-container">
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- 数据质量 -->
      <el-tab-pane label="数据质量" name="quality">
        <div class="data-quality-section">
          <!-- 统计卡片 -->
          <el-row :gutter="20" class="stats-row">
            <el-col :span="6">
              <el-card shadow="hover">
                <div class="stat-card">
                  <div class="stat-icon" style="background: #409EFF">
                    <el-icon :size="30"><Document /></el-icon>
                  </div>
                  <div class="stat-info">
                    <div class="stat-value">{{ qualityStats.total_checks || 0 }}</div>
                    <div class="stat-label">总检测次数</div>
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
                    <div class="stat-value">{{ qualityStats.passed || 0 }}</div>
                    <div class="stat-label">通过次数</div>
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover">
                <div class="stat-card">
                  <div class="stat-icon" style="background: #E6A23C">
                    <el-icon :size="30"><Warning /></el-icon>
                  </div>
                  <div class="stat-info">
                    <div class="stat-value">{{ qualityStats.warning || 0 }}</div>
                    <div class="stat-label">警告次数</div>
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card shadow="hover">
                <div class="stat-card">
                  <div class="stat-icon" style="background: #F56C6C">
                    <el-icon :size="30"><CircleCloseFilled /></el-icon>
                  </div>
                  <div class="stat-info">
                    <div class="stat-value">{{ qualityStats.failed || 0 }}</div>
                    <div class="stat-label">失败次数</div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 筛选条件 -->
          <el-card class="filter-card">
            <el-form :inline="true" :model="qualityQuery">
              <el-form-item label="项目">
                <el-select v-model="qualityQuery.project_id" placeholder="选择项目" clearable>
                  <el-option label="全部项目" value="" />
                </el-select>
              </el-form-item>
              <el-form-item label="状态">
                <el-select v-model="qualityQuery.status" placeholder="选择状态" clearable>
                  <el-option label="全部" value="" />
                  <el-option label="通过" value="passed" />
                  <el-option label="警告" value="warning" />
                  <el-option label="失败" value="failed" />
                </el-select>
              </el-form-item>
              <el-form-item label="时间范围">
                <el-select v-model="qualityQuery.days">
                  <el-option label="近7天" :value="7" />
                  <el-option label="近30天" :value="30" />
                  <el-option label="近90天" :value="90" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadQualityData">查询</el-button>
                <el-button @click="resetQualityQuery">重置</el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <!-- 数据质量列表 -->
          <el-card>
            <el-table :data="qualityList" v-loading="qualityLoading" stripe>
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="spider_name" label="爬虫名称" width="150" />
              <el-table-column prop="total_records" label="数据量" width="120" />
              <el-table-column label="空值率" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.null_rate_passed ? 'success' : 'danger'">
                    {{ row.null_rate_passed ? '通过' : '未通过' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="重复率" width="120">
                <template #default="{ row }">
                  <span>{{ row.duplicate_rate }}%</span>
                </template>
              </el-table-column>
              <el-table-column label="格式校验" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.format_passed ? 'success' : 'danger'">
                    {{ row.format_passed ? '通过' : '未通过' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="时效性" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.freshness_passed ? 'success' : 'danger'">
                    {{ row.freshness_passed ? '通过' : '未通过' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="质量评分" width="120">
                <template #default="{ row }">
                  <el-progress
                    :percentage="row.score"
                    :color="getScoreColor(row.score)"
                    :stroke-width="8"
                  />
                </template>
              </el-table-column>
              <el-table-column label="总体状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="getQualityStatusType(row.overall_status)">
                    {{ getQualityStatusText(row.overall_status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="checked_at" label="检测时间" width="180">
                <template #default="{ row }">
                  {{ formatDateTime(row.checked_at) }}
                </template>
              </el-table-column>
            </el-table>

            <el-pagination
              v-model:current-page="qualityPagination.page"
              v-model:page-size="qualityPagination.limit"
              :total="qualityPagination.total"
              :page-sizes="[20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              @current-change="loadQualityData"
              @size-change="loadQualityData"
              class="pagination"
            />
          </el-card>
        </div>
      </el-tab-pane>

      <!-- 统计报表 -->
      <el-tab-pane label="统计报表" name="statistics">
        <div class="data-statistics-section">
          <!-- 汇总统计卡片 -->
          <el-row :gutter="20" class="stats-row">
            <el-col :span="8">
              <el-card shadow="hover">
                <div class="summary-card">
                  <div class="summary-label">总数据量</div>
                  <div class="summary-value">{{ statSummary.total_records || 0 }}</div>
                  <div class="summary-unit">条</div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover">
                <div class="summary-card">
                  <div class="summary-label">平均成功率</div>
                  <div class="summary-value">{{ statSummary.average_success_rate || 0 }}%</div>
                  <el-progress
                    :percentage="statSummary.average_success_rate || 0"
                    :color="getSuccessColor(statSummary.average_success_rate)"
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
                  <div class="summary-value">{{ statSummary.period_days || 30 }}</div>
                  <div class="summary-unit">天</div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 筛选条件 -->
          <el-card class="filter-card">
            <el-form :inline="true" :model="statQuery">
              <el-form-item label="项目">
                <el-select v-model="statQuery.project_id" placeholder="选择项目">
                  <el-option label="全部项目" :value="null" />
                </el-select>
              </el-form-item>
              <el-form-item label="统计维度">
                <el-select v-model="statQuery.stat_type">
                  <el-option label="按天" value="daily" />
                  <el-option label="按周" value="weekly" />
                  <el-option label="按月" value="monthly" />
                </el-select>
              </el-form-item>
              <el-form-item label="时间范围">
                <el-select v-model="statQuery.days">
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
            <el-table :data="statisticsList" v-loading="statLoading" stripe>
              <el-table-column prop="stat_date" label="统计日期" width="180">
                <template #default="{ row }">
                  {{ formatDateOnly(row.stat_date) }}
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
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, SuccessFilled, Warning, CircleCloseFilled } from '@element-plus/icons-vue'
import { getQualityChecks, getQualityStats, getSummaryStatistics, getProjectStatistics } from '@/api/dataQuality'
import { formatDateTime } from '@/utils/common'
import * as echarts from 'echarts'

const activeTab = ref('quality')

// ==================== 数据质量 ====================

const qualityLoading = ref(false)
const qualityList = ref([])
const qualityStats = ref({})

const qualityQuery = ref({
  project_id: '',
  status: '',
  days: 30
})

const qualityPagination = ref({
  page: 1,
  limit: 20,
  total: 0
})

const loadQualityData = async () => {
  qualityLoading.value = true
  try {
    const params = {
      ...qualityQuery.value,
      skip: (qualityPagination.value.page - 1) * qualityPagination.value.limit,
      limit: qualityPagination.value.limit
    }

    const [listData, statsData] = await Promise.all([
      getQualityChecks(params),
      getQualityStats({ days: qualityQuery.value.days })
    ])

    qualityList.value = listData
    qualityStats.value = statsData
  } catch (error) {
    ElMessage.error('加载数据质量失败')
  } finally {
    qualityLoading.value = false
  }
}

const resetQualityQuery = () => {
  qualityQuery.value = { project_id: '', status: '', days: 30 }
  qualityPagination.value.page = 1
  loadQualityData()
}

const getScoreColor = (score) => {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  return '#F56C6C'
}

const getQualityStatusType = (status) => {
  const types = { passed: 'success', warning: 'warning', failed: 'danger' }
  return types[status] || 'info'
}

const getQualityStatusText = (status) => {
  const texts = { passed: '通过', warning: '警告', failed: '失败' }
  return texts[status] || status
}

// ==================== 统计报表 ====================

const statLoading = ref(false)
const statSummary = ref({})
const statisticsList = ref([])
const recordsChartRef = ref(null)
const successChartRef = ref(null)

let recordsChart = null
let successChart = null

const statQuery = ref({
  project_id: null,
  stat_type: 'daily',
  days: 30
})

const loadStatistics = async () => {
  statLoading.value = true
  try {
    const summaryData = await getSummaryStatistics({
      project_id: statQuery.value.project_id,
      days: statQuery.value.days
    })
    statSummary.value = summaryData

    if (statQuery.value.project_id) {
      const statsData = await getProjectStatistics({
        project_id: statQuery.value.project_id,
        stat_type: statQuery.value.stat_type,
        days: statQuery.value.days
      })
      statisticsList.value = statsData
      updateCharts(statsData)
    }
  } catch (error) {
    ElMessage.error('加载统计数据失败')
  } finally {
    statLoading.value = false
  }
}

const updateCharts = (data) => {
  if (!data || data.length === 0) return

  const dates = data.map(item => formatDateOnly(item.stat_date))
  const records = data.map(item => item.total_records)
  const successRates = data.map(item => item.success_rate || 0)

  if (recordsChart && recordsChartRef.value) {
    recordsChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: dates },
      yAxis: { type: 'value', name: '数据量' },
      series: [{
        data: records,
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#409EFF' }
      }]
    })
  }

  if (successChart && successChartRef.value) {
    successChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: dates },
      yAxis: { type: 'value', name: '成功率(%)', min: 0, max: 100 },
      series: [{
        data: successRates,
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#67C23A' }
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

const onTabChange = (tab) => {
  if (tab === 'statistics') {
    nextTick(() => {
      initCharts()
      loadStatistics()
    })
  }
}

const getSuccessColor = (rate) => {
  if (rate >= 95) return '#67C23A'
  if (rate >= 80) return '#E6A23C'
  return '#F56C6C'
}

const formatDateOnly = (date) => {
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
  loadQualityData()
})
</script>

<style scoped>
.data-management-container {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.filter-card {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 数据质量卡片 */
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

/* 统计报表 */
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}
</style>
