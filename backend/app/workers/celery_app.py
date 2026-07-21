"""
Celery 应用配置
用于异步任务处理（部署、容器管理、爬虫执行等）
"""
from celery import Celery
from app.core.config import settings

# 创建 Celery 实例
celery_app = Celery(
    "crawlopilot",
    broker=settings.CELERY_BROKER_URL_PROP,
    backend=settings.CELERY_RESULT_BACKEND_PROP,
    include=[
        "app.workers.deploy_tasks",
        "app.workers.container_tasks",
        "app.workers.task_tasks",
        "app.workers.schedule_tasks",
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务路由
    task_routes={
        "app.workers.deploy_tasks.*": {"queue": "deploy"},
        "app.workers.container_tasks.*": {"queue": "container"},
        "app.workers.task_tasks.*": {"queue": "tasks"},
        "app.workers.schedule_tasks.*": {"queue": "scheduler"},
    },

    # 并发设置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # 超时设置
    task_soft_time_limit=3600,  # 1小时软超时
    task_time_limit=7200,       # 2小时硬超时

    # 可靠性设置
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,      # 追踪任务开始状态

    # 默认重试策略（指数退避）
    task_default_retry_delay=60,
    task_max_retries=3,

    # 结果过期
    result_expires=3600,  # 1小时

    # Broker 连接设置
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_pool_limit=10,

    # 日志
    worker_hijack_root_logger=False,
    worker_log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    worker_task_log_format="%(asctime)s - %(name)s - %(levelname)s - [%(task_name)s] %(message)s",
)

# 任务自动发现
celery_app.autodiscover_tasks(["app.workers"])


if __name__ == "__main__":
    celery_app.start()
