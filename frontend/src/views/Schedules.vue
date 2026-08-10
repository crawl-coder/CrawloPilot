<template>
  <div class="schedules-page">
    <!-- 筛选栏 -->
    <div class="page-toolbar">
      <div class="filters">
        <el-select
          v-model="filters.enabled"
          placeholder="全部状态"
          clearable
          style="width: 140px"
          @change="loadSchedules"
        >
          <el-option label="已启用" :value="true" />
          <el-option label="已停用" :value="false" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadSchedules">
          <el-icon><Refresh /></el-icon>&nbsp;刷新
        </el-button>
      </div>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="定时任务在爬虫创建/编辑表单中配置；此处提供全局查看与快捷操作"
        style="flex: 1; margin-left: 16px"
      />
    </div>

    <!-- 调度列表 -->
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="schedules" empty-text="暂无定时任务">
        <el-table-column label="爬虫" min-width="180">
          <template #default="{ row }">
            <el-link type="primary" @click="goSpider(row)">{{ row.spider_name }}</el-link>
          </template>
        </el-table-column>

        <el-table-column label="触发方式" width="120">
          <template #default="{ row }">
            <el-tag :type="typeTagType(row.schedule_type)" size="small">
              {{ typeText(row.schedule_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="触发配置" min-width="160">
          <template #default="{ row }">
            <span v-if="row.schedule_type === 'cron'" class="mono">{{ row.cron_expr }}</span>
            <span v-else-if="row.schedule_type === 'interval'">
              每 {{ formatInterval(row.interval_seconds) }}
            </span>
            <span v-else-if="row.schedule_type === 'once'">
              {{ formatDateTime(row.run_at) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="下次运行" width="170">
          <template #default="{ row }">
            <span v-if="row.enabled && row.next_run_time">{{ formatDateTime(row.next_run_time) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="上次运行" width="160">
          <template #default="{ row }">
            <span v-if="row.last_run_at">{{ formatDateTime(row.last_run_at) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="上次状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.last_run_status" :type="statusTagType(row.last_run_status)" size="small">
              {{ statusText(row.last_run_status) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              :loading="togglingId === row.id"
              @change="toggle(row)"
            />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" plain @click="runNow(row)">
              立即执行
            </el-button>
            <el-button size="small" @click="showHistory(row)">历史</el-button>
            <el-button size="small" type="danger" plain @click="remove(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 运行历史抽屉 -->
    <el-drawer
      v-model="historyVisible"
      :title="`运行历史 - ${historySchedule?.spider_name || ''}`"
      size="560px"
    >
      <el-table v-loading="historyLoading" :data="history" empty-text="暂无运行记录">
        <el-table-column prop="id" label="任务ID" width="80" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="时长" width="90">
          <template #default="{ row }">
            {{ row.duration != null ? `${Number(row.duration).toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  getSchedules, enableSchedule, disableSchedule,
  runScheduleNow, deleteSchedule, getScheduleHistory
} from '@/api/schedule'
import { formatDateTime } from '@/utils/common'

const router = useRouter()
const loading = ref(false)
const schedules = ref([])
const filters = reactive({ enabled: undefined })

const togglingId = ref(null)
const historyVisible = ref(false)
const historyLoading = ref(false)
const history = ref([])
const historySchedule = ref(null)

const loadSchedules = async () => {
  loading.value = true
  try {
    const params = {}
    if (filters.enabled !== undefined && filters.enabled !== null) {
      params.enabled = filters.enabled
    }
    schedules.value = await getSchedules(params)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载定时任务失败')
  } finally {
    loading.value = false
  }
}

const toggle = async (row) => {
  togglingId.value = row.id
  try {
    if (row.enabled) {
      await disableSchedule(row.id)
      ElMessage.success('已停用')
    } else {
      await enableSchedule(row.id)
      ElMessage.success('已启用')
    }
    await loadSchedules()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    togglingId.value = null
  }
}

const runNow = async (row) => {
  try {
    await runScheduleNow(row.id)
    ElMessage.success('已触发立即执行')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '触发失败')
  }
}

const remove = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除 ${row.spider_name} 的定时任务吗？`, '删除确认', {
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await deleteSchedule(row.id)
    ElMessage.success('已删除')
    await loadSchedules()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

const showHistory = async (row) => {
  historySchedule.value = row
  historyVisible.value = true
  historyLoading.value = true
  try {
    history.value = await getScheduleHistory(row.id)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载历史失败')
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

const goSpider = (row) => {
  if (row.spider_id) router.push(`/spiders/${row.spider_id}`)
}

const typeText = (t) => ({ cron: 'Cron', interval: '间隔', once: '一次' }[t] || t)
const typeTagType = (t) => ({ cron: 'primary', interval: 'success', once: 'warning' }[t] || 'info')
const statusText = (s) => ({
  success: '成功', failed: '失败', cancelled: '已取消', timeout: '超时',
  running: '运行中', pending: '待执行', skipped: '跳过'
}[s] || s || '-')
const statusTagType = (s) => ({
  success: 'success', failed: 'danger', cancelled: 'info', timeout: 'warning',
  running: 'warning', pending: 'info', skipped: 'info'
}[s] || 'info')

const formatInterval = (seconds) => {
  if (!seconds) return '-'
  if (seconds % 3600 === 0) return `${seconds / 3600} 小时`
  if (seconds % 60 === 0) return `${seconds / 60} 分钟`
  return `${seconds} 秒`
}

onMounted(loadSchedules)
</script>

<style scoped>
.schedules-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-toolbar {
  display: flex;
  align-items: center;
}
.filters {
  display: flex;
  gap: 8px;
}
.table-card :deep(.el-table) {
  width: 100%;
}
.mono {
  font-family: var(--cp-mono-font, 'SF Mono', Menlo, Consolas, monospace);
  font-size: 12px;
}
</style>
