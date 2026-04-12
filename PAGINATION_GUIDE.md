# 分页功能实现指南

## ✅ 已完成

### 1. 通用分页组件
- **位置**: `/frontend/src/components/Pagination.vue`
- **状态**: ✅ 已完成
- **功能**: 支持 v-model 双向绑定、change 事件、智能显示

### 2. 已实现分页的页面
- ✅ Spiders.vue (爬虫管理)
- ✅ Projects.vue (项目管理)

---

## 📋 待实现页面清单

### 后端 API 需要修改的页面

以下后端 API 需要添加总数返回:

#### 1. Users (用户管理)
**文件**: `backend/app/api/v1/auth.py` 或 `users.py`
```python
@router.get("")
def list_users(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    total = db.query(User).count()
    users = db.query(User).offset(skip).limit(limit).all()
    return {"total": total, "items": users, "skip": skip, "limit": limit}
```

#### 2. Schedules (调度管理)
**文件**: `backend/app/api/v1/schedules.py`
```python
@router.get("")
def list_schedules(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(Schedule).count()
    schedules = db.query(Schedule).offset(skip).limit(limit).all()
    return {"total": total, "items": schedules, "skip": skip, "limit": limit}
```

#### 3. Deploy (部署管理)
**文件**: `backend/app/api/v1/deploys.py`
```python
@router.get("")
def list_deploys(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(Deploy).count()
    deploys = db.query(Deploy).offset(skip).limit(limit).all()
    return {"total": total, "items": deploys, "skip": skip, "limit": limit}
```

#### 4. Tasks (任务管理)
**文件**: `backend/app/api/v1/tasks.py`
```python
@router.get("")
def list_tasks(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(Task).count()
    tasks = db.query(Task).offset(skip).limit(limit).all()
    return {"total": total, "items": tasks, "skip": skip, "limit": limit}
```

#### 5. Alerts (告警管理)
**文件**: `backend/app/api/v1/alerts.py`
```python
@router.get("")
def list_alerts(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(Alert).count()
    alerts = db.query(Alert).offset(skip).limit(limit).all()
    return {"total": total, "items": alerts, "skip": skip, "limit": limit}
```

#### 6. AuditLogs (审计日志)
**文件**: `backend/app/api/v1/audit.py`
```python
@router.get("")
def list_audit_logs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(AuditLog).count()
    logs = db.query(AuditLog).offset(skip).limit(limit).all()
    return {"total": total, "items": logs, "skip": skip, "limit": limit}
```

#### 7. Nodes (节点管理)
**文件**: `backend/app/api/v1/nodes.py`
```python
@router.get("")
def list_nodes(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(Node).count()
    nodes = db.query(Node).offset(skip).limit(limit).all()
    return {"total": total, "items": nodes, "skip": skip, "limit": limit}
```

#### 8. ProxyPool (代理池)
**文件**: `backend/app/api/v1/proxies.py`
```python
@router.get("")
def list_proxies(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(Proxy).count()
    proxies = db.query(Proxy).offset(skip).limit(limit).all()
    return {"total": total, "items": proxies, "skip": skip, "limit": limit}
```

#### 9. ApiManagement (API管理)
**文件**: `backend/app/api/v1/apis.py`
```python
@router.get("")
def list_apis(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    total = db.query(API).count()
    apis = db.query(API).offset(skip).limit(limit).all()
    return {"total": total, "items": apis, "skip": skip, "limit": limit}
```

---

## 🎨 前端实现模板

### 标准实现步骤 (每个页面)

#### Step 1: 导入分页组件
```vue
<script setup>
import Pagination from '@/components/Pagination.vue'

const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
</script>
```

#### Step 2: 添加分页组件到模板
```vue
<template>
  <div>
    <el-table :data="list">...</el-table>
    
    <Pagination
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="total"
      @change="loadData"
    />
  </div>
</template>
```

#### Step 3: 修改加载数据函数
```javascript
const loadData = async ({ page, size } = {}) => {
  try {
    loading.value = true
    const currentPageNum = page || currentPage.value
    const pageSizeNum = size || pageSize.value
    const skip = (currentPageNum - 1) * pageSizeNum
    
    const response = await getAPI({ skip, limit: pageSizeNum })
    list.value = response.items || []
    total.value = response.total || 0
    
    currentPage.value = currentPageNum
    pageSize.value = pageSizeNum
  } catch (error) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}
```

---

## 📊 优先级建议

### P0 - 高优先级 (数据量大)
1. ✅ Spiders.vue - 已完成
2. ⏳ AuditLogs.vue - 审计日志(预计 10000+ 条)
3. ⏳ Tasks.vue - 任务记录(预计 1000+ 条)
4. ⏳ Deploy.vue - 部署记录(预计 1000+ 条)

### P1 - 中优先级 (数据量中)
5. ✅ Projects.vue - 已完成
6. ⏳ Alerts.vue - 告警记录(预计 500+ 条)
7. ⏳ Schedules.vue - 调度配置(预计 100+ 条)
8. ⏳ Users.vue - 用户列表(预计 100+ 条)
9. ⏳ ProxyPool.vue - 代理池(预计 100+ 条)

### P2 - 低优先级 (数据量小)
10. ⏳ Nodes.vue - 节点列表(预计 10-50 个)
11. ⏳ ApiManagement.vue - API配置(预计 50+ 个)

---

## 🚀 快速实现命令

如果你想让我继续实现剩余页面,请告诉我优先级:

```
选项 A: 实现 P0 高优先级 (AuditLogs, Tasks, Deploy)
选项 B: 实现 P1 中优先级 (Alerts, Schedules, Users, ProxyPool)
选项 C: 实现所有剩余页面
选项 D: 提供完整代码,自己手动应用
```

---

## 💡 注意事项

1. **后端修改后需要重启服务**
2. **前端修改后 Vite 会自动热更新**
3. **所有页面使用统一的分页组件**
4. **分页参数: skip (跳过数), limit (每页数量)**
5. **返回格式: {total, items, skip, limit}**

---

**最后更新**: 2026-04-11
