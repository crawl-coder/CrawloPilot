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
            <el-button type="primary" @click="openAddDialog">
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
                <div class="node-title-row">
                  <span class="node-name">{{ node.name }}</span>
                  <el-tag v-if="node.connect_type === 'docker'" type="warning" size="small" effect="plain">Docker</el-tag>
                  <el-tag v-else-if="node.connect_type === 'ssh'" type="success" size="small" effect="plain">SSH</el-tag>
                  <el-tag v-else-if="node.connect_type === 'agent'" type="primary" size="small" effect="plain">Agent</el-tag>
                </div>
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
              <div class="info-item" v-if="node.os_type">
                <span class="label">系统:</span>
                <span class="value">{{ node.os_type }} {{ node.os_version || '' }}</span>
              </div>
              <div class="info-item" v-if="node.cpu_cores">
                <span class="label">CPU:</span>
                <span class="value">{{ node.cpu_cores }} 核</span>
              </div>

              <!-- 资源使用率 -->
              <div class="resource-bar" v-if="node.cpu_cores">
                <span class="label">CPU:</span>
                <el-progress :percentage="Number(node.cpu_usage)" :stroke-width="10" :status="usageStatus(node.cpu_usage)" class="resource-progress" />
              </div>
              <div class="resource-bar" v-if="node.memory_total">
                <span class="label">内存:</span>
                <el-progress :percentage="Number(node.memory_usage)" :stroke-width="10" :status="usageStatus(node.memory_usage)" class="resource-progress" />
                <span class="value">{{ formatBytes(node.memory_total) }}</span>
              </div>
              <div class="resource-bar" v-if="node.disk_total">
                <span class="label">磁盘:</span>
                <el-progress :percentage="Number(node.disk_usage)" :stroke-width="10" :status="usageStatus(node.disk_usage)" class="resource-progress" />
                <span class="value">{{ formatBytes(node.disk_total) }}</span>
              </div>

              <div class="info-item" v-if="node.agent_version">
                <span class="label">Agent:</span>
                <span class="value">v{{ node.agent_version }}</span>
              </div>
              <div class="info-item" v-if="node.last_heartbeat">
                <span class="label">心跳:</span>
                <span class="value">{{ formatTime(node.last_heartbeat) }}</span>
              </div>
              <div class="info-item" v-if="node.container_count !== undefined && node.connect_type === 'docker'">
                <span class="label">容器数:</span>
                <span class="value">{{ node.container_count }}</span>
              </div>
            </div>

            <div class="node-actions">
              <el-button size="small" @click="testConnection(node)">测试</el-button>
              <el-button size="small" v-if="node.connect_type === 'docker'" @click="viewContainers(node)">容器</el-button>
              <el-button size="small" type="primary" plain @click="openEditDialog(node)">编辑</el-button>
              <el-dropdown @command="(cmd) => handleNodeAction(cmd, node)">
                <el-button size="small">
                  更多<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="activate" v-if="node.status !== 'online'">激活</el-dropdown-item>
                    <el-dropdown-item command="drain" v-if="node.status === 'online' && node.connect_type === 'docker'">排空</el-dropdown-item>
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
    <el-dialog v-model="showAddDialog" title="添加节点" width="600px">
      <el-form :model="nodeForm" label-width="120px">
        <el-form-item label="节点名称" required>
          <el-input v-model="nodeForm.name" placeholder="例如: beijing-server-1" />
        </el-form-item>
        <el-form-item label="连接方式" required>
          <el-radio-group v-model="nodeForm.connect_type" @change="onConnectTypeChange">
            <el-radio value="ssh">SSH 直连</el-radio>
            <el-tooltip content="Agent 模式 v2 支持，当前版本请使用 SSH 直连" placement="top">
              <span>
                <el-radio value="agent" disabled>Agent 代理（即将支持）</el-radio>
              </span>
            </el-tooltip>
            <el-radio value="docker">Docker API</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="主机地址" required>
          <el-input v-model="nodeForm.host" placeholder="例如: 192.168.1.100" />
        </el-form-item>
        <el-form-item :label="portLabel">
          <el-input-number v-model="nodeForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="SSH 用户" v-if="nodeForm.connect_type === 'ssh'">
          <el-input v-model="nodeForm.ssh_user" placeholder="root" />
        </el-form-item>
        <template v-if="nodeForm.connect_type === 'ssh'">
          <el-form-item label="SSH 密码">
            <el-input v-model="nodeForm.ssh_pwd" type="password" show-password placeholder="可选（与私钥二选一）" />
          </el-form-item>
          <el-form-item label="SSH 私钥">
            <el-input
              v-model="nodeForm.ssh_key"
              type="textarea"
              :rows="4"
              placeholder="-----BEGIN OPENSSH PRIVATE KEY----- ...（与密码二选一）"
            />
          </el-form-item>
        </template>
        <el-form-item label="公网 IP">
          <el-input v-model="nodeForm.public_ip" placeholder="可选" />
        </el-form-item>
        <el-form-item label="内网 IP">
          <el-input v-model="nodeForm.private_ip" placeholder="可选" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="labelsInput" placeholder="逗号分隔，例如: prod,beijing,high-memory" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddNode" :loading="adding">添加</el-button>
      </template>
    </el-dialog>

    <!-- 编辑节点对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑节点" width="600px">
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="节点名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="主机地址">
          <el-input v-model="editForm.host" />
        </el-form-item>
        <el-form-item label="连接端口">
          <el-input-number v-model="editForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="SSH 用户" v-if="editForm.connect_type === 'ssh'">
          <el-input v-model="editForm.ssh_user" />
        </el-form-item>
        <template v-if="editForm.connect_type === 'ssh'">
          <el-form-item label="SSH 密码">
            <el-input v-model="editForm.ssh_pwd" type="password" show-password placeholder="留空表示不修改" />
          </el-form-item>
          <el-form-item label="SSH 私钥">
            <el-input
              v-model="editForm.ssh_key"
              type="textarea"
              :rows="4"
              placeholder="留空表示不修改"
            />
          </el-form-item>
        </template>
        <el-form-item label="公网 IP">
          <el-input v-model="editForm.public_ip" />
        </el-form-item>
        <el-form-item label="内网 IP">
          <el-input v-model="editForm.private_ip" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editLabelsInput" placeholder="逗号分隔，例如: prod,high-memory" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleEditNode" :loading="editing">保存</el-button>
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
import { ref, reactive, onMounted, computed } from 'vue'
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
  getNodeContainers,
  updateNode
} from '@/api/node'

