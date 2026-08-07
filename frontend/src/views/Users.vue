<template>
  <div class="users-container">
    <div class="page-header">
      <div class="page-title">
        <h2>用户管理</h2>
        <span class="page-subtitle">系统账号与角色权限管理</span>
      </div>
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        创建用户
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <el-card class="users-card cp-animate-in" shadow="never">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="用户名">
          <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="searchForm.role_id" placeholder="全部" clearable style="width: 150px">
            <el-option
              v-for="role in roles"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_active" placeholder="全部" clearable style="width: 120px">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadUsers">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 用户列表 -->
    <el-card class="users-card cp-animate-in" shadow="never">
      <el-table :data="users" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="130">
          <template #default="{ row }">
            <span class="username-cell">{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column prop="full_name" label="姓名" width="110">
          <template #default="{ row }">{{ row.full_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="角色" min-width="150">
          <template #default="{ row }">
            <el-tag
              v-for="role in row.roles"
              :key="role.id"
              :type="role.name === 'admin' ? 'primary' : 'info'"
              effect="light"
              size="small"
              round
              style="margin-right: 5px"
            >
              {{ role.name }}
            </el-tag>
            <span v-if="!row.roles || row.roles.length === 0" style="color: var(--cp-info)">无</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="status-pill" :class="row.is_active ? 'is-on' : 'is-off'">
              <span class="pill-dot"></span>{{ row.is_active ? '启用' : '禁用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
            <el-button size="small" type="warning" plain @click="showResetPasswordDialog(row)">重置密码</el-button>
            <el-button
              size="small"
              :type="row.is_active ? 'warning' : 'success'"
              plain
              @click="handleToggleStatus(row)"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <Pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        @change="loadUsers"
      />
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showUserDialog" :title="editingUser ? '编辑用户' : '创建用户'" width="500px">
      <el-form :model="userForm" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" :disabled="!!editingUser" />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" placeholder="可选" />
        </el-form-item>

        <el-form-item label="姓名">
          <el-input v-model="userForm.full_name" />
        </el-form-item>

        <el-form-item label="角色">
          <el-select
            v-model="userForm.role_ids"
            multiple
            placeholder="请选择角色"
            style="width: 100%"
          >
            <el-option
              v-for="role in roles"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            >
              <span>{{ role.name }}</span>
              <span style="color: #999; margin-left: 10px; font-size: 12px">{{ role.description }}</span>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item v-if="!editingUser" label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>

        <el-form-item v-if="editingUser" label="状态">
          <el-switch v-model="userForm.is_active" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showUserDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="showPasswordDialog" title="重置密码" width="400px">
      <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="100px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="passwordForm.password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="passwordForm.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
        <el-alert title="重置密码后，用户需要使用新密码登录" type="warning" :closable="false" />
      </el-form>

      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" @click="handleResetPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getUsers, createUser, updateUser, deleteUser, resetPassword, toggleUserStatus, getRoles } from '@/api/user'
import { formatDateTime } from '@/utils/common'
import Pagination from '@/components/Pagination.vue'

const users = ref([])
const roles = ref([])
const loading = ref(false)
const showUserDialog = ref(false)
const showPasswordDialog = ref(false)
const editingUser = ref(null)
const formRef = ref(null)
const passwordFormRef = ref(null)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const targetUser = ref(null)

const searchForm = reactive({
  username: '',
  role_id: null,
  is_active: null
})

const userForm = reactive({
  username: '',
  email: '',
  full_name: '',
  password: '',
  role_ids: [],
  is_active: true
})

const passwordForm = reactive({
  password: '',
  confirmPassword: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    // 可选，但填写则需为合法邮箱
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur', min: 6 }]
}

const passwordRules = {
  password: [{ required: true, message: '请输入新密码', trigger: 'blur', min: 6 }],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

onMounted(() => {
  loadRoles()
  loadUsers()
})

const loadRoles = async () => {
  try {
    roles.value = await getRoles()
  } catch (error) {
    console.error('加载角色列表失败', error)
  }
}

const loadUsers = async ({ page, size } = {}) => {
  try {
    loading.value = true
    const currentPageNum = page || currentPage.value
    const pageSizeNum = size || pageSize.value
    const skip = (currentPageNum - 1) * pageSizeNum
    
    const params = {
      ...searchForm,
      skip,
      limit: pageSizeNum
    }
    const response = await getUsers(params)
    users.value = response.items || []
    total.value = response.total || 0
    
    currentPage.value = currentPageNum
    pageSize.value = pageSizeNum
  } catch (error) {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.username = ''
  searchForm.role_id = null
  searchForm.is_active = null
  currentPage.value = 1
  loadUsers()
}

const showCreateDialog = () => {
  editingUser.value = null
  resetUserForm()
  showUserDialog.value = true
}

const showEditDialog = (row) => {
  editingUser.value = row
  Object.assign(userForm, {
    username: row.username,
    email: row.email,
    full_name: row.full_name,
    role_ids: row.roles ? row.roles.map(r => r.id) : [],
    is_active: row.is_active
  })
  showUserDialog.value = true
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    // 邮箱可选：空串转 null，避免后端格式校验 422
    const email = userForm.email?.trim() || null

    if (editingUser.value) {
      // 更新用户
      await updateUser(editingUser.value.id, {
        email,
        full_name: userForm.full_name,
        is_active: userForm.is_active,
        role_ids: userForm.role_ids
      })
      ElMessage.success('更新成功')
    } else {
      // 创建用户
      await createUser({ ...userForm, email })
      ElMessage.success('创建成功')
    }
    
    showUserDialog.value = false
    resetUserForm()
    loadUsers()
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    } else {
      ElMessage.error('操作失败')
    }
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除用户 "${row.username}" 吗？`, '提示', {
      type: 'warning'
    })
    
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      if (error.response?.data?.detail) {
        ElMessage.error(error.response.data.detail)
      } else {
        ElMessage.error('删除失败')
      }
    }
  }
}

const showResetPasswordDialog = (row) => {
  targetUser.value = row
  passwordForm.password = ''
  passwordForm.confirmPassword = ''
  showPasswordDialog.value = true
}

const handleResetPassword = async () => {
  try {
    await passwordFormRef.value.validate()
    
    await resetPassword(targetUser.value.id, passwordForm.password)
    ElMessage.success('密码重置成功')
    showPasswordDialog.value = false
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    } else {
      ElMessage.error('密码重置失败')
    }
  }
}

const handleToggleStatus = async (row) => {
  try {
    const action = row.is_active ? '禁用' : '启用'
    await ElMessageBox.confirm(`确定要${action}用户 "${row.username}" 吗？`, '提示', {
      type: 'warning'
    })
    
    await toggleUserStatus(row.id)
    ElMessage.success(`${action}成功`)
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      if (error.response?.data?.detail) {
        ElMessage.error(error.response.data.detail)
      } else {
        ElMessage.error('操作失败')
      }
    }
  }
}

const resetUserForm = () => {
  Object.assign(userForm, {
    username: '',
    email: '',
    full_name: '',
    password: '',
    role_ids: [],
    is_active: true
  })
}

</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--cp-space-lg);
}

.page-title {
  display: flex;
  align-items: center;
  gap: var(--cp-space-sm);
}

.page-title h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--cp-text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--cp-text-secondary);
}

.users-card {
  margin-bottom: var(--cp-space-md);
  border-radius: var(--cp-radius-md);
  border: 1px solid var(--cp-border-light);
  box-shadow: var(--cp-shadow-1);
  transition: box-shadow var(--cp-motion-base) var(--cp-ease-out);
}

.users-card:hover {
  box-shadow: var(--cp-shadow-2);
}

.search-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.username-cell {
  font-weight: 500;
  color: var(--cp-text-primary);
}

/* 状态 Pill（脉冲点，与 Profile 页一致） */
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
  color: var(--cp-danger);
  background: rgba(239, 68, 68, 0.08);
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
</style>
