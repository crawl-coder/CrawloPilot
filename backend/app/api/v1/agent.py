"""
Agent 节点控制端 API

节点上的 agent 程序通过这些接口与控制端通信：
- register  注册（携带 token）→ 获得 node_id
- heartbeat 心跳（资源/进程状态）
- tasks     领取待执行任务
- code      下载爬虫代码包
- report    回报任务终态/指标
- logs      实时上报日志
- status    查询任务状态（含停止标记）

认证方式：node_id + token（agent 专用，不依赖用户 JWT）
"""

import io
import tarfile
import logging
from pathlib import Path
from app.core.config import settings
from datetime import datetime
from app.core.time_utils import cn_now
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.models import Node, NodeStatus, TaskInstance, TaskStatus, Spider, DeployMode
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nodes/agent", tags=["Agent节点"])

# 任务日志目录（与本地/SSH/Docker 执行器共用：项目根 uploads/_task_logs）
LOGS_DIR = Path(settings.UPLOAD_DIR) / "_task_logs"


# ==================== Schemas ====================

class AgentRegister(BaseModel):
    token: str
    hostname: Optional[str] = None
    os_type: Optional[str] = None
    os_version: Optional[str] = None
    cpu_cores: Optional[int] = None
    memory_total: Optional[int] = None
    agent_version: Optional[str] = None
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None


class AgentHeartbeat(BaseModel):
    node_id: int
    token: str
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    container_count: Optional[int] = None


class AgentTaskReport(BaseModel):
    node_id: int
    token: str
    status: str
    pages_crawled: Optional[int] = 0
    items_scraped: Optional[int] = 0
    errors_count: Optional[int] = 0
    error_message: Optional[str] = None
    logs: Optional[str] = None


class AgentLogs(BaseModel):
    node_id: int
    token: str
    logs: str


# ==================== 工具 ====================

def _get_node_by_token(db: Session, token: str) -> Optional[Node]:
    return db.query(Node).filter(Node.agent_token == token).first()


