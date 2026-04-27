"""
WebSocket 实时推送

提供:
- 任务日志实时推送
- 任务状态实时更新
- 任务控制命令接收
"""

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, Set, Optional
import asyncio
import json
import logging
from datetime import datetime

from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # task_id -> WebSocket 连接集合
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, task_id: str, websocket: WebSocket):
        """建立连接"""
        await websocket.accept()
        
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        
        self.active_connections[task_id].add(websocket)
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
        if task_id in self.active_connections:
            disconnected = []
            
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")
                    disconnected.append(connection)
            
            # 清理断开的连接
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
    2. 实时接收日志和指标更新
    3. 可发送控制命令 (暂停/恢复/停止)
    """
    await manager.connect(task_id, websocket)
    
    try:
        # 1. 推送当前状态
        task_status = await get_current_task_status(task_id)
        if task_status:
            await websocket.send_json({
                "type": "status",
                "data": task_status
            })
        
        # 2. 保持连接,接收客户端消息
        while True:
            # 接收客户端消息 (如: 暂停/恢复命令)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "pause":
                await handle_pause(task_id, websocket)
            elif message.get("type") == "resume":
                await handle_resume(task_id, websocket)
            elif message.get("type") == "stop":
                await handle_stop(task_id, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(task_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
        manager.disconnect(task_id, websocket)


async def get_current_task_status(task_id: str):
    """获取当前任务状态"""
    db = SessionLocal()
    try:
        # 尝试解析 task_id 为整数
        try:
            task_id_int = int(task_id)
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id_int).first()
        except ValueError:
            task = None
        
        if not task:
            return None
        
        return {
            "task_id": task.id,
            "status": task.status.value if hasattr(task.status, 'value') else task.status,
            "pages_crawled": getattr(task, 'pages_crawled', 0),
            "items_scraped": getattr(task, 'items_scraped', 0),
            "errors_count": getattr(task, 'errors_count', 0),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None
        }
    finally:
        db.close()


async def handle_pause(task_id: str, websocket: WebSocket):
    """处理暂停命令"""
    try:
        db = SessionLocal()
        try:
            try:
                task_id_int = int(task_id)
            except ValueError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid task ID"
                })
                return
            
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id_int).first()
            if not task:
                await websocket.send_json({
                    "type": "error",
                    "message": "Task not found"
                })
                return
            
            if task.status != TaskStatus.RUNNING:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Cannot pause task in {task.status} status"
                })
                return
            
            # 更新状态
            task.status = TaskStatus.PAUSED
            db.commit()
            
            # 推送状态更新
            await manager.broadcast(task_id, {
                "type": "status",
                "data": {
                    "task_id": task.id,
                    "status": "paused"
                }
            })
            
            await websocket.send_json({
                "type": "success",
                "message": "Task paused"
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to pause task: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


async def handle_resume(task_id: str, websocket: WebSocket):
    """处理恢复命令"""
    try:
        db = SessionLocal()
        try:
            try:
                task_id_int = int(task_id)
            except ValueError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid task ID"
                })
                return
            
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id_int).first()
            if not task:
                await websocket.send_json({
                    "type": "error",
                    "message": "Task not found"
                })
                return
            
            if task.status != TaskStatus.PAUSED:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Cannot resume task in {task.status} status"
                })
                return
            
            # 更新状态
            task.status = TaskStatus.RUNNING
            db.commit()
            
            # 推送状态更新
            await manager.broadcast(task_id, {
                "type": "status",
                "data": {
                    "task_id": task.id,
                    "status": "running"
                }
            })
            
            await websocket.send_json({
                "type": "success",
                "message": "Task resumed"
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to resume task: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


async def handle_stop(task_id: str, websocket: WebSocket):
    """处理停止命令"""
    try:
        db = SessionLocal()
        try:
            try:
                task_id_int = int(task_id)
            except ValueError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid task ID"
                })
                return
            
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id_int).first()
            if not task:
                await websocket.send_json({
                    "type": "error",
                    "message": "Task not found"
                })
                return
            
            # 更新状态
            task.status = TaskStatus.CANCELLED
            db.commit()
            
            # 推送状态更新
            await manager.broadcast(task_id, {
                "type": "status",
                "data": {
                    "task_id": task.id,
                    "status": "cancelled"
                }
            })
            
            await websocket.send_json({
                "type": "success",
                "message": "Task stopped"
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to stop task: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

