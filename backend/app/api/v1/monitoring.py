"""
监控数据 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime, timedelta
from typing import Any as AnyType

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.monitoring import metrics_collector
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["监控"])


@router.get("/system")
async def get_system_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取系统指标"""
    # 这里应该从 Prometheus 或其他监控系统获取实际数据
    # 目前返回模拟数据
    return {
        "cpu_usage": 45.2,
        "memory_usage": 68.5,
        "disk_usage": 52.3,
        "network_io": {
            "bytes_sent": 1234567890,
            "bytes_recv": 9876543210
        },
        "uptime_seconds": 86400 * 7  # 7 天
    }


@router.get("/spiders")
async def get_spider_metrics(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫指标"""
    # TODO: 从数据库查询实际数据
    return {
        "total_runs": 1250,
        "success_rate": 95.2,
        "avg_duration_seconds": 1800,
        "total_items_scraped": 500000,
        "recent_runs": []
    }


@router.get("/schedules")
async def get_schedule_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取调度指标"""
    from app.models import Schedule, TaskInstance
    from sqlalchemy import func
    
    # 统计调度配置
    total_schedules = db.query(Schedule).count()
    enabled_schedules = db.query(Schedule).filter(Schedule.enabled == True).count()
    
    # 统计任务实例
    total_tasks = db.query(TaskInstance).count()
    success_tasks = db.query(TaskInstance).filter(TaskInstance.status == 'success').count()
    failed_tasks = db.query(TaskInstance).filter(TaskInstance.status == 'failed').count()
    running_tasks = db.query(TaskInstance).filter(TaskInstance.status == 'running').count()
    
    return {
        "total_schedules": total_schedules,
        "enabled_schedules": enabled_schedules,
        "total_tasks": total_tasks,
        "success_tasks": success_tasks,
        "failed_tasks": failed_tasks,
        "running_tasks": running_tasks,
        "success_rate": (success_tasks / total_tasks * 100) if total_tasks > 0 else 0
    }


@router.get("/deployments")
async def get_deployment_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取部署指标"""
    from app.models import Deploy, Container
    from sqlalchemy import func
    
    # 统计部署
    total_deploys = db.query(Deploy).count()
    success_deploys = db.query(Deploy).filter(Deploy.status == 'success').count()
    failed_deploys = db.query(Deploy).filter(Deploy.status == 'failed').count()
    
    # 统计容器
    total_containers = db.query(Container).count()
    running_containers = db.query(Container).filter(Container.status == 'running').count()
    
    return {
        "total_deploys": total_deploys,
        "success_deploys": success_deploys,
        "failed_deploys": failed_deploys,
        "total_containers": total_containers,
        "running_containers": running_containers,
        "success_rate": (success_deploys / total_deploys * 100) if total_deploys > 0 else 0
    }


@router.get("/nodes")
async def get_node_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取节点指标"""
    from app.models import Node
    
    nodes = db.query(Node).all()
    node_metrics = []
    
    for node in nodes:
        node_metrics.append({
            "id": node.id,
            "name": node.name,
            "status": node.status,
            "cpu_usage": 0,  # TODO: 从监控系统获取
            "memory_usage": 0,
            "disk_usage": 0,
            "container_count": 0
        })
    
    return {
        "total_nodes": len(nodes),
        "online_nodes": len([n for n in nodes if n.status == 'online']),
        "nodes": node_metrics
    }


@router.get("/tasks/queue")
async def get_task_queue_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务队列指标"""
    # TODO: 从 Celery 获取实际数据
    return {
        "queues": {
            "deploy": {"length": 0, "active": 0},
            "container": {"length": 0, "active": 0},
            "schedule": {"length": 0, "active": 0}
        },
        "active_workers": 0,
        "total_tasks_processed": 0
    }


@router.get("/health")
async def get_health_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取系统健康状态"""
    from app.core.database import engine
    
    # 检查数据库连接
    db_healthy = True
    try:
        db.execute("SELECT 1")
    except Exception:
        db_healthy = False
    
    # 检查 Redis 连接
    redis_healthy = True
    try:
        from app.core.config import settings
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL_PROP)
        r.ping()
    except Exception:
        redis_healthy = False
    
    # 检查 Docker 连接
    docker_healthy = True
    try:
        import docker
        client = docker.DockerClient(base_url="unix://var/run/docker.sock")
        client.ping()
    except Exception:
        docker_healthy = False
    
    overall_healthy = db_healthy and redis_healthy and docker_healthy
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy"
            },
            "redis": {
                "status": "healthy" if redis_healthy else "unhealthy"
            },
            "docker": {
                "status": "healthy" if docker_healthy else "unhealthy"
            }
        }
    }


@router.get("/dashboard")
async def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Dashboard 综合数据"""
    from app.models import Schedule, TaskInstance, Deploy, Node, Container
    from sqlalchemy import func
    
    # 项目统计
    total_projects = 10  # TODO: 查询实际数据
    
    # 调度统计
    total_schedules = db.query(Schedule).count()
    enabled_schedules = db.query(Schedule).filter(Schedule.enabled == True).count()
    
    # 任务统计
    total_tasks = db.query(TaskInstance).count()
    today_tasks = db.query(TaskInstance).filter(
        TaskInstance.created_at >= datetime.utcnow() - timedelta(days=1)
    ).count()
    success_rate = 0
    if total_tasks > 0:
        success_tasks = db.query(TaskInstance).filter(TaskInstance.status == 'success').count()
        success_rate = (success_tasks / total_tasks * 100)
    
    # 部署统计
    total_deploys = db.query(Deploy).count()
    recent_deploys = db.query(Deploy).filter(
        Deploy.created_at >= datetime.utcnow() - timedelta(days=7)
    ).count()
    
    # 节点统计
    total_nodes = db.query(Node).count()
    online_nodes = db.query(Node).filter(Node.status == 'online').count()
    
    # 容器统计
    total_containers = db.query(Container).count()
    running_containers = db.query(Container).filter(Container.status == 'running').count()
    
    return {
        "projects": {
            "total": total_projects
        },
        "schedules": {
            "total": total_schedules,
            "enabled": enabled_schedules
        },
        "tasks": {
            "total": total_tasks,
            "today": today_tasks,
            "success_rate": round(success_rate, 2)
        },
        "deployments": {
            "total": total_deploys,
            "recent_7d": recent_deploys
        },
        "nodes": {
            "total": total_nodes,
            "online": online_nodes
        },
        "containers": {
            "total": total_containers,
            "running": running_containers
        }
    }
