# 分页功能 - 快速复制粘贴模板

## ✅ 已完成 (4/10)
- ✅ Spiders.vue
- ✅ Projects.vue
- ✅ Users.vue
- ✅ Schedules.vue

---

## 📋 剩余页面 (6/10)

### 通用修改步骤 (每个页面重复以下4步)

#### Step 1: 添加导入 (在 `<script setup>` 区域)
```javascript
import Pagination from '@/components/Pagination.vue'
```

#### Step 2: 添加变量 (在 ref 声明区域)
```javascript
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
```

#### Step 3: 添加分页组件 (在 `</el-table>` 后, `</el-card>` 前)
```vue
</el-table>

<!-- 分页 -->
<Pagination
  v-model:current-page="currentPage"
  v-model:page-size="pageSize"
  :total="total"
  @change="loadData"  // 或 loadXxx,根据实际函数名修改
/>
</el-card>
```

#### Step 4: 修改加载函数
**原代码**:
```javascript
const loadData = async () => {
  loading.value = true
  try {
    const params = {...}
    list.value = await getAPI(params)
  } catch (error) {
    // ...
  }
}
```

**修改后**:
```javascript
const loadData = async ({ page, size } = {}) => {
  loading.value = true
  try {
    const currentPageNum = page || currentPage.value
    const pageSizeNum = size || pageSize.value
    const skip = (currentPageNum - 1) * pageSizeNum
    
    const params = {...}
    params.skip = skip
    params.limit = pageSizeNum
    
    const response = await getAPI(params)
    list.value = response.items || []
    total.value = response.total || 0
    
    currentPage.value = currentPageNum
    pageSize.value = pageSizeNum
  } catch (error) {
    // ...
  }
}
```

---

## 🎯 各页面具体信息

### 1. Deploy.vue (部署管理)
- **列表变量**: `deploys`
- **加载函数**: `loadDeploys` 或 `loadData`
- **API函数**: `getDeploys`

### 2. Tasks.vue (任务管理)
- **列表变量**: `tasks`
- **加载函数**: `loadTasks` 或 `loadData`
- **API函数**: `getTasks`

### 3. Alerts.vue (告警管理)
- **列表变量**: `alerts`
- **加载函数**: `loadAlerts` 或 `loadData`
- **API函数**: `getAlerts`

### 4. AuditLogs.vue (审计日志)
- **列表变量**: `logs` 或 `auditLogs`
- **加载函数**: `loadLogs` 或 `loadData`
- **API函数**: `getAuditLogs`

### 5. Nodes.vue (节点管理)
- **列表变量**: `nodes`
- **加载函数**: `loadNodes` 或 `loadData`
- **API函数**: `getNodes`

### 6. ProxyPool.vue (代理池)
- **列表变量**: `proxies`
- **加载函数**: `loadProxies` 或 `loadData`
- **API函数**: `getProxies`

### 7. ApiManagement.vue (API管理)
- **列表变量**: `apis`
- **加载函数**: `loadApis` 或 `loadData`
- **API函数**: `getApis`

---

## ⚡ 快速完成命令

如果你想让我继续自动完成,请回复:
- **"继续"** - 我逐个完成剩余6个页面

如果你想自己完成:
1. 打开每个 `.vue` 文件
2. 按上述4步修改
3. 每个页面约 2-3 分钟

---

**最后更新**: 2026-04-11
