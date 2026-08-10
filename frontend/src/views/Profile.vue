<template>
  <div class="profile-container">
    <div class="page-header">
      <h2>个人中心</h2>
      <span class="page-subtitle">账号信息与 Git 凭据管理</span>
    </div>

    <!-- 身份卡 -->
    <el-card class="profile-card cp-animate-in" shadow="never">
      <div class="hero">
        <div class="hero-avatar">{{ avatarInitial }}</div>
        <div class="hero-info">
          <div class="hero-name-row">
            <span class="hero-name">{{ userStore.username }}</span>
            <el-tag
              v-for="role in userStore.user?.roles || []"
              :key="role.id"
              :type="role.name === 'admin' ? 'primary' : 'info'"
              effect="light"
              size="small"
              round
            >
              {{ role.name }}
            </el-tag>
          </div>
          <div class="hero-meta">
            <span class="meta-item">
              <el-icon><Message /></el-icon>{{ userStore.user?.email || '未设置邮箱' }}
            </span>
            <span class="meta-item">
              <el-icon><User /></el-icon>{{ userStore.user?.full_name || '未设置姓名' }}
            </span>
            <span class="meta-item">
              <el-icon><Calendar /></el-icon>注册于 {{ formatDateTime(userStore.user?.created_at) }}
            </span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 我的 Git 凭据 -->
    <el-card class="profile-card cp-animate-in" shadow="never">
      <template #header>
        <div class="panel-header">
          <div class="panel-title">
            <span class="panel-icon icon-key"><el-icon><Key /></el-icon></span>
            <h3>我的 Git 凭据</h3>
          </div>
          <span class="status-pill" :class="myCred.configured ? 'is-on' : 'is-off'">
            <span class="pill-dot"></span>{{ myCred.configured ? '已配置' : '未配置' }}
          </span>
        </div>
      </template>

      <div class="card-tip">
        配置后，创建爬虫时可一键使用本人的 Git 凭据，无需重复填写。凭据加密存储，仅本人可用。
      </div>

      <!-- 已配置摘要 -->
      <div v-if="myCred.configured" class="cred-summary">
        <el-tag :type="myCred.auth_type === 'ssh' ? 'warning' : 'primary'" effect="plain" size="small">
          {{ myCred.auth_type === 'ssh' ? 'SSH密钥' : '密码/Token' }}
        </el-tag>
        <span v-if="myCred.username" class="summary-item">
          <el-icon><User /></el-icon>{{ myCred.username }}
        </span>
        <span v-if="myCred.default_branch" class="summary-item">
          <el-icon><Share /></el-icon>{{ myCred.default_branch }}
        </span>
        <span class="summary-item summary-secret">
          <el-icon><Lock /></el-icon>秘密已加密存储
        </span>
      </div>

      <el-form :model="myCredForm" label-width="110px" style="max-width: 560px">
        <el-form-item label="认证方式">
          <el-radio-group v-model="myCredForm.auth_type">
            <el-radio value="password">密码/Token</el-radio>
            <el-radio value="ssh">SSH密钥</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="myCredForm.auth_type === 'password'">
          <el-form-item label="用户名">
            <el-input v-model="myCredForm.username" placeholder="Git 用户名" />
          </el-form-item>
          <el-form-item label="密码/Token">
            <div class="input-with-tip">
              <el-input
                v-model="myCredForm.password"
                type="password"
                show-password
                :placeholder="myCred.has_password ? '已配置，留空保持不变' : '请输入密码或访问令牌'"
              />
              <el-tooltip placement="top" content="GitHub：Settings → Developer settings → Personal access tokens（Tokens (classic) 勾选 repo）">
                <span class="field-tip"><el-icon><QuestionFilled /></el-icon>如何获取 Token？</span>
              </el-tooltip>
            </div>
          </el-form-item>
        </template>

        <template v-if="myCredForm.auth_type === 'ssh'">
          <el-form-item label="SSH私钥">
            <div class="input-with-tip">
              <el-input
                v-model="myCredForm.ssh_key"
                type="textarea"
                :rows="4"
                :placeholder="myCred.has_ssh_key ? '已配置，留空保持不变' : '-----BEGIN OPENSSH PRIVATE KEY-----'"
              />
              <span class="field-tip">
                <el-icon><QuestionFilled /></el-icon>
                <code>ssh-keygen -t ed25519</code> 生成后粘贴私钥内容；公钥添加到 Git 平台
              </span>
            </div>
          </el-form-item>
        </template>

        <el-form-item label="默认分支">
          <el-input v-model="myCredForm.default_branch" placeholder="可选，如 main" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="myCredSaving" @click="saveMyCred">保存</el-button>
          <el-popconfirm
            v-if="myCred.configured"
            title="确定清除个人 Git 凭据？"
            @confirm="clearMyCred"
          >
            <template #reference>
              <el-button type="danger" plain>清除</el-button>
            </template>
          </el-popconfirm>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 共享 Git 凭据（团队机器人，仅 admin 可管理） -->
    <el-card v-if="userStore.isAdmin" class="profile-card cp-animate-in" shadow="never">
      <template #header>
        <div class="panel-header">
          <div class="panel-title">
            <span class="panel-icon icon-team"><el-icon><Connection /></el-icon></span>
            <h3>共享 Git 凭据</h3>
            <span class="panel-sub">团队机器人账号 / Deploy Key</span>
          </div>
          <el-button type="primary" size="small" @click="showCredDialog()">
            <el-icon><Plus /></el-icon>
            新建凭据
          </el-button>
        </div>
      </template>
      <div class="card-tip">
        全体成员创建爬虫时可引用。建议配合 Git 平台的只读或受限权限账号使用。
      </div>
      <el-table :data="sharedCreds" v-loading="sharedLoading" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="140">
          <template #default="{ row }">
            <span class="cred-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="认证方式" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.auth_type === 'ssh' ? 'warning' : 'primary'" effect="plain">
              {{ row.auth_type === 'ssh' ? 'SSH密钥' : '密码/Token' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" min-width="120">
          <template #default="{ row }">{{ row.username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="default_branch" label="默认分支" width="110">
          <template #default="{ row }">{{ row.default_branch || '-' }}</template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="status-pill" :class="row.is_active ? 'is-on' : 'is-off'">
              <span class="pill-dot"></span>{{ row.is_active ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showCredDialog(row)">编辑</el-button>
            <el-button
              size="small"
              :type="row.is_active ? 'warning' : 'success'"
              plain
              @click="toggleCred(row)"
            >
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" plain @click="removeCred(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无共享凭据" :image-size="80" />
        </template>
      </el-table>
    </el-card>

    <!-- 共享凭据编辑对话框 -->
    <el-dialog
      v-model="credDialogVisible"
      :title="editingCred ? '编辑共享凭据' : '新建共享凭据'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form :model="credForm" label-width="110px">
        <el-form-item label="名称" required>
          <el-input v-model="credForm.name" placeholder="如：GitLab 只读机器人" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="credForm.description" placeholder="用途说明，可选" />
        </el-form-item>
        <el-form-item label="认证方式">
          <el-radio-group v-model="credForm.auth_type">
            <el-radio value="password">密码/Token</el-radio>
            <el-radio value="ssh">SSH密钥</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="credForm.auth_type === 'password'">
          <el-form-item label="用户名">
            <el-input v-model="credForm.username" placeholder="Git 用户名" />
          </el-form-item>
          <el-form-item label="密码/Token">
            <el-input
              v-model="credForm.password"
              type="password"
              show-password
              :placeholder="editingCred?.has_password ? '已配置，留空保持不变' : '请输入密码或访问令牌'"
            />
          </el-form-item>
        </template>

        <template v-if="credForm.auth_type === 'ssh'">
          <el-form-item label="SSH私钥">
            <el-input
              v-model="credForm.ssh_key"
              type="textarea"
              :rows="4"
              :placeholder="editingCred?.has_ssh_key ? '已配置，留空保持不变' : '-----BEGIN OPENSSH PRIVATE KEY-----'"
            />
          </el-form-item>
        </template>

        <el-form-item label="默认分支">
          <el-input v-model="credForm.default_branch" placeholder="可选，如 main" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="credDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="credSaving" @click="saveCred">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Key, Connection, Message, User, Calendar, Share, Lock, QuestionFilled } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getMyGitCredentials, saveMyGitCredentials, deleteMyGitCredentials } from '@/api/auth'
import {
  getGitCredentials,
  createGitCredential,
  updateGitCredential,
  deleteGitCredential,
} from '@/api/git-credential'
import { formatDateTime } from '@/utils/common'

const userStore = useUserStore()

const avatarInitial = computed(() => (userStore.username || '?').charAt(0).toUpperCase())

// ==================== 我的 Git 凭据 ====================

const myCred = ref({ configured: false })
const myCredSaving = ref(false)
const myCredForm = reactive({
  auth_type: 'password',
  username: '',
  password: '',
  ssh_key: '',
  default_branch: ''
})

const loadMyCred = async () => {
  try {
    const res = await getMyGitCredentials()
    myCred.value = res
    if (res.configured) {
      myCredForm.auth_type = res.auth_type || 'password'
      myCredForm.username = res.username || ''
      myCredForm.default_branch = res.default_branch || ''
      // 秘密字段不回填，留空表示保持不变
      myCredForm.password = ''
      myCredForm.ssh_key = ''
    }
  } catch (error) {
    // 读取失败不阻塞页面
  }
}

const saveMyCred = async () => {
  const isPassword = myCredForm.auth_type === 'password'
  if (isPassword && !myCredForm.password && !myCred.value.has_password) {
    ElMessage.warning('请输入密码/Token')
    return
  }
  if (!isPassword && !myCredForm.ssh_key && !myCred.value.has_ssh_key) {
    ElMessage.warning('请输入 SSH 私钥')
    return
  }
  myCredSaving.value = true
  try {
    const res = await saveMyGitCredentials({
      auth_type: myCredForm.auth_type,
      username: myCredForm.username || null,
      password: myCredForm.password || null,
      ssh_key: myCredForm.ssh_key || null,
      default_branch: myCredForm.default_branch || null
    })
    myCred.value = res
    myCredForm.password = ''
    myCredForm.ssh_key = ''
    ElMessage.success('个人 Git 凭据已保存')
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    }
  } finally {
    myCredSaving.value = false
  }
}

const clearMyCred = async () => {
  try {
    await deleteMyGitCredentials()
    myCred.value = { configured: false }
    myCredForm.password = ''
    myCredForm.ssh_key = ''
    ElMessage.success('已清除个人 Git 凭据')
  } catch (error) {
    ElMessage.error('清除失败')
  }
}

// ==================== 共享 Git 凭据（admin） ====================

const sharedCreds = ref([])
const sharedLoading = ref(false)
const credDialogVisible = ref(false)
const credSaving = ref(false)
const editingCred = ref(null)
const credForm = reactive({
  name: '',
  description: '',
  auth_type: 'password',
  username: '',
  password: '',
  ssh_key: '',
  default_branch: ''
})

const loadSharedCreds = async () => {
  if (!userStore.isAdmin) return
  sharedLoading.value = true
  try {
    sharedCreds.value = await getGitCredentials({ include_inactive: true })
  } catch (error) {
    // 忽略
  } finally {
    sharedLoading.value = false
  }
}

const showCredDialog = (row = null) => {
  editingCred.value = row
  Object.assign(credForm, {
    name: row?.name || '',
    description: row?.description || '',
    auth_type: row?.auth_type || 'password',
    username: row?.username || '',
    password: '',
    ssh_key: '',
    default_branch: row?.default_branch || ''
  })
  credDialogVisible.value = true
}

const saveCred = async () => {
  if (!credForm.name.trim()) {
    ElMessage.warning('请输入凭据名称')
    return
  }
  const isPassword = credForm.auth_type === 'password'
  if (isPassword && !credForm.password && !editingCred.value?.has_password) {
    ElMessage.warning('请输入密码/Token')
    return
  }
  if (!isPassword && !credForm.ssh_key && !editingCred.value?.has_ssh_key) {
    ElMessage.warning('请输入 SSH 私钥')
    return
  }
  credSaving.value = true
  try {
    const payload = {
      name: credForm.name.trim(),
      description: credForm.description || null,
      auth_type: credForm.auth_type,
      username: credForm.username || null,
      password: credForm.password || null,
      ssh_key: credForm.ssh_key || null,
      default_branch: credForm.default_branch || null
    }
    if (editingCred.value) {
      await updateGitCredential(editingCred.value.id, payload)
      ElMessage.success('凭据已更新')
    } else {
      await createGitCredential(payload)
      ElMessage.success('凭据已创建')
    }
    credDialogVisible.value = false
    loadSharedCreds()
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    }
  } finally {
    credSaving.value = false
  }
}

const toggleCred = async (row) => {
  try {
    await updateGitCredential(row.id, { is_active: !row.is_active })
    ElMessage.success(row.is_active ? '已停用' : '已启用')
    loadSharedCreds()
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    }
  }
}

const removeCred = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定删除共享凭据「${row.name}」？被引用的凭据将无法删除。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteGitCredential(row.id)
    ElMessage.success('删除成功')
    loadSharedCreds()
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    }
  }
}

