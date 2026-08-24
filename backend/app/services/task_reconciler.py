"""
任务对账模块：控制面启动时扫描遗留的 PENDING/RUNNING 任务，确认进程存活并收敛僵尸。

对账策略（按 deploy_mode 分发）：
  - local:  process_id 非空 → os.kill(pid, 0) 探活
  - docker: container_id 非空 → Docker API 查容器状态
  - ssh:    process_id 非空 → 远程 kill -0 PID（不可达则按超龄判定）
  - agent:  无进程标识 → 依赖心跳超龄判定

超龄兜底：任何 RUNNING/PENDING 任务超过 TASK_STALE_HOURS（默认 24h）均标记 FAILED，
独立于探活结果，防止因进程标识丢失而遗漏。
"""

import logging
import os
import socket
from datetime import timedelta
from typing import List, Dict

from sqlalchemy.orm import Session

from app.models import TaskInstance, TaskStatus, DeployMode, Node
from app.core.config import settings
from app.core.time_utils import cn_now

logger = logging.getLogger(__name__)

# 可通过环境变量调整超龄阈值（小时）
STALE_HOURS = int(os.environ.get("TASK_STALE_HOURS", "24"))


def reconcile_tasks(db: Session) -> Dict[str, List[int]]:
    """扫描遗留 PENDING/RUNNING 任务，判定进程存活并收敛僵尸。

    返回 {"recovered": [任务IDs], "stale": [任务IDs], "errors": [任务IDs]}
    """
    results = {"recovered": [], "stale": [], "errors": []}

    tasks: List[TaskInstance] = (
        db.query(TaskInstance)
        .filter(TaskInstance.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]))
        .all()
    )

    if not tasks:
        logger.info("对账：无遗留 PENDING/RUNNING 任务")
        return results

    logger.info(f"对账：发现 {len(tasks)} 个遗留任务，开始探活...")
    now = cn_now()
    stale_cutoff = now - timedelta(hours=STALE_HOURS)

    for task in tasks:
        try:
            age = (now - (task.created_at or task.started_at or now)).total_seconds()
            is_stale = task.created_at and task.created_at < stale_cutoff

            # 1. 先按超龄兜底：任何模式超龄直接标记（A2 逻辑内聚在此）
            if is_stale:
                _mark_failed(db, task, f"控制面对账：任务超龄（>{STALE_HOURS}h）无更新，"
                                       f"创建于 {task.created_at}，视为僵尸")
                results["stale"].append(task.id)
                continue

            # 2. 按 deploy_mode 分发探活
            alive = _check_alive(task)

            if alive is False:
                _mark_failed(db, task, f"控制面重启对账：{task.deploy_mode} 进程不存在"
                                       f"（process_id={task.process_id}, "
                                       f"container_id={task.container_id}）")
                results["recovered"].append(task.id)
            elif alive is None:
                # 无法确认（如 agent/ssh 不可达），且未超龄：保留，等待后续 A2 兜底
                logger.debug(f"对账：任务 #{task.id} ({task.deploy_mode}) 无法确认存活，保留")
            # alive is True → 正在运行，不动

        except Exception as e:
            logger.error(f"对账：任务 #{task.id} 探活异常: {e}", exc_info=True)
            # 探活异常不盲目标记，避免误杀；留给 A2 超龄兜底
            results["errors"].append(task.id)

    db.commit()
    logger.info(f"对账完成: recovered={len(results['recovered'])}, "
                f"stale={len(results['stale'])}, errors={len(results['errors'])}")
    return results


def _check_alive(task: TaskInstance) -> bool | None:
    """探活单个任务进程。返回 True(存活)/False(不存在)/None(无法确认)。"""
    mode = task.deploy_mode

    if mode == DeployMode.LOCAL:
        return _check_local_alive(task)

    elif mode == DeployMode.DOCKER:
        return _check_docker_alive(task)

    elif mode == DeployMode.SSH:
        return _check_ssh_alive(task)

    elif mode == DeployMode.AGENT:
        # Agent 无进程标识，无法直接探活 → 返回 None（交给超龄兜底）
        return None

    return None


def _check_local_alive(task: TaskInstance) -> bool | None:
    """local 模式：核对进程 PID 存活"""
    pid = task.process_id
    if not pid:
        return None
    try:
        os.kill(pid, 0)  # signal 0：只检查存在性，不发信号
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # 进程存在但无权探活（属主不同）→ 视为存活
        return True
    except OSError:
        return False


def _check_docker_alive(task: TaskInstance) -> bool | None:
    """docker 模式：查容器状态"""
    container_id = task.container_id
    if not container_id:
        return None
    try:
        from app.services.docker_service import DockerService
        node = _get_node_for_task(task)
        if not node:
            return None
        docker_host = node.docker_host
        if not docker_host:
            # 尝试从 ssh_host 构造
            host = node.ssh_host or node.host
            docker_host = f"tcp://{host}:2375"
        docker = DockerService(docker_host=docker_host)
        info = docker.get_container(container_id)
        status = (info.get("status") or "").lower()
        # running / restarting → 存活；exited / dead / removing → 不存活
        return status in ("running", "restarting", "created")
    except Exception as e:
        logger.debug(f"Docker 探活失败 (task={task.id}, container={container_id}): {e}")
        return None


def _check_ssh_alive(task: TaskInstance) -> bool | None:
    """ssh 模式：远程 PID 探活（best effort，不可达返回 None）"""
    pid = task.process_id
    if not pid:
        return None
    node = _get_node_for_task(task)
    if not node:
        return None
    host = node.ssh_host or node.host
    if not host:
        return None
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=node.ssh_port or 22,
                    username=node.ssh_user,
                    password=_decrypt_field(node.ssh_pwd),
                    key_filename=None, timeout=5,
                    allow_agent=False, look_for_keys=False)
        _, stdout, _ = ssh.exec_command(f"kill -0 {pid}", timeout=3)
        exit_code = stdout.channel.recv_exit_status()
        ssh.close()
        return exit_code == 0
    except socket.timeout:
        return None  # SSH 超时 → 无法确认
    except Exception:
        return None  # 连接失败 → 无法确认


def _get_node_for_task(task: TaskInstance) -> Node | None:
    """获取任务关联的节点（用于 SSH/Docker 探活）"""
    if not task.node_id:
        return None
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        return db.query(Node).filter(Node.id == task.node_id).first()
    finally:
        db.close()


def _decrypt_field(value: str | None) -> str | None:
    """解密字段（兼容明文/密文）"""
    if not value:
        return value
    try:
        from app.core.crypto import decrypt_or_plain
        return decrypt_or_plain(value)
    except Exception:
        return value


def _mark_failed(db: Session, task: TaskInstance, reason: str):
    """标记任务为 FAILED 并记录原因；发布僵尸收敛告警事件"""
    task.status = TaskStatus.FAILED
    task.finished_at = cn_now()
    task.error_message = reason[:512]  # 限长防溢出
    if task.started_at and task.finished_at:
        task.duration = round((task.finished_at - task.started_at).total_seconds(), 2)
    logger.warning(f"对账：任务 #{task.id} ({task.deploy_mode}) → FAILED: {reason}")
    # 发布僵尸收敛告警事件（Wave C）
    try:
        from app.services.alert_engine import publish
        publish("zombie_converged", {
            "target_id": task.id,
            "target_name": task.spider_name or "",
            "spider_id": task.spider_id,
            "project_id": task.spider.project_id if task.spider else None,
            "error_message": reason,
        })
    except Exception:
        pass
