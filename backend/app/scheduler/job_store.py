"""
调度任务存储
管理调度配置的持久化和查询
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Schedule, ScheduleType, TaskInstance, TaskStatus
import logging

logger = logging.getLogger(__name__)


class ScheduleStore:
    """调度配置存储"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_schedule(self, schedule_id: int) -> Optional[Schedule]:
        """获取调度配置"""
        return self.db.query(Schedule).get(schedule_id)
    
    def get_enabled_schedules(self) -> List[Schedule]:
        """获取所有启用的调度"""
        return self.db.query(Schedule).filter(
            Schedule.enabled == True
        ).all()
    
    def get_schedule_by_type(self, schedule_type: ScheduleType) -> List[Schedule]:
        """获取指定类型的调度"""
        return self.db.query(Schedule).filter(
            Schedule.schedule_type == schedule_type,
            Schedule.enabled == True
        ).all()
    
    def create_schedule(self, data: Dict[str, Any]) -> Schedule:
        """创建调度配置"""
        schedule = Schedule(
            project_id=data['project_id'],
            spider_name=data['spider_name'],
            schedule_type=data['schedule_type'],
            cron_expr=data.get('cron_expr'),
            interval_seconds=data.get('interval_seconds'),
            priority=data.get('priority', 5),
            max_concurrency=data.get('max_concurrency', 1),
            timeout_seconds=data.get('timeout_seconds', 3600),
            retry_strategy=data.get('retry_strategy'),
            enabled=data.get('enabled', True),
            created_at=datetime.utcnow()
        )
        
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        
        logger.info(f"Schedule created: {schedule.id}")
        return schedule
    
    def update_schedule(self, schedule_id: int, data: Dict[str, Any]) -> Optional[Schedule]:
        """更新调度配置"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        
        for key, value in data.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)
        
        schedule.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(schedule)
        
        logger.info(f"Schedule updated: {schedule_id}")
        return schedule
    
    def delete_schedule(self, schedule_id: int) -> bool:
        """删除调度配置"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return False
        
        self.db.delete(schedule)
        self.db.commit()
        
        logger.info(f"Schedule deleted: {schedule_id}")
        return True
    
    def toggle_schedule(self, schedule_id: int, enabled: bool) -> Optional[Schedule]:
        """启用/禁用调度"""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return None
        
        schedule.enabled = enabled
        self.db.commit()
        self.db.refresh(schedule)
        
        logger.info(f"Schedule {'enabled' if enabled else 'disabled'}: {schedule_id}")
        return schedule
    
    def update_next_run_time(self, schedule_id: int, next_run_time: datetime):
        """更新下次执行时间"""
        schedule = self.get_schedule(schedule_id)
        if schedule:
            schedule.next_run_time = next_run_time
            self.db.commit()


class TaskInstanceStore:
    """任务实例存储"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_task_instance(self, schedule_id: int, spider_name: str) -> TaskInstance:
        """创建任务实例"""
        task = TaskInstance(
            schedule_id=schedule_id,
            spider_name=spider_name,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        logger.info(f"Task instance created: {task.id}")
        return task
    
    def update_task_status(self, task_id: int, status: TaskStatus, 
                          stats: Dict = None, log_url: str = None):
        """更新任务状态"""
        task = self.db.query(TaskInstance).get(task_id)
        if not task:
            return
        
        task.status = status
        
        if status == TaskStatus.RUNNING:
            task.started_at = datetime.utcnow()
        elif status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.TIMEOUT]:
            task.finished_at = datetime.utcnow()
        
        if stats:
            task.stats = stats
        if log_url:
            task.log_url = log_url
        
        self.db.commit()
        
        logger.info(f"Task instance updated: {task_id} - {status.value}")
    
    def set_worker_info(self, task_id: int, worker_node: str, container_id: str):
        """设置 Worker 信息"""
        task = self.db.query(TaskInstance).get(task_id)
        if task:
            task.worker_node = worker_node
            task.container_id = container_id
            self.db.commit()
    
    def get_task_instance(self, task_id: int) -> Optional[TaskInstance]:
        """获取任务实例"""
        return self.db.query(TaskInstance).get(task_id)
    
    def get_tasks_by_schedule(self, schedule_id: int, limit: int = 50) -> List[TaskInstance]:
        """获取调度配置的任务实例"""
        return self.db.query(TaskInstance).filter(
            TaskInstance.schedule_id == schedule_id
        ).order_by(
            TaskInstance.created_at.desc()
        ).limit(limit).all()
    
    def get_running_tasks(self) -> List[TaskInstance]:
        """获取所有运行中的任务"""
        return self.db.query(TaskInstance).filter(
            TaskInstance.status == TaskStatus.RUNNING
        ).all()
    
    def get_recent_tasks(self, limit: int = 100) -> List[TaskInstance]:
        """获取最近的任务实例"""
        return self.db.query(TaskInstance).order_by(
            TaskInstance.created_at.desc()
        ).limit(limit).all()
    
    def get_tasks_by_status(self, status: TaskStatus, limit: int = 50) -> List[TaskInstance]:
        """获取指定状态的任务"""
        return self.db.query(TaskInstance).filter(
            TaskInstance.status == status
        ).order_by(
            TaskInstance.created_at.desc()
        ).limit(limit).all()
    
    def get_task_stats(self, schedule_id: int = None) -> Dict[str, int]:
        """获取任务统计"""
        query = self.db.query(TaskInstance)
        
        if schedule_id:
            query = query.filter(TaskInstance.schedule_id == schedule_id)
        
        total = query.count()
        success = query.filter(TaskInstance.status == TaskStatus.SUCCESS).count()
        failed = query.filter(TaskInstance.status == TaskStatus.FAILED).count()
        running = query.filter(TaskInstance.status == TaskStatus.RUNNING).count()
        pending = query.filter(TaskInstance.status == TaskStatus.PENDING).count()
        
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "running": running,
            "pending": pending,
            "success_rate": (success / total * 100) if total > 0 else 0
        }
