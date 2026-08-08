"""
Agent 任务服务端 shim

Agent 模式的任务由节点上的 agent 程序执行并回报，控制端只负责：
- 状态：读取数据库（agent 回报）
- 日志：读取 _task_logs 落盘文件（agent 实时上报）
- 停止：写入 task.stats.stop_requested 标记，agent 轮询到后终止进程
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

LOGS_DIR = Path(settings.UPLOAD_DIR) / "_task_logs"


class AgentTaskService:
    """Agent 模式任务控制"""

    async def execute_task(self, config) -> str:
        """启动任务（契约实现）。

        Agent 模式的"启动"即把任务置为 PENDING，交由节点上的 agent 拉取执行。
        本方法为幂等操作：若任务已存在且待领取，直接返回 task_id。
        """
        task_id = str(getattr(config, "task_id", ""))
        if not task_id:
            raise ValueError("Agent execute_task 缺少 task_id")
        db = SessionLocal()
        try:
            task = (
                db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first()
                if task_id.isdigit()
                else None
            )
            if not task:
                raise ValueError(f"任务 {task_id} 不存在")
            # 确保任务处于 PENDING，等待节点 agent 领取
            if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.PENDING
                db.commit()
            logger.info(f"Agent 任务 {task_id} 已就绪，等待节点领取")
            return task_id
        finally:
            db.close()

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first() \
                if str(task_id).isdigit() else None
            if not task:
                return None
            return {
                "task_id": task_id,
                "status": task.status.value if hasattr(task.status, "value") else str(task.status),
                "node_id": task.node_id,
                "pages_crawled": task.pages_crawled or 0,
                "items_scraped": task.items_scraped or 0,
                "errors_count": task.errors_count or 0,
                "duration": float(task.duration) if task.duration is not None else None,
            }
        except Exception as e:
            logger.error(f"查询 Agent 任务状态失败: {e}")
            return None
        finally:
            db.close()

    def get_task_logs(self, task_id: str, tail: int = 100) -> str:
        log_file = LOGS_DIR / f"task_{task_id}.log"
        if not log_file.exists():
            return "无日志（Agent 尚未上报）"
        try:
            lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[-tail:])
        except Exception as e:
            logger.error(f"读取 Agent 任务日志失败: {e}")
            return "读取日志失败"

    async def stop_task(self, task_id: str) -> bool:
        """写入停止标记，Agent 轮询到后终止进程"""
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first() \
                if str(task_id).isdigit() else None
            if not task:
                return False
            stats = dict(task.stats or {})
            stats["stop_requested"] = True
            task.stats = stats
            db.commit()
            logger.info(f"Agent 任务 {task_id} 已写入停止标记")
            return True
        except Exception as e:
            logger.error(f"写入 Agent 停止标记失败: {e}")
            db.rollback()
            return False
        finally:
            db.close()


_agent_service: Optional[AgentTaskService] = None


def get_agent_service() -> AgentTaskService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentTaskService()
    return _agent_service
