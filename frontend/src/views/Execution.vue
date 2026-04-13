<template>
  <div class="execution-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务执行管理</span>
          <el-button type="primary" @click="handleCreateTask">
            <el-icon><VideoPlay /></el-icon>
            新建任务
          </el-button>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="爬虫">
          <el-select v-model="queryForm.spider_id" placeholder="选择爬虫" clearable>
            <el-option
              v-for="spider in spiders"
              :key="spider.id"
              :label="spider.name"
              :value="spider.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="任务状态" clearable>
            <el-option label="待执行" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTasks">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 任务列表 -->
      <el-table :data="taskList" v-loading="loading" stripe>
        <el-table-column prop="id" label="任务ID" width="280">
          <template #default="{ row }">
            <el-text type="primary" class="clickable" @click="handleViewDetail(row)">
              {{ row.id }}
            </el-text>
          </template>
        </el-table-column>
        <el-table-column prop="spider_name" label="爬虫名称" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="container_id" label="容器ID" width="150">
          <template #default="{ row }">
            {{ row.container_id ? row.container_id.substring(0, 12) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="执行时长" width="120">
          <template #default="{ row }">
            {{ row.duration ? `${row.duration.toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'running' || row.status === 'pending'"
              type="danger"
              size="small"
              @click="handleStopTask(row)"
            >
              停止
            </el-button>
            <el-button
              type="primary"
              size="small"
              @click="handleViewLogs(row)"
            >
              日志
            </el-button>
            <el-button
              type="danger"
              size="small"
              @click="handleDeleteTask(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadTasks"
        @current-change="loadTasks"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- 日志查看对话框 -->
    <el-dialog
      v-model="logDialogVisible"
      :title="`任务日志 - ${currentTask?.spider_name}`"
      width="800px"
    >
      <div class="log-container">
        <pre class="log-content">{{ logContent || '暂无日志' }}</pre>
      </div>
      <template #footer>
        <el-button @click="logDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="refreshLogs">刷新</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import { listTasks, stopTask, deleteTask, getTaskLogs } from '@/api/execution'
import { listSpiders } from '@/api/spider'

const loading = ref(false)
const taskList = ref([])
const spiders = ref([])
const logDialogVisible = ref(false)
const currentTask = ref(null)
const logContent = ref('')

const queryForm = reactive({
  spider_id: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 加载任务列表
const loadTasks = async () => {
  loading.value = true
  try {
    const res = await listTasks({
      spider_id: queryForm.spider_id || undefined,
      status: queryForm.status || undefined,
      limit: pagination.pageSize,
      offset: (pagination.page - 1) * pagination.pageSize
    })
    taskList.value = res
    pagination.total = res.length
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

// 加载爬虫列表
const loadSpiders = async () => {
  try {
    const res = await listSpiders({ limit: 1000 })
    spiders.value = res
  } catch (error) {
    console.error('加载爬虫列表失败', error)
  }
}

// 新建任务
const handleCreateTask = () => {
  ElMessage.info('请从爬虫详情页创建任务')
}

// 停止任务
const handleStopTask = async (row) => {
  try {
    await ElMessageBox.confirm('确定要停止此任务吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await stopTask(row.id)
    ElMessage.success('任务停止请求已发送')
    await loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('停止任务失败')
    }
  }
}

// 删除任务
const handleDeleteTask = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除此任务吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await deleteTask(row.id)
    ElMessage.success('任务删除成功')
    await loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除任务失败')
    }
  }
}

// 查看日志
const handleViewLogs = async (row) => {
  currentTask.value = row
  logDialogVisible.value = true
  await refreshLogs()
}

// 刷新日志
const refreshLogs = async () => {
  if (!currentTask.value) return
  
  try {
    const res = await getTaskLogs(currentTask.value.id, 200)
    logContent.value = res.logs
  } catch (error) {
    logContent.value = '加载日志失败'
  }
}

// 查看详情
const handleViewDetail = (row) => {
  ElMessage.info(`查看任务详情: ${row.id}`)
}

// 重置
const handleReset = () => {
  queryForm.spider_id = ''
  queryForm.status = ''
  pagination.page = 1
  loadTasks()
}

// 格式化时间
const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

// 获取状态类型
const getStatusType = (status) => {
  const types = {
    pending: 'info',
    running: 'warning',
    success: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return types[status] || 'info'
}

// 获取状态文本
const getStatusText = (status) => {
  const texts = {
    pending: '待执行',
    running: '运行中',
    success: '成功',
    failed: '失败',
    cancelled: '已取消'
  }
  return texts[status] || status
}

onMounted(() => {
  loadTasks()
  loadSpiders()
})
</script>

<style scoped>
.execution-container {
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

.clickable {
  cursor: pointer;
}

.clickable:hover {
  text-decoration: underline;
}

.log-container {
  max-height: 500px;
  overflow-y: auto;
  background: #1e1e1e;
  padding: 15px;
  border-radius: 4px;
}

.log-content {
  color: #d4d4d4;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
