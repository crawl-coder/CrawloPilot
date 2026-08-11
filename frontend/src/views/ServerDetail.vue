<template>
  <div class="server-detail">
    <el-page-header @back="$router.back()">
      <template #content>
        <span class="page-title">{{ server?.name || '服务器详情' }}</span>
        <el-tag :type="statusType" size="small" style="margin-left: 12px">{{ statusText }}</el-tag>
      </template>
      <template #extra>
        <div class="header-actions">
          <el-button size="small" :loading="probing" @click="handleProbe">重新探测</el-button>
          <el-button size="small" @click="openEdit">编辑</el-button>
          <el-button
            v-if="server?.status !== 'maintenance'"
            size="small"
            type="warning"
            @click="handleMaintenance"
          >
            维护
          </el-button>
          <el-button v-else size="small" type="success" @click="handleRecover">退出维护</el-button>
          <el-button size="small" type="danger" @click="handleDelete">删除</el-button>
          <el-button type="primary" size="small" @click="showCreateChannel = true">
            <el-icon><Plus /></el-icon> 创建通道
          </el-button>
        </div>
      </template>
    </el-page-header>

    <!-- 服务器信息 -->
    <el-card shadow="hover" style="margin-top: 16px">
      <template #header><span>服务器信息</span></template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="IP 地址">{{ server?.host }}</el-descriptions-item>
        <el-descriptions-item label="机房">{{ server?.region || '-' }}</el-descriptions-item>
        <el-descriptions-item label="系统">{{ server?.os_type ? `${server.os_type} ${server.os_version || ''}` : '未探测' }}</el-descriptions-item>
        <el-descriptions-item label="CPU">{{ server?.cpu_cores || '-' }} 核</el-descriptions-item>
        <el-descriptions-item label="内存">{{ formatBytes(server?.memory_total) }}</el-descriptions-item>
        <el-descriptions-item label="最近探测">{{ formatTime(server?.last_probed_at) }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ server?.description || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 通道列表 -->
    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>执行通道（{{ channels.length }}）</span>
          <el-tag v-if="server?.online_channels" type="success" effect="plain">
            在线 {{ server.online_channels }}
          </el-tag>
        </div>
      </template>

      <el-empty v-if="channels.length === 0" description="暂无通道，点击右上角「创建通道」" />

      <template v-for="group in channelGroups" :key="group.type">
        <div class="channel-group-header">
          {{ group.label }}（{{ group.nodes.length }}）
        </div>
        <el-row :gutter="20" style="margin-bottom: 16px">
          <el-col
            v-for="n in group.nodes"
            :key="n.id"
            :xs="24" :sm="12" :md="8" :lg="6"
            style="margin-bottom: 16px"
          >
            <el-card class="channel-card" shadow="hover">
              <div class="channel-header">
                <span class="channel-name">{{ n.name }}</span>
                <el-tag :type="n.status === 'online' ? 'success' : 'info'" size="small">
                  {{ n.status === 'online' ? '在线' : n.status }}
                </el-tag>
              </div>
              <div class="channel-info">
                <div>{{ n.host }}:{{ n.port }}</div>
                <div v-if="n.connect_type === 'agent'" class="channel-agent">
                  Agent v{{ n.agent_version || '-' }}
                  <el-tag :type="n.agent_status === 'online' ? 'success' : 'info'" size="small">
                    {{ n.agent_status }}
                  </el-tag>
                </div>
                <div v-if="n.last_heartbeat" class="channel-meta">心跳 {{ formatTime(n.last_heartbeat) }}</div>
              </div>
              <div class="channel-actions">
                <el-button size="small" @click="testChannel(n)" :loading="testingId === n.id">测试</el-button>
                <el-button
                  v-if="n.status !== 'online'"
                  size="small"
                  type="primary"
                  @click="activateChannel(n)"
                >
                  激活
                </el-button>
                <el-button size="small" type="danger" @click="deleteChannel(n)">删除</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </template>
    </el-card>

    <!-- 创建通道对话框 -->
    <el-dialog v-model="showCreateChannel" title="创建执行通道" width="560px">
      <el-form :model="channelForm" label-width="110px">
        <el-form-item label="通道类型" required>
          <el-radio-group v-model="channelForm.connect_type">
            <el-radio value="ssh">SSH 直连</el-radio>
            <el-radio value="docker">Docker</el-radio>
            <el-radio value="agent">Agent</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="通道名称" required>
          <el-input v-model="channelForm.name" placeholder="如 jd-ssh-main" />
        </el-form-item>
        <template v-if="channelForm.connect_type === 'ssh'">
          <el-form-item label="SSH 用户">
            <el-input v-model="channelForm.ssh_user" placeholder="root" />
          </el-form-item>
          <el-form-item label="SSH 密码">
            <el-input v-model="channelForm.ssh_pwd" type="password" show-password />
          </el-form-item>
          <el-form-item label="SSH 私钥">
            <el-input v-model="channelForm.ssh_key" type="textarea" :rows="3" placeholder="可选" />
          </el-form-item>
        </template>
        <template v-if="channelForm.connect_type === 'docker'">
          <el-form-item label="Docker 地址">
            <el-input v-model="channelForm.docker_host" placeholder="留空默认 tcp://服务器IP:2375" />
          </el-form-item>
        </template>
        <template v-if="channelForm.connect_type === 'agent'">
          <el-alert
            title="创建后请在服务器上运行 agent 程序完成注册"
            type="info"
            :closable="false"
            show-icon
          />
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showCreateChannel = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreateChannel">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑服务器对话框 -->
    <el-dialog v-model="showEdit" title="编辑服务器" width="500px">
      <el-form :model="editForm" label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="机房">
          <el-input v-model="editForm.region" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSaveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getServer, updateServer, deleteServer, probeServer, enterMaintenance, recoverServer,
  getServerNodes, createServerNode
} from '@/api/server'
import { testNodeConnection, activateNode, deleteNode } from '@/api/node'
import { formatDateTime as formatTime } from '@/utils/common'

