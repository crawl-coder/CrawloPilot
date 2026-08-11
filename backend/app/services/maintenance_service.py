"""
日常维护：任务记录保留清理 + Docker 任务镜像 GC

- TASK_RETENTION_DAYS：终态任务记录保留天数（默认 90，0 关闭）
- DOCKER_IMAGE_KEEP：每个项目保留的任务镜像数量（默认 5，0 关闭）
"""
import logging
from datetime import timedelta

from app.core.config import settings
from app.core.time_utils import cn_now
from app.models import TaskInstance, TaskStatus, Node, NodeStatus

logger = logging.getLogger(__name__)

TASK_IMAGE_PREFIX = "crawlo-project-"


def cleanup_task_records() -> int:
    """删除超过保留期的终态任务记录（日志文件由 _task_log_cleanup_loop 单独清理）"""
    days = settings.TASK_RETENTION_DAYS
    if days <= 0:
        return 0

    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        cutoff = cn_now() - timedelta(days=days)
        deleted = db.query(TaskInstance).filter(
            TaskInstance.status.in_([
                TaskStatus.SUCCESS,
                TaskStatus.FAILED,
                TaskStatus.TIMEOUT,
                TaskStatus.CANCELLED,
            ]),
            TaskInstance.finished_at < cutoff,
        ).delete(synchronize_session=False)
        db.commit()
        if deleted:
            logger.info(f"任务记录清理: 删除 {deleted} 条超过 {days} 天的终态任务")
        return deleted
    finally:
        db.close()


def cleanup_docker_images() -> int:
    """清理各在线 Docker 节点上超出保留数量的任务镜像"""
    keep = settings.DOCKER_IMAGE_KEEP
    if keep <= 0:
        return 0

    from app.core.database import SessionLocal
    from app.services.docker_service import DockerService

    db = SessionLocal()
    removed_total = 0
    try:
        nodes = db.query(Node).filter(
            Node.connect_type == "docker",
            Node.status == NodeStatus.ONLINE,
        ).all()
        for node in nodes:
            try:
                docker_host = node.docker_host or f"tcp://{node.host}:{node.port or 2375}"
                docker = DockerService(docker_host=docker_host)
                images = docker.list_images()
                # 按项目分组：crawlo-project-{project_id}-{hash}
                groups = {}
                for img in images:
                    for tag in img.get("tags") or []:
                        name = tag.split(":")[0]
                        if name.startswith(TASK_IMAGE_PREFIX):
                            groups.setdefault(name, []).append(tag)

                for name, tags in groups.items():
                    if len(tags) <= keep:
                        continue
                    ordered = sorted(
                        tags,
                        key=lambda t: _image_created(t, images),
                    )
                    for old in ordered[:-keep]:
                        try:
                            docker.remove_image(old, force=True)
                            removed_total += 1
                        except Exception as e:
                            logger.warning(f"删除镜像 {old} 失败: {e}")
            except Exception as e:
                logger.warning(f"Docker 节点 {node.name} 镜像清理失败: {e}")

        if removed_total:
            logger.info(f"Docker 镜像清理: 删除 {removed_total} 个旧任务镜像（每项目保留 {keep} 个）")
        return removed_total
    finally:
        db.close()


def _image_created(tag: str, images) -> str:
    for img in images:
        if tag in (img.get("tags") or []):
            return img.get("created") or ""
    return ""
