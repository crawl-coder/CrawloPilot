<template>
  <div class="proxy-pool-container">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #409EFF">
              <el-icon :size="30"><Monitor /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total || 0 }}</div>
              <div class="stat-label">代理总数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #67C23A">
              <el-icon :size="30"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.active || 0 }}</div>
              <div class="stat-label">活跃代理</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #E6A23C">
              <el-icon :size="30"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.inactive || 0 }}</div>
              <div class="stat-label">不活跃</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-icon" style="background: #F56C6C">
              <el-icon :size="30"><CircleClose /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.blocked || 0 }}</div>
              <div class="stat-label">已封禁</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作栏 -->
    <el-card class="action-card">
      <el-space>
        <el-button type="primary" @click="showAddDialog = true">
          <el-icon><Plus /></el-icon>
          添加代理
        </el-button>
        <el-button type="success" @click="showBatchDialog = true">
          <el-icon><Upload /></el-icon>
          批量添加
        </el-button>
        <el-button type="warning" @click="handleCheckProxies" :loading="checking">
          <el-icon><Refresh /></el-icon>
          健康检查
        </el-button>
      </el-space>
    </el-card>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="queryForm">
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="选择状态" clearable>
            <el-option label="全部" :value="null" />
            <el-option label="活跃" value="active" />
            <el-option label="不活跃" value="inactive" />
            <el-option label="已封禁" value="blocked" />
          </el-select>
        </el-form-item>
        <el-form-item label="协议">
          <el-select v-model="queryForm.protocol" placeholder="选择协议" clearable>
            <el-option label="全部" :value="null" />
            <el-option label="HTTP" value="HTTP" />
            <el-option label="HTTPS" value="HTTPS" />
            <el-option label="SOCKS5" value="SOCKS5" />
          </el-select>
        </el-form-item>
        <el-form-item label="最低评分">
          <el-input-number v-model="queryForm.min_score" :min="0" :max="100" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 代理列表 -->
    <el-card>
      <el-table :data="proxyList" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="ip" label="IP 地址" width="150" />
        <el-table-column prop="port" label="端口" width="80" />
        <el-table-column prop="protocol" label="协议" width="100" />
        <el-table-column prop="region" label="地区" width="100" />
        <el-table-column prop="group_name" label="分组" width="120" />
        <el-table-column label="健康评分" width="150">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.health_score" 
              :color="getScoreColor(row.health_score)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_checked_at" label="最后检查" width="180">
          <template #default="{ row }">
            {{ row.last_checked_at ? formatTime(row.last_checked_at) : '未检查' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.limit"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadData"
        @size-change="loadData"
        class="pagination"
      />
    </el-card>

    <!-- 添加代理对话框 -->
    <el-dialog v-model="showAddDialog" title="添加代理" width="500px">
      <el-form :model="proxyForm" label-width="100px">
        <el-form-item label="IP 地址" required>
          <el-input v-model="proxyForm.ip" placeholder="例如：192.168.1.100" />
        </el-form-item>
        <el-form-item label="端口" required>
          <el-input-number v-model="proxyForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="协议" required>
          <el-select v-model="proxyForm.protocol">
            <el-option label="HTTP" value="HTTP" />
            <el-option label="HTTPS" value="HTTPS" />
            <el-option label="SOCKS5" value="SOCKS5" />
          </el-select>
        </el-form-item>
        <el-form-item label="地区">
          <el-input v-model="proxyForm.region" placeholder="例如：CN" />
        </el-form-item>
        <el-form-item label="分组">
          <el-input v-model="proxyForm.group_name" placeholder="例如：group1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddProxy">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量添加对话框 -->
    <el-dialog v-model="showBatchDialog" title="批量添加代理" width="600px">
      <el-alert title="每行一个代理，格式：IP:端口:协议" type="info" :closable="false" style="margin-bottom: 15px" />
      <el-input
        v-model="batchText"
        type="textarea"
        :rows="10"
        placeholder="例如：&#10;192.168.1.100:8080:HTTP&#10;10.0.0.1:3128:HTTPS&#10;10.0.0.2:1080:SOCKS5"
      />
      <template #footer>
        <el-button @click="showBatchDialog = false">取消</el-button>
        <el-button type="primary" @click="handleBatchAdd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getProxies, getProxyStats, addProxy, batchAddProxies, checkProxies, deleteProxy } from '@/api/proxyApi'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Monitor, CircleCheck, Warning, CircleClose, Plus, Upload, Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const checking = ref(false)
const proxyList = ref([])
const stats = ref({})
const showAddDialog = ref(false)
const showBatchDialog = ref(false)
const batchText = ref('')

const queryForm = ref({
  status: null,
  protocol: null,
  min_score: null
})

const pagination = ref({
  page: 1,
  limit: 20,
  total: 0
})

const proxyForm = ref({
  ip: '',
  port: 8080,
  protocol: 'HTTP',
  region: '',
  group_name: ''
})

const loadData = async ({ page: newPage, size } = {}) => {
  loading.value = true
  try {
    const currentPageNum = newPage || pagination.value.page
    const pageSizeNum = size || pagination.value.limit
    const skip = (currentPageNum - 1) * pageSizeNum
    
    const params = {
      ...queryForm.value,
      skip,
      limit: pageSizeNum
    }
    
    const [listData, statsData] = await Promise.all([
      getProxies(params),
      getProxyStats({ days: 30 })
    ])
    
    proxyList.value = listData.items || []
    stats.value = statsData
    pagination.value.total = listData.total || 0
    pagination.value.page = currentPageNum
    pagination.value.limit = pageSizeNum
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const resetQuery = () => {
  queryForm.value = {
    status: null,
    protocol: null,
    min_score: null
  }
  pagination.value.page = 1
  loadData()
}

const handleAddProxy = async () => {
  try {
    await addProxy(proxyForm.value)
    ElMessage.success('添加成功')
    showAddDialog.value = false
    loadData()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

const handleBatchAdd = async () => {
  try {
    const lines = batchText.value.trim().split('\n')
    const proxies = lines.map(line => {
      const [ip, port, protocol] = line.split(':')
      return {
        ip: ip.trim(),
        port: parseInt(port.trim()),
        protocol: protocol.trim()
      }
    })
    
    await batchAddProxies(proxies)
    ElMessage.success(`成功添加 ${proxies.length} 个代理`)
    showBatchDialog.value = false
    batchText.value = ''
    loadData()
  } catch (error) {
    ElMessage.error('批量添加失败')
  }
}

const handleCheckProxies = async () => {
  checking.value = true
  try {
    const result = await checkProxies({})
    ElMessage.success(`检查完成：可用 ${result.available} / 不可用 ${result.unavailable}`)
    loadData()
  } catch (error) {
    ElMessage.error('健康检查失败')
  } finally {
    checking.value = false
  }
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除此代理吗？', '提示', {
      type: 'warning'
    })
    await deleteProxy(id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const getScoreColor = (score) => {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  return '#F56C6C'
}

const getStatusType = (status) => {
  const types = {
    active: 'success',
    inactive: 'warning',
    blocked: 'danger'
  }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = {
    active: '活跃',
    inactive: '不活跃',
    blocked: '已封禁'
  }
  return texts[status] || status
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.proxy-pool-container {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.action-card {
  margin-bottom: 20px;
}

.filter-card {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
