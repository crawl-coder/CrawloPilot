<template>
  <div class="nodes-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>节点管理</h3>
          <div>
            <el-button @click="handleHealthCheck">
              <el-icon><Refresh /></el-icon>
              健康检查
            </el-button>
            <el-button type="primary" @click="showNodeDialog = true">
              <el-icon><Plus /></el-icon>
              添加节点
            </el-button>
          </div>
        </div>
      </template>

      <!-- 节点列表 -->
      <el-row :gutter="20">
        <el-col v-for="node in nodes" :key="node.id" :xs="24" :sm="12" :md="8" :lg="6">
          <el-card class="node-card" shadow="hover">
            <template #header>
              <div class="node-header">
                <span class="node-name">{{ node.name }}</span>
                <el-tag v-if="node.status === 'online'" type="success" size="small">在线</el-tag>
                <el-tag v-else-if="node.status === 'offline'" type="danger" size="small">离线</el-tag>
                <el-tag v-else-if="node.status === 'maintenance'" type="warning" size="small">维护中</el-tag>
                <el-tag v-else type="info" size="small">{{ node.status }}</el-tag>
              </div>
            </template>

            <div class="node-info">
              <div class="info-item">
                <span class="label">地址:</span>
                <span class="value">{{ node.host }}:{{ node.port }}</span>
              </div>
              <div class="info-item">
                <span class="label">容器数:</span>
                <span class="value">{{ node.container_count }}</span>
              </div>
              <div class="info-item" v-if="node.resources">
                <span class="label">CPU:</span>
                <span class="value">{{ node.resources.cpus }} 核</span>
              </div>
              <div class="info-item" v-if="node.resources">
                <span class="label">内存:</span>
                <span class="value">{{ formatBytes(node.resources.memory_total) }}</span>
              </div>
              <div class="info-item" v-if="node.last_heartbeat">
                <span class="label">心跳:</span>
                <span class="value">{{ formatTime(node.last_heartbeat) }}</span>
              </div>
            </div>

            <div class="node-actions">
              <el-button size="small" @click="testConnection(node)">测试</el-button>
              <el-button size="small" @click="viewContainers(node)">容器</el-button>
              <el-dropdown @command="(cmd) => handleNodeAction(cmd, node)">
                <el-button size="small">
                  更多<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="activate" v-if="node.status !== 'online'">激活</el-dropdown-item>
                    <el-dropdown-item command="drain" v-if="node.status === 'online'">排空</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="nodes.length === 0" description="暂无节点" />
    </el-card>

    <!-- 添加节点对话框 -->
    <el-dialog v-model="showNodeDialog" title="添加节点" width="600px">
      <el-form :model="nodeForm" label-width="120px">
        <el-form-item label="节点名称" required>
          <el-input v-model="nodeForm.name" placeholder="例如: node-1" />
        </el-form-item>
        <el-form-item label="主机地址" required>
          <el-input v-model="nodeForm.host" placeholder="例如: 192.168.1.100" />
        </el-form-item>
        <el-form-item label="Docker 端口">
          <el-input-number v-model="nodeForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="labelsInput" placeholder="逗号分隔，例如: prod,high-memory" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showNodeDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddNode" :loading="adding">添加</el-button>
      </template>
    </el-dialog>

    <!-- 容器列表对话框 -->
    <el-dialog v-model="showContainersDialog" :title="`容器列表 - ${currentNode?.name}`" width="900px">
      <el-table :data="containers" v-loading="loadingContainers">
        <el-table-column prop="container_id" label="容器 ID" width="200">
          <template #default="{ row }">
            {{ row.container_id?.substring(0, 12) }}
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="250" />
        <el-table-column prop="image" label="镜像" width="200" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'running'" type="success" size="small">运行中</el-tag>
            <el-tag v-else-if="row.status === 'exited'" type="info" size="small">已停止</el-tag>
            <el-tag v-else type="warning" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, ArrowDown } from '@element-plus/icons-vue'
