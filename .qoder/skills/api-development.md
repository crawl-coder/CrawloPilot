# CrawloPilot API 开发指南

## API 路由结构

### 路由位置
所有 API 路由位于 `backend/app/api/v1/` 目录

### 已实现的路由

#### 1. 认证模块 (`auth.py`)
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/auth/me` - 获取当前用户信息

#### 2. 项目管理 (`projects.py`)
- `GET /api/v1/projects` - 获取项目列表
- `POST /api/v1/projects` - 创建项目
- `GET /api/v1/projects/{id}` - 获取项目详情
- `PUT /api/v1/projects/{id}` - 更新项目
- `DELETE /api/v1/projects/{id}` - 删除项目

#### 3. 部署管理 (`deploy.py`)
- `POST /api/v1/deploys` - 创建部署
- `GET /api/v1/deploys` - 获取部署列表
- `GET /api/v1/deploys/{id}` - 获取部署详情
- `POST /api/v1/deploys/{id}/rollback` - 回滚部署
- `POST /api/v1/deploys/{id}/retry` - 重试部署

#### 4. 节点管理 (`nodes.py`)
- `POST /api/v1/nodes` - 创建节点
- `GET /api/v1/nodes` - 获取节点列表
- `GET /api/v1/nodes/{id}` - 获取节点详情
- `POST /api/v1/nodes/{id}/test` - 测试连接
- `POST /api/v1/nodes/health-check` - 批量健康检查
- `POST /api/v1/nodes/{id}/drain` - 排空节点
- `POST /api/v1/nodes/{id}/activate` - 激活节点
- `DELETE /api/v1/nodes/{id}` - 删除节点
- `GET /api/v1/nodes/{id}/containers` - 获取节点容器

#### 5. 爬虫管理 (`spiders.py`)
- `GET /api/v1/spiders` - 获取爬虫列表
- `POST /api/v1/spiders` - 创建爬虫
- `GET /api/v1/spiders/{id}` - 获取爬虫详情
- `PUT /api/v1/spiders/{id}` - 更新爬虫
- `DELETE /api/v1/spiders/{id}` - 删除爬虫
- **`POST /api/v1/spiders/{id}/run`** - ⭐**运行爬虫**（异步启动本地进程）
- **`POST /api/v1/spiders/{id}/stop?task_id={task_id}`** - ⭐**停止爬虫**

#### 6. 任务执行 (`execution.py`)
- **`GET /api/v1/execution/tasks/{task_id}/status`** - ⭐**获取任务状态**（含duration/pages/items/errors）
- **`GET /api/v1/execution/tasks/{task_id}/logs?tail=50`** - ⭐**获取任务日志**
- `GET /api/v1/execution/tasks` - 所有任务列表
- `DELETE /api/v1/execution/tasks/{task_id}` - 删除任务

## 创建新 API 路由

### 步骤

1. **创建路由文件**
```python
# backend/app/api/v1/your_module.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/your-module", tags=["你的模块"])

# Pydantic Schemas
class YourModelCreate(BaseModel):
    name: str
    description: Optional[str] = None

class YourModelResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    
    class Config:
        from_attributes = True

# API Endpoints
@router.get("/", response_model=List[YourModelResponse])
async def list_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取列表"""
    # 实现逻辑
    pass

@router.post("/", response_model=YourModelResponse)
async def create_item(
    item_data: YourModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建项"""
    # 实现逻辑
    pass
```

2. **注册路由**
```python
# backend/app/main.py
from app.api.v1 import auth, projects, deploy, nodes, your_module

app.include_router(your_module.router, prefix=settings.API_PREFIX)
```

3. **创建前端 API 封装**
```javascript
// frontend/src/api/yourModule.js
import request from './request'

export function getList(params) {
  return request.get('/your-module', { params })
}

export function createItem(data) {
  return request.post('/your-module', data)
}
```

4. **创建前端页面**
```vue
<!-- frontend/src/views/YourModule.vue -->
<template>
  <div>
    <!-- 页面内容 -->
  </div>
</template>

<script setup>
import { getList, createItem } from '@/api/yourModule'
</script>
```

5. **添加路由**
```javascript
// frontend/src/router/index.js
{
  path: 'your-module',
  name: 'YourModule',
  component: () => import('@/views/YourModule.vue')
}
```

## 最佳实践

### 1. 统一响应格式
```python
# 成功响应
return data

# 错误响应
raise HTTPException(status_code=400, detail="错误信息")
```

### 2. 权限控制
```python
@router.get("/")
async def protected_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # current_user 是已认证的用户
    pass
```

### 3. 数据库查询
```python
# 列表查询（支持分页）
query = db.query(Model)
items = query.order_by(Model.created_at.desc())\
             .limit(limit)\
             .offset(offset)\
             .all()

# 单个查询
item = db.query(Model).get(item_id)
if not item:
    raise HTTPException(status_code=404, detail="不存在")
```

### 4. 异步任务
```python
from app.workers.your_tasks import your_task

@router.post("/process")
async def process_item(
    item_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # 异步执行
    background_tasks.add_task(your_task.delay, item_id)
    return {"message": "任务已提交"}
```

## 错误处理

### 常见错误码
- 400: 请求参数错误
- 401: 未认证
- 403: 权限不足
- 404: 资源不存在
- 500: 服务器错误

### 示例
```python
try:
    result = some_operation()
    return result
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")
```
