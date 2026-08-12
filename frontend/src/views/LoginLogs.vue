<template>
  <div class="login-logs">
    <div class="page-header">
      <h2>登录日志</h2>
      <span class="page-subtitle">记录用户、IP、登录时间与结果</span>
      <div class="header-actions">
        <el-button type="primary" plain @click="load">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-input
          v-model="filters.username"
          placeholder="按用户名搜索"
          clearable
          style="width: 200px"
          @keyup.enter="resetPage"
        />
        <el-select v-model="filters.success" placeholder="全部结果" clearable style="width: 140px" @change="resetPage">
          <el-option label="成功" :value="true" />
          <el-option label="失败" :value="false" />
        </el-select>
        <el-button type="primary" plain @click="resetPage">查询</el-button>
      </div>

      <el-table :data="items" v-loading="loading" border stripe>
        <el-table-column prop="login_at" label="登录时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.login_at) }}</template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="140" />
        <el-table-column prop="ip" label="IP 地址" width="150" />
        <el-table-column prop="user_agent" label="User-Agent" min-width="240" show-overflow-tooltip />
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="说明" min-width="140" />
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 12px; justify-content: flex-end"
        @size-change="load"
        @current-change="load"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getLoginLogs } from '@/api/auth'
import { formatDateTime } from '@/utils/common'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filters = reactive({ username: '', success: undefined })

const load = async () => {
  loading.value = true
  try {
    const res = await getLoginLogs({
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
      username: filters.username || undefined,
      success: filters.success === undefined ? undefined : filters.success
    })
    items.value = res.items || []
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载登录日志失败')
  } finally {
    loading.value = false
  }
}

const resetPage = () => {
  page.value = 1
  load()
}

onMounted(load)
</script>

<style scoped>
.login-logs {
  padding: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
}

.page-subtitle {
  color: var(--cp-text-secondary);
  font-size: 13px;
}

.header-actions {
  margin-left: auto;
}

.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
</style>
