"""
定时任务调度 API

V1（方案 A）以"爬虫默认调度"为主：POST /schedules 对同一爬虫做 upsert。
独立列表页（V2）复用同一套接口。
"""
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import Node, Schedule, ScheduleType, Spider, TaskInstance, User

router = APIRouter(prefix="/schedules", tags=["定时任务"])


# ==================== Schemas ====================

class ScheduleCreate(BaseModel):
    """创建/更新调度（对同一爬虫 upsert，V1 一对一）"""
    spider_id: int
    name: Optional[str] = None
    node_id: Optional[int] = None
    schedule_type: str = "cron"  # cron / interval / once
    cron_expr: Optional[str] = None
    interval_seconds: Optional[int] = None
    run_at: Optional[datetime] = None
    timezone: str = "Asia/Shanghai"
    max_concurrency: int = 1
    timeout_seconds: int = 3600
    enabled: bool = True
    description: Optional[str] = None


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    node_id: Optional[int] = None
    schedule_type: Optional[str] = None
    cron_expr: Optional[str] = None
    interval_seconds: Optional[int] = None
    run_at: Optional[datetime] = None
    timezone: Optional[str] = None
    max_concurrency: Optional[int] = None
    timeout_seconds: Optional[int] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class ScheduleOut(BaseModel):
    id: int
    name: Optional[str] = None
    project_id: int
    spider_id: Optional[int] = None
    spider_name: Optional[str] = None
    node_id: Optional[int] = None
    schedule_type: str
    cron_expr: Optional[str] = None
    interval_seconds: Optional[int] = None
    run_at: Optional[datetime] = None
    timezone: str
    max_concurrency: int
    timeout_seconds: int
    enabled: bool
    next_run_time: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_task_id: Optional[int] = None
    run_count: int = 0
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== 工具函数 ====================

def _to_utc_naive(dt: datetime, tz: str) -> datetime:
    """输入时间按调度时区解释，转 UTC naive 存储"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    return dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _validate_payload(schedule_type: str, cron_expr, interval_seconds, run_at, timezone,
                      require_future_once: bool = False):
    """校验触发规则，非法抛 HTTPException(400)"""
    try:
        ZoneInfo(timezone)
    except Exception:
        raise HTTPException(status_code=400, detail=f"无效的时区: {timezone}")

    if schedule_type == "cron":
        if not cron_expr:
            raise HTTPException(status_code=400, detail="cron 类型必须提供 cron_expr")
        try:
            CronTrigger.from_crontab(cron_expr, timezone=ZoneInfo(timezone))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"无效的 cron 表达式: {e}")
    elif schedule_type == "interval":
        if not interval_seconds or interval_seconds < 60:
            raise HTTPException(status_code=400, detail="interval 的间隔必须 >= 60 秒")
    elif schedule_type == "once":
        if not run_at:
            raise HTTPException(status_code=400, detail="once 类型必须提供 run_at")
        if require_future_once and _to_utc_naive(run_at, timezone) <= datetime.utcnow():
            raise HTTPException(status_code=400, detail="once 类型的运行时间必须是将来的时间")
    else:
        raise HTTPException(status_code=400, detail=f"不支持的调度类型: {schedule_type}")


def _apply_payload(sched: Schedule, payload: dict):
    """把 payload 应用到 Schedule 行（含类型切换时清理无关字段）"""
    if "name" in payload and payload["name"] is not None:
        sched.name = payload["name"]
    if "node_id" in payload and payload["node_id"] is not None:
        sched.node_id = payload["node_id"]
    if "timezone" in payload and payload["timezone"]:
        sched.timezone = payload["timezone"]
    if "max_concurrency" in payload and payload["max_concurrency"] is not None:
        sched.max_concurrency = payload["max_concurrency"]
    if "timeout_seconds" in payload and payload["timeout_seconds"] is not None:
        sched.timeout_seconds = payload["timeout_seconds"]
    if "description" in payload:
        sched.description = payload["description"]
    if "enabled" in payload:
        sched.enabled = payload["enabled"]

    new_type = payload.get("schedule_type")
    if new_type and new_type != sched.schedule_type.value:
        sched.schedule_type = ScheduleType(new_type)
        # 类型切换，清理其他触发字段
        sched.cron_expr = None
        sched.interval_seconds = None
        sched.run_at = None

    if sched.schedule_type == ScheduleType.CRON:
        if "cron_expr" in payload:
            sched.cron_expr = payload["cron_expr"]
    elif sched.schedule_type == ScheduleType.INTERVAL:
        if "interval_seconds" in payload:
            sched.interval_seconds = payload["interval_seconds"]
    elif sched.schedule_type == ScheduleType.ONCE:
        if "run_at" in payload and payload["run_at"] is not None:
            sched.run_at = _to_utc_naive(payload["run_at"], sched.timezone or "Asia/Shanghai")


def _serialize(sched: Schedule) -> ScheduleOut:
    return ScheduleOut(
        id=sched.id,
        name=sched.name,
        project_id=sched.project_id,
        spider_id=sched.spider_id,
        spider_name=sched.spider_name,
        node_id=sched.node_id,
        schedule_type=sched.schedule_type.value,
        cron_expr=sched.cron_expr,
        interval_seconds=sched.interval_seconds,
        run_at=sched.run_at,
        timezone=sched.timezone or "Asia/Shanghai",
        max_concurrency=sched.max_concurrency or 1,
        timeout_seconds=sched.timeout_seconds or 3600,
        enabled=sched.enabled,
        next_run_time=sched.next_run_time,
        last_run_at=sched.last_run_at,
        last_run_status=sched.last_run_status,
        last_run_task_id=sched.last_run_task_id,
        run_count=sched.run_count or 0,
        description=sched.description,
        created_at=sched.created_at,
        updated_at=sched.updated_at,
    )


def _reload_schedule(schedule_id: int) -> Schedule:
    """调度同步后从全新会话读回（避免旧会话快照读到过期值）"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        sched = db.query(Schedule).get(schedule_id)
        if not sched:
            raise HTTPException(status_code=404, detail="调度不存在")
        return _serialize(sched)
    finally:
        db.close()


