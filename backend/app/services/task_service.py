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
from typing import Dict, Optional
from app.core.time_utils import cn_now
from threading import Thread

from app.models import (
    TaskInstance,
    TaskStatus,
    Spider,
    SpiderStatus,
    Node,
    Server,
    ServerStatus,
    DeployMode,
)
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)


def _update_spider_run_stats(db, spider):
    """回写爬虫运行统计"""
    spider.run_count = (spider.run_count or 0) + 1
    spider.last_run_at = cn_now()
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
    memory_limit=None,
    cpu_limit=None,
    timeout=None,
    task_args: Optional[str] = None,
    task_env: Optional[Dict[str, str]] = None,
    distribution_mode: str = "standalone",
    shared_redis_url: Optional[str] = None,
    worker_count: int = 1,
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
    if spider.status == SpiderStatus.DISABLED:
        raise ValueError("爬虫已禁用，无法运行")

    # B2：爬虫级并发守卫（手动 + 调度 + run-now 统一入口）
    max_concurrent = spider.max_concurrent or 0  # 0=不限
    if max_concurrent > 0:
        active_count = (
            db.query(TaskInstance)
            .filter(
                TaskInstance.spider_id == spider_id,
                TaskInstance.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]),
            )
            .count()
        )
        if active_count >= max_concurrent:
            raise ValueError(
                f"爬虫并发守卫：当前活跃任务 {active_count} ≥ 上限 {max_concurrent}，"
                f"请等待现有任务完成或调高 max_concurrent"
            )

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
        # 服务器维护中禁止分配新任务
        if node.server_id:
            server = db.query(Server).filter(Server.id == node.server_id).first()
            if server and server.status == ServerStatus.MAINTENANCE:
                raise ValueError(f"服务器 {server.name} 处于维护模式，暂不能分配任务")

    # D4：分布式模式适配（默认 standalone，不影响 V1 行为）
    dist_adapter_result = {}
    if distribution_mode != "standalone":
        from app.services.crawlo_distributed_adapter import get_distributed_adapter
        from app.models import Project
        project = db.query(Project).get(spider.project_id)
        project_name = project.name if project else "default"
        dist_adapter_result = get_distributed_adapter().prepare_task(
            task_id=None,  # task 尚未创建
            spider_name=spider_name,
            project_name=project_name,
            distribution_mode=distribution_mode,
            shared_redis_url=shared_redis_url,
            worker_count=worker_count,
        )
        # 合并分布式参数到 task_env 和 task_args
        task_env = dict(task_env) if task_env else {}
        task_env.update(dist_adapter_result.get("extra_env", {}))
        extra_args = dist_adapter_result.get("extra_args", [])
        if extra_args:
            task_args = (task_args or "").split() + extra_args
            task_args = " ".join(task_args).strip()

    # 按节点类型确定部署模式，供 executor_registry 分发 stop/status/logs
    deploy_mode = DeployMode.from_connect_type(node.connect_type if node else None)
    task = TaskInstance(
        spider_id=spider.id,
        spider_name=spider.spider_name or spider.name,
        schedule_id=schedule_id,
        expected_run_at=expected_run_at,
        status=TaskStatus.PENDING,
        node_id=node.id if node else None,
        deploy_mode=deploy_mode,
        memory_limit=memory_limit,
        cpu_limit=cpu_limit,
        stats={"args": task_args, "env": task_env} if (task_args or task_env) else None,
        distribution_mode=distribution_mode,
        shared_redis_url=shared_redis_url,
        worker_count=worker_count,
        redis_namespace=dist_adapter_result.get("redis_namespace"),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    spider_name = spider.spider_name or spider.name
    task_stats = task.stats or {}
    task_args = task_stats.get("args")
    task_env = task_stats.get("env") or {}
    if node:
        if node.connect_type == "ssh":
            result = _dispatch_ssh(
                spider, task, node, code_dir, spider_name, background_tasks,
                task_args=task_args, task_env=task_env,
            )
        elif node.connect_type == "docker":
            result = _dispatch_docker(
                spider, task, node, code_dir, spider_name, background_tasks,
                memory_limit=memory_limit, cpu_limit=cpu_limit,
                task_args=task_args, task_env=task_env,
            )
        elif node.connect_type == "agent":
            result = _dispatch_agent(spider, task, node, db)
        else:
            result = _dispatch_ssh(
                spider, task, node, code_dir, spider_name, background_tasks,
                task_args=task_args, task_env=task_env,
            )
    else:
        result = _dispatch_local(spider, task, code_dir, spider_name, background_tasks,
                                 timeout=timeout,
                                 memory_limit=memory_limit,
                                 cpu_limit=cpu_limit,
                                 task_args=task_args, task_env=task_env)

    _update_spider_run_stats(db, spider)
    return result


def create_distributed_task(
    db,
    spider_id: int,
    node_ids: list,
    distribution_mode: str = "multi_node_distributed",
    shared_redis_url: str = None,
    worker_count: int = 1,
    schedule_id: int = None,
    background_tasks=None,
    task_args: str = None,
    task_env: dict = None,
) -> dict:
    """模式 C：同时部署到多个节点，共享 Redis 队列。

    每个节点创建一个独立任务，共享同一个 redis_namespace。
    Crawlo Consumer Group 自动在多个 Worker 间负载均衡。
    """
    if not node_ids:
        raise ValueError("模式 C 至少需要一个节点")
    if distribution_mode != "multi_node_distributed":
        raise ValueError("create_distributed_task 仅支持 multi_node_distributed 模式")

    from app.services.crawlo_distributed_adapter import get_distributed_adapter, DistributionMode
    from app.models import Project

    spider = db.query(Spider).filter(Spider.id == spider_id).first()
    if not spider:
        raise ValueError("爬虫不存在")
    project = db.query(Project).get(spider.project_id)
    project_name = project.name if project else "default"
    spider_name = spider.spider_name or spider.name

    adapter = get_distributed_adapter()
    redis_ns = adapter._redis_url and build_redis_namespace(project_name, spider_name)

    results = []
    for node_id in node_ids:
        try:
            r = create_and_run_task(
                db, spider_id, node_id=node_id,
                schedule_id=schedule_id,
                background_tasks=background_tasks,
                task_args=task_args, task_env=task_env,
                distribution_mode=distribution_mode,
                shared_redis_url=shared_redis_url or adapter._redis_url,
                worker_count=worker_count,
            )
            results.append(r)
        except Exception as e:
            results.append({"error": str(e), "node_id": node_id})

    return {
        "mode": distribution_mode,
        "node_count": len(node_ids),
        "redis_namespace": redis_ns,
        "tasks": results,
    }


def _dispatch_local(spider, task, code_dir, spider_name, background_tasks, timeout=None,
                    memory_limit=None, cpu_limit=None, task_args=None, task_env=None):
    """本地模式：子进程运行"""
    from app.services.local_executor import get_local_executor, LocalTaskConfig

    config = LocalTaskConfig(
        task_id=str(task.id),
        spider_id=str(spider.id),
        spider_name=spider_name,
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider_name,
        timeout=timeout or 3600,
        memory_limit=memory_limit,
        cpu_limit=cpu_limit,
        extra_env=task_env or {},
        args=task_args,
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


def _dispatch_ssh(spider, task, node, code_dir, spider_name, background_tasks,
                  task_args=None, task_env=None):
    """SSH 模式：上传代码远程运行"""
    from app.services.ssh_executor import get_ssh_executor, SshTaskConfig
    from app.core.crypto import decrypt_or_plain

    config = SshTaskConfig(
        task_id=str(task.id),
        spider_id=str(spider.id),
        spider_name=spider_name,
        ssh_host=node.ssh_host or node.host,
        ssh_port=node.ssh_port or 22,
        ssh_user=node.ssh_user or "root",
        ssh_pwd=decrypt_or_plain(node.ssh_pwd),
        ssh_key=decrypt_or_plain(node.ssh_key),
        code_dir=code_dir,
        entry_file=spider.entry_file,
        spider_name_to_run=spider_name,
        extra_env=task_env or {},
        args=task_args,
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


def _dispatch_docker(spider, task, node, code_dir, spider_name, background_tasks,
                     memory_limit=None, cpu_limit=None, task_args=None, task_env=None):
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
        memory_limit=memory_limit or "512m",
        cpu_limit=cpu_limit or 1.0,
        args=task_args,
        env=task_env or {},
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
    task.deploy_mode = DeployMode.AGENT
    task.node_id = node.id
    db.commit()

    return {
        "message": "任务已派发给节点 Agent",
        "task_id": task.id,
        "spider_id": spider.id,
        "mode": "agent",
        "node_id": node.id,
        "node_name": node.name,
    }
