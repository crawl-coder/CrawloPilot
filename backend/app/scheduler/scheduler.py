"""
APScheduler 调度器核心
负责管理定时任务的创建、执行和监控
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from app.core.config import settings
from app.core.database import engine
import logging

logger = logging.getLogger(__name__)


class SchedulerManager:
    """调度器管理器"""
    
    def __init__(self):
        self.scheduler = None
        self.is_running = False
    
    def init_scheduler(self):
        """初始化调度器"""
        if self.scheduler:
            logger.warning("Scheduler already initialized")
            return
        
        # 配置任务存储
        jobstores = {
            'default': SQLAlchemyJobStore(
                engine=engine,
                tablename='apscheduler_jobs'
            )
        }
        
        # 配置执行器（移除ProcessPoolExecutor以避免权限问题）
        executors = {
            'default': ThreadPoolExecutor(max_workers=20)
        }
        
        # 配置任务默认值
        job_defaults = {
            'coalesce': False,  # 不合并错过的任务
            'max_instances': 3,  # 每个任务最多 3 个实例
            'misfire_grace_time': 60  # 错过执行的宽限期 60 秒
        }
        
        # 创建调度器
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=settings.TIMEZONE if hasattr(settings, 'TIMEZONE') else 'Asia/Shanghai'
        )
        
        logger.info("Scheduler initialized successfully")
    
    def start_scheduler(self):
        """启动调度器"""
        if not self.scheduler:
            self.init_scheduler()
        
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Scheduler started")
    
    def shutdown_scheduler(self, wait=True):
        """关闭调度器"""
        if self.scheduler and self.is_running:
            self.scheduler.shutdown(wait=wait)
            self.is_running = False
            logger.info("Scheduler shutdown")
    
    def add_cron_job(self, job_id: str, func, cron_expr: str, args=None, kwargs=None):
        """
        添加 Cron 定时任务
        
        Args:
            job_id: 任务 ID
            func: 执行函数
            cron_expr: Cron 表达式 (minute hour day month day_of_week)
            args: 位置参数
            kwargs: 关键字参数
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        # 解析 Cron 表达式
        minute, hour, day, month, day_of_week = cron_expr.split()
        
        job = self.scheduler.add_job(
            func,
            trigger='cron',
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            args=args or [],
            kwargs=kwargs or {},
            id=job_id,
            replace_existing=True,
            max_instances=1
        )
        
        logger.info(f"Cron job added: {job_id} - {cron_expr}")
        return job
    
    def add_interval_job(self, job_id: str, func, seconds: int = None, minutes: int = None, 
                        hours: int = None, args=None, kwargs=None):
        """
        添加间隔定时任务
        
        Args:
            job_id: 任务 ID
            func: 执行函数
            seconds: 间隔秒数
            minutes: 间隔分钟数
            hours: 间隔小时数
            args: 位置参数
            kwargs: 关键字参数
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        job = self.scheduler.add_job(
            func,
            trigger='interval',
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            args=args or [],
            kwargs=kwargs or {},
            id=job_id,
            replace_existing=True,
            max_instances=1
        )
        
        logger.info(f"Interval job added: {job_id} - every {seconds or minutes*60 or hours*3600}s")
        return job
    
    def add_date_job(self, job_id: str, func, run_date, args=None, kwargs=None):
        """
        添加一次性任务
        
        Args:
            job_id: 任务 ID
            func: 执行函数
            run_date: 执行时间 (datetime 或字符串)
            args: 位置参数
            kwargs: 关键字参数
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")
        
        job = self.scheduler.add_job(
            func,
            trigger='date',
            run_date=run_date,
            args=args or [],
            kwargs=kwargs or {},
            id=job_id,
            replace_existing=True
        )
        
        logger.info(f"One-time job added: {job_id} - at {run_date}")
        return job
    
    def remove_job(self, job_id: str):
        """删除任务"""
        if not self.scheduler:
            return
        
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Job removed: {job_id}")
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id}: {e}")
    
    def pause_job(self, job_id: str):
        """暂停任务"""
        if not self.scheduler:
            return
        
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Job paused: {job_id}")
        except Exception as e:
            logger.warning(f"Failed to pause job {job_id}: {e}")
    
    def resume_job(self, job_id: str):
        """恢复任务"""
        if not self.scheduler:
            return
        
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Job resumed: {job_id}")
        except Exception as e:
            logger.warning(f"Failed to resume job {job_id}: {e}")
    
    def get_job(self, job_id: str):
        """获取任务信息"""
        if not self.scheduler:
            return None
        
        try:
            return self.scheduler.get_job(job_id)
        except Exception:
            return None
    
    def get_all_jobs(self):
        """获取所有任务"""
        if not self.scheduler:
            return []
        
        return self.scheduler.get_jobs()
    
    def modify_job(self, job_id: str, **changes):
        """修改任务"""
        if not self.scheduler:
            return
        
        try:
            self.scheduler.modify_job(job_id, **changes)
            logger.info(f"Job modified: {job_id}")
        except Exception as e:
            logger.error(f"Failed to modify job {job_id}: {e}")
    
    def get_scheduler_info(self):
        """获取调度器信息"""
        if not self.scheduler:
            return {
                "is_running": False,
                "jobs": 0
            }
        
        jobs = self.get_all_jobs()
        return {
            "is_running": self.is_running,
            "jobs": len(jobs),
            "job_list": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                    "trigger": str(job.trigger)
                }
                for job in jobs
            ]
        }


# 全局调度器实例
scheduler_manager = SchedulerManager()


def get_scheduler() -> SchedulerManager:
    """获取调度器实例"""
    return scheduler_manager
