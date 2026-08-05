"""
调度相关异步任务
"""
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.scheduler.job_store import TaskInstanceStore, ScheduleStore
from app.models import TaskStatus, ScheduleType
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="schedule.execute_task", queue="schedule")
def execute_schedule_task(self, schedule_id: int, task_instance_id: int = None):
    """
    执行调度任务
    
    Args:
        schedule_id: 调度配置 ID
        task_instance_id: 任务实例 ID
    """
    db = SessionLocal()
    task_instance_id_local = task_instance_id
    try:
        logger.info(f"Executing schedule task: schedule_id={schedule_id}")
        
        task_store = TaskInstanceStore(db)
        schedule_store = ScheduleStore(db)
        
        # 获取调度配置
        schedule = schedule_store.get_schedule(schedule_id)
        if not schedule:
            logger.error(f"Schedule not found: {schedule_id}")
            return {"status": "failed", "error": "Schedule not found"}
        
        # 创建任务实例（如果没有提供）
        if not task_instance_id_local:
            task_instance = task_store.create_task_instance(
                schedule_id=schedule_id,
                spider_name=schedule.spider_name
            )
            task_instance_id_local = task_instance.id
        else:
            task_instance = task_store.get_task_instance(task_instance_id_local)
        
        # 更新任务状态为运行中
        task_store.update_task_status(task_instance_id_local, TaskStatus.RUNNING)
        task_store.set_worker_info(
            task_instance_id_local,
            worker_node=self.request.hostname,
            container_id=str(uuid.uuid4())
        )
        
        # 如果指定了目标节点，通过 SSH 在远程服务器上执行
        if schedule.node_id:
            _execute_on_node(db, schedule, task_instance_id_local)
        else:
            _execute_locally(db, schedule, task_instance_id_local)
        
        # 更新任务状态为成功
        task_store.update_task_status(
            task_instance_id_local,
            TaskStatus.SUCCESS,
            stats={"items_scraped": 0, "duration": 0}
        )
        
        return {
            "status": "success",
            "task_instance_id": task_instance_id_local,
            "schedule_id": schedule_id,
            "spider_name": schedule.spider_name,
            "started_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Task execution failed: {e}", exc_info=True)
        
        # 更新任务状态为失败
        if task_instance_id_local:
            task_store = TaskInstanceStore(db)
            task_store.update_task_status(
                task_instance_id_local,
                TaskStatus.FAILED,
                stats={"error": str(e)}
            )
        
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


def _execute_on_node(db, schedule, task_instance_id):
    """在指定节点上通过 SSH 执行爬虫"""
    from app.models import Spider, Node
    
    logger.info(f"Executing schedule on node {schedule.node_id}")
    
    # 查找节点
    node = db.query(Node).get(schedule.node_id)
    if not node:
        raise Exception(f"Node {schedule.node_id} not found")
    
    # 查找爬虫
    spider = db.query(Spider).filter(
        Spider.project_id == schedule.project_id,
        Spider.name == schedule.spider_name
    ).first()
    if not spider:
        raise Exception(f"Spider '{schedule.spider_name}' not found in project {schedule.project_id}")
    
    # 获取代码目录
    from app.services.upload_service import UploadService
    upload_service = UploadService()
    code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    if not code_dir:
        raise Exception("Spider code directory not found")
    
    from app.services.ssh_executor import get_ssh_executor, SshTaskConfig
    
    ssh_executor = get_ssh_executor()
    config = SshTaskConfig(
        task_id=str(task_instance_id),
        spider_id=str(spider.id),
        spider_name=spider.spider_name or spider.name,
        ssh_host=node.ssh_host or node.host,
        ssh_port=node.ssh_port or 22,
        ssh_user=node.ssh_user or "root",
        ssh_pwd=node.ssh_pwd,
        ssh_key=node.ssh_key,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider.spider_name or spider.name,
    )
    
    ssh_executor.execute_task(config)
    
    # 更新任务实例的节点信息
    from app.core.database import SessionLocal
    db2 = SessionLocal()
    try:
        task = db2.query(TaskInstance).get(int(task_instance_id))
        if task:
            task.node_id = schedule.node_id
            task.deploy_mode = "ssh"
            db2.commit()
    finally:
        db2.close()
    
    logger.info(f"Task {task_instance_id} started on node {node.name} via SSH")


