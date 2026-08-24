"""
任务终态原子更新工具

用 `UPDATE ... WHERE status NOT IN (terminal)` 在 DB 层保证终态保护：
任务一旦进入终态（SUCCESS/FAILED/CANCELLED/TIMEOUT），后续任何并发写入
（监控线程、stop_task）都无法覆盖，避免 TOCTOU 竞态把 CANCELLED 改写为 FAILED。
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import update

from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus, Schedule

logger = logging.getLogger(__name__)


TERMINAL_STATUSES = {
    TaskStatus.SUCCESS,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.TIMEOUT,
}


def update_task_completion(
    task_id,
    status: TaskStatus,
    finished_at: datetime,
    pages_crawled: int = 0,
    items_scraped: int = 0,
    errors_count: int = 0,
    error_message: Optional[str] = None,
    deploy_mode: Optional[str] = None,
    container_id: Optional[str] = None,
    logs: Optional[str] = None,
    log_dir=None,
) -> bool:
    """原子更新任务终态；任务已是终态时返回 False（不覆盖）。

    logs 非空且 log_dir 提供时，同时落盘日志（容器清理后仍可查询）。
    """
    db = SessionLocal()
    try:
        values = {
            "status": status,
            "finished_at": finished_at,
            "pages_crawled": pages_crawled,
            "items_scraped": items_scraped,
            "errors_count": errors_count,
        }
        if error_message:
            values["error_message"] = error_message
        if deploy_mode:
            values["deploy_mode"] = deploy_mode
        if container_id:
            values["container_id"] = container_id

        result = db.execute(
            update(TaskInstance)
            .where(TaskInstance.id == int(task_id))
            .where(TaskInstance.status.notin_(TERMINAL_STATUSES))
            .values(**values)
        )
        db.commit()
        updated = (result.rowcount or 0) > 0

        if not updated:
            logger.info(
                f"[{task_id}] 任务已是终态，忽略本次覆盖为 {status.value}"
            )
            return False

        # 回填 duration（finished_at - started_at）
        task = db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first()
        if task and task.started_at:
            task.duration = (finished_at - task.started_at).total_seconds()
            db.commit()

        # 回写所属调度的上次状态与成功/失败计数（修复"上次状态永远 running"）
        if task and task.schedule_id:
            sched = db.query(Schedule).filter(Schedule.id == task.schedule_id).first()
            if sched:
                sched.last_run_status = status.value
                sched.last_run_at = finished_at
                sched.last_run_task_id = task.id
                if status == TaskStatus.SUCCESS:
                    sched.success_count = (sched.success_count or 0) + 1
                elif status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
                    sched.fail_count = (sched.fail_count or 0) + 1
                db.commit()

        # 告警事件发布（Wave C 引擎 + 兼容旧 webhook）
        if status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
            try:
                from app.services.alert_engine import publish
                publish(status.value, {
                    "target_id": task.id,
                    "target_name": task.spider_name or "",
                    "spider_id": task.spider_id,
                    "project_id": task.spider.project_id if task.spider else None,
                    "error_message": error_message,
                    "duration": task.duration,
                    "started_at": task.started_at,
                    "finished_at": finished_at,
                })
            except Exception as e:
                logger.warning(f"[{task_id}] 触发告警事件异常: {e}")
            # 兼容旧版 ALERT_WEBHOOK_URL 单点通知
            try:
                from app.services.alert_service import notify_task_failed
                spider_name = task.spider_name or (task.spider.name if task.spider else "")
                project_name = task.spider.project.name if task.spider and task.spider.project else ""
                node_name = task.node.name if task.node else ""
                notify_task_failed(
                    task.id, spider_name, project_name, node_name,
                    status.value, error_message, task.duration,
                    task.started_at, finished_at,
                )
            except Exception as e:
                logger.warning(f"[{task_id}] 触发失败告警异常: {e}")

        logger.info(
            f"[{task_id}] 任务完成: status={status.value}, "
            f"pages={pages_crawled}, items={items_scraped}, "
            f"errors={errors_count}"
        )

        if logs and log_dir is not None:
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                (log_dir / f"task_{task_id}.log").write_text(logs, encoding="utf-8")
            except OSError as e:
                logger.warning(f"[{task_id}] 日志落盘失败: {e}")
        return True
    except Exception as e:
        logger.error(f"更新任务完成信息失败: {e}")
        db.rollback()
        return False
    finally:
        db.close()
