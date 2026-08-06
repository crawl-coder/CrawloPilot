"""
任务创建与执行分发服务

手动运行（run_spider）与定时触发（调度器）共用：
- 校验爬虫/代码目录/节点
- 创建 TaskInstance（含 schedule_id / expected_run_at）
- 按节点 connect_type 分发到 local / ssh / docker / agent 执行器
"""
import asyncio
import logging
import os
from datetime import datetime
from threading import Thread

from app.models import TaskInstance, TaskStatus, Spider, Node
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)


def _update_spider_run_stats(db, spider):
    """回写爬虫运行统计"""
    spider.run_count = (spider.run_count or 0) + 1
    spider.last_run_at = datetime.utcnow()
    spider.last_run_status = "running"
    db.commit()


def _fire_and_forget(executor_getter, config):
    """在无 Starlette BackgroundTasks 的上下文（调度器线程）中启动执行器"""
    def runner():
        try:
            asyncio.run(executor_getter().execute_task(config))
        except Exception as e:
            logger.error(f"后台执行任务失败 task={config.task_id}: {e}")

    Thread(target=runner, daemon=True, name=f"task-exec-{config.task_id}").start()


def create_and_run_task(
    db,
    spider_id: int,
    node_id: int = None,
    schedule_id: int = None,
    expected_run_at=None,
    background_tasks=None,
):
    """
    创建任务并按节点分发

    Args:
        db: 数据库会话
        spider_id: 爬虫 ID
        node_id: 目标节点 ID（None=本地执行）
        schedule_id: 来源调度（定时触发时传入）
        expected_run_at: 期望触发时间（调度幂等用）
        background_tasks: Starlette BackgroundTasks（API 场景），无则内部起线程

    Returns:
        任务信息 dict（message / task_id / mode / ...）
    """
    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise ValueError("爬虫不存在")
    if spider.status == "disabled":
        raise ValueError("爬虫已禁用，无法运行")

    upload_service = UploadService()
    code_dir = upload_service.get_spider_code_dir(spider.project_id, spider.id)
    if not code_dir or not os.path.exists(code_dir):
        raise ValueError("爬虫代码目录不存在，请先上传代码或克隆Git仓库")

    node = None
    if node_id:
        node = db.query(Node).get(node_id)
        if not node:
            raise ValueError("节点不存在")
        if node.status.value != "online":
            raise ValueError(f"节点 {node.name} 状态为 {node.status.value}，不可用")

    task = TaskInstance(
        spider_id=spider.id,
        spider_name=spider.spider_name or spider.name,
        schedule_id=schedule_id,
        expected_run_at=expected_run_at,
        status=TaskStatus.PENDING,
        node_id=node.id if node else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    spider_name = spider.spider_name or spider.name
    if node:
        if node.connect_type == "ssh":
            result = _dispatch_ssh(spider, task, node, code_dir, spider_name, background_tasks)
        elif node.connect_type == "docker":
            result = _dispatch_docker(spider, task, node, code_dir, spider_name, background_tasks)
        elif node.connect_type == "agent":
            result = _dispatch_agent(spider, task, node, db)
        else:
            result = _dispatch_ssh(spider, task, node, code_dir, spider_name, background_tasks)
    else:
        result = _dispatch_local(spider, task, code_dir, spider_name, background_tasks)

    _update_spider_run_stats(db, spider)
    return result


def _dispatch_local(spider, task, code_dir, spider_name, background_tasks):
    """本地模式：子进程运行"""
    from app.services.local_executor import get_local_executor, LocalTaskConfig

    config = LocalTaskConfig(
        task_id=str(task.id),
        spider_id=str(spider.id),
        spider_name=spider_name,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider_name,
    )
    if background_tasks:
        background_tasks.add_task(get_local_executor().execute_task, config)
    else:
        _fire_and_forget(get_local_executor, config)

    return {
        "message": "爬虫已启动(本地模式)",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "local",
        "code_dir": code_dir,
        "entry_file": spider.entry_file,
    }


def _dispatch_ssh(spider, task, node, code_dir, spider_name, background_tasks):
    """SSH 模式：上传代码远程运行"""
    from app.services.ssh_executor import get_ssh_executor, SshTaskConfig

    config = SshTaskConfig(
        task_id=str(task.id),
        spider_id=str(spider.id),
        spider_name=spider_name,
        ssh_host=node.ssh_host or node.host,
        ssh_port=node.ssh_port or 22,
        ssh_user=node.ssh_user or "root",
        ssh_pwd=node.ssh_pwd,
        ssh_key=node.ssh_key,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider_name,
    )
    if background_tasks:
        background_tasks.add_task(get_ssh_executor().execute_task, config)
    else:
        _fire_and_forget(get_ssh_executor, config)

    return {
        "message": "爬虫运行指令已发送(SSH模式)",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "ssh",
        "node_id": node.id,
        "node_name": node.name,
        "host": node.ssh_host or node.host,
        "workspace": f"/opt/crawlopilot/workspace/{task.id}/",
    }


def _dispatch_docker(spider, task, node, code_dir, spider_name, background_tasks):
    """Docker 模式：直连节点 Docker API"""
    from app.services.docker_executor import get_docker_executor, DockerTaskConfig

    config = DockerTaskConfig(
        task_id=str(task.id),
        spider_id=str(spider.id),
        spider_name=spider_name,
        project_id=spider.project_id,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider_name,
        node_host=node.host,
        node_port=node.port or 2375,
        docker_host=node.docker_host,
    )
    if background_tasks:
        background_tasks.add_task(get_docker_executor().execute_task, config)
    else:
        _fire_and_forget(get_docker_executor, config)

    return {
        "message": "爬虫运行指令已发送(Docker直连模式)",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "docker",
        "node_id": node.id,
        "node_name": node.name,
        "docker_host": f"{node.host}:{node.port or 2375}",
    }


def _dispatch_agent(spider, task, node, db):
    """Agent 模式：任务保持 PENDING，由节点 agent 领取执行"""
    task.deploy_mode = "agent"
    task.node_id = node.id
    task.status = TaskStatus.PENDING
    db.commit()

    return {
        "message": "任务已派发给节点 Agent",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "agent",
        "node_id": node.id,
        "node_name": node.name,
    }
