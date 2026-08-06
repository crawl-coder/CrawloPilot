<template>
  <div class="nodes-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h3>节点管理</h3>
          <div>
            <el-button @click="openAddServer">
              <el-icon><Plus /></el-icon>
              添加服务器
            </el-button>
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

      <!-- 类型 Tab：服务器 / 三种通道 -->
      <el-tabs v-model="activeType" class="node-tabs" @tab-change="resetPage">
        <el-tab-pane :label="`服务器 (${servers.length})`" name="servers" />
        <el-tab-pane :label="`SSH 通道 (${typeCount('ssh')})`" name="ssh" />
        <el-tab-pane :label="`Docker 通道 (${typeCount('docker')})`" name="docker" />
        <el-tab-pane :label="`Agent 通道 (${typeCount('agent')})`" name="agent" />
      </el-tabs>

      <!-- 工具栏：搜索 / 状态筛选 / 统计 -->
      <div class="node-toolbar">
        <div class="node-filters">
          <el-input
            v-model="keyword"
            placeholder="搜索名称/地址"
            clearable
            style="width: 220px"
            @input="resetPage"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-select
            v-model="statusFilter"
            placeholder="全部状态"
            clearable
            style="width: 140px"
            @change="resetPage"
          >
            <el-option label="在线" value="online" />
            <el-option label="离线" value="offline" />
            <el-option label="维护中" value="maintenance" />
            <el-option label="排空中" value="draining" />
          </el-select>
        </div>
        <div class="node-summary">
          <template v-if="activeType === 'servers'">
            <el-tag type="info" effect="plain">服务器 {{ servers.length }}</el-tag>
            <el-tag type="success" effect="plain">在线 {{ serverOnlineCount }}</el-tag>
            <el-tag type="danger" effect="plain">离线 {{ serverOfflineCount }}</el-tag>
            <el-tag v-if="serverMaintenanceCount > 0" type="warning" effect="plain">维护 {{ serverMaintenanceCount }}</el-tag>
          </template>
          <template v-else>
            <el-tag type="info" effect="plain">总数 {{ nodes.length }}</el-tag>
            <el-tag type="success" effect="plain">在线 {{ onlineCount }}</el-tag>
            <el-tag type="danger" effect="plain">离线 {{ offlineCount }}</el-tag>
            <el-tag v-if="maintenanceCount > 0" type="warning" effect="plain">维护 {{ maintenanceCount }}</el-tag>
          </template>
        </div>
      </div>

      <!-- 服务器列表 -->
      <el-row v-if="activeType === 'servers'" :gutter="20" class="node-group-row">
        <el-col
          v-for="sv in pagedServers"
          :key="sv.id"
          :xs="24" :sm="12" :md="8" :lg="6"
          style="margin-bottom: 20px"
        >
          <el-card class="node-card" shadow="hover" @click="goServer(sv)">
            <template #header>
              <div class="node-header">
                <span class="node-name">{{ sv.name }}</span>
                <el-tag :type="serverStatusType(sv.status)" size="small">{{ serverStatusText(sv.status) }}</el-tag>
              </div>
            </template>
            <div class="node-info">
              <div class="info-item"><span class="label">IP:</span><span class="value">{{ sv.host }}</span></div>
              <div class="info-item"><span class="label">机房:</span><span class="value">{{ sv.region || '-' }}</span></div>
              <div class="info-item"><span class="label">系统:</span><span class="value">{{ sv.os_type ? sv.os_type + ' ' + (sv.os_version || '') : '未探测' }}</span></div>
              <div class="info-item"><span class="label">资源:</span><span class="value">{{ sv.cpu_cores || '-' }}核 / {{ formatServerBytes(sv.memory_total) }}</span></div>
              <div class="info-item">
                <span class="label">通道:</span>
                <span class="value">
                  <el-tag v-if="sv.channel_summary?.ssh" size="small" effect="plain">SSH {{ sv.channel_summary.ssh }}</el-tag>
                  <el-tag v-if="sv.channel_summary?.docker" size="small" effect="plain" style="margin-left:4px">Docker {{ sv.channel_summary.docker }}</el-tag>
                  <el-tag v-if="sv.channel_summary?.agent" size="small" effect="plain" style="margin-left:4px">Agent {{ sv.channel_summary.agent }}</el-tag>
                  <span v-if="sv.online_channels">· {{ sv.online_channels }} 在线</span>
                </span>
              </div>
            </div>
            <div class="node-actions" @click.stop>
              <el-button size="small" type="primary" @click="goServer(sv)">详情</el-button>
              <el-button size="small" @click="probeServerCard(sv)">探测</el-button>
              <el-button size="small" type="danger" @click="deleteServerCard(sv)">删除</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
      <el-empty v-if="activeType === 'servers' && servers.length === 0" description="暂无服务器，请添加真实主机" />
      <el-empty v-else-if="activeType === 'servers' && serverTotal === 0" description="无匹配的服务器" />

      <!-- 通道列表 -->
      <template v-if="activeType !== 'servers'">
      <el-row :gutter="20" class="node-group-row">
        <el-col
          v-for="node in pagedNodes"
          :key="node.id"
          :xs="24" :sm="12" :md="8" :lg="6"
          style="margin-bottom: 20px"
        >
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
              <div class="info-item" v-if="node.connect_type === 'agent'">
                <span class="label">Agent状态:</span>
                <el-tag :type="node.agent_status === 'online' ? 'success' : 'info'" size="small">
                  {{ node.agent_status === 'online' ? '在线' : '离线' }}
                </el-tag>
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
      <el-empty v-else-if="total === 0" description="无匹配的节点" />
      </template>

      <!-- 分页（节点多时） -->
      <el-pagination
        v-if="activeType === 'servers' && serverTotal > serverPageSize"
        v-model:current-page="serverPage"
        :page-size="serverPageSize"
        :page-sizes="[12, 24, 48]"
        :total="serverTotal"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 12px; justify-content: flex-end"
        @current-change="scrollTop"
      />
      <el-pagination
        v-if="activeType !== 'servers' && total > pageSize"
        v-model:current-page="page"
        :page-size="pageSize"
        :page-sizes="[12, 24, 48]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 12px; justify-content: flex-end"
        @size-change="resetPage"
        @current-change="scrollTop"
      />
    </el-card>

    <!-- 添加服务器对话框 -->
    <el-dialog v-model="showAddServer" title="添加服务器" width="520px">
      <el-form :model="serverForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="serverForm.name" placeholder="如 beijing-web-01" />
        </el-form-item>
        <el-form-item label="IP 地址" required>
          <el-input v-model="serverForm.host" placeholder="如 117.72.16.51" />
        </el-form-item>
        <el-form-item label="机房">
          <el-input v-model="serverForm.region" placeholder="可选" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="serverForm.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddServer = false">取消</el-button>
        <el-button type="primary" :loading="addingServer" @click="handleAddServer">添加</el-button>
      </template>
    </el-dialog>

    <!-- 添加节点对话框 -->
    <el-dialog v-model="showAddDialog" title="添加节点" width="600px">
      <el-form :model="nodeForm" label-width="120px">
        <el-form-item label="节点名称" required>
          <el-input v-model="nodeForm.name" placeholder="例如: beijing-server-1" />
        </el-form-item>
        <el-form-item label="连接方式" required>
          <el-radio-group v-model="nodeForm.connect_type" @change="onConnectTypeChange">
            <el-radio value="ssh">SSH 直连</el-radio>
            <el-radio value="agent">Agent 代理</el-radio>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, ArrowDown, Search } from '@element-plus/icons-vue'
