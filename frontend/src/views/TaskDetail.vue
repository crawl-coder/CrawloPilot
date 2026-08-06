<template>
  <div class="task-detail">
    <el-page-header @back="$router.back()">
      <template #content>
        <span class="page-title">任务 #{{ taskId }}</span>
        <el-tag :type="statusType" size="small" style="margin-left: 12px">
          {{ statusText }}
        </el-tag>
        <el-tag v-if="task?.deploy_mode" size="small" type="info" effect="plain" style="margin-left: 6px">
          {{ modeText }}
        </el-tag>
      </template>
      <template #extra>
        <div class="header-actions">
          <el-button v-if="isRunning" size="small" type="warning" :loading="actionLoading" @click="handlePause">
            暂停
          </el-button>
          <el-button v-if="isPaused" size="small" type="success" :loading="actionLoading" @click="handleResume">
            恢复
          </el-button>
          <el-button
            v-if="isRunning || isPaused || isPending"
            size="small"
            type="danger"
            :loading="actionLoading"
            @click="handleStop"
          >
            停止
          </el-button>
          <el-button v-if="isFailed || isTimeout" size="small" type="primary" :loading="actionLoading" @click="handleRetry">
            重试
          </el-button>
          <el-button size="small" :loading="loading" @click="loadDetail">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
    </el-page-header>

    <el-alert
      v-if="task?.error_message && (isFailed || isTimeout)"
      type="error"
      :title="task.error_message"
      :closable="false"
      style="margin-top: 16px"
    />

    <!-- 状态信息 -->
    <el-row :gutter="20" style="margin-top: 16px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>任务信息</span>
          </template>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="任务 ID">{{ taskId }}</el-descriptions-item>
            <el-descriptions-item label="爬虫">
              <el-link type="primary" @click="goSpider">{{ task?.spider_name || '-' }}</el-link>
            </el-descriptions-item>
            <el-descriptions-item label="所属项目">{{ task?.project_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="部署模式">{{ modeText }}</el-descriptions-item>
            <el-descriptions-item label="执行节点">{{ task?.node_name || '本机 (local)' }}</el-descriptions-item>
            <el-descriptions-item label="进程 PID">{{ task?.process_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="开始时间">{{ formatTime(task?.started_at || task?.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="结束时间">{{ formatTime(task?.finished_at) }}</el-descriptions-item>
            <el-descriptions-item label="执行时长">{{ durationText }}</el-descriptions-item>
            <el-descriptions-item label="日志文件" :span="3">
              <el-text size="small" type="info">{{ task?.log_url || '-' }}</el-text>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <!-- 指标 -->
    <el-row :gutter="20" style="margin-top: 16px">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="爬取页面" :value="metrics.pages" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="采集条目" :value="metrics.items" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="错误数" :value="metrics.errors" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 实时日志 -->
    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>实时日志
            <el-tag v-if="wsConnected" type="success" size="small" effect="plain" style="margin-left: 8px">WebSocket 已连接</el-tag>
            <el-tag v-else type="info" size="small" effect="plain" style="margin-left: 8px">轮询模式</el-tag>
          </span>
          <div>
            <el-switch v-model="autoScroll" active-text="自动滚动" style="margin-right: 12px" />
            <el-button size="small" @click="refreshLogs" :loading="logLoading">
              <el-icon><Refresh /></el-icon>
              刷新日志
            </el-button>
          </div>
        </div>
      </template>
      <div class="log-container" ref="logContainerRef">
        <pre class="log-content">{{ logs || '暂无日志' }}</pre>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  getTaskDetail,
  getTaskStatus,
  getTaskLogs,
  pauseTask,
  resumeTask,
  stopTask,
  retryTask
} from '@/api/execution'
import TaskWebSocket from '@/utils/websocket'
import { getTaskStatusType as getStatusType, getTaskStatusText as getStatusText, formatDateTime as formatTime } from '@/utils/common'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

const task = ref(null)
const loading = ref(false)
const actionLoading = ref(false)
const logs = ref('')
const logLoading = ref(false)
const autoScroll = ref(true)
const logContainerRef = ref(null)
const wsConnected = ref(false)

const liveStatus = ref(null)
let ws = null
let pollTimer = null
let scrollTimer = null

const status = computed(() => liveStatus.value?.status || task.value?.status || 'pending')
const statusType = computed(() => getStatusType(status.value))
const statusText = computed(() => getStatusText(status.value))
const isRunning = computed(() => status.value === 'running')
const isPaused = computed(() => status.value === 'paused')
const isPending = computed(() => status.value === 'pending')
const isFailed = computed(() => status.value === 'failed')
const isTimeout = computed(() => status.value === 'timeout')
const modeText = computed(() => {
  const map = { local: '本地进程', ssh: 'SSH 节点', docker: 'Docker', agent: 'Agent' }
  return map[task.value?.deploy_mode] || task.value?.deploy_mode || '-'
})
const durationText = computed(() => {
  const d = task.value?.duration ?? liveStatus.value?.duration
  if (d === null || d === undefined) return '-'
  return `${Number(d).toFixed(1)}s`
})
const metrics = computed(() => ({
  pages: task.value?.pages_crawled ?? liveStatus.value?.pages_crawled ?? 0,
  items: task.value?.items_scraped ?? liveStatus.value?.items_scraped ?? 0,
  errors: task.value?.errors_count ?? liveStatus.value?.errors_count ?? 0
}))

const loadDetail = async () => {
  loading.value = true
  try {
    task.value = await getTaskDetail(taskId)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载任务详情失败')
  } finally {
    loading.value = false
  }
}

const refreshStatus = async () => {
  try {
    const res = await getTaskStatus(taskId)
    liveStatus.value = {
      status: res.db_status,
      pages_crawled: res.pages_crawled,
      items_scraped: res.items_scraped,
      errors_count: res.errors_count,
      duration: res.duration
    }
  } catch (error) {
    /* ignore */
  }
}

const refreshLogs = async () => {
  logLoading.value = true
  try {
    const res = await getTaskLogs(taskId, 500)
    logs.value = res.logs || '暂无日志'
    scrollToBottom()
  } catch (error) {
    logs.value = '加载日志失败'
  } finally {
    logLoading.value = false
  }
}

const scrollToBottom = () => {
  if (!autoScroll.value) return
  nextTick(() => {
    const el = logContainerRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

const appendLog = (line) => {
  logs.value += (logs.value && !logs.value.endsWith('\n') ? '\n' : '') + line
  // 限制日志长度，避免内存膨胀
  if (logs.value.length > 200000) {
    logs.value = logs.value.slice(-150000)
  }
  clearTimeout(scrollTimer)
  scrollTimer = setTimeout(scrollToBottom, 50)
}

const connectWs = () => {
  try {
    ws = new TaskWebSocket(taskId, {
      onLog: appendLog,
      onStatus: (data) => {
        liveStatus.value = data
        if (data.status) {
          // 同步任务详情中的状态
          task.value = { ...(task.value || {}), status: data.status, duration: data.duration }
        }
      },
      onError: () => { wsConnected.value = false }
    })
    ws.connect()
    wsConnected.value = true
  } catch (error) {
    console.error('WebSocket 连接失败，切换到轮询模式:', error)
    wsConnected.value = false
  }
}

const runAction = async (fn, successMsg) => {
  actionLoading.value = true
  try {
    await fn(taskId)
    ElMessage.success(successMsg)
    await Promise.all([loadDetail(), refreshStatus(), refreshLogs()])
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    actionLoading.value = false
  }
}

const handlePause = () => runAction(pauseTask, '任务已暂停')
const handleResume = () => runAction(resumeTask, '任务已恢复')
const handleStop = async () => {
  await ElMessageBox.confirm('确定要停止该任务吗？', '停止任务', { type: 'warning' })
  await runAction(stopTask, '任务已停止')
}
const handleRetry = () => runAction(retryTask, '重试已提交')

const goSpider = () => {
  if (task.value?.spider_id) {
    router.push(`/spiders/${task.value.spider_id}`)
  }
}

onMounted(async () => {
  await loadDetail()
  await Promise.all([refreshStatus(), refreshLogs()])
  connectWs()

  // 轮询兜底（WebSocket 不可用时也保证状态/日志更新）
  pollTimer = setInterval(async () => {
    if (!wsConnected.value || isRunning.value || isPending.value || isPaused.value) {
      await refreshStatus()
    }
    if (!wsConnected.value) {
      await refreshLogs()
    }
  }, 3000)
})

onUnmounted(() => {
  if (ws) ws.disconnect()
  if (pollTimer) clearInterval(pollTimer)
  if (scrollTimer) clearTimeout(scrollTimer)
})
</script>

<style scoped>
.task-detail {
  padding: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-container {
  height: 420px;
  overflow-y: auto;
  background: var(--cp-terminal-bg);
  border-radius: var(--cp-radius-sm);
  padding: var(--cp-space-sm);
}

.log-content {
  margin: 0;
  color: var(--cp-terminal-text);
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
