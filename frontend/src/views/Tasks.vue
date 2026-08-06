<template>
  <div class="tasks-container">
    <div class="page-header">
      <h2>任务管理</h2>
      <span class="page-subtitle">执行记录与实时监控</span>
      <div class="header-actions">
        <span class="auto-refresh">
          <el-switch v-model="autoRefresh" size="small" />
          自动刷新
        </span>
        <el-button @click="refreshAll" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计概览 -->
    <div class="stats-bar cp-animate-in" v-if="stats">
      <div class="stat-pill"><span class="stat-num">{{ stats.total ?? 0 }}</span><span class="stat-label">总任务</span></div>
      <div class="stat-pill"><span class="stat-num running">{{ stats.running ?? 0 }}</span><span class="stat-label">运行中</span></div>
      <div class="stat-pill"><span class="stat-num success">{{ stats.success ?? 0 }}</span><span class="stat-label">成功</span></div>
      <div class="stat-pill"><span class="stat-num failed">{{ stats.failed ?? 0 }}</span><span class="stat-label">失败</span></div>
      <div class="stat-pill"><span class="stat-num">{{ stats.today ?? 0 }}</span><span class="stat-label">今日</span></div>
      <div class="stat-pill"><span class="stat-num rate">{{ stats.success_rate ?? 0 }}%</span><span class="stat-label">成功率</span></div>
    </div>

    <el-card shadow="never" class="cp-animate-in">
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
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 表格 -->
      <el-table :data="taskList" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70">
          <template #default="{ row }">
            <el-text type="primary" class="clickable" @click="handleViewDetail(row)">
              {{ row.id }}
            </el-text>
          </template>
        </el-table-column>
        <el-table-column prop="spider_name" label="爬虫" min-width="130" show-overflow-tooltip />
        <el-table-column label="项目" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.project_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="节点" min-width="150">
          <template #default="{ row }">
            <template v-if="row.worker_node">
              <span class="cell-main">{{ row.worker_node }}</span>
            </template>
            <template v-else-if="row.node_name">
              <el-tag size="small" type="info">{{ row.node_name }}</el-tag>
              <el-tag v-if="row.deploy_mode === 'ssh'" size="small" type="warning" style="margin-left: 4px">SSH</el-tag>
              <el-tag v-else-if="row.deploy_mode" size="small" type="success" style="margin-left: 4px">{{ row.deploy_mode }}</el-tag>
              <div v-if="row.container_id" class="cell-sub mono">{{ row.container_id.substring(0, 12) }}</div>
            </template>
            <span v-else class="cell-sub">本机</span>
          </template>
        </el-table-column>
        <el-table-column label="执行时长" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">{{ displayDuration(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="190">
          <template #default="{ row }">
            <span class="mono nowrap">{{ formatTime(row.started_at || row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="结束时间" width="190">
          <template #default="{ row }">
            <span class="mono nowrap">{{ row.finished_at ? formatTime(row.finished_at) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <div style="display: flex; gap: 4px; white-space: nowrap">
              <el-button
                v-if="row.status === 'running'"
                size="small"
                type="warning"
                plain
                :loading="actionLoading === row.id + '-pause'"
                @click="handlePause(row)"
              >
                暂停
              </el-button>
              <el-button
                v-if="row.status === 'paused'"
                size="small"
                type="success"
                plain
                :loading="actionLoading === row.id + '-resume'"
                @click="handleResume(row)"
              >
                恢复
              </el-button>
              <el-button
                size="small"
                type="danger"
                :disabled="!['running', 'pending', 'paused'].includes(row.status)"
                :loading="actionLoading === row.id + '-stop'"
                @click="handleStopTask(row)"
              >
                停止
              </el-button>
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="!['failed', 'timeout', 'success', 'cancelled'].includes(row.status)"
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
                plain
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
      :title="`任务日志 #${currentTask?.id || ''} - ${currentTask?.spider_name || ''}`"
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
import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { listTasks, stopTask, pauseTask, resumeTask, deleteTask, getTaskLogs, retryTask, getTaskStats } from '@/api/execution'
import { getSpiders } from '@/api/spider'
import { getTaskStatusType as getStatusType, getTaskStatusText as getStatusText, formatDateTime as formatTime, formatDuration } from '@/utils/common'

const loading = ref(false)
const taskList = ref([])
const spiders = ref([])
const stats = ref(null)
const router = useRouter()

// 执行时长展示：结束后用 duration，运行中按 started_at 实时估算（随自动刷新更新）
const displayDuration = (row) => {
  if (row.duration != null) return `${row.duration.toFixed(1)}s`
  if (row.status === 'running' && row.started_at) {
    const secs = (Date.now() - new Date(row.started_at).getTime()) / 1000
    return secs > 0 ? formatDuration(Math.round(secs)) : '-'
  }
  return '-'
}

const loadStats = async () => {
  try {
    stats.value = await getTaskStats()
  } catch (error) {
    // 统计失败不打扰主流程
  }
}

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
  router.push(`/tasks/${row.id}`)
}

let refreshTimer = null
const autoRefresh = ref(true)

const startAutoRefresh = () => {
  stopAutoRefresh()
  refreshTimer = setInterval(refreshAll, 30000)
}

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

watch(autoRefresh, (enabled) => {
  if (enabled) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

onMounted(() => {
  loadTasks()
  loadSpiders()
  loadStats()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.tasks-container {
  padding: 0;
}

/* ===== 页头 ===== */
.page-header {
  display: flex;
  align-items: center;
  gap: var(--cp-space-sm);
  margin-bottom: var(--cp-space-md);
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

.header-actions {
  margin-left: auto;
  display: flex;
  gap: 10px;
  align-items: center;
}

.auto-refresh {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--cp-text-secondary);
}

/* ===== 统计概览条 ===== */
.stats-bar {
  display: flex;
  gap: var(--cp-space-xl);
  padding: 14px var(--cp-space-lg);
  margin-bottom: var(--cp-space-md);
  background: var(--cp-card-bg);
  border: 1px solid var(--cp-border-light);
  border-radius: var(--cp-radius-md);
  box-shadow: var(--cp-shadow-1);
}

.stat-pill {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.stat-num {
  font-size: 20px;
  font-weight: 700;
  color: var(--cp-text-primary);
  font-variant-numeric: tabular-nums;
}

.stat-num.running { color: var(--cp-warning); }
.stat-num.success { color: var(--cp-success); }
.stat-num.failed { color: var(--cp-danger); }
.stat-num.rate { color: var(--cp-primary); }

.stat-label {
  font-size: 12px;
  color: var(--cp-text-secondary);
}

.filter-form {
  margin-bottom: var(--cp-space-sm);
}

/* ===== 单元格层级 ===== */
.cell-main {
  font-size: 13px;
  color: var(--cp-text-regular);
}

.cell-sub {
  font-size: 12px;
  color: var(--cp-text-secondary);
  margin-top: 2px;
}

.mono {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}

.nowrap {
  white-space: nowrap;
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
  background: var(--cp-terminal-bg);
  padding: var(--cp-space-md);
  border-radius: var(--cp-radius-sm);
}

.log-content {
  color: var(--cp-terminal-text);
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
