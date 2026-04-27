"""
调度配置 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from typing import Any

from app.core.database import get_db, SessionLocal
from app.core.dependencies import get_current_user
from app.models import User, Schedule, ScheduleType
from app.scheduler import scheduler_manager, ScheduleStore, DAGParser
from app.scheduler.job_store import TaskInstanceStore
from app.workers.schedule_tasks import execute_schedule_task
import logging

logger = logging.getLogger(__name__)


# 包装函数：避免 Celery .delay() 方法直接给 APScheduler 序列化时参数错乱
def _schedule_celery_job(schedule_id: int):
    """APScheduler 安全的 Celery 任务调用包装"""
    execute_schedule_task.delay(schedule_id)

router = APIRouter(prefix="/schedules", tags=["调度管理"])


# Pydantic Schemas
class ScheduleCreate(BaseModel):
    project_id: int
    spider_name: str
    node_id: Optional[int] = None
    schedule_type: str  # cron, interval, once
    cron_expr: Optional[str] = None
    interval_seconds: Optional[int] = None
    priority: int = 5
    max_concurrency: int = 1
    timeout_seconds: int = 3600
    retry_strategy: Optional[str] = None
    enabled: bool = True

class ScheduleUpdate(BaseModel):
    spider_name: Optional[str] = None
    node_id: Optional[int] = None
    schedule_type: Optional[str] = None
    cron_expr: Optional[str] = None
    interval_seconds: Optional[int] = None
    priority: Optional[int] = None
    max_concurrency: Optional[int] = None
    timeout_seconds: Optional[int] = None
    retry_strategy: Optional[str] = None
    enabled: Optional[bool] = None

class ScheduleResponse(BaseModel):
    id: int
    project_id: int
    spider_name: str
    node_id: Optional[int] = None
    schedule_type: str
    cron_expr: Optional[str]
    interval_seconds: Optional[int]
    priority: int
    max_concurrency: int
    timeout_seconds: int
    retry_strategy: Optional[str]
    enabled: bool
    next_run_time: Optional[Any]
    created_at: Any
    updated_at: Optional[Any]
    
    class Config:
        from_attributes = True


@router.post("", response_model=ScheduleResponse)
async def create_schedule(
    schedule_data: ScheduleCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建调度配置"""
    try:
        # 验证调度类型
        if schedule_data.schedule_type not in ["cron", "interval", "once"]:
            raise HTTPException(status_code=400, detail="无效的调度类型")
        
        if schedule_data.schedule_type == "cron" and not schedule_data.cron_expr:
            raise HTTPException(status_code=400, detail="Cron 调度需要提供 cron_expr")
        
        if schedule_data.schedule_type == "interval" and not schedule_data.interval_seconds:
            raise HTTPException(status_code=400, detail="间隔调度需要提供 interval_seconds")
        
        # 创建调度配置
        schedule_store = ScheduleStore(db)
        schedule = schedule_store.create_schedule({
            "project_id": schedule_data.project_id,
            "spider_name": schedule_data.spider_name,
            "node_id": schedule_data.node_id,
            "schedule_type": ScheduleType(schedule_data.schedule_type),
            "cron_expr": schedule_data.cron_expr,
            "interval_seconds": schedule_data.interval_seconds,
            "priority": schedule_data.priority,
            "max_concurrency": schedule_data.max_concurrency,
            "timeout_seconds": schedule_data.timeout_seconds,
            "retry_strategy": schedule_data.retry_strategy,
            "enabled": schedule_data.enabled
        })
        
        # 添加到调度器
        if schedule.enabled:
            background_tasks.add_task(
                register_schedule_to_scheduler,
                schedule.id
            )
        
        return schedule
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create schedule: {e}")
        raise HTTPException(status_code=500, detail=f"创建调度失败: {str(e)}")


