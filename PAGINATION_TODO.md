# 分页功能快速实施指南

## ✅ 已完成

### 后端 API (已修改)
- ✅ spiders.py - 爬虫列表
- ✅ projects.py - 项目列表  
- ✅ users.py - 用户列表
- ✅ schedules.py - 调度列表
- ✅ deploy.py - 部署列表(需要添加 get_deploy_count 方法)

### 前端页面 (已修改)
- ✅ Spiders.vue - 爬虫管理
- ✅ Projects.vue - 项目管理
- ✅ Users.vue - 用户管理

---

## 📋 剩余前端页面实施步骤

### 通用模板 (适用于所有页面)

#### Step 1: 导入组件
```javascript
import Pagination from '@/components/Pagination.vue'

const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
```

#### Step 2: 添加分页组件到模板
```vue
<el-table :data="list">...</el-table>

<Pagination
  v-model:current-page="currentPage"
  v-model:page-size="pageSize"
  :total="total"
  @change="loadData"
/>
```

#### Step 3: 修改加载函数
```javascript
const loadData = async ({ page, size } = {}) => {
  const currentPageNum = page || currentPage.value
  const pageSizeNum = size || pageSize.value
  const skip = (currentPageNum - 1) * pageSizeNum
  
  const response = await getAPI({ skip, limit: pageSizeNum })
  list.value = response.items || []
  total.value = response.total || 0
  
  currentPage.value = currentPageNum
  pageSize.value = pageSizeNum
}
```

---

## 🎯 各页面具体修改

### 1. Schedules.vue (调度管理)
**文件**: `/frontend/src/views/Schedules.vue`

```vue
<!-- 在 el-table 后添加 -->
<Pagination
  v-model:current-page="currentPage"
  v-model:page-size="pageSize"
  :total="total"
  @change="loadSchedules"
/>
```

```javascript
// 添加导入和变量
import Pagination from '@/components/Pagination.vue'

const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

// 修改 loadSchedules
const loadSchedules = async ({ page, size } = {}) => {
  const currentPageNum = page || currentPage.value
  const pageSizeNum = size || pageSize.value
  const skip = (currentPageNum - 1) * pageSizeNum
  
  const params = { ...searchForm, skip, limit: pageSizeNum }
  const response = await getSchedules(params)
  schedules.value = response.items || []
  total.value = response.total || 0
  
  currentPage.value = currentPageNum
  pageSize.value = pageSizeNum
}
```

### 2. Deploy.vue (部署管理)
**文件**: `/frontend/src/views/Deploy.vue`

同 Schedules.vue 修改方式,将变量名改为 `deploys`, `loadDeploys`

### 3. Tasks.vue (任务管理)
**文件**: `/frontend/src/views/Tasks.vue`

同 Schedules.vue 修改方式,将变量名改为 `tasks`, `loadTasks`

### 4. Alerts.vue (告警管理)
**文件**: `/frontend/src/views/Alerts.vue`

同 Schedules.vue 修改方式,将变量名改为 `alerts`, `loadAlerts`

### 5. AuditLogs.vue (审计日志)
**文件**: `/frontend/src/views/AuditLogs.vue`

同 Schedules.vue 修改方式,将变量名改为 `logs`, `loadLogs`

### 6. Nodes.vue (节点管理)
**文件**: `/frontend/src/views/Nodes.vue`

同 Schedules.vue 修改方式,将变量名改为 `nodes`, `loadNodes`

### 7. ProxyPool.vue (代理池)
**文件**: `/frontend/src/views/ProxyPool.vue`

同 Schedules.vue 修改方式,将变量名改为 `proxies`, `loadProxies`

### 8. ApiManagement.vue (API管理)
**文件**: `/frontend/src/views/ApiManagement.vue`

同 Schedules.vue 修改方式,将变量名改为 `apis`, `loadApis`

---

## 🚀 快速应用命令

如果你想让我继续完成,请回复:
- **"继续前端"** - 我完成所有前端页面
- **"继续后端"** - 我完成所有后端API
- **"继续全部"** - 我完成前后端所有修改

---

**最后更新**: 2026-04-11
