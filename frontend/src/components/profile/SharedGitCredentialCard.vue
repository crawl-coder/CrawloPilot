<template>
  <el-card class="profile-card cp-animate-in" shadow="never" v-loading="loading">
    <template #header>
      <div class="panel-header">
        <div class="panel-title">
          <span class="panel-icon icon-team"><el-icon><Connection /></el-icon></span>
          <h3>共享 Git 凭据</h3>
          <span class="panel-sub">团队机器人账号 / Deploy Key</span>
        </div>
        <el-button type="primary" size="small" @click="openCreate">
          <el-icon><Plus /></el-icon>
          新建凭据
        </el-button>
      </div>
    </template>

    <div class="card-tip">
      全体成员创建爬虫时可引用。建议配合 Git 平台的只读或受限权限账号使用。
    </div>

    <div class="table-wrap">
      <el-table :data="list" style="min-width: 720px">
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
              <span class="pill-dot"></span>
              {{ row.is_active ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button
              size="small"
              :type="row.is_active ? 'warning' : 'success'"
              plain
              @click="toggle(row)"
            >
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" plain @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无共享凭据" :image-size="80" />
        </template>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑共享凭据' : '新建共享凭据'"
      width="560px"
      :close-on-click-modal="false"
      @closed="handleDialogClosed"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：GitLab 只读机器人" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="用途说明，可选" />
        </el-form-item>
        <el-form-item label="认证方式" prop="auth_type">
          <el-radio-group v-model="form.auth_type">
            <el-radio value="password">密码/Token</el-radio>
            <el-radio value="ssh">SSH密钥</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="form.auth_type === 'password'">
          <el-form-item label="用户名">
            <el-input v-model="form.username" placeholder="Git 用户名" />
          </el-form-item>
          <el-form-item label="密码/Token" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              :placeholder="editing?.has_password ? '已配置，留空保持不变' : '请输入密码或访问令牌'"
            />
          </el-form-item>
        </template>

        <template v-if="form.auth_type === 'ssh'">
          <el-form-item label="SSH私钥" prop="ssh_key">
            <SecureTextarea
              v-model="form.ssh_key"
              :rows="4"
              :placeholder="editing?.has_ssh_key ? '已配置，留空保持不变' : '-----BEGIN OPENSSH PRIVATE KEY-----'"
            />
          </el-form-item>
        </template>

        <el-form-item label="默认分支">
          <el-input v-model="form.default_branch" placeholder="可选，如 main" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Connection } from '@element-plus/icons-vue'
import { useSharedGitCredential } from '@/composables/useSharedGitCredential'
import SecureTextarea from './SecureTextarea.vue'

const {
  list, loading, dialogVisible, saving, editing, form,
  load, openCreate, openEdit, save, toggle, remove
} = useSharedGitCredential()

const formRef = ref(null)

const rules = computed(() => ({
  name: [{ required: true, message: '请输入凭据名称', trigger: 'blur' }],
  auth_type: [{ required: true, message: '请选择认证方式', trigger: 'change' }],
  password: [{
    validator: (rule, value, callback) => {
      if (form.auth_type !== 'password') return callback()
      if (!value && !editing.value?.has_password) {
        return callback(new Error('请输入密码或访问令牌'))
      }
      callback()
    },
    trigger: 'blur'
  }],
  ssh_key: [{
    validator: (rule, value, callback) => {
      if (form.auth_type !== 'ssh') return callback()
      if (!value && !editing.value?.has_ssh_key) {
        return callback(new Error('请输入 SSH 私钥'))
      }
      callback()
    },
    trigger: 'blur'
  }]
}))

onMounted(() => {
  load()
})

const handleSave = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  await save()
}

const handleDialogClosed = () => {
  formRef.value?.resetFields()
}
</script>

<style scoped>
@import './profile-shared.css';
</style>