import {
  getServers, createServer, deleteServer, probeServer
} from '@/api/server'
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
const router = useRouter()
const containers = ref([])
const loading = ref(false)
const loadingContainers = ref(false)
const adding = ref(false)
const editing = ref(false)
const showAddDialog = ref(false)
const showEditDialog = ref(false)
const showContainersDialog = ref(false)
const currentNode = ref(null)

// ============ 列表：搜索 / 筛选 / 分页 / 分组 ============

const keyword = ref('')
const statusFilter = ref('')
const activeType = ref('servers')
const page = ref(1)
const pageSize = ref(12)

// ============ 服务器数据 ============

const servers = ref([])
const serverLoading = ref(false)
const serverPage = ref(1)
const serverPageSize = ref(12)
const showAddServer = ref(false)
const addingServer = ref(false)
const serverForm = reactive({
  name: '',
  host: '',
  region: '',
  description: ''
})

const serverOnlineCount = computed(() => servers.value.filter((s) => s.status === 'online').length)
const serverOfflineCount = computed(() => servers.value.filter((s) => s.status === 'offline').length)
const serverMaintenanceCount = computed(() =>
  servers.value.filter((s) => ['maintenance', 'unknown'].includes(s.status)).length
)

const filteredServers = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return servers.value.filter((s) => {
    if (statusFilter.value && s.status !== statusFilter.value) return false
    if (kw && !`${s.name} ${s.host}`.toLowerCase().includes(kw)) return false
    return true
  })
})

const serverTotal = computed(() => filteredServers.value.length)
const pagedServers = computed(() =>
  filteredServers.value.slice(
    (serverPage.value - 1) * serverPageSize.value,
    serverPage.value * serverPageSize.value
  )
)

