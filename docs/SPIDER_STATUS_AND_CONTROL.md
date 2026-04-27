# CrawloPilot 爬虫状态监控与控制机制

**时间**: 2026-04-12  
**主题**: 实时状态反馈、暂停/停止爬虫

---

## 📊 1. 爬虫运行状态实时反馈

### 1.1 状态采集机制

```
Docker 容器 (运行爬虫)
  ↓ 输出日志到 stdout
  ↓
LogCollector (日志采集器)
  ↓ 流式读取 (类似 tail -f)
  ↓
解析日志提取指标
  ↓ 正则匹配 Crawlo 日志格式
  ↓
更新数据库 (TaskInstance)
  ↓ 页面数、数据数、错误数
  ↓
前端轮询 / WebSocket
  ↓ 实时显示
  ↓
用户界面
```

### 1.2 日志采集实现

```python
# backend/app/services/log_collector.py

class LogCollector:
    async def start_collecting(self, task_id, container_id):
        """启动日志采集"""
        container = self.docker_client.containers.get(container_id)
        
        # 流式读取日志 (实时)
        logs = container.logs(
            stream=True,      # 流式模式
            follow=True,      # 持续跟踪
            timestamps=True   # 带时间戳
        )
        
        for log_line in logs:
            # 解析日志
            parsed = self._parse_log_line(log_line)
            
            # 提取指标
            if 'Crawled 100 pages' in parsed.message:
                task.pages_crawled = 100
            
            if '50 items' in parsed.message:
                task.items_scraped = 50
            
            # 更新数据库
            db.commit()
```

### 1.3 日志格式解析

```python
def _parse_log_line(self, log_line: str) -> ParsedLog:
    """解析 Crawlo 日志"""
    # 格式: 2026-04-13 16:57:56 [INFO] Crawled 100 pages, 50 items
    
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] (.+)'
    match = re.match(pattern, log_line)
    
    timestamp = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
    level = match.group(2)
    message = match.group(3)
    
    parsed = ParsedLog(timestamp, level, message)
    
    # 提取关键信息
    if 'Spider' in message and 'started' in message:
        parsed.spider_status = 'started'
    
    if 'Crawled' in message:
        pages = re.search(r'Crawled (\d+) pages', message)
        if pages:
            parsed.pages_crawled = int(pages.group(1))
    
    if 'items' in message:
        items = re.search(r'(\d+) items', message)
        if items:
            parsed.items_scraped = int(items.group(1))
    
    return parsed
```

### 1.4 数据库状态记录

```python
# backend/app/models/__init__.py

class TaskInstance(Base):
    __tablename__ = 'task_instance'
    
    id = Column(String(36), primary_key=True)
    spider_id = Column(BigInteger, ForeignKey('spider.id'))
    
    # 状态
    status = Column(Enum(TaskStatus))
    # TaskStatus:
    # - PENDING:    待执行
    # - RUNNING:    运行中
    # - SUCCESS:    成功完成
    # - FAILED:     执行失败
    # - CANCELLED:  手动取消
    
    # 实时指标 (由 LogCollector 更新)
    pages_crawled = Column(Integer, default=0)    # 已爬取页面数
    items_scraped = Column(Integer, default=0)    # 已抓取数据数
    errors_count = Column(Integer, default=0)     # 错误数
    
    # 容器信息
    container_id = Column(String(64))
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
```

### 1.5 前端获取状态

#### 方式 1: 轮询查询 (当前实现)

```javascript
// 前端定时查询任务状态
setInterval(async () => {
    const response = await fetch(`/api/v1/execution/tasks/${taskId}/status`)
    const task = await response.json()
    
    // 更新界面
    updateStatus(task.status)
    updateMetrics({
        pages: task.pages_crawled,
        items: task.items_scraped,
        errors: task.errors_count
    })
}, 5000)  // 每 5 秒查询一次
```

#### 方式 2: WebSocket (未来优化)

