"""
WebSocket 实时推送

提供:
- 任务日志实时推送（基于 LogBroadcaster 线程安全队列）
- 任务状态实时更新
- 任务控制命令接收（暂停/恢复/停止，走真实执行器）
"""

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, Set
import asyncio
import json
import queue
import logging

from app.core.database import SessionLocal
from app.models import TaskInstance, DeployMode
from app.services.log_broadcaster import get_log_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

TERMINAL_STATUSES = ("success", "failed", "cancelled", "timeout")


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # task_id -> WebSocket 连接集合
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        """建立连接"""
        await websocket.accept()
        self.active_connections.setdefault(task_id, set()).add(websocket)
        logger.info(f"WebSocket connected for task {task_id}")

    def disconnect(self, task_id: str, websocket: WebSocket):
        """断开连接"""
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
            logger.info(f"WebSocket disconnected for task {task_id}")

    async def broadcast(self, task_id: str, message: dict):
        """广播消息给所有订阅该任务的客户端"""
        if task_id not in self.active_connections:
            return
        disconnected = []
        for connection in self.active_connections[task_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(task_id, conn)


# 全局连接管理器
manager = ConnectionManager()


@router.websocket("/tasks/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str):
    """
    任务实时数据 WebSocket

    客户端连接后:
    1. 立即推送当前状态
    2. 实时接收日志行（LogBroadcaster）
    3. 周期性推送状态更新
    4. 可发送控制命令 (暂停/恢复/停止)
    """
    # WebSocket 鉴权：从 query 参数读取 token，无效则拒绝连接
    from app.core.security import decode_access_token
    token = websocket.query_params.get("token")
    payload = decode_access_token(token) if token else None
    if not payload or not payload.get("sub"):
        await websocket.close(code=4401, reason="未授权")
        return

    await manager.connect(task_id, websocket)
    broadcaster = get_log_broadcaster()
    log_queue = broadcaster.subscribe(task_id)
    closed = False

    async def send(msg: dict):
        nonlocal closed
        try:
            await websocket.send_json(msg)
        except Exception:
            closed = True

    async def writer():
        """日志 + 状态推送"""
        last_snapshot = None
        while not closed:
            await asyncio.sleep(0.3)

            # 清空日志队列
            while True:
                try:
                    line = log_queue.get_nowait()
                except queue.Empty:
                    break
                await send({"type": "log", "data": line})
                if closed:
                    return

            status = await get_current_task_status(task_id)
            if not status:
                continue

            snapshot = (
                status.get("status"),
                status.get("pages_crawled"),
                status.get("items_scraped"),
                status.get("errors_count"),
            )
            if snapshot != last_snapshot:
                await send({"type": "status", "data": status})
                last_snapshot = snapshot

            # 终态：排空剩余日志后退出
            if status.get("status") in TERMINAL_STATUSES:
                await asyncio.sleep(0.8)
                while True:
                    try:
                        line = log_queue.get_nowait()
                    except queue.Empty:
                        return
                    await send({"type": "log", "data": line})
                    if closed:
                        return

    async def reader():
        """客户端控制命令"""
        while not closed:
            try:
                data = await websocket.receive_text()
            except Exception:
                return

            try:
                message = json.loads(data)
            except Exception:
                continue

            mtype = message.get("type")
            if mtype not in ("pause", "resume", "stop"):
                continue

            new_status = {"pause": "paused", "resume": "running", "stop": "cancelled"}[mtype]

            db = SessionLocal()
            try:
                task = _get_task(db, task_id)
                deploy_mode = getattr(task, "deploy_mode", None) or DeployMode.LOCAL
            finally:
                db.close()

            if deploy_mode == DeployMode.SSH:
                from app.services.ssh_executor import get_ssh_executor
                executor = get_ssh_executor()
            elif deploy_mode == DeployMode.DOCKER:
                from app.services.docker_executor import get_docker_executor
                executor = get_docker_executor()
            elif deploy_mode == DeployMode.AGENT:
                from app.services.agent_service import get_agent_service
                executor = get_agent_service()
            else:
                from app.services.local_executor import get_local_executor
                executor = get_local_executor()

            from app.services.executor_protocol import supports_pause
            if mtype in ("pause", "resume") and not supports_pause(executor):
                await send({"type": "error", "message": f"{deploy_mode.upper()} 模式暂不支持暂停/恢复"})
                continue

            if mtype == "pause":
                ok = await executor.pause_task(task_id)
            elif mtype == "resume":
                ok = await executor.resume_task(task_id)
            else:
                ok = await executor.stop_task(task_id)
                if not ok:
                    # 进程不存在：兜底将数据库置为取消
                    db = SessionLocal()
                    try:
                        task = _get_task(db, task_id)
                        if task:
                            from app.models import TaskStatus
                            task.status = TaskStatus.CANCELLED
                            from datetime import datetime
                            task.finished_at = datetime.utcnow()
                            db.commit()
                            ok = True
                    finally:
                        db.close()

            if not ok:
                await send({"type": "error", "message": f"{mtype} failed: process not found"})
                continue

            await manager.broadcast(task_id, {
                "type": "status",
                "data": {"task_id": task_id, "status": new_status}
            })
            await send({"type": "success", "message": f"Task {mtype}d"})

    try:
        writer_task = asyncio.create_task(writer())
        reader_task = asyncio.create_task(reader())
        done, pending = await asyncio.wait(
            {writer_task, reader_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
    finally:
        broadcaster.unsubscribe(task_id, log_queue)
        manager.disconnect(task_id, websocket)


def _get_task(db, task_id: str):
    """按 ID 查询任务（兼容 int/str）"""
    try:
        return db.query(TaskInstance).filter(TaskInstance.id == int(task_id)).first()
    except (ValueError, TypeError):
        return None


async def get_current_task_status(task_id: str):
    """获取当前任务状态（含指标）"""
    db = SessionLocal()
    try:
        task = _get_task(db, task_id)
        if not task:
            return None

        status = task.status.value if hasattr(task.status, "value") else task.status
        duration = None
        if task.duration is not None:
            duration = float(task.duration)
        elif task.started_at and task.finished_at:
            duration = round((task.finished_at - task.started_at).total_seconds(), 2)

        return {
            "task_id": task.id,
            "status": status,
            "pages_crawled": getattr(task, "pages_crawled", 0) or 0,
            "items_scraped": getattr(task, "items_scraped", 0) or 0,
            "errors_count": getattr(task, "errors_count", 0) or 0,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "duration": duration,
        }
    finally:
        db.close()
