<template>
  <div class="audit-logs-container">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #409EFF">
              <el-icon :size="30"><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total || 0 }}</div>
              <div class="stat-label">总操作次数</div>
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
              <div class="stat-value">{{ actionStats.CREATE || 0 }}</div>
              <div class="stat-label">创建操作</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #E6A23C">
              <el-icon :size="30"><Edit /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ actionStats.UPDATE || 0 }}</div>
              <div class="stat-label">更新操作</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #F56C6C">
              <el-icon :size="30"><Delete /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ actionStats.DELETE || 0 }}</div>
              <div class="stat-label">删除操作</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="queryForm">
        <el-form-item label="操作类型">
          <el-select v-model="queryForm.action" placeholder="选择操作" clearable>
            <el-option label="全部" :value="null" />
            <el-option label="创建" value="CREATE" />
            <el-option label="更新" value="UPDATE" />
            <el-option label="删除" value="DELETE" />
          </el-select>
        </el-form-item>
        <el-form-item label="资源类型">
          <el-select v-model="queryForm.resource_type" placeholder="选择资源" clearable>
            <el-option label="全部" :value="null" />
            <el-option label="项目" value="project" />
            <el-option label="调度" value="schedule" />
            <el-option label="代理" value="proxy" />
            <el-option label="API配置" value="api_config" />
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

    <!-- 审计日志列表 -->
    <el-card>
      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column label="操作类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)">
              {{ getActionText(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源类型" width="120" />
        <el-table-column prop="resource_id" label="资源ID" width="100" />
        <el-table-column prop="ip_address" label="IP地址" width="150" />
        <el-table-column prop="created_at" label="操作时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作详情" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-if="row.new_value || row.old_value">
              <span v-if="row.old_value" class="old-value">旧值: {{ JSON.stringify(row.old_value) }}</span>
              <span v-if="row.new_value" class="new-value">新值: {{ JSON.stringify(row.new_value) }}</span>
            </div>
            <span v-else class="no-change">-</span>
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
import { ref, computed, onMounted } from 'vue'
import { getAuditLogs, getAuditStats } from '@/api/audit'
import { ElMessage } from 'element-plus'
import { Document, SuccessFilled, Edit, Delete } from '@element-plus/icons-vue'

const loading = ref(false)
const logs = ref([])
const stats = ref({})

const queryForm = ref({
  action: null,
  resource_type: null,
  days: 30
})

const pagination = ref({
  page: 1,
  limit: 20,
  total: 0
})

const actionStats = computed(() => {
  const result = {}
  const actionList = stats.value.action_stats || []
  actionList.forEach(item => {
    result[item.action] = item.count
  })
  return result
})

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      ...queryForm.value,
      skip: (pagination.value.page - 1) * pagination.value.limit,
      limit: pagination.value.limit
    }
    
    const [logsData, statsData] = await Promise.all([
      getAuditLogs(params),
      getAuditStats({ days: queryForm.value.days })
    ])
    
    logs.value = logsData
    stats.value = statsData
    pagination.value.total = logsData.length
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const resetQuery = () => {
  queryForm.value = {
    action: null,
    resource_type: null,
    days: 30
  }
  pagination.value.page = 1
  loadData()
}

const getActionType = (action) => {
  const types = {
    CREATE: 'success',
    UPDATE: 'warning',
    DELETE: 'danger'
  }
  return types[action] || 'info'
}

const getActionText = (action) => {
  const texts = {
    CREATE: '创建',
    UPDATE: '更新',
    DELETE: '删除',
    LOGIN: '登录'
  }
  return texts[action] || action
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
.audit-logs-container {
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

.old-value {
  color: #909399;
  font-size: 12px;
  display: block;
  margin-bottom: 2px;
}

.new-value {
  color: #409EFF;
  font-size: 12px;
}

.no-change {
  color: #C0C4CC;
}
</style>
