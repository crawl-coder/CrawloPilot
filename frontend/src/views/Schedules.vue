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
        <el-button type="success" @click="openCreate">
          <el-icon><Plus /></el-icon>&nbsp;新建定时任务
        </el-button>
      </div>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="一个爬虫可配置多条定时任务；创建/编辑可在爬虫表单，也可在此新建"
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

        <el-table-column label="下次运行" width="180">
          <template #default="{ row }">
            <span v-if="row.enabled && row.next_run_time" class="nowrap">{{ formatDateTime(row.next_run_time) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="上次运行" width="180">
          <template #default="{ row }">
            <span v-if="row.last_run_at" class="nowrap">{{ formatDateTime(row.last_run_at) }}</span>
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

        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" type="success" plain @click="runNow(row)">
                立即执行
              </el-button>
              <el-button size="small" @click="showHistory(row)">历史</el-button>
              <el-button size="small" type="danger" plain @click="remove(row)">
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑定时任务对话框 -->
    <el-dialog v-model="createVisible" :title="editingId ? '编辑定时任务' : '新建定时任务'" width="560px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="项目" required>
          <el-select
            v-model="createForm.project_id"
            placeholder="选择项目"
            filterable
            :disabled="!!editingId"
            style="width: 100%"
            @change="onProjectChange"
          >
            <el-option
              v-for="p in projectOptions"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="爬虫" required>
          <el-select
            v-model="createForm.spider_id"
            placeholder="选择爬虫"
            filterable
            :disabled="!!editingId"
            style="width: 100%"
          >
            <el-option
              v-for="s in filteredSpiderOptions"
              :key="s.id"
              :label="`${s.name}${s.project_name ? '（' + s.project_name + '）' : ''}`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="触发方式">
          <el-radio-group v-model="createForm.schedule_type">
            <el-radio value="cron">Cron</el-radio>
            <el-radio value="interval">间隔</el-radio>
            <el-radio value="once">一次</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="createForm.schedule_type === 'cron'" label="Cron" required>
          <el-input v-model="createForm.cron_expr" placeholder="如 */5 * * * *（每5分钟）" />
        </el-form-item>

        <el-form-item v-if="createForm.schedule_type === 'interval'" label="间隔(分钟)" required>
          <el-input-number v-model="createForm.interval_minutes" :min="1" :max="10080" />
        </el-form-item>

        <el-form-item v-if="createForm.schedule_type === 'once'" label="运行时间" required>
          <el-date-picker
            v-model="createForm.run_at"
            type="datetime"
            placeholder="选择运行时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="节点">
          <el-select v-model="createForm.node_id" placeholder="默认(本地)" clearable style="width: 100%">
            <el-option v-for="n in nodeOptions" :key="n.id" :label="n.name" :value="n.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="立即启用">
          <el-switch v-model="createForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">
          {{ editingId ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Plus } from '@element-plus/icons-vue'
import {
  getSchedules, createSchedule, updateSchedule, enableSchedule, disableSchedule,
  runScheduleNow, deleteSchedule, getScheduleHistory
} from '@/api/schedule'
import { formatDateTime } from '@/utils/common'
import { getSpiders } from '@/api/spider'
import { getNodes } from '@/api/node'
import { getProjects } from '@/api/project'

const router = useRouter()
const loading = ref(false)
const schedules = ref([])
const filters = reactive({ enabled: undefined })

const togglingId = ref(null)
const historyVisible = ref(false)
const historyLoading = ref(false)
const history = ref([])
const historySchedule = ref(null)

const spiderOptions = ref([])
const projectOptions = ref([])
const nodeOptions = ref([])
const createVisible = ref(false)
const creating = ref(false)
const editingId = ref(null)
const createForm = reactive({
  project_id: null,
  spider_id: null,
  schedule_type: 'cron',
  cron_expr: '',
  interval_minutes: 60,
  run_at: null,
  node_id: null,
  enabled: true
})

const filteredSpiderOptions = computed(() => {
  if (!createForm.project_id) return spiderOptions.value
  return spiderOptions.value.filter(s => s.project_id === createForm.project_id)
})

const loadOptions = async () => {
  try {
    const [spiders, nodes, projects] = await Promise.all([
      getSpiders({ limit: 1000 }),
      getNodes(),
      getProjects({ limit: 1000 })
    ])
    const items = spiders?.items ?? spiders ?? []
    spiderOptions.value = Array.isArray(items) ? items : []
    nodeOptions.value = Array.isArray(nodes) ? nodes.filter(n => n.status === 'online') : []
    const projItems = projects?.items ?? projects ?? []
    projectOptions.value = Array.isArray(projItems) ? projItems : []
  } catch (error) {
    ElMessage.warning('加载爬虫/节点列表失败：' + (error.response?.data?.detail || error.message))
  }
}

const openCreate = () => {
  editingId.value = null
  createForm.project_id = null
  createForm.spider_id = null
  createForm.schedule_type = 'cron'
  createForm.cron_expr = ''
  createForm.interval_minutes = 60
  createForm.run_at = null
  createForm.node_id = null
  createForm.enabled = true
  createVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  createForm.project_id = row.project_id ?? null
  createForm.spider_id = row.spider_id ?? null
  createForm.schedule_type = row.schedule_type || 'cron'
  createForm.cron_expr = row.cron_expr || ''
  createForm.interval_minutes = row.interval_seconds
    ? Math.max(1, Math.round(row.interval_seconds / 60))
    : 60
  createForm.run_at = row.run_at ? row.run_at.slice(0, 19) : null
  createForm.node_id = row.node_id ?? null
  createForm.enabled = !!row.enabled
  createVisible.value = true
}

const onProjectChange = () => {
  createForm.spider_id = null
}

const submitCreate = async () => {
  if (!createForm.spider_id) {
    ElMessage.warning('请选择爬虫')
    return
  }
  const payload = {
    schedule_type: createForm.schedule_type,
    node_id: createForm.node_id || undefined,
    timezone: 'Asia/Shanghai',
    enabled: createForm.enabled
  }
  if (!editingId.value) {
    payload.spider_id = createForm.spider_id
  }
  if (createForm.schedule_type === 'cron') {
    if (!createForm.cron_expr?.trim()) {
      ElMessage.warning('请填写 Cron 表达式')
      return
    }
    payload.cron_expr = createForm.cron_expr.trim()
  } else if (createForm.schedule_type === 'interval') {
    payload.interval_seconds = Math.round(createForm.interval_minutes * 60)
  } else {
    if (!createForm.run_at) {
      ElMessage.warning('请选择运行时间')
      return
    }
    payload.run_at = new Date(createForm.run_at).toISOString()
  }

  creating.value = true
  try {
    if (editingId.value) {
      await updateSchedule(editingId.value, payload)
      ElMessage.success('定时任务已更新')
    } else {
      await createSchedule(payload)
      ElMessage.success('定时任务已创建')
    }
    createVisible.value = false
    await loadSchedules()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

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

onMounted(() => {
  loadSchedules()
  loadOptions()
})
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
.row-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.row-actions .el-button {
  margin-left: 0;
  padding: 4px 8px;
}
.nowrap {
  white-space: nowrap;
}
.mono {
  font-family: var(--cp-mono-font, 'SF Mono', Menlo, Consolas, monospace);
  font-size: 12px;
}
</style>
