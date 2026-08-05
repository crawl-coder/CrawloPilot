# CrawloPilot Celery 异步任务开发指南

## 概述
CrawloPilot 使用 Celery + Redis 实现异步任务处理，主要用于：
- 部署任务（耗时长）
- 容器管理（可能失败）
- 定时任务（周期性执行）

## 架构

```
┌─────────────┐
│   FastAPI   │
│  (Web API)  │
└──────┬──────┘
       │ 提交任务
       ▼
┌─────────────┐
│    Redis    │
│  (Broker)   │
└──────┬──────┘
       │ 消息队列
       ▼
┌─────────────┐
│   Celery    │
│  (Worker)   │
└──────┬──────┘
       │ 执行结果
       ▼
┌─────────────┐
│    Redis    │
│ (Backend)   │
└─────────────┘
```

## 项目结构
```
backend/app/workers/
├── celery_app.py          # Celery 应用配置
├── deploy_tasks.py        # 部署相关任务
└── container_tasks.py     # 容器管理任务
```

## 创建新任务

### 1. 创建任务文件
```python
# backend/app/workers/your_tasks.py
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.your_service import YourService
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="your_module.task_name", queue="your_queue")
def your_task(self, param1: int, param2: str):
    """
    你的异步任务
    
    Args:
        param1: 参数1
        param2: 参数2
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting task with param1={param1}, param2={param2}")
        
        # 执行任务逻辑
        service = YourService(db)
        result = service.do_something(param1, param2)
        
        logger.info(f"Task completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise
    finally:
        db.close()
```

### 2. 配置任务队列
```python
# backend/app/workers/celery_app.py
celery_app.conf.update(
    task_routes={
        "app.workers.deploy_tasks.*": {"queue": "deploy"},
        "app.workers.container_tasks.*": {"queue": "container"},
        "app.workers.your_tasks.*": {"queue": "your_queue"}
    }
)
```

### 3. 在 API 中调用
```python
from fastapi import BackgroundTasks
from app.workers.your_tasks import your_task

@router.post("/process")
async def process_item(
    item_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """处理项目（异步）"""
    
    # 方式 1: 使用 BackgroundTasks（推荐）
    background_tasks.add_task(your_task.delay, item_id)
    
    return {"message": "任务已提交", "task": "your_task"}
    
    # 方式 2: 直接调用（不推荐，会阻塞）
    # result = your_task.delay(item_id)
    # return {"task_id": result.id}
```

## 任务装饰器选项

### 基本选项
```python
@celery_app.task(
    bind=True,                    # 绑定任务实例
    name="module.task_name",      # 任务名称
    queue="queue_name",           # 队列名称
    max_retries=3,                # 最大重试次数
    default_retry_delay=60,       # 默认重试延迟（秒）
    acks_late=True,               # 任务完成后确认
    reject_on_worker_lost=True    # Worker 丢失时拒绝
)
def my_task(self, *args):
    pass
```

### 超时设置
```python
@celery_app.task(
    soft_time_limit=3600,  # 软超时（秒）- 抛出 SoftTimeLimitExceeded
    time_limit=7200        # 硬超时（秒）- 直接终止
)
def long_running_task(self):
    pass
```

## 任务重试

### 自动重试
```python
@celery_app.task(bind=True, max_retries=3)
def unreliable_task(self, data):
    try:
        # 可能失败的操作
        result = risky_operation(data)
        return result
    except Exception as e:
        # 自动重试，延迟递增
        countdown = 60 * (self.request.retries + 1)
        self.retry(exc=e, countdown=countdown)
```

### 手动重试
```python
@celery_app.task(bind=True)
def manual_retry_task(self, url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        if self.request.retries < 3:
            logger.warning(f"Retry {self.request.retries + 1}/3: {e}")
            raise self.retry(exc=e, countdown=30)
        else:
            logger.error(f"Failed after 3 retries: {e}")
            raise
```

## 任务链和编排

### 任务链（串行）
```python
from celery import chain

# task1 -> task2 -> task3
workflow = chain(
    task1.s(arg1),
    task2.s(),
    task3.s()
)
result = workflow.apply_async()
```

### 任务组（并行）
```python
from celery import group

# 并行执行多个任务
workflow = group(
    task1.s(arg1),
    task2.s(arg2),
    task3.s(arg3)
)
result = workflow.apply_async()
```

### 和弦（并行 + 回调）
```python
from celery import chord

# 并行执行后执行回调
workflow = chord(
    group(task1.s(), task2.s(), task3.s()),
    callback_task.s()
)
result = workflow.apply_async()
```

## 定时任务

### 配置定时任务
```python
# backend/app/workers/celery_app.py
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'sync-container-status': {
        'task': 'app.workers.container_tasks.sync_container_status_task',
        'schedule': 300.0,  # 每 5 分钟
    },
    'daily-cleanup': {
        'task': 'app.workers.cleanup_tasks.daily_cleanup',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨 2 点
    },
}
```

