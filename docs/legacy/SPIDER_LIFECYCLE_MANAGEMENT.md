# CrawloPilot 爬虫生命周期管理详解

**时间**: 2026-04-12  
**主题**: 启动、暂停、状态监控机制

---

## 📋 核心架构

CrawloPilot 通过 **Docker 容器** 管理爬虫的完整生命周期:

```
用户操作 (前端/API)
    ↓
FastAPI 后端
    ↓
TaskExecutor (任务执行器)
    ↓
Docker API
    ↓
Spider Runner 容器 (运行爬虫)
    ↓
日志采集 + 状态监控
```

---

## 1️⃣ 启动爬虫

### 完整流程

```python
# 1. 用户调用 API
POST /api/v1/execution/tasks
{
    "spider_id": 12,
    "git_url": "/path/to/spider",
    "spider_name": "of_week"
}

# 2. 后端处理 (execution.py)
@router.post("/tasks")
async def create_and_execute_task(task_data: TaskCreate):
    # 创建任务记录
    task = TaskInstance(...)
    db.add(task)
    db.commit()
    
    # 提交到 Celery 异步执行
    celery_app.send_task(
        'execute_task',
        args=[task.id]
    )
    
    return task

# 3. Celery Worker 执行 (celery_tasks.py)
@celery_app.task(name='execute_task')
def execute_task_celery(task_id: str):
    executor = get_executor()
    
    # 构建任务配置
    config = TaskConfig(
        task_id=task_id,
        spider_id=spider_id,
        spider_name=spider_name,
        git_url=git_url,
        ...
    )
    
    # 执行任务
    container_id = asyncio.run(executor.execute_task(config))

# 4. TaskExecutor 启动容器 (task_executor.py)
async def execute_task(self, config: TaskConfig) -> str:
    # 4.1 从 Git 拉取代码
    code_dir = await self._clone_git_repository(config)
    
    # 4.2 构建容器配置
    container_config = self._build_container_config(config, code_dir)
    # 包含:
    # - 镜像: crawlopilot/spider-runner:latest
    # - 环境变量: SPIDER_NAME, TASK_ID, etc.
    # - 卷挂载: 代码目录 -> /spider/code
    # - 资源限制: CPU, 内存
    
    # 4.3 创建并启动容器
    container = self.docker_client.containers.run(
        image='crawlopilot/spider-runner:latest',
        name=f'task-{task_id[:8]}',
        environment={
            'SPIDER_NAME': 'of_week',
            'TASK_ID': task_id,
            ...
        },
        volumes={
            code_dir: {'bind': '/spider/code', 'mode': 'ro'},
            f'task-output-{task_id}': {'bind': '/output', 'mode': 'rw'}
        },
        mem_limit='512m',
        nano_cpus=1000000000,  # 1 CPU
        detach=True
    )
    
    # 4.4 启动日志采集
    collector = get_collector()
    await collector.start_collecting(
        task_id=task_id,
        container_id=container.id
    )
    
    # 4.5 更新数据库状态
    task.status = TaskStatus.RUNNING
    task.container_id = container.id
    db.commit()
    
    return container.id

# 5. 容器内运行爬虫 (spider-runner/run_spider.py)
def main():
    # 读取环境变量
    spider_name = os.environ['SPIDER_NAME']
    
    # 加载爬虫代码
    sys.path.insert(0, '/spider/code')
    
    # 启动 Crawlo 爬虫
    from crawlo.crawler import CrawlerProcess
    asyncio.run(CrawlerProcess().crawl(spider_name))
```

### 关键技术点