const loadServers = async () => {
  serverLoading.value = true
  try {
    const res = await getServers({ limit: 100 })
    servers.value = res.items || []
  } catch (error) {
    ElMessage.error('加载服务器列表失败')
  } finally {
    serverLoading.value = false
  }
}

const serverStatusType = (status) => {
  const map = { online: 'success', offline: 'danger', maintenance: 'warning', unknown: 'info' }
  return map[status] || 'info'
}

const serverStatusText = (status) => {
  const map = { online: '在线', offline: '离线', maintenance: '维护中', unknown: '未探测' }
  return map[status] || status
}

const formatServerBytes = (bytes) => {
  if (!bytes) return '-'
  const gb = bytes / (1024 ** 3)
  return gb >= 1 ? `${gb.toFixed(1)}G` : `${Math.round(bytes / 1024 ** 2)}M`
}

const goServer = (sv) => {
  router.push(`/servers/${sv.id}`)
}

const openAddServer = () => {
  serverForm.name = ''
  serverForm.host = ''
  serverForm.region = ''
  serverForm.description = ''
  showAddServer.value = true
}

const handleAddServer = async () => {
  if (!serverForm.name || !serverForm.host) {
    ElMessage.warning('请填写名称和 IP')
    return
  }
  addingServer.value = true
  try {
    const res = await createServer(serverForm)
    ElMessage.success('服务器已添加')
    showAddServer.value = false
    loadServers()
    if (res.probe) {
      ElMessage.info(`探测完成: SSH ${res.probe.ports?.ssh ? '通' : '不通'} / Docker ${res.probe.ports?.docker ? '通' : '不通'}`)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加服务器失败')
  } finally {
    addingServer.value = false
  }
}

const probeServerCard = async (sv) => {
  try {
    const res = await probeServer(sv.id)
    ElMessage.success(`探测完成: ${res.status}`)
    loadServers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '探测失败')
  }
}

const deleteServerCard = async (sv) => {
  await ElMessageBox.confirm(`删除服务器「${sv.name}」及其通道？`, '删除', { type: 'warning' })
  try {
    await deleteServer(sv.id)
    ElMessage.success('服务器已删除')
    loadServers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

const onlineCount = computed(() => nodes.value.filter((n) => n.status === 'online').length)
const offlineCount = computed(() => nodes.value.filter((n) => n.status === 'offline').length)
const maintenanceCount = computed(
  () => nodes.value.filter((n) => ['maintenance', 'draining'].includes(n.status)).length
)

const typeCount = (type) => nodes.value.filter((n) => n.connect_type === type).length

const filteredNodes = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return nodes.value.filter((n) => {
    if (statusFilter.value && n.status !== statusFilter.value) return false
    if (kw && !`${n.name} ${n.host} ${n.public_ip || ''} ${n.private_ip || ''}`.toLowerCase().includes(kw)) {
      return false
    }
    return true
  })
})

// 当前 Tab 下的节点（全部或指定类型）
const displayNodes = computed(() => {
  if (activeType.value === 'servers') return []
  return filteredNodes.value.filter((n) => n.connect_type === activeType.value)
})

const total = computed(() => displayNodes.value.length)
const pagedNodes = computed(() =>
  displayNodes.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value)
)

const resetPage = () => {
  page.value = 1
}

const scrollTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

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
    const created = await createNode(nodeForm)
    ElMessage.success('节点添加成功')
    showAddDialog.value = false
    loadNodes()

    if (nodeForm.connect_type === 'agent') {
      // Agent 节点：展示注册令牌，由节点上的 agent 程序使用
      ElMessageBox.alert(
        `请在节点服务器上运行：\n\npython crawlo_agent.py --server http://<控制端>:8000 --token ${created.agent_token}\n\nAgent 启动后会自动注册并上线。`,
        'Agent 注册令牌（仅显示一次）',
        { confirmButtonText: '我已复制' }
      )
    } else {
      // 其他类型：添加后自动测试连接，给出即时反馈
      try {
        const result = await testNodeConnection(created.id)
        ElMessage.success(result.message || '连接测试成功')
        loadNodes()
      } catch (testError) {
        ElMessage.warning(testError.response?.data?.detail || '连接测试失败，节点状态为离线')
      }
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
  loadServers()
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
  height: 100%;
  display: flex;
  flex-direction: column;
}

.node-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.node-tabs {
  margin-bottom: 4px;
}

.node-group-row {
  margin-bottom: 4px;
}

.node-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}

.node-filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.node-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
  flex: 1;
  margin-bottom: 15px;
  min-height: 150px;
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
  padding-top: 10px;
  border-top: 1px solid #f0f0f0;
}
</style>
