<template>
  <div class="data-quality-container">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #409EFF">
              <el-icon :size="30"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_checks || 0 }}</div>
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
              <div class="stat-value">{{ stats.passed || 0 }}</div>
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
              <div class="stat-value">{{ stats.warning || 0 }}</div>
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
              <div class="stat-value">{{ stats.failed || 0 }}</div>
              <div class="stat-label">失败次数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="queryForm">
        <el-form-item label="项目">
          <el-select v-model="queryForm.project_id" placeholder="选择项目" clearable>
            <el-option label="全部项目" value="" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="选择状态" clearable>
            <el-option label="全部" value="" />
            <el-option label="通过" value="passed" />
            <el-option label="警告" value="warning" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-select v-model="queryForm.days" placeholder="选择时间">
            <el-option label="近7天" :value="7" />
            <el-option label="近30天" :value="30" />
            <el-option label="近90天" :value="90" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数据质量列表 -->
    <el-card>
      <el-table :data="qualityList" v-loading="loading" stripe>
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
            <el-tag :type="getStatusType(row.overall_status)">
              {{ getStatusText(row.overall_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="checked_at" label="检测时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.checked_at) }}
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.limit"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadData"
        @size-change="loadData"
        class="pagination"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getQualityChecks, getQualityStats } from '@/api/dataQuality'
import { ElMessage } from 'element-plus'
import { Document, SuccessFilled, Warning, CircleCloseFilled } from '@element-plus/icons-vue'

const loading = ref(false)
const qualityList = ref([])
const stats = ref({})

const queryForm = ref({
  project_id: '',
  status: '',
  days: 30
})

const pagination = ref({
  page: 1,
  limit: 20,
  total: 0
})

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      ...queryForm.value,
      skip: (pagination.value.page - 1) * pagination.value.limit,
      limit: pagination.value.limit
    }
    
    const [listData, statsData] = await Promise.all([
      getQualityChecks(params),
      getQualityStats({ days: queryForm.value.days })
    ])
    
    qualityList.value = listData
    stats.value = statsData
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const resetQuery = () => {
  queryForm.value = {
    project_id: '',
    status: '',
    days: 30
  }
  pagination.value.page = 1
  loadData()
}

const getScoreColor = (score) => {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  return '#F56C6C'
}

const getStatusType = (status) => {
  const types = {
    passed: 'success',
    warning: 'warning',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = {
    passed: '通过',
    warning: '警告',
    failed: '失败'
  }
  return texts[status] || status
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.data-quality-container {
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

.filter-card {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
