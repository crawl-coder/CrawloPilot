"""
定时任务调度服务（进程内 APScheduler）

- 随 FastAPI lifespan 启停
- 启动时从 DB 加载 enabled 调度注册 job，并做错跑检测（记录 skipped，不追跑）
- API 变更通过 sync/remove 热更新 job
- 触发时：校验 + 并发守卫 + 幂等（唯一索引兜底）+ 复用 task_service 创建任务
"""
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import SessionLocal
from app.models import Schedule, ScheduleType, TaskInstance, TaskStatus

logger = logging.getLogger(__name__)

DEFAULT_TZ = "Asia/Shanghai"


class SchedulerService:
    """调度器：与数据库 Schedule 记录一一对应，job_id = schedule-{id}"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=ZoneInfo(DEFAULT_TZ))
        self._started = False

    # ==================== 生命周期 ====================

    def start(self):
        """启动调度器并从 DB 恢复 job"""
        if self._started:
            return
        self.scheduler.start()
        self._started = True
        self._recover_from_db()
        logger.info("调度器已启动，已从 DB 恢复定时任务")

    def shutdown(self):
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("调度器已停止")

    def _recover_from_db(self):
        """启动恢复：错跑检测 + 注册所有 enabled 调度"""
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            window = timedelta(hours=int(os.environ.get("SCHEDULE_COMPENSATION_HOURS", "24")))
            for sched in db.query(Schedule).filter(Schedule.enabled == True).all():
                if sched.schedule_type == ScheduleType.ONCE:
                    if sched.run_at and sched.run_at < now:
                        # 一次性调度已过期：停用并记录 skipped
                        sched.enabled = False
                        sched.last_run_status = "skipped"
                        db.commit()
                        continue
                elif sched.next_run_time and sched.next_run_time < now:
                    # 错跑检测：补偿窗口内记录 skipped，超窗只推进不执行
                    if sched.next_run_time >= now - window:
                        sched.last_run_status = "skipped"
                        db.commit()
                self._register_job(sched)
                self._sync_next_run_time(db, sched)
                db.commit()
        finally:
            db.close()

    # ==================== job 管理 ====================

    def sync_schedule(self, schedule_id: int):
        """创建/更新后同步 job 并回写 next_run_time"""
        db = SessionLocal()
        try:
            sched = db.query(Schedule).get(schedule_id)
            if not sched:
                return
            if sched.enabled:
                self._register_job(sched)
                self._sync_next_run_time(db, sched)
            else:
                self.remove_schedule(schedule_id)
                sched.next_run_time = None
            db.commit()
        finally:
            db.close()

    def remove_schedule(self, schedule_id: int):
        job_id = self._job_id(schedule_id)
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    def pause_schedule(self, schedule_id: int):
        job_id = self._job_id(schedule_id)
        job = self.scheduler.get_job(job_id)
        if job:
            job.pause()

    def resume_schedule(self, schedule_id: int):
        """启用：重新注册 job（resume 后 next_run_time 重新计算）"""
        self.sync_schedule(schedule_id)

    def run_now(self, schedule_id: int):
        """立即执行一次（不改变周期；忽略 enabled 状态）"""
        self._fire_schedule(schedule_id, ignore_enabled=True)

    @staticmethod
    def _job_id(schedule_id: int) -> str:
        return f"schedule-{schedule_id}"

    def _register_job(self, sched: Schedule):
        trigger = self._build_trigger(sched)
        if trigger is None:
            logger.warning(f"调度 {sched.id} 无法构建触发器，跳过注册")
            return
        job_id = self._job_id(sched.id)
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        self.scheduler.add_job(
            self._fire_schedule,
            trigger=trigger,
            id=job_id,
            args=[sched.id],
            misfire_grace_time=60,
            coalesce=True,
            max_instances=1,
            replace_existing=True,
        )
        logger.info(f"注册调度 job {job_id}: type={sched.schedule_type.value}, enabled={sched.enabled}")

    def _build_trigger(self, sched: Schedule):
        tz = ZoneInfo(sched.timezone or DEFAULT_TZ)
        if sched.schedule_type == ScheduleType.CRON:
            if not sched.cron_expr:
                return None
            return CronTrigger.from_crontab(sched.cron_expr, timezone=tz)
        if sched.schedule_type == ScheduleType.INTERVAL:
            seconds = sched.interval_seconds or 60
            return IntervalTrigger(seconds=seconds)
        if sched.schedule_type == ScheduleType.ONCE:
            if not sched.run_at:
                return None
            return DateTrigger(run_date=sched.run_at, timezone=ZoneInfo("UTC"))
        return None

    def _sync_next_run_time(self, db, sched: Schedule):
        job = self.scheduler.get_job(self._job_id(sched.id))
        if job and job.next_run_time:
            sched.next_run_time = job.next_run_time.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        else:
            sched.next_run_time = None

    # ==================== 触发 ====================

    def _fire_schedule(self, schedule_id: int, ignore_enabled: bool = False):
        db = SessionLocal()
        try:
            sched = db.query(Schedule).get(schedule_id)
            if not sched:
                return
            if not ignore_enabled and not sched.enabled:
                return

            # 并发守卫：同调度运行中/等待任务数 >= max_concurrency 则跳过
            running = db.query(TaskInstance).filter(
                TaskInstance.schedule_id == schedule_id,
                TaskInstance.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]),
            ).count()
            if running >= (sched.max_concurrency or 1):
                logger.warning(
                    f"调度 {schedule_id} 触发被并发守卫拦截（运行中 {running} >= {sched.max_concurrency}）"
                )
                return

            expected_run_at = datetime.utcnow()
            from app.services.task_service import create_and_run_task
            result = create_and_run_task(
                db,
                spider_id=sched.spider_id,
                node_id=sched.node_id,
                schedule_id=sched.id,
                expected_run_at=expected_run_at,
            )

            sched.last_run_at = datetime.utcnow()
            sched.last_run_status = "running"
            sched.last_run_task_id = result["task_id"]
            sched.run_count = (sched.run_count or 0) + 1
            if sched.schedule_type == ScheduleType.ONCE:
                # 一次性调度触发后停用
                sched.enabled = False
                self.remove_schedule(sched.id)
            else:
                self._sync_next_run_time(db, sched)
            db.commit()
            logger.info(
                f"调度 {schedule_id} 触发成功: task={result['task_id']}, "
                f"mode={result.get('mode')}"
            )
        except Exception as e:
            logger.error(f"调度 {schedule_id} 触发失败: {e}", exc_info=True)
            sched = db.query(Schedule).get(schedule_id)
            if sched:
                sched.last_run_status = "failed"
                db.commit()
        finally:
            db.close()


_scheduler_service: SchedulerService = None


def get_scheduler_service() -> SchedulerService:
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service
