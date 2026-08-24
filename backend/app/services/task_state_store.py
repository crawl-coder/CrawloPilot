"""
TaskStateStore：任务级状态中间层（Wave D）

任务状态变更的唯一入口。所有执行器（local/ssh/docker/agent）的状态写入
必须经过此模块，保证：
1. DB 层原子转换（UPDATE WHERE status IN ... 只成功一次）
2. Redis 心跳 TTL（分布式模式下 60s 过期由 reaper 标记 failed）
3. 审计日志（每次 transition 记录）
4. 指标统计回写（pages/items/errors）

V1 standalone 模式：仅 DB 操作，Redis 可选。
V2 distributed 模式：DB + Redis 双写，心跳 TTL 在 Redis 中管理。
"""
import logging
from datetime import timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy import update, and_
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.time_utils import cn_now
from app.core.redis import get_redis, is_redis_available
from app.models import TaskInstance, TaskStatus

logger = logging.getLogger(__name__)

# 心跳 TTL（秒）：Crawlo Worker 心跳 15s ± jitter，60s 覆盖 2 次心跳周期
HEARTBEAT_TTL = 60

# 终态集合
TERMINAL_STATUSES = {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT}


class TaskStateStore:
    """任务级状态变更的唯一入口"""

    def complete_task(
        self,
        task_id,
        status: TaskStatus,
        finished_at,
        pages_crawled: int = 0,
        items_scraped: int = 0,
        errors_count: int = 0,
        error_message=None,
        deploy_mode=None,
        container_id=None,
        logs=None,
        log_dir=None,
    ) -> bool:
        """终态更新（委托 task_updater 实现，保持所有业务逻辑不变）。

        执行器统一通过此方法写入终态，不直接写 DB。
        """
        from app.services.task_updater import update_task_completion
        return update_task_completion(
            task_id, status, finished_at,
            pages_crawled, items_scraped, errors_count,
            error_message, deploy_mode, container_id, logs, log_dir,
        )

    def transition(
        self,
        db: Session,
        task_id,
        from_statuses: List[TaskStatus],
        to_status: TaskStatus,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """原子状态转换。仅当当前状态在 from_statuses 中时才转换。

        Args:
            db: 数据库会话
            task_id: 任务 ID
            from_statuses: 允许的起始状态列表
            to_status: 目标状态
            payload: 附加字段（pages_crawled/items_scraped/errors_count/error_message 等）

        Returns:
            True 表示转换成功，False 表示状态已变（不匹配 from_statuses）
        """
        values = {"status": to_status}
        if payload:
            values.update(payload)
        if to_status in TERMINAL_STATUSES:
            values["finished_at"] = cn_now()

        stmt = (
            update(TaskInstance)
            .where(and_(
                TaskInstance.id == task_id,
                TaskInstance.status.in_(from_statuses),
            ))
            .values(**values)
        )
        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 0:
            logger.debug(f"TaskStateStore: task={task_id} 状态已变，转换 {from_statuses}→{to_status} 跳过")
            return False

        logger.info(f"TaskStateStore: task={task_id} {from_statuses}→{to_status}")
        return True

    def heartbeat(self, task_id, metrics: Optional[Dict] = None):
        """执行器心跳上报。Redis TTL 60s，过期由 reaper 标记任务 failed。

        metrics: {cpu_usage, memory_usage, pages_crawled, items_scraped, ...}
        """
        r = get_redis()
        if not r:
            return  # standalone 模式无需 Redis 心跳
        try:
            key = f"crawlopilot:task:heartbeat:{task_id}"
            import json
            data = {"ts": cn_now().isoformat()}
            if metrics:
                data.update(metrics)
            r.setex(key, HEARTBEAT_TTL, json.dumps(data, default=str))
        except Exception as e:
            logger.warning(f"TaskStateStore heartbeat failed: {e}")

    def check_stale_tasks(self, stale_seconds: int = HEARTBEAT_TTL * 3):
        """扫描 Redis 中心跳过期的 running 任务，标记为 failed（reaper）。

        仅在 Redis 可用时执行（distributed 模式）；standalone 模式由 task_reconciler 处理。
        """
        r = get_redis()
        if not r:
            return
        db = SessionLocal()
        try:
            running_tasks = (
                db.query(TaskInstance.id)
                .filter(TaskInstance.status == TaskStatus.RUNNING)
                .all()
            )
            now = cn_now()
            for (task_id,) in running_tasks:
                key = f"crawlopilot:task:heartbeat:{task_id}"
                if not r.exists(key):
                    # 心跳 key 不存在（过期或从未上报）→ 检查任务是否超龄
                    task = db.query(TaskInstance).get(task_id)
                    if task and task.started_at:
                        age = (now - task.started_at).total_seconds()
                        if age > stale_seconds:
                            self.transition(db, task_id, [TaskStatus.RUNNING], TaskStatus.FAILED,
                                            {"error_message": f"TaskStateStore: 心跳超期 ({stale_seconds}s)，标记 failed"})
        finally:
            db.close()

    def update_stats(self, task_id, stats: Dict[str, Any]):
        """更新爬虫统计指标（来自 Crawlo ProgressAggregator 或日志解析）"""
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).get(task_id)
            if not task:
                return
            if "pages_crawled" in stats:
                task.pages_crawled = stats["pages_crawled"]
            if "items_scraped" in stats:
                task.items_scraped = stats["items_scraped"]
            if "errors_count" in stats:
                task.errors_count = stats["errors_count"]
            db.commit()
        finally:
            db.close()

    def append_log(self, task_id, line: str, level: str = "INFO"):
        """日志写入（V1 保留文件落盘，此处为扩展点供 Loki 等接入）"""
        # V1 行为：日志由各执行器直接写入 uploads/_task_logs/task_{id}.log
        # 此方法为 V2 Loki 聚合预留接口
        pass


# 全局单例
_store = TaskStateStore()


def get_task_state_store() -> TaskStateStore:
    return _store
