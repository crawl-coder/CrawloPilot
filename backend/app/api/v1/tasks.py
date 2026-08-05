"""
任务实例 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from typing import Any

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, TaskInstance, TaskStatus, Schedule
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/task-instances", tags=["任务实例"])


# Pydantic Schemas
class TaskInstanceResponse(BaseModel):
    id: int
    schedule_id: int
    spider_name: str
    status: str
    stats: Optional[dict]
    worker_node: Optional[str]
    container_id: Optional[str]
    log_url: Optional[str]
    started_at: Optional[Any]
    finished_at: Optional[Any]
    created_at: Any
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[TaskInstanceResponse])
async def list_task_instances(
    schedule_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务实例列表"""
    query = db.query(TaskInstance)
    
    if schedule_id:
        query = query.filter(TaskInstance.schedule_id == schedule_id)
    
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的任务状态")
        query = query.filter(TaskInstance.status == task_status)
    
    tasks = query.order_by(
        TaskInstance.created_at.desc()
    ).limit(limit).offset(offset).all()
    
    return tasks


@router.get("/{task_id}", response_model=TaskInstanceResponse)
async def get_task_instance(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务实例详情"""
    task = db.query(TaskInstance).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务实例不存在")
    
    return task


@router.get("/schedule/{schedule_id}", response_model=List[TaskInstanceResponse])
async def get_tasks_by_schedule(
    schedule_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取调度配置的任务实例"""
    return db.query(TaskInstance).filter(
        TaskInstance.schedule_id == schedule_id
    ).order_by(TaskInstance.created_at.desc()).limit(limit).all()


@router.get("/status/{status}", response_model=List[TaskInstanceResponse])
async def get_tasks_by_status(
    status: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定状态的任务实例"""
    try:
        task_status = TaskStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的任务状态")
    
    return db.query(TaskInstance).filter(
        TaskInstance.status == task_status
    ).order_by(TaskInstance.created_at.desc()).limit(limit).all()


@router.get("/running", response_model=List[TaskInstanceResponse])
async def get_running_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取运行中的任务"""
    return db.query(TaskInstance).filter(
        TaskInstance.status == TaskStatus.RUNNING
    ).order_by(TaskInstance.created_at.desc()).all()


@router.get("/stats/summary")
async def get_task_stats(
    schedule_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务统计"""
    query = db.query(TaskInstance)
    if schedule_id:
        query = query.filter(TaskInstance.schedule_id == schedule_id)

    total = query.count()
    running = query.filter(TaskInstance.status == TaskStatus.RUNNING).count()
    success = query.filter(TaskInstance.status == TaskStatus.SUCCESS).count()
    failed = query.filter(TaskInstance.status == TaskStatus.FAILED).count()
    today_start = datetime.utcnow() - timedelta(days=1)
    today = query.filter(TaskInstance.created_at >= today_start).count()

    return {
        "total": total,
        "running": running,
        "failed": failed,
        "success": success,
        "today": today,
        "success_rate": round(success / total * 100, 2) if total > 0 else 0,
    }


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重试任务"""
    task = db.query(TaskInstance).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务实例不存在")
    
    if task.status not in [TaskStatus.FAILED, TaskStatus.TIMEOUT]:
        raise HTTPException(status_code=400, detail="只能重试失败或超时的任务")
    
    # 查询爬虫并复用本地执行器重跑
    from app.models import Spider
    from app.services.local_executor import get_local_executor, LocalTaskConfig
    from app.services.upload_service import UploadService
    import os

    spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在，无法重试")

    upload_service = UploadService()
    code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    if not code_dir or not os.path.exists(code_dir):
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在，请先上传代码")

    # 创建新的任务实例并后台执行
    new_task = TaskInstance(
        spider_id=spider.id,
        spider_name=spider.spider_name or spider.name,
        schedule_id=None,
        node_id=task.node_id,
        deploy_mode="local",
        status=TaskStatus.PENDING,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    config = LocalTaskConfig(
        task_id=str(new_task.id),
        spider_id=str(spider.id),
        spider_name=spider.spider_name or spider.name,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider.spider_name or spider.name,
    )
    background_tasks.add_task(get_local_executor().execute_task, config)

    return {"message": "任务重试已提交", "task_id": new_task.id}


@router.post("/{task_id}/stop")
async def stop_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """停止运行中的任务"""
    task = db.query(TaskInstance).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务实例不存在")
    
    if task.status != TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="只能停止运行中的任务")
    
    from app.services.local_executor import get_local_executor
    ok = await get_local_executor().stop_task(str(task_id))
    if not ok:
        raise HTTPException(status_code=500, detail="停止任务失败（进程不存在或已结束）")
    
    return {"message": "任务已停止", "task_id": task_id}


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: int,
    tail: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务日志"""
    task = db.query(TaskInstance).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务实例不存在")
    
    from app.services.local_executor import get_local_executor
    logs_text = get_local_executor().get_task_logs(str(task_id), tail=tail)
    return {
        "task_id": task_id,
        "container_id": task.container_id,
        "logs": logs_text,
        "total_lines": len(logs_text.split("\n")) if logs_text else 0,
    }


@router.get("/recent", response_model=List[TaskInstanceResponse])
async def get_recent_tasks(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取最近的任务实例"""
    return db.query(TaskInstance).order_by(
        TaskInstance.created_at.desc()
    ).limit(limit).all()
