"""
执行器注册表

按任务的部署模式返回对应执行器，供 stop 等操作复用，
避免各 API 路由各自实现分发逻辑导致模式遗漏。
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _is_mode(deploy_mode, target: str) -> bool:
    """兼容 Enum 与字符串两种 deploy_mode 表达（历史数据可能是字符串）。"""
    if deploy_mode is None:
        return False
    lhs = deploy_mode.value if hasattr(deploy_mode, "value") else str(deploy_mode)
    return lhs == target


def get_executor_for_task(task: Any):
    """
    按任务的部署模式返回对应执行器
    - ssh: SshExecutor（远程节点）
    - docker: DockerExecutor（直连节点 Docker API）
    - agent: AgentService（反向代理节点）
    - 其他: LocalExecutor（本地进程）
    """
    deploy_mode = getattr(task, 'deploy_mode', None)
    if _is_mode(deploy_mode, 'ssh'):
        from app.services.ssh_executor import get_ssh_executor
        return get_ssh_executor()
    if _is_mode(deploy_mode, 'docker'):
        from app.services.docker_executor import get_docker_executor
        return get_docker_executor()
    if _is_mode(deploy_mode, 'agent'):
        from app.services.agent_service import get_agent_service
        return get_agent_service()
    from app.services.local_executor import get_local_executor
    return get_local_executor()
