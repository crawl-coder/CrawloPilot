"""
监控数据 API 路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["监控"])


@router.get("/health")
async def get_health_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取系统健康状态"""
    from app.core.database import engine
    from sqlalchemy import text
    
    # 检查数据库连接
    db_healthy = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_healthy = False
    
    return {
        "status": "healthy" if db_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy"
            }
        }
    }


@router.get("/dashboard")
async def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Dashboard 综合数据"""
    from app.models import Project, TaskInstance, TaskStatus, Deploy, Node, Container
    
    # 项目统计
    total_projects = db.query(Project).count()
    
    # 任务统计
    total_tasks = db.query(TaskInstance).count()
    today_tasks = db.query(TaskInstance).filter(
        TaskInstance.created_at >= datetime.utcnow() - timedelta(days=1)
    ).count()
    success_rate = 0
    if total_tasks > 0:
        success_tasks = db.query(TaskInstance).filter(TaskInstance.status == TaskStatus.SUCCESS).count()
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
        "tasks": {
            "total": total_tasks,
            "today": today_tasks,
            "running": db.query(TaskInstance).filter(TaskInstance.status == TaskStatus.RUNNING).count(),
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