**Docker 容器配置**:
```python
{
    'image': 'crawlopilot/spider-runner:latest',
    'name': f'task-{task_id[:8]}',
    'environment': {
        'SPIDER_NAME': 'of_week',        # 爬虫名称
        'TASK_ID': 'task_123',           # 任务 ID
        'API_URL': 'http://backend:8000', # 平台 API
        'GIT_URL': '/path/to/repo',      # Git 路径
    },
    'volumes': {
        '/tmp/spider-xxx': {             # 爬虫代码
            'bind': '/spider/code',
            'mode': 'ro'                 # 只读
        },
        'task-output-xxx': {             # 输出目录
            'bind': '/output',
            'mode': 'rw'
        }
    },
    'mem_limit': '512m',                # 内存限制
    'nano_cpus': 1000000000,            # CPU 限制 (1核)
    'network': 'crawlopilot-network',   # 网络
    'labels': {                         # 标签 (用于查找)
        'crawlopilot.task_id': 'task_123',
        'crawlopilot.spider_name': 'of_week'
    }
}
```

---

## 2️⃣ 暂停/停止爬虫

### 实现方式

```python
# 用户调用 API
POST /api/v1/execution/tasks/{task_id}/stop

# 后端处理 (execution.py)
@router.post("/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    executor = get_executor()
    success = await executor.stop_task(task_id)
    
    if success:
        return {"message": "Task stopped"}
    else:
        raise HTTPException(status_code=404, detail="Task not found")

# TaskExecutor 停止容器 (task_executor.py)
async def stop_task(self, task_id: str) -> bool:
    # 1. 查找容器
    container = self.active_tasks.get(task_id)
    
    if not container:
        # 通过标签查找
        container = self._find_container_by_task_id(task_id)
    
    if not container:
        return False
    
    # 2. 停止容器 (发送 SIGTERM)
    container.stop(timeout=10)  # 等待 10 秒优雅关闭
    
    # 3. 删除容器
    container.remove(force=True)
    
    # 4. 从活动任务中移除
    self.active_tasks.pop(task_id, None)
    
    # 5. 更新数据库状态
    task.status = TaskStatus.CANCELLED
    task.finished_at = datetime.utcnow()
    db.commit()
    
    # 6. 停止日志采集
    collector = get_collector()
    await collector.stop_collecting(task_id)
    
    return True
```

### Docker 停止流程

```
container.stop(timeout=10)
    ↓
发送 SIGTERM 信号到容器内主进程
    ↓
Crawlo 框架捕获信号
    ↓
优雅关闭:
  - 完成当前请求
  - 保存进度
  - 清理资源
    ↓
10 秒后发送 SIGKILL (强制终止)
    ↓
容器停止
```

---

## 3️⃣ 实时监控爬虫状态

### 3.1 容器状态监控

```python
# 获取任务状态
async def get_task_status(self, task_id: str) -> Dict:
    # 1. 查找容器
    container = self._find_container_by_task_id(task_id)
    
    if not container:
        return None
    
    # 2. 刷新容器信息
    container.reload()
    
    # 3. 返回状态
    return {
        'task_id': task_id,
        'container_id': container.id,
        'status': container.status,  # running/exited/paused
        'created_at': container.attrs['Created'],
        'started_at': container.attrs['State']['StartedAt'],
        'finished_at': container.attrs['State']['FinishedAt'],
        'exit_code': container.attrs['State']['ExitCode'],
        'error': container.attrs['State']['Error'],
        'pid': container.attrs['State']['Pid'],
    }

# 容器状态值:
# - running:  运行中
# - exited:   已退出
# - paused:   已暂停
# - restarting: 重启中
# - dead:     死亡
```

### 3.2 日志实时监控

```python
# LogCollector 流式采集 (log_collector.py)
async def start_collecting(self, task_id: str, container_id: str):
    container = self.docker_client.containers.get(container_id)
    
    # 流式读取日志 (类似 tail -f)
    logs = container.logs(
        stream=True,      # 流式
        follow=True,      # 持续跟踪
        timestamps=True   # 带时间戳
    )
    
    for log_line in logs:
        # 解析日志
        parsed = self._parse_log_line(log_line.decode('utf-8'))
        
        # 提取指标
        if 'Crawled 100 pages' in parsed.message:
            task.pages_crawled = 100
        
        if '50 items' in parsed.message:
            task.items_scraped = 50
        
        # 更新数据库
        db.commit()
        
        # 推送到前端 (WebSocket)
        await websocket.send_json({
            'type': 'log',
            'task_id': task_id,
            'message': parsed.message,
            'timestamp': parsed.timestamp.isoformat()
        })
```

