"""
任务管理 API

提供任务执行、停止、状态查询、日志查看等接口
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import TaskInstance, TaskStatus, Spider, User
from app.schemas.task import TaskCreate, TaskResponse, TaskStatusResponse, TaskLogResponse
from app.services.task_executor import get_executor
from app.workers.celery_app import celery_app

router = APIRouter(prefix="/execution", tags=["execution"])

logger = logging.getLogger(__name__)


@router.post("/tasks", response_model=TaskResponse)
async def create_and_execute_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建并执行任务
    
    - **spider_id**: 爬虫 ID
    - **git_url**: Git 仓库地址 (可选)
    - **git_branch**: Git 分支
    - **node_id**: 节点 ID (可选)
    - **memory_limit**: 内存限制
    - **cpu_limit**: CPU 限制
    - **timeout**: 超时时间
    """
    # 验证爬虫存在
    spider = db.query(Spider).filter(Spider.id == task_data.spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="Spider not found")
    
    # 创建任务记录
    task = TaskInstance(
        spider_id=spider.id,
        schedule_id=None,  # 手动执行,没有调度
        status=TaskStatus.PENDING,
        worker_node=None
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    logger.info(f"Task created: {task.id} for spider {spider.name}")
    
    # 异步执行任务
    celery_app.send_task(
        'app.workers.task_tasks.execute_spider_task',
        args=[
            task.id,
            spider.id,
            spider.name
        ],
        kwargs={
            'git_url': task_data.git_url or spider.git_url,
            'git_branch': task_data.git_branch or spider.git_branch or 'main',
            'entry_file': spider.entry_file,  # 传递入口文件
            'spider_name': spider.spider_name or spider.name,  # 传递爬虫名称
            'node_id': task_data.node_id,
            'memory_limit': task_data.memory_limit or '512m',
            'cpu_limit': task_data.cpu_limit or 1.0,
            'timeout': task_data.timeout or 3600,
        }
    )
    
    return TaskResponse(
        id=task.id,
        spider_id=task.spider_id,
        spider_name=spider.name,
        status=task.status,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at
    )


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """暂停任务"""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 检查任务状态
    if task.status != TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail=f"Cannot pause task in {task.status} status")
    
    # 异步暂停任务
    result = celery_app.send_task(
        'app.workers.task_tasks.pause_spider_task',
        args=[task_id]
    )
    
    return {
        "message": "Pause task requested",
        "task_id": task_id,
        "celery_task_id": result.id
    }


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """恢复任务"""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 检查任务状态
    if task.status != TaskStatus.PAUSED:
        raise HTTPException(status_code=400, detail=f"Cannot resume task in {task.status} status")
    
    # 异步恢复任务
    result = celery_app.send_task(
        'app.workers.task_tasks.resume_spider_task',
        args=[task_id]
    )
    
    return {
        "message": "Resume task requested",
        "task_id": task_id,
        "celery_task_id": result.id
    }


@router.post("/tasks/{task_id}/stop")
async def stop_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """停止任务"""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 检查任务状态
    if task.status not in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
        raise HTTPException(status_code=400, detail=f"Cannot stop task in {task.status} status")
    
    # 异步停止任务
    result = celery_app.send_task(
        'app.workers.task_tasks.stop_spider_task',
        args=[task_id]
    )
    
    return {
        "message": "Stop task requested",
        "task_id": task_id,
        "celery_task_id": result.id
    }


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务状态"""
    # 查询数据库
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 尝试获取容器/本地状态
    container_status = None
    local_metrics = {}
    
    # 如果有 process_id，尝试从本地执行器获取
    if getattr(task, 'process_id', None):
        try:
            from app.services.local_executor import get_local_executor
            local_executor = get_local_executor()
            status = local_executor.get_task_status(task_id)
            if status:
                container_status = status.get('status', 'unknown')
                local_metrics = {
                    'pages_crawled': status.get('pages_crawled', 0),
                    'items_scraped': status.get('items_scraped', 0),
                    'errors_count': status.get('errors_count', 0),
                }
        except Exception as e:
            logger.warning(f"获取本地状态失败: {e}")
    else:
        # 尝试通过 Celery 查询容器状态
        try:
            result = celery_app.send_task(
                'app.workers.task_tasks.get_task_status',
                args=[task_id]
            )
            container_status_raw = result.get(timeout=5)
            if container_status_raw and container_status_raw.get('success'):
                container_status = container_status_raw.get('status')
        except Exception as e:
            logger.warning(f"获取容器状态失败: {e}")
    
    # 计算 duration
    duration = None
    if task.duration is not None:
        duration = float(task.duration)
    elif task.started_at and task.finished_at:
        duration = (task.finished_at - task.started_at).total_seconds()
    
    return TaskStatusResponse(
        task_id=task_id,
        db_status=task.status.value if hasattr(task.status, 'value') else str(task.status),
        container_status=container_status,
        container_id=task.container_id,
        started_at=task.started_at,
        finished_at=task.finished_at,
        error_message=getattr(task, 'error_message', None),
        duration=duration
    )


@router.get("/tasks/{task_id}/logs", response_model=TaskLogResponse)
async def get_task_logs(
    task_id: str,
    tail: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务日志"""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    logs_text = ''
    
    # 如果有 process_id，从本地执行器获取日志
    if getattr(task, 'process_id', None):
        try:
            from app.services.local_executor import get_local_executor
            local_executor = get_local_executor()
            logs_text = local_executor.get_task_logs(task_id, tail=tail)
        except Exception as e:
            logger.warning(f"获取本地日志失败: {e}")
    else:
        # 尝试通过 Celery 获取容器日志
        try:
            result = celery_app.send_task(
                'app.workers.task_tasks.get_task_logs',
                args=[task_id, tail]
            )
            logs_data = result.get(timeout=5)
            if logs_data and logs_data.get('success'):
                logs_text = logs_data.get('logs', '')
        except Exception as e:
            logger.warning(f"获取容器日志失败: {e}")
    
    return TaskLogResponse(
        task_id=task_id,
        logs=logs_text,
        total_lines=len(logs_text.split('\n')) if logs_text else 0
    )


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    spider_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询任务列表
    
    - **spider_id**: 爬虫 ID (可选)
    - **status**: 任务状态 (可选)
    - **limit**: 返回数量限制
    - **offset**: 偏移量
    """
    query = db.query(TaskInstance)
    
    if spider_id:
        query = query.filter(TaskInstance.spider_id == spider_id)
    
    if status:
        query = query.filter(TaskInstance.status == status)
    
    tasks = query.order_by(TaskInstance.started_at.desc()).offset(offset).limit(limit).all()
    
    result = []
    for task in tasks:
        spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
        result.append(TaskResponse(
            id=task.id,
            spider_id=task.spider_id,
            spider_name=spider.name if spider else "Unknown",
            project_name=spider.project.name if spider and spider.project else None,
            status=task.status,
            schedule_id=task.schedule_id,
            worker_node=task.worker_node,
            container_id=task.container_id,
            node_id=task.node_id,
            node_name=task.node.name if task.node else None,
            deploy_mode=task.deploy_mode,
            created_at=task.created_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
            duration=task.duration,
            error_message=task.error_message
        ))
    
    return result


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除任务记录"""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 如果任务正在运行,先停止
    if task.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
        try:
            from app.services.local_executor import get_local_executor
            local_executor = get_local_executor()
            await local_executor.stop_task(str(task_id))
        except Exception as e:
            logger.warning(f"停止任务失败: {e}")
    
    # 删除数据库记录
    db.delete(task)
    db.commit()
    
    return {"message": "Task deleted successfully"}
