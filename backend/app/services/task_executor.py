"""
任务执行引擎

负责:
- 创建并管理 Docker 容器
- 执行爬虫任务
- 监控容器状态
- 采集日志和数据
"""

import asyncio
import logging
import uuid
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, field

import docker
from docker.models.containers import Container

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import TaskInstance, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class TaskConfig:
    """任务执行配置"""
    
    task_id: str
    spider_id: str
    spider_name: str
    git_url: Optional[str] = None
    git_branch: str = "main"
    node_id: Optional[str] = None
    
    # 爬虫入口文件 (可选)
    entry_file: Optional[str] = None  # 例如: run.py, main.py, crawl.sh
    
    # 资源限制
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    network: str = "crawlopilot-network"
    
    # 超时配置
    timeout: int = 3600  # 1小时
    
    # 环境变量
    extra_env: Dict[str, str] = field(default_factory=dict)


class TaskExecutor:
    """
    任务执行器
    
    负责在 Docker 容器中执行爬虫任务
    """
    
    def __init__(self):
        """初始化执行器"""
        self.docker_client = None
        self.active_tasks: Dict[str, Container] = {}
        self._initialized = False
    
    async def initialize(self):
        """初始化执行器"""
        if not self._initialized:
            try:
                # docker-py 兼容性已在 docker_service 模块加载时通过
                # monkey-patch APIClient.__init__ 解决
                self.docker_client = docker.from_env()
                self._ensure_network()
                self._initialized = True
                logger.info("TaskExecutor initialized with Docker")
            except Exception as e:
                logger.warning(f"Docker not available, running in mock mode: {e}")
                self._initialized = True  # 仍然标记为已初始化
    
    def _ensure_network(self):
        """确保 CrawloPilot 网络存在"""
        network_name = "crawlopilot-network"
        try:
            self.docker_client.networks.get(network_name)
            logger.debug(f"Network {network_name} already exists")
        except docker.errors.NotFound:
            self.docker_client.networks.create(
                network_name,
                driver="bridge"
            )
            logger.info(f"Created network {network_name}")
    
    async def execute_task(self, config: TaskConfig) -> str:
        """
        执行任务
        
        Args:
            config: 任务配置
            
        Returns:
            容器 ID
        """
        await self.initialize()
        
        logger.info(f"Executing task {config.task_id}: {config.spider_name}")
        
        # 1. 从 Git 拉取爬虫代码
        code_dir = None
        if config.git_url:
            code_dir = await self._clone_git_repository(config)
        
        # 2. 构建容器配置
        container_config = self._build_container_config(config, code_dir)
        
        # 3. 创建并启动容器
        try:
            container = self.docker_client.containers.run(
                detach=True,
                **container_config
            )
            
            # 记录容器
            self.active_tasks[config.task_id] = container
            
            # 启动日志采集
            from app.services.log_collector import get_collector
            collector = get_collector()
            await collector.start_collecting(
                task_id=config.task_id,
                container_id=container.id
            )
            
            # 更新数据库状态
            self._update_task_status(
                config.task_id,
                TaskStatus.RUNNING,
                container_id=container.id
            )
            
            logger.info(f"Container started: {container.id[:12]}")
            return container.id
            
        except Exception as e:
            logger.error(f"Failed to start container: {e}")
            self._update_task_status(
                config.task_id,
                TaskStatus.FAILED,
                error_message=str(e)
            )
            # 清理临时目录
            if code_dir:
                shutil.rmtree(code_dir, ignore_errors=True)
            raise
    
    async def _clone_git_repository(self, config: TaskConfig) -> Optional[str]:
        """
        从 Git 仓库拉取爬虫代码
        
        Args:
            config: 任务配置
            
        Returns:
            代码目录路径
        """
        if not config.git_url:
            return None
        
        logger.info(f"Cloning git repository: {config.git_url}")
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix=f"spider-{config.task_id}-")
        
        try:
            # 使用 git 命令克隆
            import subprocess
            cmd = [
                'git', 'clone',
                '--branch', config.git_branch,
                '--depth', '1',  # 只克隆最新版本
                config.git_url,
                temp_dir
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")
            
            logger.info(f"Git repository cloned to {temp_dir}")
            return temp_dir
            
        except Exception as e:
            logger.error(f"Failed to clone git repository: {e}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    def _build_container_config(self, config: TaskConfig, code_dir: Optional[str] = None) -> Dict:
        """
        构建容器配置
        
        Args:
            config: 任务配置
            
        Returns:
            Docker run 配置
        """
        # 基础环境变量
        env = {
            'API_URL': settings.API_URL,
            'API_TOKEN': self._get_api_token(),
            'TASK_ID': config.task_id,
            'SPIDER_NAME': config.spider_name,  # 爬虫名称 (用于 crawlo run)
            'NODE_ID': config.node_id or '',
            'GIT_URL': config.git_url or '',
            'GIT_BRANCH': config.git_branch,
            'OUTPUT_PATH': '/output',
            'LOG_LEVEL': 'INFO',
            # 爬虫入口文件 (如果有)
            'ENTRY_FILE': config.entry_file or '',
        }
        
        # 合并额外环境变量
        env.update(config.extra_env)
        
        # 挂载爬虫代码
        volumes = {}
        if code_dir and Path(code_dir).exists():
            volumes[code_dir] = {
                'bind': '/spider/code',
                'mode': 'ro'  # 只读
            }
            logger.info(f"Mounting spider code: {code_dir} -> /spider/code")
        
        # 输出目录
        volumes[f"task-output-{config.task_id}"] = {
            'bind': '/output',
            'mode': 'rw'
        }
        
        # 容器配置
        container_config = {
            'image': settings.SPIDER_RUNNER_IMAGE or 'crawlopilot/spider-runner:latest',
            'name': f"task-{config.task_id[:8]}",
            'environment': env,
            'mem_limit': config.memory_limit,
            'nano_cpus': int(config.cpu_limit * 1e9),
            'network': config.network,
            'volumes': volumes,
            'labels': {
                'crawlopilot.task_id': config.task_id,
                'crawlopilot.spider_id': config.spider_id,
                'crawlopilot.spider_name': config.spider_name,
                'crawlopilot.created_at': datetime.utcnow().isoformat(),
            },
            'restart_policy': {
                'Name': 'no'
            },
        }
        
        return container_config
    
    async def pause_task(self, task_id: str) -> bool:
        """
        暂停任务 (Docker 容器暂停)
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功
        """
        container = self.active_tasks.get(task_id)
        
        if not container:
            # 尝试通过标签查找
            container = self._find_container_by_task_id(task_id)
        
        if not container:
            logger.warning(f"Container not found for task {task_id}")
            return False
        
        try:
            # Docker pause (使用 cgroup freezer 暂停所有进程)
            container.pause()
            
            # 更新数据库
            self._update_task_status(task_id, TaskStatus.PAUSED)
            
            logger.info(f"Task {task_id} paused")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause task {task_id}: {e}")
            return False
    
    async def resume_task(self, task_id: str) -> bool:
        """
        恢复任务 (Docker 容器恢复)
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功
        """
        container = self.active_tasks.get(task_id)
        
        if not container:
            # 尝试通过标签查找
            container = self._find_container_by_task_id(task_id)
        
        if not container:
            logger.warning(f"Container not found for task {task_id}")
            return False
        
        try:
            # Docker unpause (恢复所有进程)
            container.unpause()
            
            # 更新数据库
            self._update_task_status(task_id, TaskStatus.RUNNING)
            
            logger.info(f"Task {task_id} resumed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resume task {task_id}: {e}")
            return False
    
    async def stop_task(self, task_id: str) -> bool:
        """
        停止任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            是否成功
        """
        container = self.active_tasks.get(task_id)
        
        if not container:
            # 尝试通过标签查找
            container = self._find_container_by_task_id(task_id)
        
        if not container:
            logger.warning(f"Container not found for task {task_id}")
            return False
        
        try:
            container.stop(timeout=10)
            container.remove(force=True)
            
            # 从活动任务中移除
            self.active_tasks.pop(task_id, None)
            
            # 更新数据库
            self._update_task_status(task_id, TaskStatus.CANCELLED)
            
            logger.info(f"Task {task_id} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop task {task_id}: {e}")
            return False
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态
        
        Args:
            task_id: 任务 ID
            
        Returns:
            任务状态信息
        """
        container = self.active_tasks.get(task_id)
        
        if not container:
            container = self._find_container_by_task_id(task_id)
        
        if not container:
            return None
        
        try:
            container.reload()
            
            return {
                'task_id': task_id,
                'container_id': container.id,
                'status': container.status,
                'created_at': container.attrs.get('Created'),
                'started_at': container.attrs.get('State', {}).get('StartedAt'),
                'finished_at': container.attrs.get('State', {}).get('FinishedAt'),
                'exit_code': container.attrs.get('State', {}).get('ExitCode'),
                'error': container.attrs.get('State', {}).get('Error'),
            }
            
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return None
    
    async def get_task_logs(self, task_id: str, tail: int = 100) -> str:
        """
        获取任务日志
        
        Args:
            task_id: 任务 ID
            tail: 日志行数
            
        Returns:
            日志内容
        """
        container = self.active_tasks.get(task_id)
        
        if not container:
            container = self._find_container_by_task_id(task_id)
        
        if not container:
            return "Container not found"
        
        try:
            logs = container.logs(
                tail=tail,
                timestamps=True,
                stderr=True,
                stdout=True
            )
            return logs.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return f"Error: {str(e)}"
    
    def _find_container_by_task_id(self, task_id: str) -> Optional[Container]:
        """通过任务 ID 查找容器"""
        try:
            containers = self.docker_client.containers.list(
                all=True,
                filters={'label': f'crawlopilot.task_id={task_id}'}
            )
            return containers[0] if containers else None
        except Exception as e:
            logger.error(f"Failed to find container: {e}")
            return None
    
    def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        container_id: str = None,
        error_message: str = None
    ):
        """
        更新数据库中的任务状态
        
        Args:
            task_id: 任务 ID
            status: 任务状态
            container_id: 容器 ID
            error_message: 错误信息
        """
        db = SessionLocal()
        try:
            task = db.query(TaskInstance).filter(TaskInstance.id == task_id).first()
            
            if task:
                task.status = status
                if container_id:
                    task.container_id = container_id
                if error_message:
                    task.error_message = error_message if hasattr(task, 'error_message') else None
                if status == TaskStatus.RUNNING:
                    task.started_at = datetime.utcnow()
                elif status in [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    task.finished_at = datetime.utcnow()
                
                db.commit()
                logger.debug(f"Task {task_id} status updated to {status.value}")
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _get_api_token(self) -> str:
        """获取 API Token"""
        # 从配置或环境变量获取
        return settings.API_SECRET_KEY or "default-token"
    
    async def cleanup(self):
        """清理资源"""
        logger.info("Cleaning up TaskExecutor")
        
        # 停止所有活动任务
        for task_id, container in list(self.active_tasks.items()):
            try:
                container.stop(timeout=5)
                container.remove(force=True)
                logger.info(f"Cleaned up task {task_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup task {task_id}: {e}")
        
        self.active_tasks.clear()

    # 注意：不定义 __del__ 方法，清理由 lifespan 生命周期管理负责


# 全局执行器实例
_executor = None


def get_executor() -> TaskExecutor:
    """获取全局执行器实例"""
    global _executor
    if _executor is None:
        _executor = TaskExecutor()
    return _executor