### 3.3 日志解析示例

```python
# Crawlo 日志格式:
# 2026-04-13 16:57:56 [INFO] Starting spider: of_week
# 2026-04-13 16:57:57 [INFO] Crawled 100 pages, 50 items
# 2026-04-13 16:57:58 [ERROR] Failed to parse url: xxx

def _parse_log_line(self, log_line: str) -> ParsedLog:
    # 正则匹配
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
    
    return parsed
```

### 3.4 前端实时更新

```javascript
// 前端使用 WebSocket 接收实时日志
const ws = new WebSocket('ws://localhost:8000/ws/tasks/{task_id}/logs');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'log') {
        // 追加日志到界面
        appendLog(data.message);
    }
    
    if (data.type === 'status') {
        // 更新状态
        updateStatus(data.status);
    }
    
    if (data.type === 'metrics') {
        // 更新指标
        updateMetrics({
            pages: data.pages_crawled,
            items: data.items_scraped,
            errors: data.errors_count
        });
    }
};
```

---

## 4️⃣ 完整生命周期状态机

```
                    创建任务
                       ↓
                   PENDING (待执行)
                       ↓
                  提交到 Celery
                       ↓
                   RUNNING (运行中) ←┐
                       ↓              │
              ┌────────────────┐     │
              │  容器运行中     │     │
              │  日志采集中     │     │
              │  指标更新中     │     │
              └────────────────┘     │
                       ↓              │
              ┌────────────────┐     │
              │  正常完成       │     │
              │  手动停止       │─────┤
              │  异常失败       │─────┤
              │  超时终止       │─────┘
              └────────────────┘
                       ↓
            ┌──────────┼──────────┐
            ↓          ↓          ↓
        SUCCESS   FAILED   CANCELLED
        (成功)    (失败)    (取消)
            ↓          ↓          ↓
            └──────────┼──────────┘
                       ↓
                 清理资源
                   (容器/日志/临时文件)
```

---

## 5️⃣ 数据库状态记录

```python
class TaskInstance(Base):
    __tablename__ = 'tasks'
    
    id = Column(String(36), primary_key=True)
    spider_id = Column(Integer, ForeignKey('spiders.id'))
    
    # 状态
    status = Column(Enum(TaskStatus))  
    # TaskStatus:
    # - PENDING:    待执行
    # - RUNNING:    运行中
    # - SUCCESS:    成功完成
    # - FAILED:     执行失败
    # - CANCELLED:  手动取消
    
    # 容器信息
    container_id = Column(String(64))
    
    # 指标
    pages_crawled = Column(Integer, default=0)
    items_scraped = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    
    # 时间
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    
    # 错误信息
    error_message = Column(Text)
```

---

## 6️⃣ API 接口汇总

### 启动爬虫

```bash
POST /api/v1/execution/tasks
{
    "spider_id": 12,
    "git_url": "/path/to/spider",
    "memory_limit": "512m",
    "cpu_limit": 1.0,
    "timeout": 3600
}

响应:
{
    "id": "task_123",
    "status": "PENDING",
    "container_id": null
}
```

### 停止爬虫

```bash
POST /api/v1/execution/tasks/{task_id}/stop

响应:
{
    "message": "Task stopped"
}
```

### 查询状态

```bash
GET /api/v1/execution/tasks/{task_id}

响应:
{
    "id": "task_123",
    "status": "RUNNING",
    "container_id": "abc123def456",
    "pages_crawled": 100,
    "items_scraped": 50,
    "errors_count": 0,
    "started_at": "2026-04-13T16:57:55",
    "finished_at": null
}
```

### 查看日志