def _extract_token(request: Request) -> Optional[str]:
    """仅从 Authorization: Bearer header 取 token。

    不再接受 body/query 中的 token（避免 token-in-URL 泄露）。
    旧版 agent 已全部升级为 Bearer，无兼容负担。
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def _validate_agent(db: Session, node_id: int, token: str) -> Node:
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node or node.connect_type != "agent" or node.agent_token != token:
        raise HTTPException(status_code=401, detail="Agent 认证失败")
    return node


def _task_log_path(task_id) -> Path:
    return LOGS_DIR / f"task_{task_id}.log"


def _write_task_logs(task_id, logs: str):
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        _task_log_path(task_id).write_text(logs or "", encoding="utf-8")
    except Exception as e:
        logger.warning(f"写 Agent 任务日志失败: {e}")


def _append_task_logs(task_id, logs: str):
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_task_log_path(task_id), "a", encoding="utf-8") as f:
            f.write(logs or "")
    except Exception as e:
        logger.warning(f"追加 Agent 任务日志失败: {e}")


def _update_spider_stats(db, task: TaskInstance, status: TaskStatus):
    try:
        if not task.spider_id:
            return
        spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
        if not spider:
            return
        spider.last_run_at = cn_now()
        spider.last_run_status = status.value
        if status == TaskStatus.SUCCESS:
            spider.success_count = (spider.success_count or 0) + 1
        elif status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
            spider.error_count = (spider.error_count or 0) + 1
        db.commit()
        logger.info(f"任务 {task.id} 已更新爬虫统计: {spider.name} -> {status.value}")
    except Exception as e:
        logger.error(f"更新爬虫统计失败: {e}")
        db.rollback()


# ==================== API ====================

@router.post("/register")
async def agent_register(
    data: AgentRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    """Agent 注册：用令牌换取 node_id（Bearer header）"""
    token = _extract_token(request)
    node = _get_node_by_token(db, token or "")
    if not node:
        raise HTTPException(status_code=401, detail="无效的 Agent 令牌")

    node.agent_status = "online"
    node.status = NodeStatus.ONLINE
    node.last_heartbeat = cn_now()
    node.agent_version = data.agent_version or node.agent_version
    if data.hostname:
        # 节点名以创建时用户指定为准；hostname 仅记录到 labels，
        # 避免多个 agent 同主机名时撞 node.name 唯一索引（500 IntegrityError）
        labels = dict(node.labels or {})
        labels["hostname"] = data.hostname
        node.labels = labels
    if data.os_type:
        node.os_type = data.os_type
    if data.os_version:
        node.os_version = data.os_version
    if data.cpu_cores:
        node.cpu_cores = data.cpu_cores
    if data.memory_total:
        node.memory_total = data.memory_total
    if data.public_ip:
        node.public_ip = data.public_ip
    if data.private_ip:
        node.private_ip = data.private_ip
    db.commit()
    db.refresh(node)

    logger.info(f"Agent 注册成功: node={node.id} ({node.name})")
    return {
        "node_id": node.id,
        "name": node.name,
        "task_poll_interval": 5,
    }


@router.post("/heartbeat")
async def agent_heartbeat(
    data: AgentHeartbeat,
    request: Request,
    db: Session = Depends(get_db),
):
    """Agent 心跳（Bearer header）"""
    token = _extract_token(request)
    node = _validate_agent(db, data.node_id, token or "")
    node.last_heartbeat = cn_now()
    node.agent_status = "online"
    node.status = NodeStatus.ONLINE
    if data.cpu_usage is not None:
        node.cpu_usage = data.cpu_usage
    if data.memory_usage is not None:
        node.memory_usage = data.memory_usage
    if data.disk_usage is not None:
        node.disk_usage = data.disk_usage
    if data.container_count is not None:
        node.container_count = data.container_count
    db.commit()
    return {"ok": True, "node_id": node.id}


@router.get("/tasks")
async def agent_get_tasks(
    node_id: int,
    request: Request,
    long_poll: int = 0,
    db: Session = Depends(get_db),
):
    """领取待执行任务（同一时间只给一个）

    long_poll=1 时长轮询：无任务时挂起最多 25 秒，减少节点空载轮询压力；
    有任务立即返回。鉴权走 Authorization: Bearer header。
    """
    import asyncio
    import time as _time
    token = _extract_token(request)
    node = _validate_agent(db, node_id, token or "")
    wait_seconds = min(max(long_poll, 0), 25)
    deadline = _time.time() + wait_seconds

    while True:
        task = (
            db.query(TaskInstance)
            .filter(
                TaskInstance.deploy_mode == DeployMode.AGENT,
                TaskInstance.node_id == node.id,
                TaskInstance.status == TaskStatus.PENDING,
            )
            .order_by(TaskInstance.id.asc())
            .first()
        )
        if task:
            # 原子领取：用条件 UPDATE 确保只有本节点能抢占该任务，
            # 避免多个 agent 同时读到同一 PENDING 任务导致重复执行。
            claimed = db.execute(
                update(TaskInstance)
                .where(
                    TaskInstance.id == task.id,
                    TaskInstance.status == TaskStatus.PENDING,
                )
                .values(status=TaskStatus.RUNNING,
                        started_at=task.started_at or cn_now())
            )
            db.commit()
            if claimed.rowcount == 0:
                # 已被其他 agent 抢占，继续找下一个
                continue
            return {
                "task": {
                    "task_id": task.id,
                    "spider_id": task.spider_id,
                    "spider_name": task.spider_name,
                    "entry_file": task.spider.entry_file if task.spider else None,
                    "args": (task.stats or {}).get("args"),
                    "env": (task.stats or {}).get("env"),
                }
            }

        if not wait_seconds or _time.time() >= deadline:
            return {"task": None}
        await asyncio.sleep(2)


@router.get("/tasks/{task_id}/status")
async def agent_get_task_status(
    task_id: int,
    node_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """查询任务状态（Agent 运行中轮询，检测停止标记）"""
    token = _extract_token(request)
    _validate_agent(db, node_id, token or "")
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    stats = task.stats or {}
    return {
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "stop_requested": bool(stats.get("stop_requested")),
    }


@router.get("/tasks/{task_id}/code")
async def agent_get_task_code(
    task_id: int,
    node_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """下载爬虫代码包（tar.gz）"""
    token = _extract_token(request)
    _validate_agent(db, node_id, token or "")
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task or not task.spider_id:
        raise HTTPException(status_code=404, detail="任务或爬虫不存在")

    spider = db.query(Spider).filter(Spider.id == task.spider_id).first()
    if not spider:
        raise HTTPException(status_code=404, detail="爬虫不存在")

    upload_service = UploadService()
    code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    if not code_dir or not Path(code_dir).exists():
        raise HTTPException(status_code=400, detail="爬虫代码目录不存在")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(code_dir, arcname="code")

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="task_{task_id}.tar.gz"'},
    )


@router.post("/tasks/{task_id}/logs")
async def agent_upload_logs(
    task_id: int,
    data: AgentLogs,
    request: Request,
    db: Session = Depends(get_db),
):
    """实时上报日志（追加写入，Bearer header）"""
    token = _extract_token(request)
    _validate_agent(db, data.node_id, token or "")
    _append_task_logs(task_id, data.logs)
    return {"ok": True}


@router.post("/tasks/{task_id}/report")
async def agent_report_task(
    task_id: int,
    data: AgentTaskReport,
    request: Request,
    db: Session = Depends(get_db),
):
    """回报任务终态（Bearer header）"""
    token = _extract_token(request)
    _validate_agent(db, data.node_id, token or "")
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    try:
        status = TaskStatus(data.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的任务状态: {data.status}")

    # 终态原子更新：若任务已被取消/超时等进入终态，不覆盖（防 stop 后 agent 回报改写）
    from app.services.task_updater import update_task_completion
    updated = update_task_completion(
        task_id,
        status=status,
        finished_at=cn_now(),
        pages_crawled=data.pages_crawled or 0,
        items_scraped=data.items_scraped or 0,
        errors_count=data.errors_count or 0,
        error_message=data.error_message,
        deploy_mode="agent",
        logs=data.logs,
        log_dir=LOGS_DIR,
    )

    if not updated:
        logger.info(f"Agent 回报任务 {task_id} 终态 {status.value}，但任务已是终态，已忽略")

    # 统计回写（仅当任务确实进入终态时）
    task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
    if task:
        _update_spider_stats(db, task, task.status if hasattr(task.status, "value") else TaskStatus(task.status))
    logger.info(
        f"Agent 任务 {task_id} 完成: {status.value}, "
        f"pages={task.pages_crawled}, items={task.items_scraped}, duration={task.duration}s"
    )
    return {"ok": True}
