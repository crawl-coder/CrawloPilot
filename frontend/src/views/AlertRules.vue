<template>
  <div class="alert-rules">
    <div class="page-header">
      <h3>告警规则</h3>
      <el-button type="primary" @click="openCreate">新建规则</el-button>
    </div>

    <el-table :data="rules" v-loading="loading" stripe>
      <el-table-column prop="name" label="规则名称" min-width="120" />
      <el-table-column prop="rule_type" label="规则类型" width="160">
        <template #default="{ row }">
          <el-tag size="small">{{ ruleTypeLabel(row.rule_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="severity" label="严重级别" width="100">
        <template #default="{ row }">
          <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="threshold" label="阈值" width="80" />
      <el-table-column prop="window_minutes" label="窗口(分)" width="90" />
      <el-table-column prop="cooldown_minutes" label="冷却(分)" width="90" />
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="toggleRule(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建/编辑规则对话框 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑规则' : '新建规则'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="规则名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="规则类型">
          <el-select v-model="form.rule_type" :disabled="!!editingId">
            <el-option v-for="t in ruleTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="严重级别">
          <el-select v-model="form.severity">
            <el-option label="info" value="info" />
            <el-option label="warning" value="warning" />
            <el-option label="critical" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值">
          <el-input-number v-model="form.threshold" :min="1" />
          <span class="form-hint">连续失败次数 / 成功率百分比等</span>
        </el-form-item>
        <el-form-item label="统计窗口">
          <el-input-number v-model="form.window_minutes" :min="1" />
          <span class="form-hint">分钟</span>
        </el-form-item>
        <el-form-item label="冷却期">
          <el-input-number v-model="form.cooldown_minutes" :min="1" />
          <span class="form-hint">同规则同目标不重复触发的时间（分钟）</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">{{ editingId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAlertRules, createAlertRule, updateAlertRule, deleteAlertRule
} from '@/api/alert'

const rules = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)

const ruleTypes = [
  { value: 'task_failed', label: '任务失败' },
  { value: 'task_timeout', label: '任务超时' },
  { value: 'consecutive_failures', label: '连续失败' },
  { value: 'success_rate', label: '成功率过低' },
  { value: 'node_offline', label: '节点离线' },
  { value: 'zombie_converged', label: '僵尸任务清理' },
]

const defaultForm = {
  name: '', rule_type: 'task_failed', severity: 'warning',
  threshold: 1, window_minutes: 60, cooldown_minutes: 30, enabled: true,
}
const form = ref({ ...defaultForm })

const ruleTypeLabel = (v) => ruleTypes.find(t => t.value === v)?.label || v
const severityType = (s) => ({ critical: 'danger', warning: 'warning', info: '' }[s] || '')

const loadRules = async () => {
  loading.value = true
  try { rules.value = await getAlertRules() } finally { loading.value = false }
}

const openCreate = () => { editingId.value = null; form.value = { ...defaultForm }; dialogVisible.value = true }
const openEdit = (row) => {
  editingId.value = row.id
  form.value = { name: row.name, rule_type: row.rule_type, severity: row.severity, threshold: row.threshold, window_minutes: row.window_minutes, cooldown_minutes: row.cooldown_minutes, enabled: row.enabled }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  try {
    if (editingId.value) {
      await updateAlertRule(editingId.value, form.value)
      ElMessage.success('规则已更新')
    } else {
      await createAlertRule(form.value)
      ElMessage.success('规则已创建')
    }
    dialogVisible.value = false
    loadRules()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '操作失败') }
}

const toggleRule = async (row) => {
  try { await updateAlertRule(row.id, { enabled: row.enabled }) } catch { row.enabled = !row.enabled }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm('确认删除该规则？', '提示')
  await deleteAlertRule(row.id)
  ElMessage.success('规则已删除')
  loadRules()
}

onMounted(loadRules)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.form-hint { margin-left: 8px; color: #999; font-size: 12px; }
</style>