```javascript
// 实时推送 (未实现)
const ws = new WebSocket(`ws://localhost:8000/ws/tasks/${taskId}/logs`)

ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    
    if (data.type === 'metrics') {
        updateMetrics({
            pages: data.pages_crawled,
            items: data.items_scraped
        })
    }
}
```

---

## 🛑 2. 暂停/停止爬虫

### 2.1 当前实现: 停止任务

```python
# backend/app/services/task_executor.py

async def stop_task(self, task_id: str) -> bool:
    """停止任务"""
    # 1. 查找容器
    container = self.active_tasks.get(task_id)
    
    if not container:
        # 通过标签查找
        container = self._find_container_by_task_id(task_id)
    
    if not container:
        return False
    
    # 2. 停止容器
    container.stop(timeout=10)  # 发送 SIGTERM,等待 10 秒
    container.remove(force=True)  # 删除容器
    
    # 3. 更新数据库
    self._update_task_status(task_id, TaskStatus.CANCELLED)
    
    # 4. 停止日志采集
    await collector.stop_collecting(task_id)
    
    return True
```

### 2.2 API 接口

```python
# backend/app/api/v1/execution.py

@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    """停止任务"""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 检查任务状态
    if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
        raise HTTPException(status_code=400, detail=f"Cannot stop task in {task.status}")
    
    # 异步停止任务 (通过 Celery)
    celery_app.send_task(
        'app.workers.task_tasks.stop_spider_task',
        args=[task_id]
    )
    
    return {
        "message": "Stop task requested",
        "task_id": task_id
    }
```

### 2.3 Docker 停止流程

```
container.stop(timeout=10)
  ↓
发送 SIGTERM 信号到容器主进程
  ↓
Crawlo 框架捕获信号
  ↓
优雅关闭:
  - 完成当前请求
  - 保存进度到数据库
  - 清理资源
  ↓
10 秒内正常退出
  ↓
容器停止 (exit code 0)
  ↓
container.remove(force=True)
  ↓
容器删除
```

---

## ⚠️ 3. 当前限制

### 3.1 缺少"暂停"功能

**现状**: 
- ✅ 支持"停止" (终止任务)
- ❌ 不支持"暂停" (临时挂起,后续恢复)

**原因**:
- Docker 支持 `pause`/`unpause` (使用 cgroup freezer)
- 但 Crawlo 框架不支持断点续爬
- 暂停后恢复可能导致数据重复或丢失

### 3.2 状态更新延迟

**现状**:
- 日志采集是实时的 (流式)
- 但前端是轮询 (5 秒一次)
- 存在 5 秒延迟

**优化方案**:
- 使用 WebSocket 实时推送
- 减少延迟到 < 1 秒

---

## 🎯 4. 完整流程图

### 4.1 启动爬虫

```
用户点击"运行"
  ↓
POST /api/v1/execution/tasks
  ↓
创建 TaskInstance (PENDING)
  ↓
Celery 异步执行
  ↓
TaskExecutor.execute_task()
  ├─ Git 拉取代码
  ├─ 创建 Docker 容器
  └─ 启动容器
       ↓
容器运行爬虫
  ├─ 输出日志到 stdout
  └─ Crawlo 框架标准格式
       ↓
LogCollector 采集
  ├─ 流式读取日志
  ├─ 解析指标
  └─ 更新数据库
       ↓
前端轮询
  ├─ GET /api/v1/execution/tasks/{id}/status
  ├─ 获取最新状态
  └─ 更新界面
```

### 4.2 停止爬虫

```
用户点击"停止"
  ↓
POST /api/v1/execution/tasks/{id}/stop
  ↓
Celery 异步执行
  ↓
TaskExecutor.stop_task()
  ├─ 查找容器
  ├─ container.stop(timeout=10)
  │    ↓
  │   发送 SIGTERM
  │    ↓
  │   Crawlo 优雅关闭
  │    ↓
  │   容器退出
  ├─ container.remove()
  └─ 更新数据库 (CANCELLED)
       ↓
停止日志采集
  ↓
