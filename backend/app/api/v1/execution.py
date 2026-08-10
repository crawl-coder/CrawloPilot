"""
任务管理 API

提供任务执行、停止、状态查询、日志查看等接口
"""

import logging
import re
from datetime import datetime, timedelta
from app.core.time_utils import cn_now
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import TaskInstance, TaskStatus, Spider, User, DeployMode
from app.schemas.task import TaskCreate, TaskResponse, TaskStatusResponse, TaskLogResponse

router = APIRouter(prefix="/execution", tags=["execution"])

logger = logging.getLogger(__name__)


def _get_executor_for_task(task):
    """按任务的部署模式返回对应执行器（复用公共执行器注册表）"""
    from app.services.executor_registry import get_executor_for_task
    return get_executor_for_task(task)


def _is_remote_mode(task) -> bool:
    """deploy_mode 是 ssh/docker/agent 或有 process_id 时，需要通过执行器取运行态数据。
    兼容 Enum 与字符串两种 deploy_mode（老数据是字符串）。
    """
    if getattr(task, 'process_id', None):
        return True
    dm = getattr(task, 'deploy_mode', None)
    if dm is None:
        return False
    dm_val = dm.value if hasattr(dm, "value") else str(dm)
    return dm_val in ('ssh', 'docker', 'agent')


def _filter_logs(logs: str, level: Optional[str] = None, since: Optional[str] = None) -> str:
    """对日志文本做 level 关键词与 since 时间窗口过滤。

    - level: 匹配行内级别关键词（ERROR/WARN/INFO 等，大小写不敏感）
    - since: 仅保留最近一段时间内的行（解析行首时间戳，如 `1h`/`30m`/`1d`）
    """
    if not logs:
        return logs
    lines = logs.split('\n')

    # level 关键词过滤
    if level:
        kw = level.strip().upper()
        allowed = []
        for ln in lines:
            up = ln.upper()
            if kw == 'ERROR' and ('ERROR' in up or ' TRACE' in up and ' Traceback' in ln):
                allowed.append(ln)
            elif kw == 'WARN' and ('WARN' in up or 'WARNING' in up):
                allowed.append(ln)
            elif kw == 'INFO' and ('INFO' in up or 'INFO' in up):
                allowed.append(ln)
            else:
                allowed.append(ln) if kw not in ('ERROR', 'WARN', 'INFO') else None
        lines = allowed

    # since 时间窗口过滤（解析行首时间戳）
    if since:
        m = re.fullmatch(r'(\d+)([smhd])', since.strip())
        if m:
            num = int(m.group(1))
            unit = m.group(2)
            seconds = num * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit]
            cutoff = cn_now() - timedelta(seconds=seconds)
            kept = []
            for ln in lines:
                ts = _extract_log_ts(ln)
                if ts is None or ts >= cutoff:
                    kept.append(ln)
            lines = kept

    return '\n'.join(lines)


def _extract_log_ts(line: str):
    """尝试从日志行首解析时间戳，返回 datetime 或 None。

    支持两种格式：`2026-08-08 12:00:00`（完整）与 `12:00:00`（仅时间，
    视为今天的该时刻）。
    """
    if not line:
        return None
    # 完整格式：YYYY-MM-DD HH:MM:SS
    m = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    if m:
        try:
            return datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
    # 仅时间格式：HH:MM:SS（按今天处理）
    m2 = re.match(r'^(\d{2}:\d{2}:\d{2})', line)
    if m2:
        try:
            today = cn_now().date()
            return datetime.combine(today, datetime.strptime(m2.group(1), '%H:%M:%S').time())
        except ValueError:
            return None
    return None


