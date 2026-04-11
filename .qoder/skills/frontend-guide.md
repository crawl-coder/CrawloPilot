# CrawloPilot 前端开发指南

## 技术栈
- **框架**: Vue 3 (Composition API)
- **构建工具**: Vite
- **UI 库**: Element Plus
- **路由**: Vue Router
- **HTTP 客户端**: Axios

## 项目结构
```
frontend/src/
├── api/              # API 封装
│   ├── request.js    # Axios 实例配置
│   ├── auth.js       # 认证相关 API
│   ├── project.js    # 项目相关 API
│   └── deploy.js     # 部署相关 API
├── views/            # 页面组件
│   ├── Login.vue     # 登录页
│   ├── Layout.vue    # 主布局
│   ├── Dashboard.vue # 仪表盘
│   ├── Projects.vue  # 项目管理
│   ├── Deploy.vue    # 部署管理
│   ├── Nodes.vue     # 节点管理
│   └── Users.vue     # 用户管理
├── router/           # 路由配置
│   └── index.js
├── App.vue           # 根组件
└── main.js           # 应用入口
```

## 开发规范

### 1. 组件结构
```vue
<template>
  <!-- 模板 -->
</template>

<script setup>
// 导入
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 响应式数据
const loading = ref(false)
const dataList = ref([])

// 方法
const loadData = async () => {
  loading.value = true
  try {
    // 加载数据
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 生命周期
onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* 样式 */
</style>
```

### 2. API 调用

#### API 封装
```javascript
// frontend/src/api/yourModule.js
import request from './request'

export function getList(params) {
  return request.get('/your-module', { params })
}

export function createItem(data) {
  return request.post('/your-module', data)
}

export function updateItem(id, data) {
  return request.put(`/your-module/${id}`, data)
}

export function deleteItem(id) {
  return request.delete(`/your-module/${id}`)
}
```

#### 组件中使用
```vue
<script setup>
import { getList, createItem } from '@/api/yourModule'

const loadData = async () => {
  try {
    const data = await getList({ page: 1, size: 20 })
    dataList.value = data
  } catch (error) {
    ElMessage.error('加载失败')
  }
}
</script>
```

### 3. 路由配置

#### 添加新路由
```javascript
// frontend/src/router/index.js
{
  path: '/',
  component: () => import('@/views/Layout.vue'),
  children: [
    {
      path: 'your-page',
      name: 'YourPage',
      component: () => import('@/views/YourPage.vue')
    }
  ]
}
```

#### 导航
```vue
<template>
  <el-menu router>
    <el-menu-item index="/your-page">
      <el-icon><Document /></el-icon>
      <span>你的页面</span>
    </el-menu-item>
  </el-menu>
</template>
```

### 4. 表单处理

#### 基本表单
```vue
<template>
  <el-form :model="form" :rules="rules" ref="formRef">
    <el-form-item label="名称" prop="name">
      <el-input v-model="form.name" />
    </el-form-item>
    
    <el-form-item label="描述" prop="description">
      <el-input v-model="form.description" type="textarea" />
    </el-form-item>
    
    <el-form-item>
      <el-button type="primary" @click="handleSubmit">
        提交
      </el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { createItem } from '@/api/yourModule'

const formRef = ref(null)
const form = reactive({
  name: '',
  description: ''
})

const rules = {
  name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ]
}

const handleSubmit = async () => {
  await formRef.value.validate()
  try {
    await createItem(form)
    ElMessage.success('创建成功')
  } catch (error) {
    ElMessage.error('创建失败')
  }
}
</script>
```

### 5. 表格使用

#### 基本表格
```vue
<template>
  <el-table :data="tableData" v-loading="loading">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="name" label="名称" />
    <el-table-column prop="status" label="状态">
      <template #default="{ row }">
        <el-tag v-if="row.status === 'active'" type="success">
          活跃
        </el-tag>
        <el-tag v-else type="info">非活跃</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{ row }">
        <el-button size="small" @click="handleEdit(row)">
          编辑
        </el-button>
        <el-button size="small" type="danger" @click="handleDelete(row)">
          删除
        </el-button>
      </template>
    </el-table-column>
  </el-table>
  
  <el-pagination
    v-model:current-page="page"
    v-model:page-size="pageSize"
    :total="total"
    @current-change="loadData"
  />
</template>
```

### 6. 对话框
```vue
<template>
  <el-dialog v-model="dialogVisible" title="标题" width="600px">
    <el-form :model="form">
      <!-- 表单内容 -->
    </el-form>
    
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>
```

### 7. 消息提示
```javascript
import { ElMessage, ElMessageBox } from 'element-plus'

// 普通消息
ElMessage.success('操作成功')
ElMessage.error('操作失败')
ElMessage.warning('请注意')
ElMessage.info('提示信息')

// 确认对话框
try {
  await ElMessageBox.confirm('确定要删除吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
  // 用户点击确定
} catch {
  // 用户点击取消
}
```

## Element Plus 常用组件

### 布局
```vue
<el-container>
  <el-header>Header</el-header>
  <el-main>Main</el-main>
  <el-footer>Footer</el-footer>
</el-container>

<el-row :gutter="20">
  <el-col :span="12">Left</el-col>
  <el-col :span="12">Right</el-col>
</el-row>
```

### 按钮
```vue
<el-button>默认</el-button>
<el-button type="primary">主要</el-button>
<el-button type="success">成功</el-button>
<el-button type="warning">警告</el-button>
<el-button type="danger">危险</el-button>
<el-button :loading="true">加载中</el-button>
```

### 标签
```vue
<el-tag>默认</el-tag>
<el-tag type="success">成功</el-tag>
<el-tag type="warning">警告</el-tag>
<el-tag type="danger">危险</el-tag>
<el-tag type="info">信息</el-tag>
```

### 图标
```vue
<script setup>
import { Plus, Edit, Delete, Refresh } from '@element-plus/icons-vue'
</script>

<template>
  <el-icon><Plus /></el-icon>
  <el-icon><Edit /></el-icon>
  <el-icon><Delete /></el-icon>
  <el-icon><Refresh /></el-icon>
</template>
```

## 状态管理

### 局部状态（推荐）
```vue
<script setup>
import { ref, reactive } from 'vue'

const count = ref(0)
const form = reactive({
  name: '',
  age: 0
})
</script>
```

### 全局状态（按需使用）
```javascript
// stores/user.js
import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null,
    token: localStorage.getItem('token')
  }),
  actions: {
    setUser(user) {
      this.user = user
    }
  }
})
```

## 开发技巧

### 1. 计算属性
```vue
<script setup>
import { computed } from 'vue'

const filteredList = computed(() => {
  return list.value.filter(item => item.status === 'active')
})
</script>
```

### 2. 监听器
```vue
<script setup>
import { watch } from 'vue'

watch(searchQuery, (newVal) => {
  loadData(newVal)
})
</script>
```

### 3. 生命周期
```vue
<script setup>
import { onMounted, onUnmounted } from 'vue'

onMounted(() => {
  // 组件挂载后
})

onUnmounted(() => {
  // 组件卸载前
})
</script>
```

## 调试技巧

### 1. Vue DevTools
安装 Vue DevTools 浏览器扩展

### 2. 控制台日志
```javascript
console.log('数据:', JSON.stringify(data, null, 2))
```

### 3. 网络请求
打开浏览器开发者工具 -> Network 查看 API 请求

## 构建部署

### 开发模式
```bash
cd frontend
npm run dev
```

### 生产构建
```bash
npm run build
```

### 预览构建结果
```bash
npm run preview
```