onMounted(() => {
  loadMyCred()
  loadSharedCreds()
})
</script>

<style scoped>
.profile-container {
  padding: 0;
  max-width: 1080px;
  margin: 0 auto;
}

/* ==================== 页头 ==================== */
.page-header {
  display: flex;
  align-items: center;
  gap: var(--cp-space-sm);
  margin-bottom: var(--cp-space-lg);
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--cp-text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--cp-text-secondary);
}

/* ==================== 卡片基础 ==================== */
.profile-card {
  margin-bottom: var(--cp-space-md);
  border-radius: var(--cp-radius-md);
  border: 1px solid var(--cp-border-light);
  box-shadow: var(--cp-shadow-1);
  transition: box-shadow var(--cp-motion-base) var(--cp-ease-out);
}

.profile-card:hover {
  box-shadow: var(--cp-shadow-2);
}

/* ==================== 身份 Hero ==================== */
.hero {
  display: flex;
  align-items: center;
  gap: var(--cp-space-lg);
  padding: var(--cp-space-xs) var(--cp-space-sm);
}

@media (max-width: 768px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
  }
  .hero-meta {
    flex-direction: column;
    gap: 6px;
  }
}

.hero-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--cp-primary) 0%, #7c5cff 100%);
  box-shadow: 0 4px 14px rgba(59, 124, 255, 0.35);
  flex-shrink: 0;
}

