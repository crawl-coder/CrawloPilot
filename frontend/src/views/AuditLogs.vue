<template>
  <div class="audit-logs">
    <div class="page-header">
      <h3>操作审计</h3>
      <div class="filters">
        <el-input v-model="filters.username" placeholder="用户名" size="small" style="width:120px" clearable />
        <el-select v-model="filters.action" clearable placeholder="操作类型" size="small" style="width:120px">
          <el-option label="创建" value="create" />
          <el-option label="更新" value="update" />
          <el-option label="删除" value="delete" />
          <el-option label="执行" value="execute" />
          <el-option label="停止" value="stop" />
          <el-option label="启用" value="enable" />
          <el-option label="禁用" value="disable" />
        </el-select>
        <el-select v-model="filters.resource_type" clearable placeholder="资源类型" size="small" style="width:120px">
          <el-option label="项目" value="project" />
          <el-option label="爬虫" value="spider" />
          <el-option label="调度" value="schedule" />
          <el-option label="任务" value="task" />
          <el-option label="节点" value="node" />
          <el-option label="用户" value="user" />
          <el-option label="告警规则" value="alert_rule" />
        </el-select>
        <el-button size="small" @click="loadLogs">刷新</el-button>
      </div>
    </div>

    <el-table :data="logs" v-loading="loading" stripe>
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="username" label="用户" width="100" />
      <el-table-column prop="action" label="操作" width="80">
        <template #default="{ row }">
          <el-tag :type="actionType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="resource_type" label="资源类型" width="100">
        <template #default="{ row }">{{ resourceLabel(row.resource_type) }}</template>
      </el-table-column>
      <el-table-column prop="resource_name" label="资源名称" width="160" show-overflow-tooltip />
      <el-table-column prop="resource_id" label="ID" width="70" />
      <el-table-column prop="path" label="路径" min-width="200" show-overflow-tooltip />
      <el-table-column prop="ip" label="IP" width="130" />
      <el-table-column prop="detail" label="详情" min-width="150" show-overflow-tooltip />
    </el-table>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getAuditLogs } from '@/api/audit'

const logs = ref([])
const loading = ref(false)
const filters = reactive({ username: '', action: '', resource_type: '' })

const formatTime = (t) => t ? new Date(t).toLocaleString('zh-CN') : '-'

const actionMap = { create: '创建', update: '更新', delete: '删除', execute: '执行', stop: '停止', enable: '启用', disable: '禁用', retry: '重试', clone: '克隆', upload: '上传', deploy: '部署' }
const actionLabel = (a) => actionMap[a] || a
const actionType = (a) => ({ delete: 'danger', stop: 'warning', create: 'success', execute: '' }[a] || '')

const resourceMap = { project: '项目', spider: '爬虫', schedule: '调度', task: '任务', node: '节点', user: '用户', alert_rule: '告警规则', alert_channel: '通知通道', auth: '认证' }
const resourceLabel = (r) => resourceMap[r] || r || '-'

const loadLogs = async () => {
  loading.value = true
  try {
    const params = {}
    if (filters.username) params.username = filters.username
    if (filters.action) params.action = filters.action
    if (filters.resource_type) params.resource_type = filters.resource_type
    logs.value = await getAuditLogs(params)
  } finally { loading.value = false }
}

onMounted(loadLogs)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.filters { display: flex; gap: 8px; }
</style>