def _execute_locally(db, schedule, task_instance_id):
    """在本地执行爬虫（Docker 或本地进程）"""
    # 调用执行引擎执行爬虫任务
    from app.services.task_executor import TaskExecutor, TaskConfig
    import asyncio
    
    executor = TaskExecutor()
    config = TaskConfig(
        task_id=str(task_instance_id),
        spider_id=schedule.spider_id if hasattr(schedule, 'spider_id') else '',
        spider_name=schedule.spider_name,
        git_url=schedule.git_url if hasattr(schedule, 'git_url') else None,
        git_branch=schedule.git_branch if hasattr(schedule, 'git_branch') else 'main',
        memory_limit=schedule.memory_limit if hasattr(schedule, 'memory_limit') else '512m',
        cpu_limit=schedule.cpu_limit if hasattr(schedule, 'cpu_limit') else 1.0,
        timeout=schedule.timeout if hasattr(schedule, 'timeout') else 3600,
    )
    
    container_id = asyncio.run(executor.execute_task(config))
    
    logger.info(f"Task {task_instance_id} started in container {container_id[:12]}")


@celery_app.task(bind=True, name="schedule.check_and_trigger", queue="schedule")
def check_and_trigger_schedules(self):
    """
    检查并触发到期的调度任务
    这个任务应该定期执行（例如每分钟）
    """
    db = SessionLocal()
    try:
        logger.info("Checking schedules...")
        
        schedule_store = ScheduleStore(db)
        enabled_schedules = schedule_store.get_enabled_schedules()
        
        triggered_count = 0
        
        for schedule in enabled_schedules:
            # 检查是否需要执行
            if should_trigger_schedule(schedule):
                # 触发任务
                execute_schedule_task.delay(schedule.id)
                triggered_count += 1
                
                # 更新下次执行时间
                next_run = calculate_next_run_time(schedule)
                if next_run:
                    schedule_store.update_next_run_time(schedule.id, next_run)
        
        if triggered_count > 0:
            logger.info(f"Triggered {triggered_count} schedules")
        
        return {"triggered": triggered_count}
        
    except Exception as e:
        logger.error(f"Failed to check schedules: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()


def should_trigger_schedule(schedule) -> bool:
    """
    判断调度是否应该触发
    
    Args:
        schedule: 调度配置对象
    
    Returns:
        是否应该触发
    """
    # 检查是否有下次执行时间
    if not schedule.next_run_time:
        return True
    
    # 检查是否到期
    now = datetime.utcnow()
    return now >= schedule.next_run_time


def calculate_next_run_time(schedule) -> datetime:
    """
    计算下次执行时间
    
    Args:
        schedule: 调度配置对象
    
    Returns:
        下次执行时间
    """
    from datetime import timedelta
    
    now = datetime.utcnow()
    
    if schedule.schedule_type == ScheduleType.INTERVAL and schedule.interval_seconds:
        # 间隔调度
        return now + timedelta(seconds=schedule.interval_seconds)
    
    elif schedule.schedule_type == ScheduleType.ONCE:
        # 一次性调度，执行后不再调度
        return None
    
    elif schedule.schedule_type == ScheduleType.CRON and schedule.cron_expr:
        # Cron 调度（简化版，实际应该使用 croniter 库）
        # 这里只是示例
        return now + timedelta(hours=1)
    
    return None


@celery_app.task(bind=True, name="schedule.retry_task", queue="schedule", max_retries=3)
def retry_failed_task(self, task_instance_id: int):
    """
    重试失败的任务
    
    Args:
        task_instance_id: 任务实例 ID
    """
    db = SessionLocal()
    try:
        task_store = TaskInstanceStore(db)
        task = task_store.get_task_instance(task_instance_id)
        
        if not task:
            logger.error(f"Task instance not found: {task_instance_id}")
            return {"status": "failed", "error": "Task not found"}
        
        # 重置任务状态
        task_store.update_task_status(task_instance_id, TaskStatus.PENDING)
        
        # 重新执行
        execute_schedule_task.delay(task.schedule_id, task_instance_id)
        
        logger.info(f"Task retry initiated: {task_instance_id}")
        return {"status": "retried", "task_instance_id": task_instance_id}
        
    except Exception as e:
        logger.error(f"Failed to retry task: {e}")
        self.retry(exc=e, countdown=60 * (self.request.retries + 1))
    finally:
        db.close()


@celery_app.task(bind=True, name="schedule.cleanup_old_tasks", queue="schedule")
def cleanup_old_tasks(self, days: int = 30):
    """
    清理旧的任务记录
    
    Args:
        days: 保留天数
    """
    db = SessionLocal()
    try:
        from datetime import timedelta
        from sqlalchemy import delete
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # 删除旧的任务实例
        old_tasks = db.query(TaskInstance).filter(
            TaskInstance.created_at < cutoff_date,
            TaskInstance.status.in_([TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.TIMEOUT])
        ).all()
        
        count = len(old_tasks)
        
        for task in old_tasks:
            db.delete(task)
        
        db.commit()
        
        logger.info(f"Cleaned up {count} old task instances")
        return {"cleaned": count}
        
    except Exception as e:
        logger.error(f"Failed to cleanup tasks: {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