@router.post("/tasks", response_model=TaskResponse)
async def create_and_execute_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建并执行任务（委托统一任务服务，按节点自动分发 local/ssh/docker/agent）

    - **spider_id**: 爬虫 ID
    - **git_url**: Git 仓库地址 (可选)
    - **git_branch**: Git 分支
    - **node_id**: 节点 ID (可选)
    - **memory_limit**: 内存限制
    - **cpu_limit**: CPU 限制
    - **timeout**: 超时时间
    """
    from app.services.task_service import create_and_run_task

    try:
        result = create_and_run_task(
            db,
            spider_id=int(task_data.spider_id),
            node_id=int(task_data.node_id) if task_data.node_id else None,
            background_tasks=background_tasks,
            memory_limit=task_data.memory_limit,
            cpu_limit=task_data.cpu_limit,
            timeout=task_data.timeout,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task = db.query(TaskInstance).filter(TaskInstance.id == result["task_id"]).first()
    spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
    return TaskResponse(
        id=task.id,
        spider_id=task.spider_id,
        spider_name=spider.name if spider else task.spider_name,
        status=task.status,
        deploy_mode=task.deploy_mode or "local",
        node_id=task.node_id,
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
    
    executor = _get_executor_for_task(task)
    from app.services.executor_protocol import supports_pause
    if not supports_pause(executor):
        mode = getattr(task, 'deploy_mode', 'unknown')
        raise HTTPException(status_code=400, detail=f"{mode} 模式暂不支持暂停/恢复")
    ok = await executor.pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=500, detail="暂停任务失败（进程不存在或已结束）")

    return {
        "message": "Pause task requested",
        "task_id": task_id,
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
    
    executor = _get_executor_for_task(task)
    from app.services.executor_protocol import supports_pause
    if not supports_pause(executor):
        mode = getattr(task, 'deploy_mode', 'unknown')
        raise HTTPException(status_code=400, detail=f"{mode} 模式暂不支持暂停/恢复")
    ok = await executor.resume_task(task_id)
    if not ok:
        raise HTTPException(status_code=500, detail="恢复任务失败（进程不存在或已结束）")

    return {
        "message": "Resume task requested",
        "task_id": task_id,
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
    
    executor = _get_executor_for_task(task)
    ok = await executor.stop_task(task_id)
    if not ok:
        # 进程不存在时仍将数据库状态置为取消，保证记录可收敛
        task.status = TaskStatus.CANCELLED
        task.finished_at = cn_now()
        db.commit()
        logger.warning(f"Stop task {task_id}: process not found, marked CANCELLED")
        return {
            "message": "Task marked as cancelled",
            "task_id": task_id,
        }
    
    return {
        "message": "Stop task requested",
        "task_id": task_id,
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
    
    # 有进程（本地 PID / 远程 PID / 容器 ID）时从对应执行器获取实时状态
    if _is_remote_mode(task):
        try:
            executor = _get_executor_for_task(task)
            status = executor.get_task_status(task_id)
            if status:
                container_status = status.get('status', 'unknown')
                local_metrics = {
                    'pages_crawled': status.get('pages_crawled', 0),
                    'items_scraped': status.get('items_scraped', 0),
                    'errors_count': status.get('errors_count', 0),
                }
        except Exception as e:
            logger.warning(f"获取执行器状态失败: {e}")
    
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
    level: Optional[str] = None,
    since: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务日志

    - **tail**: 返回末尾 N 行（默认 100）
    - **level**: 按级别过滤（ERROR/WARN/INFO，对日志文本做关键词匹配）
    - **since**: 按时间过滤，如 `1h`（最近1小时）、`30m`、`1d`
    """
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    logs_text = ''

    # 有进程（本地 PID / 远程 PID / 容器 ID）时从对应执行器获取日志
    if _is_remote_mode(task):
        try:
            executor = _get_executor_for_task(task)
            logs_text = executor.get_task_logs(task_id, tail=tail)
        except Exception as e:
            logger.warning(f"获取执行器日志失败: {e}")

    # 二次过滤：level 关键词 + since 时间窗口（针对本地文件日志）
    logs_text = _filter_logs(logs_text, level=level, since=since)

    return TaskLogResponse(
        task_id=task_id,
        logs=logs_text,
        total_lines=len(logs_text.split('\n')) if logs_text else 0
    )


