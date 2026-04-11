<template>
  <div class="schedules-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>调度管理</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            创建调度
          </el-button>
        </div>
      </template>

      <!-- 筛选 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="项目">
          <el-select v-model="filters.projectId" placeholder="选择项目" clearable @change="loadData">
            <el-option label="全部" value="" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.enabled" placeholder="状态" clearable @change="loadData">
            <el-option label="全部" value="" />
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- 表格 -->
      <el-table :data="schedules" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="spider_name" label="爬虫名称" />
        <el-table-column prop="schedule_type" label="调度类型" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.schedule_type === 'cron'" type="primary">Cron</el-tag>
            <el-tag v-else-if="row.schedule_type === 'interval'" type="success">间隔</el-tag>
            <el-tag v-else type="info">一次性</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="调度规则" width="150">
          <template #default="{ row }">
            <span v-if="row.schedule_type === 'cron'">{{ row.cron_expr }}</span>
            <span v-else-if="row.schedule_type === 'interval'">每 {{ row.interval_seconds }} 秒</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.enabled" type="success">启用</el-tag>
            <el-tag v-else type="info">禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下次执行" width="180">
          <template #default="{ row }">
            {{ row.next_run_time || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleTrigger(row)">触发</el-button>
            <el-button 
              size="small" 
              :type="row.enabled ? 'warning' : 'success'"
              @click="handleToggle(row)"
            >
              {{ row.enabled ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="项目 ID" prop="project_id">
          <el-input-number v-model="form.project_id" :min="1" />
        </el-form-item>
        <el-form-item label="爬虫名称" prop="spider_name">
          <el-input v-model="form.spider_name" placeholder="输入爬虫名称" />
        </el-form-item>
        <el-form-item label="调度类型" prop="schedule_type">
          <el-radio-group v-model="form.schedule_type">
            <el-radio label="cron">Cron</el-radio>
            <el-radio label="interval">间隔</el-radio>
            <el-radio label="once">一次性</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.schedule_type === 'cron'" label="Cron 表达式" prop="cron_expr">
          <el-input v-model="form.cron_expr" placeholder="例如: */5 * * * *" />
        </el-form-item>
        <el-form-item v-if="form.schedule_type === 'interval'" label="间隔秒数" prop="interval_seconds">
          <el-input-number v-model="form.interval_seconds" :min="1" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-slider v-model="form.priority" :min="1" :max="10" show-stops />
        </el-form-item>
        <el-form-item label="最大并发">
          <el-input-number v-model="form.max_concurrency" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="超时时间(秒)">
          <el-input-number v-model="form.timeout_seconds" :min="60" :step="60" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { 
  getSchedules, 
  createSchedule, 
  updateSchedule, 
  deleteSchedule,
  enableSchedule,
  disableSchedule,
  triggerSchedule
} from '@/api/schedule'

const loading = ref(false)
const submitting = ref(false)
const schedules = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('创建调度')
const formRef = ref(null)

const filters = reactive({
  projectId: '',
  enabled: ''
})

const form = reactive({
  project_id: 1,
  spider_name: '',
  schedule_type: 'cron',
  cron_expr: '*/5 * * * *',
  interval_seconds: 300,
  priority: 5,
  max_concurrency: 1,
  timeout_seconds: 3600,
  enabled: true
})

const rules = {
  project_id: [{ required: true, message: '请输入项目 ID', trigger: 'blur' }],
  spider_name: [{ required: true, message: '请输入爬虫名称', trigger: 'blur' }],
  schedule_type: [{ required: true, message: '请选择调度类型', trigger: 'change' }]
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {}
    if (filters.projectId) params.project_id = filters.projectId
    if (filters.enabled !== '') params.enabled = filters.enabled
    
    schedules.value = await getSchedules(params)
  } catch (error) {
    ElMessage.error('加载调度列表失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  dialogTitle.value = '创建调度'
  Object.assign(form, {
    project_id: 1,
    spider_name: '',
    schedule_type: 'cron',
    cron_expr: '*/5 * * * *',
    interval_seconds: 300,
    priority: 5,
    max_concurrency: 1,
    timeout_seconds: 3600,
    enabled: true
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑调度'
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  submitting.value = true
  
  try {
    if (dialogTitle.value === '创建调度') {
      await createSchedule(form)
      ElMessage.success('创建成功')
    } else {
      await updateSchedule(form.id, form)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该调度吗？', '提示', {
      type: 'warning'
    })
    await deleteSchedule(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleToggle = async (row) => {
  try {
    if (row.enabled) {
      await disableSchedule(row.id)
      ElMessage.success('已禁用')
    } else {
      await enableSchedule(row.id)
      ElMessage.success('已启用')
    }
    loadData()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleTrigger = async (row) => {
  try {
    await triggerSchedule(row.id)
    ElMessage.success('任务已触发')
  } catch (error) {
    ElMessage.error('触发失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.schedules-container {
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
</style>