```bash
GET /api/v1/execution/tasks/{task_id}/logs?lines=100

响应:
{
    "logs": "2026-04-13 16:57:55 [INFO] Spider started\n..."
}
```

### 实时监控 (WebSocket)

```javascript
ws://localhost:8000/ws/tasks/{task_id}/logs

消息格式:
{
    "type": "log|status|metrics",
    "task_id": "task_123",
    "message": "...",
    "timestamp": "2026-04-13T16:57:55"
}
```

---

## 7️⃣ 核心技术总结

| 功能 | 技术实现 | 说明 |
|------|---------|------|
| **启动** | Docker API `containers.run()` | 创建并启动容器 |
| **停止** | Docker API `container.stop()` | 发送 SIGTERM 信号 |
| **状态** | Docker API `container.status` | 实时容器状态 |
| **日志** | Docker API `container.logs(stream=True)` | 流式日志采集 |
| **指标** | 正则解析日志 | 提取页面/数据/错误数 |
| **实时更新** | WebSocket | 推送到前端 |
| **持久化** | MySQL 数据库 | 记录任务状态 |
| **异步执行** | Celery + Redis | 后台任务队列 |
| **定时调度** | APScheduler | 定时触发任务 |

---

## 8️⃣ 零侵入设计验证

```
爬虫代码:
✅ 完全独立,不感知平台
✅ 正常输出日志到 stdout
✅ 不需要导入 SDK
✅ 不需要修改代码

平台管理:
✅ Docker 容器隔离运行
✅ 流式采集日志 (不侵入)
✅ 容器指标监控 (Docker API)
✅ 状态自动更新 (日志解析)

交互方式:
✅ 标准化 (Docker/日志)
✅ 非侵入 (不修改爬虫)
✅ 实时 (流式处理)
```

---

## 9️⃣ 完整流程图

```
用户操作
  ↓
[前端] 点击"启动爬虫"
  ↓
[API] POST /api/v1/execution/tasks
  ↓
[后端] 创建 TaskInstance (PENDING)
  ↓
[Celery] 异步任务 execute_task
  ↓
[TaskExecutor]
  ├─ Git 拉取代码
  ├─ 构建容器配置
  └─ Docker 创建容器
       ↓
[Spider Runner 容器]
  ├─ 加载爬虫代码 (/spider/code)
  ├─ 设置环境变量 (SPIDER_NAME)
  └─ 运行 Crawlo 爬虫
       ↓
[爬虫运行中]
  ├─ 输出日志到 stdout
  ├─ Crawlo 框架标准日志格式
  └─ 正常爬取数据
       ↓
[LogCollector]
  ├─ 流式读取 Docker 日志
  ├─ 解析日志提取指标
  │    ├─ 页面数量
  │    ├─ 数据条数
  │    └─ 错误数量
  └─ 更新数据库
       ↓
[前端实时更新]
  ├─ WebSocket 推送日志
  ├─ 轮询查询状态
  └─ 显示实时指标
       ↓
[爬虫完成]
  ├─ 容器退出 (exit code 0)
  ├─ 状态更新 (SUCCESS)
  └─ 资源清理
```

---

## ✅ 总结

CrawloPilot 通过 **Docker 容器 + 日志采集** 实现爬虫的全生命周期管理:

1. **启动**: Docker API 创建容器,挂载代码,设置环境变量
2. **停止**: Docker API 停止容器,优雅关闭,清理资源
3. **监控**: 流式采集日志,解析指标,实时更新数据库
4. **零侵入**: 爬虫完全独立,平台通过标准化方式管理

**核心优势**:
- ✅ 爬虫代码零修改
- ✅ 完整的生命周期管理
- ✅ 实时状态监控
- ✅ 日志自动采集解析
- ✅ 资源隔离 (Docker)
- ✅ 可扩展 (多节点部署)

---

**这就是 CrawloPilot 管理 Crawlo 爬虫的完整机制!** 🎯
