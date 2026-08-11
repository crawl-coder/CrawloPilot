<template>
  <el-card class="profile-card cp-animate-in" shadow="never" v-loading="loading">
    <template #header>
      <div class="panel-header">
        <div class="panel-title">
          <span class="panel-icon icon-key"><el-icon><Key /></el-icon></span>
          <h3>我的 Git 凭据</h3>
        </div>
        <span class="status-pill" :class="myCred.configured ? 'is-on' : 'is-off'">
          <span class="pill-dot"></span>
          {{ myCred.configured ? '已配置' : '未配置' }}
        </span>
      </div>
    </template>

    <div class="card-tip">
      配置后，创建爬虫时可一键使用本人的 Git 凭据，无需重复填写。凭据加密存储，仅本人可用。
    </div>

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

    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" style="max-width: 560px">
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
          <div class="input-with-tip">
            <el-input
              v-model="form.password"
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

      <template v-if="form.auth_type === 'ssh'">
        <el-form-item label="SSH私钥" prop="ssh_key">
          <div class="input-with-tip">
            <SecureTextarea
              v-model="form.ssh_key"
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
        <el-input v-model="form.default_branch" placeholder="可选，如 main" />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        <el-popconfirm
          v-if="myCred.configured"
          title="确定清除个人 Git 凭据？"
          @confirm="handleClear"
        >
          <template #reference>
            <el-button type="danger" plain>清除</el-button>
          </template>
        </el-popconfirm>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { Key, User, Share, Lock, QuestionFilled } from '@element-plus/icons-vue'
import { useMyGitCredential } from '@/composables/useMyGitCredential'
import SecureTextarea from './SecureTextarea.vue'

const { myCred, loading, saving, load, save, clear } = useMyGitCredential()

const formRef = ref(null)
const form = reactive({
  auth_type: 'password',
  username: '',
  password: '',
  ssh_key: '',
  default_branch: ''
})

const rules = {
  auth_type: [{ required: true, message: '请选择认证方式', trigger: 'change' }],
  password: [{
    validator: (rule, value, callback) => {
      if (form.auth_type !== 'password') return callback()
      if (!value && !myCred.value.has_password) {
        return callback(new Error('请输入密码或访问令牌'))
      }
      callback()
    },
    trigger: 'blur'
  }],
  ssh_key: [{
    validator: (rule, value, callback) => {
      if (form.auth_type !== 'ssh') return callback()
      if (!value && !myCred.value.has_ssh_key) {
        return callback(new Error('请输入 SSH 私钥'))
      }
      callback()
    },
    trigger: 'blur'
  }]
}

watch(() => myCred.value, (val) => {
  if (val?.configured) {
    form.auth_type = val.auth_type || 'password'
    form.username = val.username || ''
    form.default_branch = val.default_branch || ''
    form.password = ''
    form.ssh_key = ''
  }
}, { immediate: true })

onMounted(() => {
  load()
})

const handleSave = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  const ok = await save(form)
  if (ok) {
    form.password = ''
    form.ssh_key = ''
  }
}

const handleClear = async () => {
  const ok = await clear()
  if (ok) {
    formRef.value.resetFields()
  }
}
</script>

<style scoped>
@import './profile-shared.css';
</style>