def _get_schedule_or_404(db, schedule_id) -> Schedule:
    sched = db.query(Schedule).get(schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="调度不存在")
    return sched


# ==================== API ====================

@router.get("", response_model=List[ScheduleOut])
async def list_schedules(
    project_id: Optional[int] = None,
    spider_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """调度列表（可按项目/爬虫/状态筛选）"""
    from app.core.pagination import clamp_pagination
    skip, limit = clamp_pagination(skip, limit, default_limit=50)
    query = db.query(Schedule)
    if project_id:
        query = query.filter(Schedule.project_id == project_id)
    if spider_id:
        query = query.filter(Schedule.spider_id == spider_id)
    if enabled is not None:
        query = query.filter(Schedule.enabled == enabled)
    return [_serialize(s) for s in query.order_by(Schedule.id.desc()).offset(skip).limit(limit).all()]


@router.get("/preview")
async def preview_schedule(
    schedule_type: str,
    cron_expr: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    run_at: Optional[datetime] = None,
    timezone: str = "Asia/Shanghai",
    count: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """预览下次 N 次运行时间"""
    _validate_payload(schedule_type, cron_expr, interval_seconds, run_at, timezone)
    tz = ZoneInfo(timezone)
    try:
        if schedule_type == "cron":
            trigger = CronTrigger.from_crontab(cron_expr, timezone=tz)
        elif schedule_type == "interval":
            trigger = IntervalTrigger(seconds=interval_seconds)
        else:
            trigger = None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"触发规则无效: {e}")

    if schedule_type == "once":
        return {"runs": [run_at], "timezone": timezone}

    now = datetime.now(tz)
    runs = []
    for _ in range(min(max(count, 1), 20)):
        next_time = trigger.get_next_fire_time(None, now)
        if next_time is None:
            break
        runs.append(next_time)
        now = next_time + timedelta(seconds=1)
    return {"runs": runs, "timezone": timezone}


@router.post("", response_model=ScheduleOut, status_code=201)
async def create_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建调度；同一爬虫已存在调度时执行 upsert（V1 一对一）"""
    spider = db.query(Spider).filter(Spider.id == data.spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")
    if data.node_id:
        node = db.query(Node).get(data.node_id)
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")

    _validate_payload(
        data.schedule_type, data.cron_expr, data.interval_seconds, data.run_at, data.timezone,
        require_future_once=data.enabled,
    )

    existing = db.query(Schedule).filter(Schedule.spider_id == data.spider_id).first()
    if existing:
        # upsert：更新现有调度
        payload = data.dict(exclude={"spider_id"})
        _apply_payload(existing, payload)
        db.commit()
        from app.services.scheduler_service import get_scheduler_service
        get_scheduler_service().sync_schedule(existing.id)
        return _reload_schedule(existing.id)

    sched = Schedule(
        name=data.name or f"{spider.name}-调度",
        project_id=spider.project_id,
        spider_id=spider.id,
        spider_name=spider.spider_name or spider.name,
        node_id=data.node_id,
        schedule_type=ScheduleType(data.schedule_type),
        cron_expr=data.cron_expr if data.schedule_type == "cron" else None,
        interval_seconds=data.interval_seconds if data.schedule_type == "interval" else None,
        run_at=_to_utc_naive(data.run_at, data.timezone) if data.schedule_type == "once" and data.run_at else None,
        timezone=data.timezone,
        max_concurrency=data.max_concurrency,
        timeout_seconds=data.timeout_seconds,
        enabled=data.enabled,
        description=data.description,
        created_by=current_user.id,
    )
    db.add(sched)
    db.commit()
    from app.services.scheduler_service import get_scheduler_service
    get_scheduler_service().sync_schedule(sched.id)
    return _reload_schedule(sched.id)


@router.get("/{schedule_id}", response_model=ScheduleOut)
async def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _serialize(_get_schedule_or_404(db, schedule_id))


@router.put("/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: int,
    data: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sched = _get_schedule_or_404(db, schedule_id)
    payload = data.dict(exclude_unset=True)
    _apply_payload(sched, payload)
    # 更新后按最新类型/字段整体校验
    _validate_payload(
        sched.schedule_type.value,
        sched.cron_expr,
        sched.interval_seconds,
        sched.run_at,
        sched.timezone or "Asia/Shanghai",
    )
    # once 未来时间检查：仅在改动 run_at 或重新启用时触发，避免编辑历史 once 调度被误伤
    # 注意 sched.run_at 已是 UTC naive（库存储格式），直接与 utcnow 比较
    if (
        sched.enabled
        and sched.schedule_type == ScheduleType.ONCE
        and ("run_at" in payload or payload.get("enabled") is True)
        and sched.run_at
        and sched.run_at <= datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="once 类型的运行时间必须是将来的时间")
    db.commit()
    from app.services.scheduler_service import get_scheduler_service
    get_scheduler_service().sync_schedule(sched.id)
    return _reload_schedule(sched.id)


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sched = _get_schedule_or_404(db, schedule_id)
    from app.services.scheduler_service import get_scheduler_service
    get_scheduler_service().remove_schedule(sched.id)
    # 任务历史保留：解除外键引用后再删调度（task_instance.schedule_id 无 ON DELETE 行为）
    db.query(TaskInstance).filter(TaskInstance.schedule_id == schedule_id).update(
        {"schedule_id": None}, synchronize_session=False
    )
    db.delete(sched)
    db.commit()
    return {"message": "调度已删除"}


@router.post("/{schedule_id}/enable", response_model=ScheduleOut)
async def enable_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sched = _get_schedule_or_404(db, schedule_id)
    sched.enabled = True
    db.commit()
    from app.services.scheduler_service import get_scheduler_service
    get_scheduler_service().sync_schedule(sched.id)
    return _reload_schedule(sched.id)


@router.post("/{schedule_id}/disable", response_model=ScheduleOut)
async def disable_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """停用：保留行、置 enabled=false、移除 job（不删配置）"""
    sched = _get_schedule_or_404(db, schedule_id)
    sched.enabled = False
    sched.next_run_time = None
    db.commit()
    from app.services.scheduler_service import get_scheduler_service
    get_scheduler_service().remove_schedule(sched.id)
    db.refresh(sched)
    return _serialize(sched)


@router.post("/{schedule_id}/run-now")
async def run_schedule_now(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """立即执行一次（不改变周期）"""
    sched = _get_schedule_or_404(db, schedule_id)
    from app.services.scheduler_service import get_scheduler_service
    get_scheduler_service().run_now(sched.id)
    return {"message": "已触发立即执行", "schedule_id": sched.id}


@router.get("/{schedule_id}/history")
async def schedule_history(
    schedule_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """该调度的运行历史（任务列表）"""
    from app.core.pagination import clamp_pagination
    _, limit = clamp_pagination(0, limit, default_limit=20)
    _get_schedule_or_404(db, schedule_id)
    tasks = (
        db.query(TaskInstance)
        .filter(TaskInstance.schedule_id == schedule_id)
        .order_by(TaskInstance.id.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )
    return [
        {
            "id": t.id,
            "status": t.status.value,
            "spider_name": t.spider_name,
            "started_at": t.started_at,
            "finished_at": t.finished_at,
            "duration": float(t.duration) if t.duration is not None else None,
            "pages_crawled": t.pages_crawled,
            "items_scraped": t.items_scraped,
        }
        for t in tasks
    ]