const route = useRoute()
const router = useRouter()
const serverId = route.params.id

const server = ref(null)
const channels = ref([])
const probing = ref(false)
const saving = ref(false)
const creating = ref(false)
const testingId = ref(null)
const showCreateChannel = ref(false)
const showEdit = ref(false)

const channelForm = reactive({
  name: '',
  connect_type: 'ssh',
  ssh_user: 'root',
  ssh_pwd: '',
  ssh_key: '',
  docker_host: ''
})

const editForm = reactive({
  name: '',
  region: '',
  description: ''
})

const statusType = computed(() => {
  const map = { online: 'success', offline: 'danger', maintenance: 'warning', unknown: 'info' }
  return map[server.value?.status] || 'info'
})
const statusText = computed(() => {
  const map = { online: '在线', offline: '离线', maintenance: '维护中', unknown: '无通道' }
  return map[server.value?.status] || server.value?.status
})
const channelGroups = computed(() => {
  const defs = [
    { type: 'ssh', label: 'SSH 通道' },
    { type: 'docker', label: 'Docker 通道' },
    { type: 'agent', label: 'Agent 通道' },
  ]
  return defs
    .map((d) => ({ ...d, nodes: channels.value.filter((n) => n.connect_type === d.type) }))
    .filter((g) => g.nodes.length > 0)
})

const formatBytes = (bytes) => {
  if (!bytes) return '-'
  const gb = bytes / (1024 ** 3)
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(0)} MB`
}

const load = async () => {
  try {
    server.value = await getServer(serverId)
    channels.value = await getServerNodes(serverId)
  } catch (error) {
    ElMessage.error('加载服务器详情失败')
  }
}

const handleProbe = async () => {
  probing.value = true
  try {
    const res = await probeServer(serverId)
    const os = res.os_version || res.os_type || ''
    ElMessage.success(`探测完成: ${res.status}（SSH:${res.ports?.ssh ? '通' : '不通'} Docker:${res.ports?.docker ? '通' : '不通'}${os ? ` 系统:${os}` : ''}）`)
    load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '探测失败')
  } finally {
    probing.value = false
  }
}

const openEdit = () => {
  editForm.name = server.value?.name || ''
  editForm.region = server.value?.region || ''
  editForm.description = server.value?.description || ''
  showEdit.value = true
}

const handleSaveEdit = async () => {
  saving.value = true
  try {
    await updateServer(serverId, editForm)
    ElMessage.success('保存成功')
    showEdit.value = false
    load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleMaintenance = async () => {
  await ElMessageBox.confirm('进入维护模式会先排空在线 Docker 通道，确定？', '维护', { type: 'warning' })
  try {
    await enterMaintenance(serverId)
    ElMessage.success('已进入维护模式')
    load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const handleRecover = async () => {
  await ElMessageBox.confirm('退出维护模式后将重新探测通道并恢复任务分配，确定？', '退出维护', { type: 'warning' })
  try {
    await recoverServer(serverId)
    ElMessage.success('已退出维护模式')
    load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const handleDelete = async () => {
  await ElMessageBox.confirm('删除服务器将同时删除其全部通道，且要求无在线通道，确定？', '删除', { type: 'warning' })
  try {
    await deleteServer(serverId)
    ElMessage.success('服务器已删除')
    router.back()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

const handleCreateChannel = async () => {
  if (!channelForm.name) {
    ElMessage.warning('请输入通道名称')
    return
  }
  creating.value = true
  try {
    const data = { ...channelForm }
    if (data.connect_type === 'ssh' && !data.ssh_pwd && !data.ssh_key) {
      ElMessage.warning('SSH 通道需要密码或私钥')
      return
    }
    const res = await createServerNode(serverId, data)
    showCreateChannel.value = false
    ElMessage.success('通道创建成功')
    if (res.connect_type === 'agent' && res.agent_token) {
      ElMessageBox.alert(
        `在服务器上运行：\npython crawlo_agent.py --server http://<管理服务器>:18000 --token ${res.agent_token}`,
        'Agent 注册令牌（仅显示一次）',
        { confirmButtonText: '我已复制' }
      )
    }
    load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建通道失败')
  } finally {
    creating.value = false
  }
}

const testChannel = async (n) => {
  testingId.value = n.id
  try {
    const res = await testNodeConnection(n.id)
    ElMessage.success(res.message || '连接成功')
    load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '连接失败')
  } finally {
    testingId.value = null
  }
}

const activateChannel = async (n) => {
  try {
    await activateNode(n.id)
    ElMessage.success('通道已激活')
    load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '激活失败')
  }
}

const deleteChannel = async (n) => {
  await ElMessageBox.confirm(`删除通道「${n.name}」？`, '删除', { type: 'warning' })
  try {
    await deleteNode(n.id)
    ElMessage.success('通道已删除')
    load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.server-detail {
  padding: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.channel-group-header {
  font-weight: 600;
  color: #606266;
  margin: 12px 0 10px;
}

.channel-card {
  height: 100%;
}

.channel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.channel-name {
  font-weight: 600;
}

.channel-info {
  font-size: 13px;
  color: #606266;
  margin-bottom: 12px;
}

.channel-agent {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.channel-meta {
  margin-top: 6px;
  color: #909399;
}

.channel-actions {
  display: flex;
  gap: 6px;
}
</style>
