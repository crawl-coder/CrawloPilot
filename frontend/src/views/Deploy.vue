<template>
  <div class="deploy-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>部署管理</h3>
          <el-button type="primary" @click="showDeployDialog = true">
            <el-icon><Plus /></el-icon>
            新建部署
          </el-button>
        </div>
      </template>

      <!-- 筛选器 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="项目">
          <el-select v-model="filters.project_id" placeholder="选择项目" clearable @change="loadDeploys">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="选择状态" clearable @change="loadDeploys">
            <el-option label="等待中" value="pending" />
            <el-option label="部署中" value="deploying" />
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="已回滚" value="rolled_back" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- 部署列表 -->
      <el-table :data="deploys" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="project_id" label="项目 ID" width="100" />
        <el-table-column prop="strategy" label="策略" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.strategy === 'blue_green'" type="success">蓝绿部署</el-tag>
            <el-tag v-else-if="row.strategy === 'rolling'" type="warning">滚动更新</el-tag>
            <el-tag v-else>重新创建</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'success'" type="success">成功</el-tag>
            <el-tag v-else-if="row.status === 'deploying'" type="warning">部署中</el-tag>
            <el-tag v-else-if="row.status === 'failed'" type="danger">失败</el-tag>
            <el-tag v-else-if="row.status === 'rolled_back'" type="info">已回滚</el-tag>
            <el-tag v-else>等待中</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_env" label="环境" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="viewDeploy(row)">详情</el-button>
            <el-button 
              v-if="row.status === 'failed'" 
              size="small" 
              type="warning"
              @click="handleRetry(row)"
            >
              重试
            </el-button>
            <el-button 
              v-if="row.status === 'success'" 
              size="small" 
              type="danger"
              @click="handleRollback(row)"
            >
              回滚
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadDeploys"
        @current-change="loadDeploys"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- 新建部署对话框 -->
    <el-dialog v-model="showDeployDialog" title="新建部署" width="600px">
      <el-form :model="deployForm" label-width="100px">
        <el-form-item label="项目" required>
          <el-select v-model="deployForm.project_id" placeholder="选择项目" style="width: 100%">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="版本" required>
          <el-input v-model="deployForm.version_id" placeholder="版本 ID" />
        </el-form-item>
        <el-form-item label="部署策略" required>
          <el-select v-model="deployForm.strategy" style="width: 100%">
            <el-option label="重新创建" value="recreate" />
            <el-option label="蓝绿部署" value="blue_green" />
            <el-option label="滚动更新" value="rolling" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标节点" required>
          <el-select v-model="deployForm.node_id" placeholder="选择节点" style="width: 100%">
            <el-option v-for="node in nodes" :key="node.id" :label="node.name" :value="node.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标环境">
          <el-select v-model="deployForm.target_env" style="width: 100%">
            <el-option label="生产环境" value="production" />
            <el-option label="预发布环境" value="staging" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeployDialog = false">取消</el-button>
        <el-button type="primary" @click="handleDeploy" :loading="deploying">部署</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { createDeploy, getDeploys, rollbackDeploy, retryDeploy } from '@/api/deploy'
import request from '@/api/request'
import Pagination from '@/components/Pagination.vue'

const loading = ref(false)
const deploying = ref(false)
const showDeployDialog = ref(false)
const deploys = ref([])
const projects = ref([])
const nodes = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const filters = reactive({
  project_id: null,
  status: null
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const deployForm = reactive({
  project_id: null,
  version_id: '',
  strategy: 'recreate',
  node_id: null,
  target_env: 'production'
})

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadDeploys = async ({ page, size } = {}) => {
  loading.value = true
  try {
    const currentPageNum = page || pagination.page
    const pageSizeNum = size || pagination.size
    const offset = (currentPageNum - 1) * pageSizeNum
    
    const params = {
      offset,
      limit: pageSizeNum
    }
    if (filters.project_id) params.project_id = filters.project_id
    if (filters.status) params.status = filters.status

    const response = await getDeploys(params)
    deploys.value = response.items || []
    pagination.total = response.total || 0
    pagination.page = currentPageNum
    pagination.size = pageSizeNum
  } catch (error) {
    ElMessage.error('加载部署列表失败')
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const data = await request.get('/projects')
    projects.value = data
  } catch (error) {
    console.error('加载项目列表失败', error)
  }
}

const loadNodes = async () => {
  try {
    const data = await request.get('/nodes')
    nodes.value = data
  } catch (error) {
    console.error('加载节点列表失败', error)
  }
}

const handleDeploy = async () => {
  if (!deployForm.project_id || !deployForm.version_id || !deployForm.node_id) {
    ElMessage.warning('请填写完整信息')
    return
  }

  deploying.value = true
  try {
    await createDeploy(deployForm)
    ElMessage.success('部署任务已创建')
    showDeployDialog.value = false
    loadDeploys()
  } catch (error) {
    ElMessage.error('创建部署失败')
  } finally {
    deploying.value = false
  }
}

const handleRollback = async (row) => {
  try {
    await ElMessageBox.confirm('确定要回滚此部署吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await rollbackDeploy(row.id)
    ElMessage.success('回滚任务已提交')
    loadDeploys()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('回滚失败')
    }
  }
}

const handleRetry = async (row) => {
  try {
    await retryDeploy(row.id)
    ElMessage.success('重试任务已提交')
    loadDeploys()
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

const viewDeploy = (row) => {
  ElMessage.info(`查看部署详情: ${row.id}`)
}

onMounted(() => {
  loadDeploys()
  loadProjects()
  loadNodes()
})
</script>

<style scoped>
.deploy-container {
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
