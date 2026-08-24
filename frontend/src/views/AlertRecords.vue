<template>
  <div class="alert-records">
    <div class="page-header">
      <h3>告警记录</h3>
      <div class="filters">
        <el-select v-model="filters.severity" clearable placeholder="严重级别" size="small" style="width:120px">
          <el-option label="critical" value="critical" />
          <el-option label="warning" value="warning" />
          <el-option label="info" value="info" />
        </el-select>
        <el-select v-model="filters.acknowledged" clearable placeholder="确认状态" size="small" style="width:120px">
          <el-option label="未确认" :value="false" />
          <el-option label="已确认" :value="true" />
        </el-select>
        <el-button size="small" @click="loadRecords">刷新</el-button>
      </div>
    </div>

    <el-table :data="records" v-loading="loading" stripe>
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="event_type" label="事件类型" width="150">
        <template #default="{ row }">
          <el-tag size="small">{{ row.event_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="target_name" label="目标" width="150" />
      <el-table-column prop="message" label="消息" min-width="250" show-overflow-tooltip />
      <el-table-column prop="severity" label="级别" width="90">
        <template #default="{ row }">
          <el-tag :type="severityType(row.severity)" size="small">{{ row.severity }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.acknowledged ? 'success' : 'warning'" size="small">
            {{ row.acknowledged ? '已确认' : '待处理' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.acknowledged" size="small" type="primary" @click="handleAck(row)">确认</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAlertRecords, acknowledgeAlertRecord } from '@/api/alert'

const records = ref([])
const loading = ref(false)
const filters = reactive({ severity: null, acknowledged: null })

const severityType = (s) => ({ critical: 'danger', warning: 'warning', info: '' }[s] || '')
const formatTime = (t) => t ? new Date(t).toLocaleString('zh-CN') : '-'

const loadRecords = async () => {
  loading.value = true
  try {
    const params = {}
    if (filters.severity) params.severity = filters.severity
    if (filters.acknowledged !== null && filters.acknowledged !== '') params.acknowledged = filters.acknowledged
    records.value = await getAlertRecords(params)
  } finally { loading.value = false }
}

const handleAck = async (row) => {
  await acknowledgeAlertRecord(row.id)
  row.acknowledged = true
  ElMessage.success('已确认')
}

onMounted(loadRecords)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.filters { display: flex; gap: 8px; }
</style>