@router.get("")
async def list_schedules(
    project_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取调度列表(带分页)"""
    query = db.query(Schedule)
    
    if project_id:
        query = query.filter(Schedule.project_id == project_id)
    
    if enabled is not None:
        query = query.filter(Schedule.enabled == enabled)
    
    total = query.count()
    schedules = query.order_by(Schedule.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": schedules, "skip": skip, "limit": limit}


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取调度详情"""
    schedule = db.query(Schedule).get(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="调度配置不存在")
    
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新调度配置"""
    schedule_store = ScheduleStore(db)
    schedule = schedule_store.get_schedule(schedule_id)
    
    if not schedule:
        raise HTTPException(status_code=404, detail="调度配置不存在")
    
    update_data = schedule_data.dict(exclude_unset=True)
    
    # 转换 schedule_type
    if "schedule_type" in update_data:
        update_data["schedule_type"] = ScheduleType(update_data["schedule_type"])
    
    schedule = schedule_store.update_schedule(schedule_id, update_data)
    
    # 重新注册到调度器
    if schedule.enabled:
        scheduler_manager.remove_job(f"schedule_{schedule_id}")
        scheduler_manager.add_cron_job(
            f"schedule_{schedule_id}",
            _schedule_celery_job,
            schedule.cron_expr or "*/5 * * * *",
            args=[schedule_id]
        )
    
    return schedule


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除调度配置"""
    schedule_store = ScheduleStore(db)
    
    # 从调度器移除
    scheduler_manager.remove_job(f"schedule_{schedule_id}")
    
    # 删除数据库记录
    success = schedule_store.delete_schedule(schedule_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="调度配置不存在")
    
    return {"message": "调度配置已删除"}


@router.post("/{schedule_id}/enable")
async def enable_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """启用调度"""
    schedule_store = ScheduleStore(db)
    schedule = schedule_store.toggle_schedule(schedule_id, True)
    
    if not schedule:
        raise HTTPException(status_code=404, detail="调度配置不存在")
    
    # 添加到调度器
    if schedule.cron_expr:
        scheduler_manager.add_cron_job(
            f"schedule_{schedule_id}",
            _schedule_celery_job,
            schedule.cron_expr,
            args=[schedule_id]
        )
    
    return {"message": "调度已启用"}


@router.post("/{schedule_id}/disable")
async def disable_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """禁用调度"""
    schedule_store = ScheduleStore(db)
    schedule = schedule_store.toggle_schedule(schedule_id, False)
    
    if not schedule:
        raise HTTPException(status_code=404, detail="调度配置不存在")
    
    # 从调度器移除
    scheduler_manager.remove_job(f"schedule_{schedule_id}")
    
    return {"message": "调度已禁用"}


@router.post("/{schedule_id}/trigger")
async def trigger_schedule(
    schedule_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动触发调度"""
    schedule = db.query(Schedule).get(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="调度配置不存在")
    
    # 异步执行任务
    background_tasks.add_task(execute_schedule_task.delay, schedule_id)
    
    return {"message": "任务已触发"}


@router.get("/{schedule_id}/dag")
async def get_schedule_dag(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取调度的 DAG 依赖关系"""
    # 获取项目的所有调度
    schedule = db.query(Schedule).get(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="调度配置不存在")
    
    project_schedules = db.query(Schedule).filter(
        Schedule.project_id == schedule.project_id
    ).all()
    
    # 构建 DAG
    dag_parser = DAGParser()
    for s in project_schedules:
        dag_parser.add_task(
            schedule_id=s.id,
            task_id=f"schedule_{s.id}",
            dependencies=[]  # TODO: 从配置中获取依赖
        )
    
    dag_info = dag_parser.get_dag_info()
    return dag_info


def register_schedule_to_scheduler(schedule_id: int):
    """注册调度到调度器"""
    db = SessionLocal()
    try:
        from app.core.database import SessionLocal
        from app.scheduler import ScheduleStore
        
        schedule_store = ScheduleStore(db)
        schedule = schedule_store.get_schedule(schedule_id)
        
        if schedule and schedule.enabled and schedule.cron_expr:
            scheduler_manager.add_cron_job(
                f"schedule_{schedule_id}",
                _schedule_celery_job,
                schedule.cron_expr,
                args=[schedule_id]
            )
            logger.info(f"Schedule registered: {schedule_id}")
    except Exception as e:
        logger.error(f"Failed to register schedule {schedule_id}: {e}")
    finally:
        db.close()