.hero-name-row {
  display: flex;
  align-items: center;
  gap: var(--cp-space-xs);
  margin-bottom: var(--cp-space-xs);
}

.hero-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--cp-text-primary);
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--cp-space-xs) var(--cp-space-lg);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--cp-text-secondary);
}

.meta-item .el-icon {
  font-size: 14px;
}

/* ==================== 面板头 ==================== */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: var(--cp-space-sm);
}

.panel-title h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--cp-text-primary);
  margin: 0;
}

.panel-sub {
  font-size: 12px;
  color: var(--cp-text-secondary);
}

.panel-icon {
  width: 30px;
  height: 30px;
  border-radius: var(--cp-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.icon-key {
  color: var(--cp-primary);
  background: rgba(59, 124, 255, 0.1);
}

.icon-team {
  color: #7c5cff;
  background: rgba(124, 92, 255, 0.1);
}

/* ==================== 状态 Pill（脉冲点） ==================== */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
}

.status-pill.is-on {
  color: var(--cp-success);
  background: rgba(34, 197, 94, 0.1);
}

.status-pill.is-off {
  color: var(--cp-info);
  background: rgba(148, 163, 184, 0.12);
}

.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-pill.is-on .pill-dot {
  animation: pill-pulse 2s infinite;
}

@keyframes pill-pulse {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

/* ==================== 凭据摘要条 ==================== */
.cred-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--cp-space-md);
  padding: 10px 14px;
  margin-bottom: var(--cp-space-md);
  border-radius: var(--cp-radius-sm);
  background: rgba(59, 124, 255, 0.05);
  border: 1px dashed var(--cp-border-light);
}

.summary-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--cp-text-regular);
}

.summary-secret {
  color: var(--cp-text-secondary);
  font-size: 12px;
}

/* ==================== 其他 ==================== */
.card-tip {
  margin-bottom: 16px;
  color: var(--cp-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.input-with-tip {
  width: 100%;
}

.input-with-tip .el-input,
.input-with-tip .el-textarea {
  width: 100%;
}

.field-tip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--cp-text-secondary);
  cursor: pointer;
}

.field-tip code {
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.12);
  font-size: 11px;
}

.field-tip:hover {
  color: var(--cp-primary);
}

.cred-name {
  font-weight: 500;
  color: var(--cp-text-primary);
}

.profile-card :deep(.el-card__body) {
  padding: 20px;
}

.profile-card :deep(.el-table) {
  border-radius: var(--cp-radius-sm);
}
</style>