@router.get("/tasks")
async def list_tasks(
    spider_id: Optional[str] = None,
    schedule_id: Optional[int] = None,
    node_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询任务列表

    - **spider_id**: 爬虫 ID (可选)
    - **schedule_id**: 调度 ID (可选)
    - **node_id**: 节点 ID (可选)
    - **status**: 任务状态 (可选)
    - **limit**: 返回数量限制
    - **offset**: 偏移量
    """
    from app.core.pagination import clamp_pagination
    offset, limit = clamp_pagination(offset, limit, default_limit=50)
    query = db.query(TaskInstance)

    if spider_id:
        query = query.filter(TaskInstance.spider_id == spider_id)

    if schedule_id:
        query = query.filter(TaskInstance.schedule_id == schedule_id)

    if node_id:
        query = query.filter(TaskInstance.node_id == node_id)

    if status:
        query = query.filter(TaskInstance.status == status)

    total = query.count()
    tasks = query.order_by(TaskInstance.id.desc()).offset(offset).limit(limit).all()

    result = []
    for task in tasks:
        try:
            spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
            result.append(_serialize_task(task, spider))
        except Exception:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Failed to serialize task %s, skipping", task.id, exc_info=True)

    return {
        "total": total,
        "items": result,
        "skip": offset,
        "limit": limit
    }


# ==================== 静态子路径（必须注册在 /tasks/{task_id} 之前） ====================

@router.get("/tasks/running")
async def get_running_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取运行中的任务"""
    tasks = db.query(TaskInstance).filter(
        TaskInstance.status.in_([TaskStatus.RUNNING, TaskStatus.PENDING])
    ).order_by(TaskInstance.created_at.desc()).all()
    return [_serialize_task(t) for t in tasks]


@router.get("/tasks/stats/summary")
async def get_task_stats(
    schedule_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务统计概览"""
    query = db.query(TaskInstance)
    if schedule_id:
        query = query.filter(TaskInstance.schedule_id == schedule_id)

    total = query.count()
    running = query.filter(TaskInstance.status == TaskStatus.RUNNING).count()
    success = query.filter(TaskInstance.status == TaskStatus.SUCCESS).count()
    failed = query.filter(TaskInstance.status == TaskStatus.FAILED).count()
    today = query.filter(
        TaskInstance.created_at >= cn_now() - timedelta(days=1)
    ).count()

    return {
        "total": total,
        "running": running,
        "failed": failed,
        "success": success,
        "today": today,
        "success_rate": round(success / total * 100, 2) if total > 0 else 0,
    }


@router.get("/tasks/recent")
async def get_recent_tasks(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取最近的任务"""
    from app.core.pagination import clamp_pagination
    _, limit = clamp_pagination(0, limit, default_limit=100)
    tasks = db.query(TaskInstance).order_by(
        TaskInstance.created_at.desc()
    ).limit(limit).all()
    return [_serialize_task(t) for t in tasks]


@router.get("/tasks/schedule/{schedule_id}")
async def get_tasks_by_schedule(
    schedule_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定调度的任务"""
    from app.core.pagination import clamp_pagination
    _, limit = clamp_pagination(0, limit, default_limit=50)
    tasks = db.query(TaskInstance).filter(
        TaskInstance.schedule_id == schedule_id
    ).order_by(TaskInstance.created_at.desc()).limit(limit).all()
    return [_serialize_task(t) for t in tasks]


@router.get("/tasks/status/{status}")
async def get_tasks_by_status(
    status: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定状态的任务"""
    from app.core.pagination import clamp_pagination
    _, limit = clamp_pagination(0, limit, default_limit=50)
    try:
        task_status = TaskStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的任务状态")

    tasks = db.query(TaskInstance).filter(
        TaskInstance.status == task_status
    ).order_by(TaskInstance.created_at.desc()).limit(limit).all()
    return [_serialize_task(t) for t in tasks]


def _serialize_task(task: TaskInstance, spider: Optional[Spider] = None) -> dict:
    """任务序列化（供列表/详情复用）"""
    if spider is None:
        spider = task.spider
    return {
        "id": task.id,
        "spider_id": task.spider_id,
        "spider_name": spider.name if spider else task.spider_name,
        "project_id": spider.project_id if spider else None,
        "project_name": spider.project.name if spider and spider.project else None,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "schedule_id": task.schedule_id,
        "worker_node": task.worker_node,
        "container_id": task.container_id,
        "node_id": task.node_id,
        "node_name": task.node.name if task.node else None,
        "deploy_mode": task.deploy_mode.value if hasattr(task.deploy_mode, "value") else task.deploy_mode,
        "memory_limit": task.memory_limit,
        "cpu_limit": task.cpu_limit,
        "process_id": task.process_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "duration": float(task.duration) if task.duration is not None else None,
        "error_message": task.error_message,
        "pages_crawled": task.pages_crawled or 0,
        "items_scraped": task.items_scraped or 0,
        "errors_count": task.errors_count or 0,
        "log_url": task.log_url,
    }


@router.get("/tasks/{task_id}")
async def get_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务完整详情（供执行详情页使用）"""
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
    data = _serialize_task(task, spider)

    # 附带实时进程状态（按部署模式取对应执行器）
    process_status = None
    if _is_remote_mode(task):
        try:
            executor = _get_executor_for_task(task)
            process_status = executor.get_task_status(str(task.id))
        except Exception as e:
            logger.warning(f"获取执行器进程状态失败: {e}")

    data["process_status"] = process_status
    return data


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重试任务（终态任务：失败/超时=纠错重跑，成功/取消=再跑一次）

    走统一任务服务创建并分发，保留原任务的节点与部署模式
    （旧实现强制 local 重跑，docker/ssh 任务重试会降级，已修复）
    """
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    TERMINAL_STATUSES = [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.CANCELLED]
    if task.status not in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="运行中的任务不能重试，请先停止")

    from app.services.task_service import create_and_run_task
    try:
        result = create_and_run_task(
            db,
            spider_id=task.spider_id,
            node_id=task.node_id,
            schedule_id=None,       # 重试视为手动触发，不占调度幂等槽位
            expected_run_at=None,
            memory_limit=task.memory_limit,  # 保留原任务 Docker 资源限制
            cpu_limit=task.cpu_limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # create_and_run_task 返回任务信息 dict（含 task_id/mode 等）
    return {"message": "任务重试已提交", **result}


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
    
    # 如果任务正在运行,先按部署模式停止对应执行器
    if task.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
        try:
            from app.services.executor_registry import get_executor_for_task
            executor = get_executor_for_task(task)
            await executor.stop_task(str(task_id))
        except Exception as e:
            logger.warning(f"停止任务失败: {e}")
    
    # 删除数据库记录
    db.delete(task)
    db.commit()
    
    return {"message": "Task deleted successfully"}