const nodes = ref([])
const containers = ref([])
const loading = ref(false)
const loadingContainers = ref(false)
const adding = ref(false)
const editing = ref(false)
const showAddDialog = ref(false)
const showEditDialog = ref(false)
const showContainersDialog = ref(false)
const currentNode = ref(null)

const portLabel = computed(() => {
  if (nodeForm.connect_type === 'docker') return 'Docker 端口'
  return '连接端口'
})

const nodeForm = reactive({
  name: '',
  host: '',
  port: 22,
  connect_type: 'ssh',
  ssh_user: 'root',
  ssh_pwd: '',
  ssh_key: '',
  public_ip: '',
  private_ip: '',
  labels: {}
})

const editForm = reactive({
  id: null,
  name: '',
  host: '',
  port: 22,
  connect_type: 'ssh',
  ssh_user: 'root',
  ssh_pwd: '',
  ssh_key: '',
  public_ip: '',
  private_ip: '',
  labels: {}
})

const labelsInput = ref('')
const editLabelsInput = ref('')

const formatBytes = (bytes) => {
  if (!bytes || bytes === 0) return '-'
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

const usageStatus = (value) => {
  const v = Number(value)
  if (v >= 90) return 'exception'
  if (v >= 70) return 'warning'
  return 'success'
}

const onConnectTypeChange = () => {
  if (nodeForm.connect_type === 'docker') {
    nodeForm.port = 2375
  } else if (nodeForm.connect_type === 'ssh') {
    nodeForm.port = 22
  } else {
    nodeForm.port = 22
  }
}

const openAddDialog = () => {
  nodeForm.name = ''
  nodeForm.host = ''
  nodeForm.port = 22
  nodeForm.connect_type = 'ssh'
  nodeForm.ssh_user = 'root'
  nodeForm.ssh_pwd = ''
  nodeForm.ssh_key = ''
  nodeForm.public_ip = ''
  nodeForm.private_ip = ''
  nodeForm.labels = {}
  labelsInput.value = ''
  showAddDialog.value = true
}

const openEditDialog = (node) => {
  editForm.id = node.id
  editForm.name = node.name
  editForm.host = node.host
  editForm.port = node.port
  editForm.connect_type = node.connect_type
  editForm.ssh_user = node.ssh_user || 'root'
  editForm.ssh_pwd = ''
  editForm.ssh_key = ''
  editForm.public_ip = node.public_ip || ''
  editForm.private_ip = node.private_ip || ''
  
  if (node.labels && typeof node.labels === 'object') {
    editLabelsInput.value = Object.values(node.labels).join(', ')
  } else {
    editLabelsInput.value = ''
  }
  
  showEditDialog.value = true
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
    ElMessage.success('节点添加成功，正在测试连接...')
    showAddDialog.value = false
    loadNodes()

    // 添加后自动测试连接，给出即时反馈
    try {
      const list = await getNodes()
      const created = list.find(n => n.name === nodeForm.name)
      if (created) {
        const result = await testNodeConnection(created.id)
        ElMessage.success(result.message || '连接测试成功')
        loadNodes()
      }
    } catch (testError) {
      ElMessage.warning(testError.response?.data?.detail || '连接测试失败，节点状态为离线')
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加节点失败')
  } finally {
    adding.value = false
  }
}

const handleEditNode = async () => {
  editing.value = true
  try {
    const data = { ...editForm }
    delete data.id

    // 密码/私钥留空表示不修改
    if (!data.ssh_pwd) delete data.ssh_pwd
    if (!data.ssh_key) delete data.ssh_key
    
    // 解析标签
    if (editLabelsInput.value) {
      data.labels = editLabelsInput.value.split(',').reduce((acc, label, idx) => {
        acc[`label_${idx}`] = label.trim()
        return acc
      }, {})
    }
    
    await updateNode(editForm.id, data)
    ElMessage.success('节点更新成功')
    showEditDialog.value = false
    loadNodes()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新节点失败')
  } finally {
    editing.value = false
  }
}

const testConnection = async (node) => {
  try {
    const result = await testNodeConnection(node.id)
    ElMessage.success(result.message || '连接测试成功')
    loadNodes()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '连接测试失败')
  }
}

const handleHealthCheck = async () => {
  try {
    await checkNodesHealth()
    ElMessage.success('健康检查完成')
    loadNodes()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '健康检查失败')
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
      ElMessage.error(error.response?.data?.detail || '操作失败')
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
    ElMessage.error(error.response?.data?.detail || '加载容器列表失败')
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

.node-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
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

.resource-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #f0f0f0;
}

.resource-bar .label {
  color: #909399;
  font-size: 14px;
  min-width: 40px;
  flex-shrink: 0;
}

.resource-bar .value {
  color: #909399;
  font-size: 12px;
  min-width: 70px;
  text-align: right;
  flex-shrink: 0;
}

.resource-progress {
  flex: 1;
}

.node-actions {
  display: flex;
  gap: 8px;
}
</style>
