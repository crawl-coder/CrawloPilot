<template>
  <div>
    <div style="margin-bottom: 20px">
      <h2>个人中心</h2>
    </div>

    <!-- 基本信息 -->
    <el-card class="profile-card" shadow="never">
      <template #header>
        <span class="card-title">基本信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户名">{{ userStore.username }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ userStore.user?.full_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ userStore.user?.email }}</el-descriptions-item>
        <el-descriptions-item label="角色">
          <el-tag
            v-for="role in userStore.user?.roles || []"
            :key="role.id"
            size="small"
            style="margin-right: 5px"
          >
            {{ role.name }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 我的 Git 凭据 -->
    <el-card class="profile-card" shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span class="card-title">我的 Git 凭据</span>
          <el-tag v-if="myCred.configured" type="success" size="small">已配置</el-tag>
          <el-tag v-else type="info" size="small">未配置</el-tag>
        </div>
      </template>
      <div class="card-tip">
        配置后，创建爬虫时可一键使用本人的 Git 凭据，无需重复填写。凭据加密存储，仅本人可用。
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
            <el-input
              v-model="myCredForm.password"
              type="password"
              show-password
              :placeholder="myCred.has_password ? '已配置，留空保持不变' : '请输入密码或访问令牌'"
            />
          </el-form-item>
        </template>

        <template v-if="myCredForm.auth_type === 'ssh'">
          <el-form-item label="SSH私钥">
            <el-input
              v-model="myCredForm.ssh_key"
              type="textarea"
              :rows="4"
              :placeholder="myCred.has_ssh_key ? '已配置，留空保持不变' : '-----BEGIN OPENSSH PRIVATE KEY-----'"
            />
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
    <el-card v-if="userStore.isAdmin" class="profile-card" shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span class="card-title">共享 Git 凭据（团队机器人）</span>
          <el-button type="primary" size="small" @click="showCredDialog()">
            <el-icon><Plus /></el-icon>
            新建凭据
          </el-button>
        </div>
      </template>
      <div class="card-tip">
        团队级机器人账号 / Deploy Key，全体成员创建爬虫时可引用。建议配合 Git 平台的只读或受限权限账号使用。
      </div>
      <el-table :data="sharedCreds" v-loading="sharedLoading" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="140" />
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
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getMyGitCredentials, saveMyGitCredentials, deleteMyGitCredentials } from '@/api/auth'
import {
  getGitCredentials,
  createGitCredential,
  updateGitCredential,
  deleteGitCredential,
} from '@/api/git-credential'

const userStore = useUserStore()

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
.profile-card {
  margin-bottom: 20px;
  border-radius: var(--cp-radius-md);
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--cp-text-primary);
}

.card-tip {
  margin-bottom: 16px;
  color: var(--cp-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
</style>
