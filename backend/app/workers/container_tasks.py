"""
容器管理异步任务
"""
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.docker_service import get_docker_service
from app.models import Container, ContainerStatus
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="container.start", queue="container")
def start_container_task(self, container_id: str):
    """启动容器"""
    try:
        logger.info(f"Starting container: {container_id}")
        docker = get_docker_service()
        result = docker.start_container(container_id)
        
        # 更新数据库
        db = SessionLocal()
        try:
            container = db.query(Container).filter(
                Container.container_id == container_id
            ).first()
            if container:
                container.status = ContainerStatus.RUNNING
                container.started_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        return {"status": "started", "container_id": container_id}
    except Exception as e:
        logger.error(f"Failed to start container: {e}")
        raise


@celery_app.task(bind=True, name="container.stop", queue="container")
def stop_container_task(self, container_id: str):
    """停止容器"""
    try:
        logger.info(f"Stopping container: {container_id}")
        docker = get_docker_service()
        result = docker.stop_container(container_id)
        
        # 更新数据库
        db = SessionLocal()
        try:
            container = db.query(Container).filter(
                Container.container_id == container_id
            ).first()
            if container:
                container.status = ContainerStatus.EXITED
                container.stopped_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        return {"status": "stopped", "container_id": container_id}
    except Exception as e:
        logger.error(f"Failed to stop container: {e}")
        raise


@celery_app.task(bind=True, name="container.restart", queue="container")
def restart_container_task(self, container_id: str):
    """重启容器"""
    try:
        logger.info(f"Restarting container: {container_id}")
        docker = get_docker_service()
        result = docker.restart_container(container_id)
        
        return {"status": "restarted", "container_id": container_id}
    except Exception as e:
        logger.error(f"Failed to restart container: {e}")
        raise


@celery_app.task(bind=True, name="container.remove", queue="container")
def remove_container_task(self, container_id: str, force: bool = False):
    """删除容器"""
    try:
        logger.info(f"Removing container: {container_id}")
        docker = get_docker_service()
        result = docker.remove_container(container_id, force=force)
        
        # 更新数据库
        db = SessionLocal()
        try:
            container = db.query(Container).filter(
                Container.container_id == container_id
            ).first()
            if container:
                container.status = ContainerStatus.DEAD
                container.stopped_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        return {"status": "removed", "container_id": container_id}
    except Exception as e:
        logger.error(f"Failed to remove container: {e}")
        raise


@celery_app.task(bind=True, name="container.get_logs", queue="container")
def get_container_logs_task(self, container_id: str, tail: int = 100):
    """获取容器日志"""
    try:
        logger.info(f"Getting logs for container: {container_id}")
        docker = get_docker_service()
        logs = docker.get_container_logs(container_id, tail=tail)
        return {"container_id": container_id, "logs": logs}
    except Exception as e:
        logger.error(f"Failed to get container logs: {e}")
        raise


@celery_app.task(bind=True, name="container.get_stats", queue="container")
def get_container_stats_task(self, container_id: str):
    """获取容器资源统计"""
    try:
        logger.info(f"Getting stats for container: {container_id}")
        docker = get_docker_service()
        stats = docker.get_container_stats(container_id)
        return {"container_id": container_id, "stats": stats}
    except Exception as e:
        logger.error(f"Failed to get container stats: {e}")
        raise


@celery_app.task(bind=True, name="container.sync_status", queue="container")
def sync_container_status_task(self):
    """同步所有容器状态（定期任务）"""
    db = SessionLocal()
    try:
        logger.info("Syncing container statuses...")
        docker = get_docker_service()
        
        # 获取所有运行中的容器
        docker_containers = docker.list_containers(all=True)
        docker_container_ids = {c["id"] for c in docker_containers}
        
        # 更新数据库中的容器状态
        db_containers = db.query(Container).all()
        updated_count = 0
        
        for container in db_containers:
            if container.container_id in docker_container_ids:
                # 容器在 Docker 中存在
                docker_container = next(
                    (c for c in docker_containers if c["id"] == container.container_id),
                    None
                )
                if docker_container:
                    # 映射状态
                    status_map = {
                        "running": ContainerStatus.RUNNING,
                        "created": ContainerStatus.CREATED,
                        "paused": ContainerStatus.PAUSED,
                        "restarting": ContainerStatus.RESTARTING,
                        "exited": ContainerStatus.EXITED,
                        "dead": ContainerStatus.DEAD
                    }
                    new_status = status_map.get(docker_container["status"], container.status)
                    
                    if container.status != new_status:
                        container.status = new_status
                        updated_count += 1
            else:
                # 容器在 Docker 中不存在
                if container.status in [ContainerStatus.RUNNING, ContainerStatus.CREATED]:
                    container.status = ContainerStatus.DEAD
                    container.stopped_at = datetime.utcnow()
                    updated_count += 1
        
        db.commit()
        logger.info(f"Synced {updated_count} container statuses")
        return {"updated": updated_count}
        
    except Exception as e:
        logger.error(f"Failed to sync container statuses: {e}")
        db.rollback()
        raise
    finally:
        db.close()
