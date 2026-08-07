"""
执行器注册表

按任务的部署模式返回对应执行器，供 stop 等操作复用，
避免各 API 路由各自实现分发逻辑导致模式遗漏。
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_executor_for_task(task: Any):
    """
    按任务的部署模式返回对应执行器
    - ssh: SshExecutor（远程节点）
    - docker: DockerExecutor（直连节点 Docker API）
    - agent: AgentService（反向代理节点）
    - 其他: LocalExecutor（本地进程）
    """
    deploy_mode = getattr(task, 'deploy_mode', None)
    if deploy_mode == 'ssh':
        from app.services.ssh_executor import get_ssh_executor
        return get_ssh_executor()
    if deploy_mode == 'docker':
        from app.services.docker_executor import get_docker_executor
        return get_docker_executor()
    if deploy_mode == 'agent':
        from app.services.agent_service import get_agent_service
        return get_agent_service()
    from app.services.local_executor import get_local_executor
    return get_local_executor()