### 启动 Beat
```bash
celery -A app.workers.celery_app beat --loglevel=info
```

## 监控和管理

### 查看任务状态
```python
from app.workers.celery_app import celery_app

# 检查任务状态
result = your_task.AsyncResult(task_id)
print(result.status)  # PENDING, STARTED, SUCCESS, FAILURE
print(result.result)  # 任务结果
```

### Flower 监控
```bash
# 安装 Flower
pip install flower

# 启动 Flower
celery -A app.workers.celery_app flower --port=5555

# 访问 http://localhost:5555
```

## 最佳实践

### 1. 任务设计原则
- **幂等性**: 任务可以被安全地重试
- **原子性**: 任务应该是一个完整的工作单元
- **无状态**: 任务不应依赖全局状态
- **快速失败**: 尽早发现并报告错误

### 2. 数据库会话管理
```python
@celery_app.task(bind=True)
def db_task(self):
    db = SessionLocal()
    try:
        # 使用数据库
        result = do_something(db)
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
```

### 3. 日志记录
```python
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def logging_task(self, data):
    logger.info(f"Task started: {self.request.id}")
    try:
        result = process(data)
        logger.info(f"Task completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
        raise
```

### 4. 大任务分片
```python
@celery_app.task(bind=True)
def process_large_dataset(self, dataset_id):
    # 获取数据集
    dataset = get_dataset(dataset_id)
    
    # 分片处理
    chunks = split_into_chunks(dataset, chunk_size=100)
    
    # 并行处理每个分片
    from celery import group
    workflow = group(
        process_chunk.s(chunk) for chunk in chunks
    )
    result = workflow.apply_async()
    
    return result
```

### 5. 错误处理
```python
@celery_app.task(bind=True, max_retries=3)
def robust_task(self, url):
    try:
        # 主要逻辑
        result = do_work(url)
        return result
    except TemporaryError as e:
        # 临时错误，可以重试
        logger.warning(f"Temporary error: {e}")
        raise self.retry(exc=e, countdown=60)
    except PermanentError as e:
        # 永久错误，不重试
        logger.error(f"Permanent error: {e}")
        raise
    except Exception as e:
        # 未知错误，重试
        logger.error(f"Unknown error: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=120)
```

## 启动 Worker

### 开发环境
```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

### 指定队列
```bash
# 只处理 deploy 队列
celery -A app.workers.celery_app worker --loglevel=info -Q deploy

# 处理多个队列
celery -A app.workers.celery_app worker --loglevel=info -Q deploy,container
```

### 生产环境
```bash
# 后台运行
celery -A app.workers.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --max-tasks-per-child=1000 \
    --logfile=/var/log/celery/worker.log \
    --detach
```

## 调试技巧

### 1. 同步执行（调试用）
```python
# 不推荐在生产环境使用
result = your_task.apply(args=[param1, param2])
print(result.result)
```

### 2. 查看任务日志
```bash
# Worker 日志
tail -f /var/log/celery/worker.log

# 或通过 Docker
docker-compose logs -f celery-worker
```

### 3. 测试任务
```python
# 在 Python shell 中测试
from app.workers.your_tasks import your_task

# 异步执行
result = your_task.delay(arg1, arg2)
print(f"Task ID: {result.id}")

# 等待结果
result.wait(timeout=60)
print(f"Result: {result.result}")
```

## 常见问题

### 1. 任务不执行
- 检查 Worker 是否启动
- 检查队列名称是否匹配
- 检查 Redis 连接

### 2. 任务卡住
- 检查是否有死锁
- 检查超时设置
- 查看 Worker 日志

### 3. 内存泄漏
- 使用 `--max-tasks-per-child` 限制
- 检查数据库连接是否关闭
- 检查是否有未释放的资源

---

## ⚠️ 已知问题：APScheduler + Celery 集成报错

### 现象
控制台周期性打印以下错误，但不影响主流程：
```
Job "execute_schedule_task.delay (trigger: cron[month='*', day='*', day_of_week='*', hour='*', minute='*/5'], next run at: ...)" raised an exception
TypeError: execute_schedule_task() takes from 2 to 3 positional arguments but 207 were given
```

### 根因
- APScheduler 的 `trigger` 配置将 `delay` 方法的参数错误地传递给了 Celery 任务函数
- `schedule_service.py` 中的 `execute_schedule_task.delay()` 调用时，APScheduler 把触发器的参数解析结果（如 year=*, month=*, ... 共200+个参数）传给了 `delay()`

### 临时解决
当前未修复，因为：
1. 定时调度不是核心功能（爬虫手动运行即可）
2. 错误不会阻塞主流程或影响普通 API 调用
3. 修复需要重构 APScheduler 与 Celery 的参数传递逻辑

### 如需修复
检查 `backend/app/services/schedule_service.py` 中 `execute_schedule_task` 的调用方式，可能需要：
- 使用 `functools.partial` 包装参数
- 或者改用 `APScheduler` 原生的 `add_job(func, trigger, args=[...])` 方式，而非通过 `delay()`