前端更新状态
```

---

## 📋 5. API 接口汇总

### 5.1 查询任务状态

```bash
GET /api/v1/execution/tasks/{task_id}/status

响应:
{
    "task_id": "task_123",
    "db_status": "RUNNING",
    "container_status": "running",
    "pages_crawled": 100,
    "items_scraped": 50,
    "errors_count": 0,
    "started_at": "2026-04-13T16:57:55",
    "finished_at": null
}
```

### 5.2 停止任务

```bash
POST /api/v1/execution/tasks/{task_id}/stop

响应:
{
    "message": "Stop task requested",
    "task_id": "task_123",
    "celery_task_id": "celery_456"
}
```

### 5.3 查看日志

```bash
GET /api/v1/execution/tasks/{task_id}/logs?lines=100

响应:
{
    "logs": "2026-04-13 16:57:55 [INFO] Spider started\n..."
}
```

---

## 🔮 6. 未来优化

### 6.1 添加"暂停"功能

```python
async def pause_task(self, task_id: str) -> bool:
    """暂停任务 (不删除容器)"""
    container = self._find_container_by_task_id(task_id)
    
    if not container:
        return False
    
    # Docker pause (使用 cgroup freezer)
    container.pause()
    
    # 更新数据库
    self._update_task_status(task_id, TaskStatus.PAUSED)
    
    return True

async def resume_task(self, task_id: str) -> bool:
    """恢复任务"""
    container = self._find_container_by_task_id(task_id)
    
    if not container:
        return False
    
    # Docker unpause
    container.unpause()
    
    # 更新数据库
    self._update_task_status(task_id, TaskStatus.RUNNING)
    
    return True
```

**注意**: 需要 Crawlo 框架支持断点续爬

### 6.2 WebSocket 实时推送

```python
# backend/app/api/v1/websocket.py

@router.websocket("/ws/tasks/{task_id}/logs")
async def task_logs_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()
    
    # 订阅日志
    collector = get_collector()
    
    async def on_log(parsed: ParsedLog):
        await websocket.send_json({
            "type": "log",
            "message": parsed.message,
            "timestamp": parsed.timestamp.isoformat()
        })
        
        # 推送指标
        await websocket.send_json({
            "type": "metrics",
            "pages": parsed.pages_crawled,
            "items": parsed.items_scraped,
            "errors": parsed.errors_count
        })
    
    await collector.start_collecting(task_id, container_id, callback=on_log)
```

### 6.3 前端实时更新

```javascript
// 使用 WebSocket 替代轮询
const ws = new WebSocket(`ws://localhost:8000/ws/tasks/${taskId}/logs`)

ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    
    if (data.type === 'metrics') {
        // 实时更新指标 (无延迟)
        updateMetrics({
            pages: data.pages,
            items: data.items,
            errors: data.errors
        })
    }
}
```

---

## ✅ 7. 总结

### 当前实现

| 功能 | 状态 | 实现方式 |
|------|------|---------|
| **启动爬虫** | ✅ 已实现 | Docker 容器 + Celery |
| **停止爬虫** | ✅ 已实现 | container.stop() + SIGTERM |
| **暂停爬虫** | ❌ 未实现 | 需要 Crawlo 支持断点续爬 |
| **状态监控** | ✅ 已实现 | LogCollector 流式采集 |
| **实时反馈** | ⚠️ 部分实现 | 前端轮询 (5秒延迟) |
| **日志查看** | ✅ 已实现 | Docker logs API |

### 状态流转

```
PENDING → RUNNING → SUCCESS (正常完成)
              ↓
          FAILED (异常失败)
              ↓
          CANCELLED (手动停止)
```

### 关键组件

1. **LogCollector**: 流式采集日志,提取指标
2. **TaskExecutor**: 管理容器生命周期
3. **Celery**: 异步任务执行
4. **数据库**: 持久化状态和指标
5. **前端轮询**: 定时查询状态 (可优化为 WebSocket)

---

**当前支持"停止",暂不支持"暂停"。状态监控通过日志采集实现,前端轮询更新!** 🎯
