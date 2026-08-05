<template>
  <div class="tasks-container">
    <!-- 统计卡片 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="总任务数" :value="stats.total" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="运行中" :value="stats.running" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="成功率" :value="stats.success_rate" suffix="%" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="失败数" :value="stats.failed" />
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务管理</span>
          <div class="header-actions">
            <el-button @click="refreshAll" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button type="primary" @click="handleCreateTask">
              <el-icon><VideoPlay /></el-icon>
              新建任务
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="爬虫">
          <el-select v-model="filters.spider_id" placeholder="选择爬虫" clearable style="width: 200px" @change="loadTasks">
            <el-option
              v-for="spider in spiders"
              :key="spider.id"
              :label="spider.name"
              :value="spider.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 140px" @change="loadTasks">
            <el-option label="待执行" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="已暂停" value="paused" />
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="超时" value="timeout" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTasks">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 表格 -->
      <el-table :data="taskList" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="任务ID" width="100">
          <template #default="{ row }">
            <el-text type="primary" class="clickable" @click="handleViewDetail(row)">
              {{ row.id }}
            </el-text>
          </template>
        </el-table-column>
        <el-table-column prop="spider_name" label="爬虫名称" width="150" />
        <el-table-column label="项目名称" width="180">
          <template #default="{ row }">
            {{ row.project_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="调度ID" width="100">
          <template #default="{ row }">
            {{ row.schedule_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="节点" width="160">
          <template #default="{ row }">
            <template v-if="row.worker_node">
              {{ row.worker_node }}
            </template>
            <template v-else-if="row.node_name">
              <el-tag size="small" type="info">{{ row.node_name }}</el-tag>
              <el-tag v-if="row.deploy_mode === 'ssh'" size="small" type="warning" style="margin-left: 4px">SSH</el-tag>
              <el-tag v-else-if="row.deploy_mode" size="small" type="success" style="margin-left: 4px">{{ row.deploy_mode }}</el-tag>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="容器ID" width="140">
          <template #default="{ row }">
            <el-text size="small" type="info">
              {{ row.container_id ? row.container_id.substring(0, 12) : '-' }}
            </el-text>
          </template>
        </el-table-column>
        <el-table-column label="执行时长" width="110">
          <template #default="{ row }">
            {{ row.duration ? `${row.duration.toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">
            {{ row.started_at ? formatTime(row.started_at) : formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="结束时间" width="170">
          <template #default="{ row }">
            {{ row.finished_at ? formatTime(row.finished_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="256" fixed="right">
          <template #default="{ row }">
            <div style="display: flex; gap: 4px; white-space: nowrap">
              <el-button
                v-if="row.status === 'running'"
                size="small"
                type="warning"
                :loading="actionLoading === row.id + '-pause'"
                @click="handlePause(row)"
              >
                暂停
              </el-button>
              <el-button
                v-if="row.status === 'paused'"
                size="small"
                type="success"
                :loading="actionLoading === row.id + '-resume'"
                @click="handleResume(row)"
              >
                恢复
              </el-button>
              <el-button
                v-if="row.status === 'running' || row.status === 'pending' || row.status === 'paused'"
                size="small"
                type="danger"
                :loading="actionLoading === row.id + '-stop'"
                @click="handleStopTask(row)"
              >
                停止
              </el-button>
              <el-button
                v-if="row.status === 'failed' || row.status === 'timeout'"
                size="small"
                type="primary"
                :loading="actionLoading === row.id + '-retry'"
                @click="handleRetry(row)"
              >
                重试
              </el-button>
              <el-button
                size="small"
                @click="handleViewLogs(row)"
              >
                日志
              </el-button>
              <el-button
                size="small"
                type="danger"
                :loading="actionLoading === row.id + '-delete'"
                @click="handleDeleteTask(row)"
              >
                删除
              </el-button>
            </div>
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
      :title="`任务日志 - ${currentTask?.spider_name || ''}`"
      width="800px"
      destroy-on-close
    >
      <div class="log-container">
        <pre class="log-content">{{ logContent || '暂无日志' }}</pre>
      </div>
      <template #footer>
        <el-button @click="logDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="refreshLogs" :loading="logRefreshing">刷新日志</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, VideoPlay } from '@element-plus/icons-vue'
import { listTasks, stopTask, pauseTask, resumeTask, deleteTask, getTaskLogs } from '@/api/execution'
import { getTaskStats, retryTask } from '@/api/schedule'
import { getSpiders } from '@/api/spider'
import { getTaskStatusType as getStatusType, getTaskStatusText as getStatusText, formatDateTime as formatTime } from '@/utils/common'

const loading = ref(false)
const taskList = ref([])
const spiders = ref([])

const stats = reactive({
  total: 0,
  running: 0,
  failed: 0,
  success_rate: 0
})

const filters = reactive({
  spider_id: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const actionLoading = ref('')

// 日志
const logDialogVisible = ref(false)
const logRefreshing = ref(false)
const currentTask = ref(null)
const logContent = ref('')

const loadTasks = async () => {
  loading.value = true
  try {
    const params = {
      spider_id: filters.spider_id || undefined,
      status: filters.status || undefined,
      limit: pagination.pageSize,
      offset: (pagination.page - 1) * pagination.pageSize
    }
    const res = await listTasks(params)
    taskList.value = Array.isArray(res) ? res : (res.items || [])
    pagination.total = res.total || (Array.isArray(res) ? res.length : 0)
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const data = await getTaskStats()
    if (data) {
      stats.total = data.total || 0
      stats.running = data.running || 0
      stats.failed = data.failed || 0
      stats.success_rate = data.success_rate || 0
    }
  } catch (error) {
    console.error('加载统计失败', error)
  }
}

const loadSpiders = async () => {
  try {
    const res = await getSpiders({ limit: 1000 })
    spiders.value = Array.isArray(res) ? res : (res.items || [])
  } catch (error) {
    console.error('加载爬虫列表失败', error)
  }
}

const refreshAll = () => {
  loadTasks()
  loadStats()
}

const handleCreateTask = () => {
  ElMessage.info('请从爬虫详情页创建任务')
}

const handleReset = () => {
  filters.spider_id = ''
  filters.status = ''
  pagination.page = 1
  loadTasks()
}

// 暂停
const handlePause = async (row) => {
  actionLoading.value = row.id + '-pause'
  try {
    await ElMessageBox.confirm('确定要暂停该任务吗？', '提示', { type: 'warning' })
    await pauseTask(row.id)
    ElMessage.success('任务已暂停')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('暂停失败')
  } finally {
    actionLoading.value = ''
  }
}

// 恢复
const handleResume = async (row) => {
  actionLoading.value = row.id + '-resume'
  try {
    await ElMessageBox.confirm('确定要恢复该任务吗？', '提示', { type: 'warning' })
    await resumeTask(row.id)
    ElMessage.success('任务已恢复')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('恢复失败')
  } finally {
    actionLoading.value = ''
  }
}

// 停止
const handleStopTask = async (row) => {
  actionLoading.value = row.id + '-stop'
  try {
    await ElMessageBox.confirm('确定要停止此任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await stopTask(row.id)
    ElMessage.success('任务停止请求已发送')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('停止任务失败')
  } finally {
    actionLoading.value = ''
  }
}

// 重试
const handleRetry = async (row) => {
  actionLoading.value = row.id + '-retry'
  try {
    await ElMessageBox.confirm('确定要重试该任务吗？', '提示', { type: 'warning' })
    await retryTask(row.id)
    ElMessage.success('重试请求已提交')
    setTimeout(() => loadTasks(), 1000)
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('重试失败')
  } finally {
    actionLoading.value = ''
  }
}

// 删除
const handleDeleteTask = async (row) => {
  actionLoading.value = row.id + '-delete'
  try {
    await ElMessageBox.confirm('确定要删除此任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteTask(row.id)
    ElMessage.success('任务删除成功')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除任务失败')
  } finally {
    actionLoading.value = ''
  }
}

// 查看日志
const handleViewLogs = async (row) => {
  currentTask.value = row
  logDialogVisible.value = true
  await refreshLogs()
}

const refreshLogs = async () => {
  if (!currentTask.value) return
  logRefreshing.value = true
  try {
    const res = await getTaskLogs(currentTask.value.id, 200)
    logContent.value = res.logs || '暂无日志'
  } catch (error) {
    logContent.value = '加载日志失败'
  } finally {
    logRefreshing.value = false
  }
}

const handleViewDetail = (row) => {
  ElMessage.info(`查看任务详情: ${row.id}`)
}

let refreshTimer = null

onMounted(() => {
  loadTasks()
  loadStats()
  loadSpiders()

  // 每 30 秒自动刷新
  refreshTimer = setInterval(refreshAll, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.tasks-container {
  padding: 20px;
}

.stat-card {
  text-align: center;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
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
