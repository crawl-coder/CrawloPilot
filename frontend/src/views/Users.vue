<template>
  <div>
    <div style="display: flex; justify-content: space-between; margin-bottom: 20px">
      <h2>用户管理</h2>
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        创建用户
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <el-form :inline="true" :model="searchForm" style="margin-bottom: 20px">
      <el-form-item label="用户名">
        <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
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

    <!-- 用户列表 -->
    <el-table :data="users" v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" width="150" />
      <el-table-column prop="email" label="邮箱" width="200" />
      <el-table-column prop="full_name" label="姓名" width="120" />
      <el-table-column label="角色" width="200">
        <template #default="{ row }">
          <el-tag
            v-for="role in row.roles"
            :key="role.id"
            size="small"
            style="margin-right: 5px"
          >
            {{ role.name }}
          </el-tag>
          <span v-if="!row.roles || row.roles.length === 0" style="color: #999">无</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
          <el-button size="small" type="warning" @click="showResetPasswordDialog(row)">重置密码</el-button>
          <el-button 
            size="small" 
            :type="row.is_active ? 'danger' : 'success'"
            @click="handleToggleStatus(row)"
          >
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
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

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showUserDialog" :title="editingUser ? '编辑用户' : '创建用户'" width="500px">
      <el-form :model="userForm" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" :disabled="!!editingUser" />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" />
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
import { parseDate } from '@/utils/format'
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
    { required: true, message: '请输入邮箱', trigger: 'blur' },
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
    
    if (editingUser.value) {
      // 更新用户
      await updateUser(editingUser.value.id, {
        email: userForm.email,
        full_name: userForm.full_name,
        is_active: userForm.is_active,
        role_ids: userForm.role_ids
      })
      ElMessage.success('更新成功')
    } else {
      // 创建用户
      await createUser(userForm)
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

const formatDate = (dateStr) => {
  const date = parseDate(dateStr)
  if (!date || isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN')
}
</script>