import { 
  createNode, 
  getNodes, 
  testNodeConnection, 
  checkNodesHealth,
  drainNode,
  activateNode,
  deleteNode,
  getNodeContainers
} from '@/api/deploy'

const nodes = ref([])
const containers = ref([])
const loading = ref(false)
const loadingContainers = ref(false)
const adding = ref(false)
const showNodeDialog = ref(false)
const showContainersDialog = ref(false)
const currentNode = ref(null)

const nodeForm = reactive({
  name: '',
  host: '',
  port: 2375,
  labels: {}
})

const labelsInput = ref('')

const formatBytes = (bytes) => {
  if (!bytes) return '-'
  const gb = bytes / (1024 * 1024 * 1024)
  return gb.toFixed(2) + ' GB'
}

const formatTime = (timeStr) => {
  if (!timeStr) return '-'
  const time = new Date(timeStr)
  const now = new Date()
  const diff = Math.floor((now - time) / 1000)
  
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前'
  return time.toLocaleString('zh-CN')
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadNodes = async () => {
  loading.value = true
  try {
    const data = await getNodes()
    nodes.value = data
  } catch (error) {
    ElMessage.error('加载节点列表失败')
  } finally {
    loading.value = false
  }
}

const handleAddNode = async () => {
  if (!nodeForm.name || !nodeForm.host) {
    ElMessage.warning('请填写完整信息')
    return
  }

  // 解析标签
  if (labelsInput.value) {
    nodeForm.labels = labelsInput.value.split(',').reduce((acc, label, idx) => {
      acc[`label_${idx}`] = label.trim()
      return acc
    }, {})
  }

  adding.value = true
  try {
    await createNode(nodeForm)
    ElMessage.success('节点添加成功')
    showNodeDialog.value = false
    loadNodes()
    
    // 重置表单
    nodeForm.name = ''
    nodeForm.host = ''
    nodeForm.port = 2375
    nodeForm.labels = {}
    labelsInput.value = ''
  } catch (error) {
    ElMessage.error('添加节点失败')
  } finally {
    adding.value = false
  }
}

const testConnection = async (node) => {
  try {
    const result = await testNodeConnection(node.id)
    ElMessage.success(result.message)
    loadNodes()
  } catch (error) {
    ElMessage.error('连接测试失败')
  }
}

const handleHealthCheck = async () => {
  try {
    await checkNodesHealth()
    ElMessage.success('健康检查完成')
    loadNodes()
  } catch (error) {
    ElMessage.error('健康检查失败')
  }
}

const handleNodeAction = async (action, node) => {
  try {
    switch (action) {
      case 'activate':
        await activateNode(node.id)
        ElMessage.success('节点已激活')
        break
      case 'drain':
        await ElMessageBox.confirm('确定要排空此节点吗？所有容器将被停止。', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await drainNode(node.id)
        ElMessage.success('节点排空成功')
        break
      case 'delete':
        await ElMessageBox.confirm('确定要删除此节点吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteNode(node.id)
        ElMessage.success('节点删除成功')
        break
    }
    loadNodes()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const viewContainers = async (node) => {
  currentNode.value = node
  showContainersDialog.value = true
  loadingContainers.value = true
  
  try {
    const data = await getNodeContainers(node.id)
    containers.value = data.containers || []
  } catch (error) {
    ElMessage.error('加载容器列表失败')
    containers.value = []
  } finally {
    loadingContainers.value = false
  }
}

onMounted(() => {
  loadNodes()
})
</script>

<style scoped>
.nodes-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.node-card {
  margin-bottom: 20px;
}

.node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.node-name {
  font-weight: 600;
  font-size: 16px;
}

.node-info {
  margin-bottom: 15px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-item .label {
  color: #909399;
  font-size: 14px;
}

.info-item .value {
  color: #303133;
  font-size: 14px;
}

.node-actions {
  display: flex;
  gap: 8px;
}
</style>
