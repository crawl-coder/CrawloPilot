<template>
  <div class="tasks-container">
    <el-row :gutter="20" style="margin-bottom: 20px">
      <!-- 统计卡片 -->
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总任务数" :value="stats.total" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="运行中" :value="stats.running" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="成功率" :value="stats.success_rate" suffix="%" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="失败数" :value="stats.failed" />
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务实例</span>
          <el-button @click="loadData" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <!-- 筛选 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="调度 ID">
          <el-input-number v-model="filters.scheduleId" :min="1" placeholder="调度 ID" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="状态" clearable @change="loadData">
            <el-option label="全部" value="" />
            <el-option label="等待中" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="超时" value="timeout" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>

      <!-- 表格 -->
      <el-table :data="tasks" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="schedule_id" label="调度 ID" width="100" />
        <el-table-column prop="spider_name" label="爬虫名称" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'pending'" type="info">等待中</el-tag>
            <el-tag v-else-if="row.status === 'running'" type="primary">运行中</el-tag>
            <el-tag v-else-if="row.status === 'success'" type="success">成功</el-tag>
            <el-tag v-else-if="row.status === 'failed'" type="danger">失败</el-tag>
            <el-tag v-else-if="row.status === 'timeout'" type="warning">超时</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Worker" width="150">
          <template #default="{ row }">
            {{ row.worker_node || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="容器 ID" width="150">
          <template #default="{ row }">
            <el-text size="small" type="info">{{ row.container_id ? row.container_id.substring(0, 12) : '-' }}</el-text>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="180">
          <template #default="{ row }">
            {{ row.started_at || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="row.status === 'running'" 
              size="small" 
              type="warning"
              @click="handleStop(row)"
            >
              停止
            </el-button>
            <el-button 
              v-if="row.status === 'failed' || row.status === 'timeout'" 
              size="small" 
              type="primary"
              @click="handleRetry(row)"
            >
              重试
            </el-button>
            <el-button size="small" @click="handleViewLogs(row)">日志</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadData"
        @size-change="loadData"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- 日志对话框 -->
    <el-dialog v-model="logDialogVisible" title="任务日志" width="800px">
      <div class="log-container">
        <pre>{{ logs }}</pre>
      </div>
      <template #footer>
        <el-button @click="logDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { 
  getTaskInstances, 
  getTaskStats,
  retryTask,
  stopTask,
  getTaskLogs
} from '@/api/schedule'

const loading = ref(false)
const tasks = ref([])
const stats = reactive({
  total: 0,
  success: 0,
  failed: 0,
  running: 0,
  pending: 0,
  success_rate: 0
})
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

const filters = reactive({
  scheduleId: null,
  status: ''
})

const logDialogVisible = ref(false)
const logs = ref('')

const loadData = async ({ page: newPage, size } = {}) => {
  loading.value = true
  try {
    const currentPageNum = newPage || page.value
    const pageSizeNum = size || pageSize.value
    const offset = (currentPageNum - 1) * pageSizeNum
    
    const params = {
      limit: pageSizeNum,
      offset
    }
    
    if (filters.scheduleId) {
      params.schedule_id = filters.scheduleId
    }
    if (filters.status) {
      params.status = filters.status
    }
    
    const response = await getTaskInstances(params)
    tasks.value = response.items || []
    total.value = response.total || 0
    
    page.value = currentPageNum
    pageSize.value = pageSizeNum
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const data = await getTaskStats()
    Object.assign(stats, data)
  } catch (error) {
    console.error('加载统计失败', error)
  }
}

const handleRetry = async (row) => {
  try {
    await ElMessageBox.confirm('确定要重试该任务吗？', '提示', {
      type: 'warning'
    })
    await retryTask(row.id)
    ElMessage.success('重试请求已提交')
    setTimeout(() => loadData(), 1000)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重试失败')
    }
  }
}

const handleStop = async (row) => {
  try {
    await ElMessageBox.confirm('确定要停止该任务吗？', '提示', {
      type: 'warning'
    })
    await stopTask(row.id)
    ElMessage.success('任务已停止')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('停止失败')
    }
  }
}

const handleViewLogs = async (row) => {
  try {
    const data = await getTaskLogs(row.id)
    logs.value = data.logs || '暂无日志'
    logDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取日志失败')
  }
}

onMounted(() => {
  loadData()
  loadStats()
  
  // 每 30 秒刷新一次
  setInterval(() => {
    loadData()
    loadStats()
  }, 30000)
})
</script>

<style scoped>
.tasks-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-form {
  margin-bottom: 20px;
}

.log-container {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 20px;
  border-radius: 4px;
  max-height: 500px;
  overflow: auto;
}

.log-container pre {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
}
</style>
