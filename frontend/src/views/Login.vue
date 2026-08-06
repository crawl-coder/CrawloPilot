<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="login-header">
          <img src="@/assets/crawlopilot-logo.png" class="login-logo" alt="CrawloPilot" />
          <h2>CrawloPilot 登录</h2>
        </div>
      </template>
      
      <el-form :model="loginForm" :rules="rules" ref="loginFormRef" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            size="large" 
            @click="handleLogin"
            :loading="loading"
            style="width: 100%"
          >
            登录
          </el-button>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            size="large" 
            @click="showRegister = true"
            style="width: 100%"
          >
            注册新账号
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 注册对话框 -->
    <el-dialog v-model="showRegister" title="注册" width="500px">
      <el-form :model="registerForm" :rules="registerRules" ref="registerFormRef">
        <el-form-item prop="username" label="用户名">
          <el-input v-model="registerForm.username" />
        </el-form-item>
        
        <el-form-item prop="email" label="邮箱">
          <el-input v-model="registerForm.email" type="email" />
        </el-form-item>
        
        <el-form-item prop="full_name" label="姓名">
          <el-input v-model="registerForm.full_name" />
        </el-form-item>
        
        <el-form-item prop="password" label="密码">
          <el-input v-model="registerForm.password" type="password" show-password />
        </el-form-item>
        
        <el-form-item prop="confirm_password" label="确认密码">
          <el-input v-model="registerForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showRegister = false">取消</el-button>
        <el-button type="primary" @click="handleRegister">注册</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register } from '@/api/auth'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const loginFormRef = ref(null)
const registerFormRef = ref(null)
const loading = ref(false)
const showRegister = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const registerForm = reactive({
  username: '',
  email: '',
  full_name: '',
  password: '',
  confirm_password: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== registerForm.password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const registerRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  confirm_password: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleLogin = async () => {
  try {
    loading.value = true
    const res = await login(loginForm)
    userStore.setToken(res.access_token)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (error) {
    ElMessage.error('登录失败')
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  try {
    await registerFormRef.value.validate()
    const { confirm_password, ...data } = registerForm
    await register(data)
    ElMessage.success('注册成功，请登录')
    showRegister.value = false
  } catch (error) {
    ElMessage.error('注册失败')
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--cp-login-gradient);
}

.login-card {
  width: 400px;
}

.login-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.login-logo {
  width: 72px;
  height: 72px;
  object-fit: contain;
}

.login-card :deep(.el-card__header) {
  text-align: center;
}
</style>
